"""Resuelve credenciales Netlify sin pedirlas en la UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def resolve_netlify_token(explicit: str = "") -> str:
    """
    Orden:
    1) token explícito (si viniera)
    2) NETLIFY_AUTH_TOKEN / OAL_NETLIFY_TOKEN (Render o local)
    3) config del Netlify CLI (~/.netlify/config.json)
    """
    for value in (
        explicit,
        os.environ.get("NETLIFY_AUTH_TOKEN", ""),
        os.environ.get("OAL_NETLIFY_TOKEN", ""),
    ):
        token = (value or "").strip()
        if token and token != "oal-lab-clean":
            return token

    home = Path.home()
    candidates = [
        home / ".netlify" / "config.json",
        home / ".config" / "netlify" / "config.json",
        Path(os.environ.get("APPDATA", "")) / "netlify" / "Config" / "config.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # formatos posibles del CLI
        for key in ("access_token", "token", "authToken"):
            token = str(data.get(key) or "").strip()
            if token:
                return token
        users = data.get("users") or data.get("userId") 
        if isinstance(data.get("users"), dict):
            for user in data["users"].values():
                if isinstance(user, dict):
                    token = str(user.get("auth", {}).get("token") or user.get("access_token") or "").strip()
                    if token:
                        return token
    return ""
