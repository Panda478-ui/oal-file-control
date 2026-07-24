"""Espejo público de un sitio: conectar solo con la URL, sin tokens ni agente."""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional, Set

MAX_PAGES = 80
MAX_ASSETS = 200
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 25

SKIP_EXT = {
    "exe",
    "dmg",
    "iso",
    "zip",
    "rar",
    "7z",
    "mp4",
    "webm",
    "mkv",
    "avi",
}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr = dict(attrs)
        for key in ("href", "src", "data-src", "poster"):
            val = attr.get(key)
            if val:
                self.links.append(val)
        srcset = attr.get("srcset") or attr.get("data-srcset")
        if srcset:
            for part in srcset.split(","):
                url = part.strip().split(" ")[0]
                if url:
                    self.links.append(url)


def _request(url: str) -> tuple[str, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "File-Clear/1.0 (public mirror)",
            "Accept": "*/*",
            "ngrok-skip-browser-warning": "1",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RuntimeError(f"Archivo demasiado grande: {url}")
        final = resp.geturl()
        return final, data, ctype


def _same_origin(base: urllib.parse.ParseResult, other: str) -> Optional[str]:
    joined = urllib.parse.urljoin(
        urllib.parse.urlunparse((base.scheme, base.netloc, base.path or "/", "", "", "")),
        other,
    )
    parsed = urllib.parse.urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() != base.netloc.lower():
        return None
    # quitar fragmento
    clean = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, "")
    )
    return clean


def _path_from_url(url: str, site_root: urllib.parse.ParseResult) -> str:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path or "/")
    if path.endswith("/"):
        path = path + "index.html"
    if path == "" or path == "/":
        path = "/index.html"
    # query distinta = archivo distinto
    if parsed.query:
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
        stem = Path(path).name or "index"
        parent = str(Path(path).parent).replace("\\", "/")
        if parent == ".":
            parent = "/"
        path = f"{parent.rstrip('/')}/{stem}__{digest}"
    return path.lstrip("/")


def _is_probably_html(ctype: str, path: str) -> bool:
    if "html" in ctype:
        return True
    lower = path.lower()
    return lower.endswith(".html") or lower.endswith(".htm") or lower.endswith("/")


def _extract_links(html: str) -> List[str]:
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    # sitemap / extras por regex
    extra = re.findall(r"""(?i)(?:href|src)\s*=\s*['"]([^'"]+)['"]""", html)
    return list(dict.fromkeys(parser.links + extra))


def _extract_sitemap_locs(xml: str) -> List[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, flags=re.I)


def mirror_root_for(url: str, storage_dir: Path) -> Path:
    host = urllib.parse.urlparse(url).netloc.lower() or "site"
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", host)
    root = (storage_dir / "mirrors" / safe).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sync_public_mirror(url: str, storage_dir: Path) -> Path:
    """
    Descarga lo público del sitio a storage/mirrors/<host>/ sin tokens.
    Así se puede navegar y borrar en la copia local.
    """
    value = (url or "").strip()
    if not value:
        raise ValueError("URL vacía")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL debe ser http(s)://...")

    base = parsed._replace(path=parsed.path or "/", params="", query="", fragment="")
    start = urllib.parse.urlunparse(base)
    root = mirror_root_for(start, storage_dir)

    queue: List[str] = [start]
    for extra in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml"):
        queue.append(
            urllib.parse.urlunparse((base.scheme, base.netloc, extra, "", "", ""))
        )

    seen: Set[str] = set()
    saved = 0
    pages = 0

    while queue and saved < MAX_ASSETS and pages < MAX_PAGES:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)

        path_rel = _path_from_url(current, base)
        ext = path_rel.rsplit(".", 1)[-1].lower() if "." in path_rel else ""
        if ext in SKIP_EXT:
            continue

        try:
            final_url, data, ctype = _request(current)
        except Exception:
            continue

        # guardar
        target = root.joinpath(*path_rel.split("/"))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            saved += 1
        except OSError:
            continue

        if _is_probably_html(ctype, path_rel):
            pages += 1
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                continue
            for link in _extract_links(text):
                abs_url = _same_origin(base, link)
                if abs_url and abs_url not in seen:
                    queue.append(abs_url)
            if path_rel.endswith("sitemap.xml") or "xml" in ctype:
                for loc in _extract_sitemap_locs(text):
                    abs_url = _same_origin(base, loc)
                    if abs_url and abs_url not in seen:
                        queue.append(abs_url)

        # robots.txt: buscar Sitemap:
        if path_rel.endswith("robots.txt"):
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            for line in text.splitlines():
                if line.lower().startswith("sitemap:"):
                    loc = line.split(":", 1)[1].strip()
                    abs_url = _same_origin(base, loc)
                    if abs_url and abs_url not in seen:
                        queue.append(abs_url)

    if saved == 0:
        raise RuntimeError(
            "No se pudo leer ningún archivo público de ese sitio. "
            "Revisa la URL o pega la carpeta local del proyecto."
        )

    # marca de origen
    (root / ".file-clear-source").write_text(start + "\n", encoding="utf-8")
    return root


def resolve_mirror_if_exists(url: str, storage_dir: Path) -> Optional[Path]:
    try:
        root = mirror_root_for(url, storage_dir)
    except Exception:
        return None
    if root.is_dir() and any(root.iterdir()):
        return root
    return None
