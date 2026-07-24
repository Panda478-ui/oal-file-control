"""Cliente/proxy para agentes OAL remotos (PHP u otra instancia)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

DEFAULT_TOKEN = "oal-lab-clean"


def normalize_remote_url(raw: str) -> str:
    """
    Normaliza URLs como:
      https://host/lab_sys/index.php  -> https://host/lab_sys
      https://host/lab_sys/oal_agent.php -> https://host/lab_sys/oal_agent.php
      https://host/lab_sys/ -> https://host/lab_sys
    """
    value = (raw or "").strip()
    if not value:
        raise ValueError("URL remota vacía")

    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL remota debe ser http(s)")

    path = parsed.path or "/"
    lower = path.lower()

    if lower.endswith("/oal_agent.php"):
        agent_path = path
        base_dir = path[: -len("/oal_agent.php")] or ""
    elif lower.endswith(".php") or lower.endswith(".html") or lower.endswith(".htm"):
        # quitar archivo final (index.php, login.php, etc.)
        base_dir = path.rsplit("/", 1)[0]
        agent_path = (base_dir.rstrip("/") + "/oal_agent.php") if base_dir else "/oal_agent.php"
    else:
        base_dir = path.rstrip("/")
        agent_path = (base_dir + "/oal_agent.php") if base_dir else "/oal_agent.php"

    agent_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, agent_path, "", "", "")
    )
    base_url = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, base_dir.rstrip("/") or "", "", "", "")
    )
    return agent_url


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
        "User-Agent": "OAL-File-Control/1.0",
        "ngrok-skip-browser-warning": "1",
        "X-OAL-Token": token,
    }

    if payload is not None:
        body = dict(payload)
        body.setdefault("token", token)
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


def remote_ping(remote_url: str, token: str = DEFAULT_TOKEN) -> dict:
    agent = normalize_remote_url(remote_url)
    query = urllib.parse.urlencode({"action": "ping", "token": token})
    return _request(f"{agent}?{query}", token=token)


def remote_list_files(remote_url: str, path: str = "", token: str = DEFAULT_TOKEN) -> dict:
    agent = normalize_remote_url(remote_url)
    query = urllib.parse.urlencode({"action": "files", "path": path or "", "token": token})
    result = _request(f"{agent}?{query}", token=token)
    result["remote_url"] = remote_url
    result["agent_url"] = agent
    return result


def remote_delete_files(
    remote_url: str,
    files: list,
    path: str = "",
    token: str = DEFAULT_TOKEN,
) -> dict:
    agent = normalize_remote_url(remote_url)
    return _request(
        agent,
        method="POST",
        payload={"action": "eliminar", "files": files, "path": path or "", "token": token},
        token=token,
    )
