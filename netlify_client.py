"""Cliente Netlify API — listar y borrar archivos REALES del sitio en vivo."""

from __future__ import annotations

import json
import time
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
    raw_body: Optional[bytes] = None,
    content_type: Optional[str] = None,
    timeout: int = 90,
) -> Any:
    token = (token or "").strip()
    if not token or token == "oal-lab-clean":
        raise RuntimeError(
            "Para borrar de verdad en Netlify necesitas un Personal Access Token. "
            "Netlify -> User settings -> Applications -> Personal access tokens -> New access token. "
            "Pegalo en Clave y vuelve a Conectar."
        )

    data = raw_body
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "File-Clear/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        headers["Content-Type"] = content_type or "application/octet-stream"

    url = path if path.startswith("http") else API + path
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ctype or (raw[:1] in (b"{", b"[")):
                text = raw.decode("utf-8", errors="replace")
                return json.loads(text) if text else {}
            return raw
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

    if hint:
        try:
            site = _request("GET", f"/sites/{urllib.parse.quote(hint)}", token)
            if isinstance(site, dict) and site.get("id"):
                return site
        except Exception:
            pass

    raise RuntimeError(
        f"No encontré el sitio Netlify '{hint or target}' con ese token. "
        "Usa el token de la misma cuenta que publicó el sitio."
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


def _norm_path(value: str) -> str:
    full = "/" + "/".join(p for p in str(value or "").replace("\\", "/").split("/") if p)
    return full if full != "/" else "/"


def list_netlify_files(site_url: str, path: str = "", token: str = "") -> dict:
    site = resolve_site(token, site_url)
    site_id = site["id"]
    files = _request("GET", f"/sites/{site_id}/files", token)
    if not isinstance(files, list):
        raise RuntimeError("No se pudo listar archivos de Netlify")

    rel = (path or "").replace("\\", "/").strip().strip("/")
    prefix = f"/{rel}" if rel else ""

    folders: set[str] = set()
    file_rows: List[dict] = []

    for item in files:
        full = _norm_path(item.get("path") or item.get("id") or "")
        if full == "/":
            continue

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
            folders.add(rest.split("/", 1)[0])
            continue

        size = int(item.get("size") or 0)
        file_rows.append(
            {
                "name": rest,
                "type": "file",
                "path": f"{rel}/{rest}".strip("/") if rel else rest,
                "size": size,
                "size_label": _human_size(size),
                "ext": _ext_of(rest),
                "protected": False,
                "selected_default": False,
            }
        )

    folder_rows = [
        {
            "name": name,
            "type": "folder",
            "path": f"{rel}/{name}".strip("/") if rel else name,
            "protected": False,
        }
        for name in sorted(folders)
    ]

    file_rows.sort(key=lambda f: f["name"].lower())
    crumbs = [{"name": "Inicio", "path": ""}]
    if rel:
        built = []
        for part in rel.split("/"):
            built.append(part)
            crumbs.append({"name": part, "path": "/".join(built)})

    parent = "/".join(rel.split("/")[:-1]) if rel else None
    total = sum(int(f.get("size") or 0) for f in file_rows)
    root = site.get("ssl_url") or site.get("url") or site_url

    return {
        "ok": True,
        "provider": "netlify",
        "root": root,
        "folder": root if not rel else f"{root.rstrip('/')}/{rel}",
        "path": rel,
        "parent": parent,
        "breadcrumb": crumbs,
        "folders": folder_rows,
        "files": file_rows,
        "folder_count": len(folder_rows),
        "file_count": len(file_rows),
        "reclaimable_label": _human_size(total),
        "total_size_label": _human_size(total),
        "site_id": site_id,
        "site_name": site.get("name"),
        "remote_url": site_url,
        "label": f"Netlify en vivo · {site.get('name') or root}",
    }


def _download_site_file(site_id: str, file_path: str, token: str, public_url: str) -> bytes:
    # 1) API del archivo
    api_path = file_path if file_path.startswith("/") else "/" + file_path
    try:
        raw = _request(
            "GET",
            f"/sites/{site_id}/files{urllib.parse.quote(api_path, safe='/')}",
            token,
        )
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
    except Exception:
        pass

    # 2) URL pública del sitio
    pub = (public_url or "").rstrip("/") + api_path
    req = urllib.request.Request(
        pub,
        headers={"User-Agent": "File-Clear/1.0", "Accept": "*/*"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _wait_deploy(site_id: str, deploy_id: str, token: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = _request("GET", f"/sites/{site_id}/deploys/{deploy_id}", token)
        state = str(last.get("state") or "")
        if state in {"ready", "current"}:
            return last
        if state in {"error", "rejected"}:
            raise RuntimeError(f"Deploy Netlify falló: {state}")
        time.sleep(1.5)
    return last


def delete_netlify_files(
    site_url: str,
    names: list,
    path: str = "",
    token: str = "",
) -> dict:
    """Publica un nuevo deploy sin los archivos/carpetas marcados (borrado real en el dominio)."""
    site = resolve_site(token, site_url)
    site_id = site["id"]
    public_url = str(site.get("ssl_url") or site.get("url") or site_url).rstrip("/")
    current = _request("GET", f"/sites/{site_id}/files", token)
    if not isinstance(current, list):
        raise RuntimeError("No se pudo leer el deploy actual de Netlify")

    rel = (path or "").replace("\\", "/").strip().strip("/")
    remove: set[str] = set()
    for name in names:
        item = str(name or "").replace("\\", "/").strip().strip("/")
        if not item:
            continue
        if rel and not item.startswith(rel + "/") and item != rel:
            full = f"/{rel}/{item}"
        else:
            full = "/" + item
        remove.add(_norm_path(full))

    keep_files: dict[str, str] = {}
    sha_to_path: dict[str, str] = {}
    deleted: List[str] = []

    for item in current:
        full = _norm_path(item.get("path") or item.get("id") or "")
        sha = str(item.get("sha") or "").strip()
        if full == "/" or not sha:
            continue

        drop = any(
            full == target or full.startswith(target.rstrip("/") + "/")
            for target in remove
        )
        if drop:
            deleted.append(full)
            continue
        keep_files[full] = sha
        sha_to_path[sha] = full

    if not deleted:
        return {
            "ok": False,
            "deleted": [],
            "errors": [{"file": n, "error": "No encontrado en el deploy"} for n in names],
            "remaining": len(keep_files),
            "message": "No se encontró nada para borrar en Netlify.",
        }

    if not keep_files:
        # Netlify no acepta deploy vacío fácilmente: deja un index mínimo
        raise RuntimeError(
            "No se puede dejar el sitio Netlify sin archivos. "
            "Deja al menos index.html u otro archivo."
        )

    deploy = _request(
        "POST",
        f"/sites/{site_id}/deploys",
        token,
        payload={"files": keep_files, "draft": False},
    )
    deploy_id = str(deploy.get("id") or "")
    if not deploy_id:
        raise RuntimeError("Netlify no devolvió deploy_id")

    required = list(deploy.get("required") or [])
    for sha in required:
        file_path = sha_to_path.get(sha)
        if not file_path:
            raise RuntimeError(
                f"Netlify pidió re-subir un archivo desconocido ({sha[:8]}…)."
            )
        content = _download_site_file(site_id, file_path, token, public_url)
        upload_path = urllib.parse.quote(file_path.lstrip("/"), safe="/")
        _request(
            "PUT",
            f"/deploys/{deploy_id}/files/{upload_path}",
            token,
            raw_body=content,
            content_type="application/octet-stream",
        )

    ready = _wait_deploy(site_id, deploy_id, token)
    state = str(ready.get("state") or deploy.get("state") or "")
    live = ready.get("ssl_url") or ready.get("deploy_ssl_url") or public_url

    return {
        "ok": True,
        "provider": "netlify",
        "deleted": deleted,
        "errors": [],
        "remaining": len(keep_files),
        "deploy_id": deploy_id,
        "deploy_state": state,
        "deploy_url": live,
        "message": (
            f"Borrado real en Netlify: {len(deleted)} elemento(s). "
            f"Estado deploy: {state or 'ok'}. Revisa {live}"
        ),
    }
