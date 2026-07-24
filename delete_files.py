"""Listado y eliminación segura de archivos del proyecto."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

# Núcleo de la aplicación: no se puede eliminar desde la interfaz
PROTECTED_FILES = {
    "app.py",
    "delete_files.py",
    "iniciar.bat",
}

SKIP_NAMES = {"__pycache__", ".git"}


def _human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def list_project_files(base_dir: Optional[Path] = None) -> dict:
    """Lista todos los archivos del directorio del proyecto."""
    base = (base_dir or Path(__file__).resolve().parent).resolve()
    files = []

    for path in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if path.name in SKIP_NAMES or path.is_dir():
            continue
        if not path.is_file():
            continue

        protected = path.name in PROTECTED_FILES
        ext = path.suffix.lower()
        files.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "size_label": _human_size(path.stat().st_size),
                "ext": ext.lstrip(".") or "sin extensión",
                "protected": protected,
                "selected_default": not protected,
            }
        )

    reclaimable = [item for item in files if not item["protected"]]
    total_bytes = sum(item["size"] for item in reclaimable)
    return {
        "folder": str(base),
        "count": len(files),
        "deletable_count": len(reclaimable),
        "reclaimable_label": _human_size(total_bytes),
        "files": files,
    }


def _safe_resolve(base: Path, name: str) -> Optional[Path]:
    """Resuelve un nombre solo si permanece dentro del directorio base."""
    if not name or name != Path(name).name:
        return None
    if name in PROTECTED_FILES or name in SKIP_NAMES:
        return None

    candidate = (base / name).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None

    return candidate if candidate.is_file() else None


def delete_selected_files(
    names: Iterable[str],
    base_dir: Optional[Path] = None,
) -> dict:
    """Elimina cualquier archivo seleccionado que no esté protegido."""
    base = (base_dir or Path(__file__).resolve().parent).resolve()
    deleted = []
    missing = []
    blocked = []
    freed = 0

    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        if name in PROTECTED_FILES:
            blocked.append(name)
            continue

        path = _safe_resolve(base, name)
        if path is None:
            missing.append(name)
            continue

        size = path.stat().st_size
        path.unlink()
        deleted.append(name)
        freed += size

    if deleted and not missing and not blocked:
        message = f"Eliminados {len(deleted)} archivo(s): {', '.join(deleted)}"
    elif deleted:
        parts = [f"Eliminados: {', '.join(deleted)}"]
        if missing:
            parts.append(f"No encontrados: {', '.join(missing)}")
        if blocked:
            parts.append(f"Protegidos: {', '.join(blocked)}")
        message = ". ".join(parts)
    elif blocked and not missing:
        message = f"No se pueden eliminar (protegidos): {', '.join(blocked)}"
    elif missing:
        message = f"No se encontraron: {', '.join(missing)}"
    else:
        message = "No había archivos para eliminar"

    return {
        "deleted": deleted,
        "missing": missing,
        "blocked": blocked,
        "freed": freed,
        "freed_label": _human_size(freed),
        "message": message,
    }


TARGET_FILES = ["oal.txt", "oal2.txt"]


def delete_target_files(base_dir: Optional[Path] = None) -> dict:
    return delete_selected_files(TARGET_FILES, base_dir)


if __name__ == "__main__":
    listing = list_project_files()
    print(f"Carpeta: {listing['folder']}")
    for item in listing["files"]:
        flag = " [protegido]" if item["protected"] else ""
        print(f"  - {item['name']} ({item['size_label']}){flag}")
