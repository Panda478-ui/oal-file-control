"""Cliente/proxy para agentes File Clear en sitios que tú controlas."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, List, Optional

DEFAULT_TOKEN = "oal-lab-clean"


def _join_url(scheme: str, netloc: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def candidate_agent_urls(raw: str) -> List[str]:
    """
    Genera posibles URLs del agente a partir de cualquier enlace del sitio.
    """
    value = (raw or "").strip()
    if not value:
        raise ValueError("URL remota vacía")

    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL remota debe ser http(s)://...")

    path = parsed.path or "/"
    lower = path.lower().rstrip("/")
    parts = [p for p in path.split("/") if p]
    candidates: List[str] = []

    def add(agent_path: str) -> None:
        url = _join_url(parsed.scheme, parsed.netloc, agent_path)
        if url not in candidates:
            candidates.append(url)

    agent_names = (
        "oal_agent.php",
        "oal-lab-clean.php",
        "file_clear.php",
        ".netlify/functions/oal-clean",
        ".netlify/functions/oal-clean.js",
    )

    if any(lower.endswith(name.rstrip(".js")) or lower.endswith(name) for name in agent_names):
        # si ya apuntan al agente, úsalo
        if "oal-clean" in lower or lower.endswith("oal_agent.php") or lower.endswith("file_clear.php") or lower.endswith("oal-lab-clean.php"):
            add(path if path.startswith("/") else "/" + path)
            return candidates

    host = (parsed.netloc or "").lower()
    # Netlify: función serverless primero (borrado real sin pegar PAT en el panel)
    if host.endswith(".netlify.app") or host.endswith(".netlify.com"):
        add("/.netlify/functions/oal-clean")

    if lower.endswith(".php") or lower.endswith(".html") or lower.endswith(".htm"):
        parts = parts[:-1]

    bases = []
    base = "/" + "/".join(parts) if parts else ""
    bases.append(base)
    if len(parts) >= 1:
        parent = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""
        bases.append(parent)
    bases.append("")

    for folder in bases:
        for name in ("oal_agent.php", "oal-lab-clean.php", "file_clear.php"):
            add((folder + "/" + name) if folder else "/" + name)

    return candidates


def normalize_remote_url(raw: str) -> str:
    return (raw or "").strip()


def _looks_like_agent_payload(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    if "files" in parsed and isinstance(parsed.get("files"), list):
        return True
    if parsed.get("ok") and parsed.get("agent"):
        return True
    if "deleted" in parsed or "errors" in parsed:
        return True
    if "error" in parsed:
        return True
    return False


def _request(
    url: str,
    method: str = "GET",
    payload: Optional[dict] = None,
    token: str = DEFAULT_TOKEN,
    timeout: int = 45,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "File-Clear/1.0",
        "ngrok-skip-browser-warning": "1",
        "X-OAL-Token": token or DEFAULT_TOKEN,
    }

    if payload is not None:
        body = dict(payload)
        body.setdefault("token", token or DEFAULT_TOKEN)
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read().decode("utf-8", errors="replace")
            stripped = raw.lstrip()
            if (
                "html" in content_type
                or stripped.lower().startswith("<!doctype")
                or stripped.lower().startswith("<html")
            ):
                raise RuntimeError(
                    "El sitio respondió HTML (no es un endpoint File Clear)."
                )
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Respuesta no JSON (ese dominio no expone File Clear)."
                ) from exc
            if not _looks_like_agent_payload(parsed):
                raise RuntimeError("Respuesta remota no reconocida como File Clear.")
            if isinstance(parsed, dict) and parsed.get("error") and "files" not in parsed:
                raise RuntimeError(str(parsed["error"]))
            return parsed
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("error") or detail
        except Exception:
            if detail.lstrip().lower().startswith("<!"):
                message = "HTML en lugar de JSON"
            else:
                message = detail or str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo contactar el origen: {exc.reason}") from exc


def _with_first_working_agent(
    remote_url: str,
    token: str,
    runner,
) -> dict:
    errors = []
    for agent in candidate_agent_urls(remote_url):
        try:
            result = runner(agent)
            if isinstance(result, dict):
                result["agent_url"] = agent
                result["remote_url"] = remote_url
            return result
        except Exception as exc:
            errors.append(f"{agent}: {exc}")
            continue

    host = urllib.parse.urlparse(remote_url).netloc
    raise RuntimeError(
        f"No se pudo conectar a {host or remote_url}. "
        "File Clear solo gestiona sitios donde tú puedes instalar el endpoint "
        "(tu XAMPP/ngrok/hosting), no apps de terceros como WhatsApp. "
        "En tu sitio coloca oal_agent.php + oal-lab-clean y vuelve a conectar."
    )


def remote_ping(remote_url: str, token: str = DEFAULT_TOKEN) -> dict:
    token = token or DEFAULT_TOKEN

    def runner(agent: str) -> dict:
        query = urllib.parse.urlencode({"action": "ping", "token": token})
        return _request(f"{agent}?{query}", token=token)

    return _with_first_working_agent(remote_url, token, runner)


def remote_list_files(remote_url: str, path: str = "", token: str = DEFAULT_TOKEN) -> dict:
    token = token or DEFAULT_TOKEN

    def runner(agent: str) -> dict:
        query = urllib.parse.urlencode(
            {"action": "files", "path": path or "", "token": token}
        )
        return _request(f"{agent}?{query}", token=token)

    return _with_first_working_agent(remote_url, token, runner)


def remote_delete_files(
    remote_url: str,
    files: list,
    path: str = "",
    token: str = DEFAULT_TOKEN,
) -> dict:
    token = token or DEFAULT_TOKEN

    def runner(agent: str) -> dict:
        return _request(
            agent,
            method="POST",
            payload={
                "action": "eliminar",
                "files": files,
                "path": path or "",
                "token": token,
            },
            token=token,
        )

    return _with_first_working_agent(remote_url, token, runner)
