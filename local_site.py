"""Resuelve rutas locales y busca el proyecto en disco sin tokens."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

DEFAULT_DOCROOTS = [
    Path(os.environ["DOCROOT"]) if os.environ.get("DOCROOT") else None,
    Path(r"C:\xampp\htdocs"),
    Path("/opt/lampp/htdocs"),
    Path("/var/www/html"),
]


def _home() -> Path:
    return Path.home()


def _search_roots() -> List[Path]:
    home = _home()
    roots = [
        *DEFAULT_DOCROOTS,
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Projects",
        home / "source",
        home / "repos",
        home / "dev",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
    ]
    out: List[Path] = []
    for root in roots:
        if root is None:
            continue
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        if resolved.is_dir():
            out.append(resolved)
    return out


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


def site_name_from_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if host.endswith(".netlify.app"):
        return host[: -len(".netlify.app")]
    if host.endswith(".vercel.app"):
        return host[: -len(".vercel.app")]
    if host.endswith(".onrender.com"):
        return host[: -len(".onrender.com")]
    if host in {"localhost", "127.0.0.1", "::1"}:
        return _clean_url_path(parsed.path).split("/")[0] if parsed.path else ""
    return host.split(".")[0] if host else ""


def resolve_local_path(raw: str) -> Optional[Path]:
    """Acepta C:\\proyecto, /home/user/app o file:///..."""
    value = (raw or "").strip().strip('"').strip("'")
    if not value:
        return None

    if value.lower().startswith("file:"):
        parsed = urlparse(value)
        value = unquote(parsed.path or "")
        if re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]

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


def find_project_folder(name: str) -> Optional[Path]:
    """Busca una carpeta con ese nombre en ubicaciones típicas (sin token)."""
    needle = (name or "").strip().lower()
    if not needle or needle in {"www", "app", "web", "site", "com", "net", "org"}:
        return None

    for base in _search_roots():
        direct = base / name
        if direct.is_dir():
            return direct.resolve()
        # búsqueda poco profunda
        try:
            for child in base.iterdir():
                if child.is_dir() and child.name.lower() == needle:
                    return child.resolve()
        except OSError:
            continue
        # un nivel más (Documents/foo/omga)
        try:
            for child in base.iterdir():
                if not child.is_dir():
                    continue
                candidate = child / name
                if candidate.is_dir():
                    return candidate.resolve()
        except OSError:
            continue
    return None


def resolve_site_root_from_url(raw_url: str) -> Optional[Path]:
    """
    Resuelve a una carpeta local sin tokens:
    ruta absoluta, DOCROOT, o búsqueda por nombre del sitio.
    """
    value = (raw_url or "").strip()
    if not value:
        return None

    local = resolve_local_path(value)
    if local is not None:
        return local

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        # tal vez es nombre de carpeta relativo conocido
        found = find_project_folder(value)
        return found

    rel = _clean_url_path(parsed.path)
    host_folder = site_name_from_url(value)

    candidates_rel = []
    if rel:
        candidates_rel.append(rel)
    if host_folder:
        candidates_rel.append(host_folder)

    for root in _search_roots():
        for item in candidates_rel:
            candidate = (root / item.replace("/", os.sep))
            try:
                resolved = candidate.resolve()
                resolved.relative_to(root.resolve())
            except (OSError, ValueError):
                continue
            if resolved.is_dir():
                return resolved

    if host_folder:
        return find_project_folder(host_folder)
    return None
