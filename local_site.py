"""Resuelve rutas locales y URLs bajo DOCROOT sin oal_agent.php."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

DEFAULT_DOCROOTS = [
    Path(os.environ["DOCROOT"]) if os.environ.get("DOCROOT") else None,
    Path(r"C:\xampp\htdocs"),
    Path("/opt/lampp/htdocs"),
    Path("/var/www/html"),
]


def _clean_url_path(path: str) -> str:
    raw = (path or "/").replace("\\", "/")
    parts = []
    for part in raw.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            continue
        lower = part.lower()
        if lower in {
            "index.php",
            "index.html",
            "index.htm",
            "oal_agent.php",
            "oal-lab-clean.php",
        }:
            break
        parts.append(part)
    return "/".join(parts)


def resolve_local_path(raw: str) -> Optional[Path]:
    """Acepta C:\\proyecto, /home/user/app o file:///..."""
    value = (raw or "").strip().strip('"').strip("'")
    if not value:
        return None

    if value.lower().startswith("file:"):
        parsed = urlparse(value)
        value = unquote(parsed.path or "")
        # file:///C:/xampp/... en Windows llega como /C:/xampp/...
        if re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]

    # Ruta Windows o Unix absoluta
    looks_windows = bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")
    looks_unix = value.startswith("/")
    if not (looks_windows or looks_unix):
        return None

    try:
        path = Path(value).expanduser().resolve()
    except OSError:
        return None
    if path.is_dir():
        return path
    return None


def resolve_site_root_from_url(raw_url: str) -> Optional[Path]:
    """
    Si la URL apunta a una carpeta bajo DOCROOT (XAMPP), úsala en disco.
    """
    value = (raw_url or "").strip()
    if not value:
        return None

    local = resolve_local_path(value)
    if local is not None:
        return local

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    rel = _clean_url_path(parsed.path)
    # también probar subdominio como carpeta: omga.netlify.app -> htdocs/omga
    host = (parsed.hostname or "").lower()
    host_folder = ""
    if host.endswith(".netlify.app"):
        host_folder = host[: -len(".netlify.app")]
    elif host not in {"localhost", "127.0.0.1"}:
        host_folder = host.split(".")[0]

    candidates_rel = []
    if rel:
        candidates_rel.append(rel)
    if host_folder:
        candidates_rel.append(host_folder)

    for root in DEFAULT_DOCROOTS:
        if root is None:
            continue
        try:
            base = root.resolve()
        except OSError:
            continue
        if not base.is_dir():
            continue
        for item in candidates_rel:
            candidate = (base / item.replace("/", os.sep)).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                continue
            if candidate.is_dir():
                return candidate
    return None
