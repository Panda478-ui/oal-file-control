"""Cliente/proxy para agentes File Clear en cualquier dominio."""

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
    Ejemplos:
      https://host/lab_sys/index.php
      https://host/lab_sys/
      https://host/
      https://host/lab_sys/oal_agent.php
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

    if lower.endswith("oal_agent.php"):
        add(path if path.startswith("/") else "/" + path)
    else:
        if lower.endswith(".php") or lower.endswith(".html") or lower.endswith(".htm"):
            parts = parts[:-1]
        # carpeta actual
        base = "/" + "/".join(parts) if parts else ""
        add((base + "/oal_agent.php") if base else "/oal_agent.php")
        # subir un nivel (por si pegaron una subruta)
        if len(parts) >= 1:
            parent = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""
            add((parent + "/oal_agent.php") if parent else "/oal_agent.php")
        # raíz del dominio
        add("/oal_agent.php")

    return candidates


def normalize_remote_url(raw: str) -> str:
    return candidate_agent_urls(raw)[0]


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
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise ValueError("Respuesta remota inválida")
            return parsed
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("error") or detail
        except Exception:
            message = detail or str(exc)
        raise RuntimeError(f"Remoto HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo contactar el origen remoto: {exc.reason}") from exc


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
            errors.append(f"{agent} -> {exc}")
            continue
    raise RuntimeError(
        "No se encontró oal_agent.php en ese dominio. "
        "Sube oal_agent.php y el archivo oal-lab-clean a la carpeta del sitio. "
        + " | ".join(errors[:3])
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
