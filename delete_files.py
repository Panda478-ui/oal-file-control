"""Listado y eliminación de archivos y carpetas (sin lista de protegidos)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, List, Optional

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


def _normalize_rel(rel_path: str) -> str:
    raw = (rel_path or "").replace("\\", "/").strip().strip("/")
    if not raw:
        return ""
    parts: List[str] = []
    for part in raw.split("/"):
        if not part or part == ".":
            continue
        if part == ".." or part in SKIP_NAMES:
            raise ValueError("Ruta no permitida")
        parts.append(part)
    return "/".join(parts)


def resolve_workdir(base_dir: Path, rel_path: str = "") -> Path:
    """Devuelve un directorio dentro de base_dir a partir de una ruta relativa."""
    base = base_dir.resolve()
    rel = _normalize_rel(rel_path)
    target = (base / rel).resolve() if rel else base
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Ruta fuera del directorio permitido") from exc
    if not target.exists():
        raise FileNotFoundError("La carpeta no existe")
    if not target.is_dir():
        raise ValueError("La ruta no es una carpeta")
    return target


def list_project_files(base_dir: Optional[Path] = None, rel_path: str = "") -> dict:
    """Lista carpetas y archivos dentro de una ruta relativa al root."""
    base = (base_dir or Path(__file__).resolve().parent).resolve()
    work = resolve_workdir(base, rel_path)
    rel = _normalize_rel(rel_path)

    folders = []
    files = []

    entries = sorted(work.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for path in entries:
        if path.name in SKIP_NAMES:
            continue

        if path.is_dir():
            folders.append(
                {
                    "name": path.name,
                    "type": "folder",
                    "path": f"{rel}/{path.name}".strip("/"),
                    "protected": False,
                }
            )
            continue

        if not path.is_file():
            continue

        ext = path.suffix.lower()
        files.append(
            {
                "name": path.name,
                "type": "file",
                "path": f"{rel}/{path.name}".strip("/"),
                "size": path.stat().st_size,
                "size_label": _human_size(path.stat().st_size),
                "ext": ext.lstrip(".") or "sin extensión",
                "protected": False,
                "selected_default": ext in {".log", ".tmp", ".cache", ".bak", ".old"},
            }
        )

    reclaimable = list(files)
    total_bytes = sum(item["size"] for item in reclaimable)
    crumbs = [{"name": "Inicio", "path": ""}]
    if rel:
        built = []
        for part in rel.split("/"):
            built.append(part)
            crumbs.append({"name": part, "path": "/".join(built)})

    parent = "/".join(rel.split("/")[:-1]) if rel else None

    return {
        "root": str(base),
        "folder": str(work),
        "path": rel,
        "parent": parent,
        "breadcrumb": crumbs,
        "count": len(files) + len(folders),
        "folder_count": len(folders),
        "file_count": len(files),
        "deletable_count": len(reclaimable),
        "reclaimable_label": _human_size(total_bytes),
        "folders": folders,
        "files": files,
    }


def _safe_file(base: Path, rel_file: str) -> Optional[Path]:
    try:
        rel = _normalize_rel(rel_file)
    except ValueError:
        return None
    if not rel:
        return None
    if Path(rel).name in SKIP_NAMES:
        return None

    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _safe_dir(base: Path, rel_dir: str) -> Optional[Path]:
    try:
        rel = _normalize_rel(rel_dir)
    except ValueError:
        return None
    if not rel:
        return None
    if Path(rel).name in SKIP_NAMES:
        return None

    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_dir() else None


def _dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def delete_selected_files(
    names: Iterable[str],
    base_dir: Optional[Path] = None,
    current_path: str = "",
) -> dict:
    """Elimina archivos y carpetas completas (recursivo). Sin lista de protegidos."""
    base = (base_dir or Path(__file__).resolve().parent).resolve()
    prefix = _normalize_rel(current_path)
    deleted = []
    missing = []
    blocked = []
    freed = 0

    for raw in names:
        name = str(raw).strip().replace("\\", "/")
        if not name:
            continue

        rel = name if "/" in name else f"{prefix}/{name}".strip("/")

        try:
            normalized = _normalize_rel(rel)
        except ValueError:
            missing.append(name)
            continue

        if not normalized:
            blocked.append(name)
            continue

        file_path = _safe_file(base, normalized)
        if file_path is not None:
            size = file_path.stat().st_size
            file_path.unlink()
            deleted.append(file_path.name)
            freed += size
            continue

        dir_path = _safe_dir(base, normalized)
        if dir_path is not None:
            size = _dir_size(dir_path)
            shutil.rmtree(dir_path)
            deleted.append(dir_path.name + "/")
            freed += size
            continue

        missing.append(name)

    if deleted and not missing and not blocked:
        message = f"Eliminados {len(deleted)} elemento(s): {', '.join(deleted)}"
    elif deleted:
        parts = [f"Eliminados: {', '.join(deleted)}"]
        if missing:
            parts.append(f"No encontrados: {', '.join(missing)}")
        if blocked:
            parts.append(f"Bloqueados: {', '.join(blocked)}")
        message = ". ".join(parts)
    elif blocked and not missing:
        message = f"No se pueden eliminar: {', '.join(blocked)}"
    elif missing:
        message = f"No se encontraron: {', '.join(missing)}"
    else:
        message = "No había elementos para eliminar"

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
    print(f"Root: {listing['root']}")
    for folder in listing["folders"]:
        print(f"  [dir] {folder['name']}")
    for item in listing["files"]:
        print(f"  - {item['name']} ({item['size_label']})")
