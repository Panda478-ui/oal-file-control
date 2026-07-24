"""Resuelve URLs locales / rutas bajo DOCROOT sin necesitar oal_agent.php."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

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
        if lower in {"index.php", "index.html", "index.htm", "oal_agent.php", "oal-lab-clean.php"}:
            break
        parts.append(part)
    return "/".join(parts)


def resolve_site_root_from_url(raw_url: str) -> Optional[Path]:
    """
    Si la URL apunta a una carpeta que existe bajo DOCROOT (p. ej. XAMPP),
    devuelve esa carpeta para gestionarla en disco sin agente PHP.
    Sirve para localhost y también para ngrok cuando File Clear corre en el mismo PC.
    """
    value = (raw_url or "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    rel = _clean_url_path(parsed.path)
    if not rel:
        return None

    for root in DEFAULT_DOCROOTS:
        if root is None:
            continue
        try:
            base = root.resolve()
        except OSError:
            continue
        if not base.is_dir():
            continue
        candidate = (base / rel.replace("/", os.sep)).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            continue
        if candidate.is_dir():
            return candidate
    return None
