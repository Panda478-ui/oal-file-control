"""Arma un ZIP listo para arrastrar a Netlify (sitio + agente)."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from public_site import sync_public_mirror


def _safe_host(url: str) -> str:
    host = (urlparse(url).hostname or "site").lower()
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", host)


def build_netlify_install_zip(
    site_url: str,
    storage_dir: Path,
    agent_file: Path,
) -> Path:
    """
    Descarga lo público del sitio, mete netlify/functions/oal-clean.js
    y devuelve la ruta de un .zip para Deploy manual en Netlify.
    """
    mirror = sync_public_mirror(site_url, storage_dir)
    host = _safe_host(site_url)
    packages = storage_dir / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    staging = packages / f"{host}-install"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    for path in mirror.rglob("*"):
        if path.name == ".file-clear-source":
            continue
        rel = path.relative_to(mirror)
        dest = staging / rel
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    fn_dir = staging / "netlify" / "functions"
    fn_dir.mkdir(parents=True, exist_ok=True)
    if not agent_file.is_file():
        raise RuntimeError("Falta agents/netlify/oal-clean.js")
    shutil.copy2(agent_file, fn_dir / "oal-clean.js")

    # guía corta dentro del zip
    (staging / "FILE-CLEAR-INSTALAR.txt").write_text(
        "\n".join(
            [
                "File Clear — instalacion Netlify",
                "",
                "1) En Netlify abre tu sitio -> Deploys",
                "2) Arrastra este ZIP (o la carpeta descomprimida) a Deploy",
                "3) Site configuration -> Environment variables:",
                "   NETLIFY_AUTH_TOKEN = (Personal Access Token de tu cuenta)",
                "4) Vuelve a publicar / Trigger deploy",
                "5) En File Clear conecta solo con la URL del sitio",
                "",
            ]
        ),
        encoding="utf-8",
    )

    zip_path = packages / f"{host}-file-clear-ready.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(staging).as_posix())
    return zip_path
