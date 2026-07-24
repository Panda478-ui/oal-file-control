"""Cliente Netlify API — listar/eliminar archivos sin oal_agent.php."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, List, Optional
from urllib.parse import urlparse

API = "https://api.netlify.com/api/v1"


def is_netlify_url(raw: str) -> bool:
    host = (urlparse(raw).hostname or "").lower()
    return host.endswith(".netlify.app") or host.endswith(".netlify.com") or host == "netlify.app"


def _site_hint(raw: str) -> str:
    host = (urlparse(raw).hostname or "").lower()
    if host.endswith(".netlify.app"):
        return host[: -len(".netlify.app")]
    return host.split(".")[0] if host else ""


def _request(
    method: str,
    path: str,
    token: str,
    payload: Optional[dict] = None,
    timeout: int = 60,
) -> Any:
    token = (token or "").strip()
    if not token or token == "oal-lab-clean":
        raise RuntimeError(
            "Para Netlify pega tu Personal Access Token en Clave "
            "(Netlify → User settings → Applications → Personal access tokens). "
            "No hace falta oal_agent.php."
        )

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "File-Clear/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    url = API + path
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("message") or parsed.get("error") or detail
        except Exception:
            message = detail or str(exc)
        if exc.code in {401, 403}:
            raise RuntimeError(
                "Token Netlify inválido o sin permisos. Genera uno nuevo en Netlify."
            ) from exc
        raise RuntimeError(f"Netlify HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo contactar Netlify: {exc.reason}") from exc


def resolve_site(token: str, site_url: str) -> dict:
    hint = _site_hint(site_url)
    sites = _request("GET", "/sites?per_page=100", token)
    if not isinstance(sites, list):
        raise RuntimeError("Respuesta de sitios Netlify inválida")

    target = (urlparse(site_url).hostname or "").lower()
    for site in sites:
        names = {
            str(site.get("name") or "").lower(),
            str(site.get("id") or "").lower(),
            urlparse(str(site.get("url") or "")).hostname or "",
            urlparse(str(site.get("ssl_url") or "")).hostname or "",
        }
        custom = site.get("custom_domain") or ""
        if custom:
            names.add(str(custom).lower())
        for domain in site.get("domain_aliases") or []:
            names.add(str(domain).lower())

        if target and target in names:
            return site
        if hint and hint == str(site.get("name") or "").lower():
            return site

    # intento directo por id/nombre
    if hint:
        try:
            site = _request("GET", f"/sites/{urllib.parse.quote(hint)}", token)
            if isinstance(site, dict) and site.get("id"):
                return site
        except Exception:
            pass

    raise RuntimeError(
        f"No encontré el sitio Netlify '{hint or target}' con ese token. "
        "Revisa que el token sea de la misma cuenta que publicó omga.netlify.app."
    )


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


def _ext_of(name: str) -> str:
    if "." not in name or name.startswith("."):
        return name.lstrip(".").upper() or "FILE"
    return name.rsplit(".", 1)[-1].upper()


def list_netlify_files(site_url: str, path: str = "", token: str = "") -> dict:
    site = resolve_site(token, site_url)
    site_id = site["id"]
    files = _request("GET", f"/sites/{site_id}/files", token)
    if not isinstance(files, list):
        raise RuntimeError("No se pudo listar archivos de Netlify")

    rel = (path or "").replace("\\", "/").strip().strip("/")
    prefix = f"/{rel}" if rel else ""

    folders: set[str] = set()
    entries: List[dict] = []

    for item in files:
        full = str(item.get("path") or item.get("id") or "")
        if not full.startswith("/"):
            full = "/" + full
        # normalizar
        full = "/" + "/".join(p for p in full.split("/") if p)

        if prefix:
            if full == prefix:
                continue
            if not full.startswith(prefix + "/"):
                continue
            rest = full[len(prefix) + 1 :]
        else:
            rest = full.lstrip("/")

        if not rest:
            continue

        if "/" in rest:
            folder_name = rest.split("/", 1)[0]
            folders.add(folder_name)
            continue

        size = int(item.get("size") or 0)
        entries.append(
            {
                "name": rest,
                "path": f"{rel}/{rest}".strip("/") if rel else rest,
                "size": size,
                "size_label": _human_size(size),
                "ext": _ext_of(rest),
                "kind": "file",
                "protected": False,
                "selected": False,
            }
        )

    for name in sorted(folders):
        entries.append(
            {
                "name": name,
                "path": f"{rel}/{name}".strip("/") if rel else name,
                "size": 0,
                "size_label": "carpeta",
                "ext": "CARPETA",
                "kind": "folder",
                "protected": False,
                "selected": False,
            }
        )

    entries.sort(key=lambda f: (0 if f["kind"] == "folder" else 1, f["name"].lower()))
    folder_count = sum(1 for f in entries if f["kind"] == "folder")
    file_count = len(entries) - folder_count
    total = sum(int(f.get("size") or 0) for f in entries if f["kind"] == "file")

    return {
        "ok": True,
        "provider": "netlify",
        "root": site.get("ssl_url") or site.get("url") or site_url,
        "folder": rel or "/",
        "parent": "/".join(rel.split("/")[:-1]) if rel else None,
        "files": entries,
        "file_count": file_count,
        "folder_count": folder_count,
        "total_size": total,
        "total_size_label": _human_size(total),
        "site_id": site_id,
        "site_name": site.get("name"),
        "remote_url": site_url,
    }


def delete_netlify_files(
    site_url: str,
    names: list,
    path: str = "",
    token: str = "",
) -> dict:
    site = resolve_site(token, site_url)
    site_id = site["id"]
    current = _request("GET", f"/sites/{site_id}/files", token)
    if not isinstance(current, list):
        raise RuntimeError("No se pudo leer el deploy actual de Netlify")

    rel = (path or "").replace("\\", "/").strip().strip("/")
    remove: set[str] = set()
    for name in names:
        item = str(name or "").replace("\\", "/").strip().strip("/")
        if not item:
            continue
        # rutas absolutas dentro del sitio
        if rel and not item.startswith(rel + "/") and item != rel:
            full = f"/{rel}/{item}"
        else:
            full = "/" + item
        full = "/" + "/".join(p for p in full.split("/") if p)
        remove.add(full)

    keep_files: dict[str, str] = {}
    deleted: List[str] = []
    for item in current:
        full = str(item.get("path") or item.get("id") or "")
        if not full.startswith("/"):
            full = "/" + full
        full = "/" + "/".join(p for p in full.split("/") if p)
        sha = str(item.get("sha") or "")
        if not sha:
            continue

        drop = False
        for target in remove:
            if full == target or full.startswith(target.rstrip("/") + "/"):
                drop = True
                break
        if drop:
            deleted.append(full)
            continue
        keep_files[full] = sha

    if not deleted:
        return {
            "ok": True,
            "deleted": [],
            "errors": [{"file": n, "error": "No encontrado en el deploy"} for n in names],
            "remaining": len(keep_files),
        }

    deploy = _request(
        "POST",
        f"/sites/{site_id}/deploys",
        token,
        payload={"files": keep_files},
    )
    required = deploy.get("required") or []
    if required:
        # Los digests ya deberían existir en Netlify al solo borrar.
        # Si pide upload, algo falló con los SHA.
        raise RuntimeError(
            "Netlify pidió re-subir archivos al borrar. "
            "Vuelve a intentar o elimina desde el proyecto local y redespliega."
        )

    return {
        "ok": True,
        "provider": "netlify",
        "deleted": deleted,
        "errors": [],
        "remaining": len(keep_files),
        "deploy_id": deploy.get("id"),
        "deploy_url": deploy.get("deploy_ssl_url") or deploy.get("ssl_url"),
    }
