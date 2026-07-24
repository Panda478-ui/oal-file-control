"""
File Clear — panel web para limpiar archivos y carpetas.

URL principal: https://oal-file-control.onrender.com
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from delete_files import delete_selected_files, list_project_files
from local_site import resolve_site_root_from_url
from netlify_auth import resolve_netlify_token
from netlify_client import (
    delete_netlify_files,
    is_netlify_url,
    list_netlify_files,
)
from remote_client import (
    DEFAULT_TOKEN,
    remote_delete_files,
    remote_list_files,
)

HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", str(ROOT_DIR / "storage"))).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = STORAGE_DIR
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1" if HOST in {"127.0.0.1", "localhost"} else "0") == "1"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://oal-file-control.onrender.com")
AGENT_TOKEN = os.environ.get("OAL_AGENT_TOKEN", DEFAULT_TOKEN)
AGENT_FILE = ROOT_DIR / "agents" / "oal_agent.php"


def _open_target(remote: str, token: str = "", rel: str = "", refresh: bool = False):
    """Conecta a un origen REAL: disco, agente Netlify/PHP, o API Netlify con auth automática."""
    remote = (remote or "").strip()
    token = (token or "").strip()
    local_root = resolve_site_root_from_url(remote)
    if local_root is not None and not is_netlify_url(remote):
        data = list_project_files(local_root, rel)
        data["remote_url"] = remote
        data["provider"] = "local-disk"
        data["agent_url"] = "local-disk"
        return data

    agent_error: Exception | None = None
    if remote.lower().startswith("http://") or remote.lower().startswith("https://"):
        try:
            data = remote_list_files(remote, rel, token or DEFAULT_TOKEN)
            provider = "php-agent"
            agent_url = str(data.get("agent_url") or "")
            if "oal-clean" in agent_url or data.get("provider") == "netlify-agent":
                provider = "netlify-agent"
            elif is_netlify_url(remote) and data.get("agent") == "oal-clean":
                provider = "netlify-agent"
            data["provider"] = data.get("provider") or provider
            data["label"] = data.get("label") or (
                f"Netlify en vivo · {remote}" if provider == "netlify-agent" else remote
            )
            return data
        except Exception as exc:
            agent_error = exc

    if is_netlify_url(remote):
        api_token = resolve_netlify_token(token)
        if api_token:
            data = list_netlify_files(remote, rel, api_token)
            data["provider"] = "netlify"
            return data
        raise RuntimeError(
            "Para borrar de verdad en Netlify sin pegar tokens en el panel: "
            "1) Descarga 'Agente Netlify'  "
            "2) Guárdalo como netlify/functions/oal-clean.js en TU proyecto  "
            "3) En Netlify → Environment variables crea NETLIFY_AUTH_TOKEN (una vez en Netlify, no aquí)  "
            "4) Publica y Conecta solo con la URL. "
            f"Detalle: {agent_error}"
        )

    raise RuntimeError(
        "No se pudo conectar. En hosting PHP sube oal_agent.php. "
        f"Detalle: {agent_error}"
    )


def _delete_target(remote: str, token: str = "", names: list = None, current: str = ""):
    remote = (remote or "").strip()
    token = (token or "").strip()
    names = names or []
    local_root = resolve_site_root_from_url(remote)
    if local_root is not None and not is_netlify_url(remote):
        return delete_selected_files(names, local_root, str(current or ""))

    # Preferir agente instalado en el sitio (borrado real)
    if remote.lower().startswith("http://") or remote.lower().startswith("https://"):
        try:
            return remote_delete_files(remote, names, str(current or ""), token or DEFAULT_TOKEN)
        except Exception as agent_exc:
            if not is_netlify_url(remote):
                raise
            api_token = resolve_netlify_token(token)
            if not api_token:
                raise RuntimeError(
                    "No hay agente Netlify respondiendo y no hay NETLIFY_AUTH_TOKEN. "
                    "Instala oal-clean.js o define la variable de entorno. "
                    f"Detalle: {agent_exc}"
                ) from agent_exc
            return delete_netlify_files(remote, names, str(current or ""), api_token)

    raise RuntimeError("Origen remoto inválido")

PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>File Clear</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #101218;
      --surface: rgba(255, 255, 255, 0.03);
      --line: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(255, 255, 255, 0.14);
      --text: #f2f3f5;
      --muted: #9aa3b2;
      --accent: #c4a574;
      --accent-deep: #a8844f;
      --danger: #d95c5c;
      --danger-bg: rgba(217, 92, 92, 0.1);
      --ok: #7dba8e;
      --warn: #d2b15a;
      --focus: rgba(196, 165, 116, 0.35);
      --space: 1.25rem;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Instrument Sans", sans-serif;
      background:
        radial-gradient(1200px 600px at 50% -20%, rgba(196, 165, 116, 0.09), transparent 55%),
        linear-gradient(180deg, #0c0e13 0%, var(--bg) 45%, #12151c 100%);
      min-height: 100vh;
    }
    .frame {
      width: min(880px, 92vw);
      margin: 0 auto;
      padding: 3.25rem 0 4rem;
      animation: enter 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
    }
    @keyframes enter {
      from { opacity: 0; transform: translateY(14px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
    @keyframes modalIn {
      from { opacity: 0; transform: translateY(10px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .brand-mark {
      display: inline-flex;
      align-items: center;
      gap: 0.7rem;
      margin-bottom: 1.15rem;
      color: var(--accent);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    .brand-mark::before {
      content: "";
      width: 1.6rem;
      height: 1px;
      background: var(--accent);
    }
    .brand {
      margin: 0;
      font-family: "Instrument Serif", serif;
      font-size: clamp(2.8rem, 8vw, 4rem);
      font-weight: 400;
      letter-spacing: -0.03em;
      line-height: 0.95;
    }
    .brand em { font-style: italic; color: var(--accent); }
    .lede {
      margin: 1.15rem 0 2rem;
      max-width: 48ch;
      color: var(--muted);
      line-height: 1.6;
      font-size: 1.02rem;
    }
    .connect {
      display: grid;
      gap: 1rem;
      margin-bottom: 1.75rem;
      padding: 1.45rem 1.4rem 1.35rem;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: rgba(0,0,0,0.18);
    }
    .connect label {
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
      margin-bottom: 0.15rem;
    }
    .connect-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 0.75rem;
    }
    .connect input {
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 4px;
      background: rgba(255,255,255,0.03);
      color: var(--text);
      padding: 0.95rem 1rem;
      font: 500 0.95rem "Instrument Sans", sans-serif;
    }
    .connect input:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--focus);
    }
    .hint {
      margin: 0.35rem 0 0;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.55;
    }
    .hint a { color: var(--accent); }
    .panel {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
      overflow: hidden;
    }
    .panel-head, .panel-foot {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      justify-content: space-between;
      padding: 1.25rem 1.4rem;
      border-color: var(--line);
      background: rgba(0,0,0,0.16);
    }
    .panel-head { border-bottom: 1px solid var(--line); }
    .panel-foot { border-top: 1px solid var(--line); }
    .meta { color: var(--muted); font-size: 0.9rem; line-height: 1.5; }
    .meta strong { color: var(--text); }
    .path { display: block; margin-top: 0.35rem; font-size: 0.78rem; color: rgba(154,163,178,0.8); word-break: break-all; }
    .tools, .crumbs { display: flex; flex-wrap: wrap; gap: 0.55rem; }
    .crumbs { margin-top: 0.85rem; }
    .tool, .crumb {
      border: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      border-radius: 4px;
      padding: 0.55rem 0.85rem;
      font: 500 0.82rem "Instrument Sans", sans-serif;
      cursor: pointer;
    }
    .tool:hover, .crumb:hover {
      color: var(--text);
      border-color: var(--line-strong);
      background: var(--surface);
    }
    .crumb.active {
      color: var(--accent);
      border-color: rgba(196,165,116,0.35);
    }
    .file-list {
      max-height: min(54vh, 520px);
      overflow: auto;
      padding: 0.35rem 0;
      scrollbar-width: thin;
      scrollbar-color: rgba(196,165,116,0.35) transparent;
    }
    .row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 1rem;
      align-items: center;
      padding: 1.15rem 1.4rem;
      margin: 0.35rem 0.7rem;
      border: 1px solid transparent;
      border-radius: 5px;
      transition: background 0.18s, border-color 0.18s;
      animation: enter 0.4s ease both;
    }
    .row:hover { background: rgba(255,255,255,0.03); border-color: var(--line); }
    .row.file { cursor: pointer; }
    .row.file.is-selected {
      background: rgba(196,165,116,0.08);
      border-color: rgba(196,165,116,0.28);
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .row.folder { cursor: default; }
    .row.folder:hover { background: rgba(255,255,255,0.03); }
    .row.folder.is-selected {
      background: rgba(196,165,116,0.08);
      border-color: rgba(196,165,116,0.28);
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .row.is-protected { opacity: 0.48; cursor: not-allowed; }
    .check {
      width: 1.15rem;
      height: 1.15rem;
      border: 1.5px solid rgba(154,163,178,0.55);
      border-radius: 3px;
      display: grid;
      place-items: center;
    }
    .row.is-selected .check {
      background: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--focus);
    }
    .check svg {
      width: 0.7rem;
      height: 0.7rem;
      opacity: 0;
      transform: scale(0.7);
      transition: 0.12s;
    }
    .row.is-selected .check svg { opacity: 1; transform: scale(1); }
    .open-btn {
      border: 1px solid var(--line);
      background: transparent;
      color: var(--text);
      border-radius: 4px;
      padding: 0.45rem 0.8rem;
      font: 600 0.8rem "Instrument Sans", sans-serif;
      cursor: pointer;
      white-space: nowrap;
    }
    .open-btn:hover {
      border-color: rgba(196,165,116,0.45);
      color: var(--accent);
    }
    .folder-actions {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .tool:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
    .name { font-weight: 600; letter-spacing: -0.015em; word-break: break-all; font-size: 0.98rem; }
    .sub { margin-top: 0.3rem; color: var(--muted); font-size: 0.82rem; line-height: 1.4; }
    .ext {
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 3px;
      padding: 0.35rem 0.5rem;
      white-space: nowrap;
    }
    .ext.lock { color: var(--accent); border-color: rgba(196,165,116,0.35); }
    .ext.dir { color: #9ec0ff; border-color: rgba(158,192,255,0.3); }
    .primary, .secondary {
      border-radius: 4px;
      padding: 0.9rem 1.15rem;
      font: 650 0.92rem "Instrument Sans", sans-serif;
      cursor: pointer;
    }
    .primary {
      border: 0;
      background: linear-gradient(180deg, #d1b184, var(--accent-deep));
      color: #1a140c;
    }
    .primary:disabled { opacity: 0.4; cursor: not-allowed; }
    .secondary {
      border: 1px solid var(--line-strong);
      background: transparent;
      color: var(--text);
    }
    .status { min-height: 1.25rem; color: var(--muted); font-size: 0.88rem; }
    .status.ok { color: var(--ok); }
    .status.warn { color: var(--warn); }
    .status.err { color: var(--danger); }
    .empty { padding: 2.8rem 1.4rem; text-align: center; color: var(--muted); }
    .modal-backdrop {
      position: fixed; inset: 0; z-index: 50;
      display: grid; place-items: center; padding: 1.25rem;
      background: rgba(8,10,14,0.78);
      backdrop-filter: blur(10px);
      animation: fade 0.2s ease both;
    }
    .modal-backdrop[hidden] { display: none; }
    .modal {
      width: min(460px, 100%);
      border: 1px solid rgba(217,92,92,0.28);
      border-radius: 6px;
      background:
        radial-gradient(420px 160px at 0% 0%, var(--danger-bg), transparent 55%),
        linear-gradient(180deg, #1a1e27, #13161d);
      padding: 1.6rem;
      animation: modalIn 0.22s ease both;
    }
    .modal h2 {
      margin: 0 0 0.55rem;
      font-family: "Instrument Serif", serif;
      font-size: 1.55rem;
      font-weight: 400;
    }
    .modal p { margin: 0 0 1.15rem; color: var(--muted); line-height: 1.5; }
    .modal-list {
      margin: 0 0 1.35rem;
      padding: 0.9rem 1rem;
      max-height: 170px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: rgba(0,0,0,0.25);
      font-size: 0.9rem;
      line-height: 1.6;
    }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.7rem; }
    .btn-cancel, .btn-danger {
      border-radius: 4px;
      padding: 0.8rem 1.1rem;
      font: 600 0.9rem "Instrument Sans", sans-serif;
      cursor: pointer;
    }
    .btn-cancel { border: 1px solid var(--line-strong); background: transparent; color: var(--text); }
    .btn-danger { border: 0; background: linear-gradient(180deg, #e07070, #c24a4a); color: #fff; }
    @media (max-width: 720px) {
      .frame { padding: 2.25rem 0 3rem; }
      .connect { padding: 1.2rem; gap: 0.85rem; }
      .connect-row { grid-template-columns: 1fr; }
      .panel-head, .panel-foot { flex-direction: column; align-items: stretch; }
      .row { margin: 0.25rem 0.45rem; padding: 1rem; }
      .primary { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="frame">
    <div class="brand-mark">Panel central</div>
    <h1 class="brand">File <em>Clear</em></h1>

    <section class="connect">
      <label for="apiUrl">URL del sitio (borrado real remoto)</label>
      <div class="connect-row">
        <input id="apiUrl" type="text" placeholder="https://tilin2.netlify.app">
        <button type="button" class="secondary" id="btnConnect">Conectar</button>
        <button type="button" class="secondary" id="btnThis">Storage local</button>
      </div>
      <div class="connect-row" style="grid-template-columns: 1fr auto auto;">
        <p class="hint" style="margin:0;align-self:center;">Netlify: instala el agente una vez. PHP: usa oal_agent.php.</p>
        <a class="secondary" href="/agents/netlify/oal-clean.js" download="oal-clean.js" style="text-decoration:none;display:inline-flex;align-items:center;">Agente Netlify</a>
        <a class="secondary" href="/agents/oal_agent.php" download="oal_agent.php" style="text-decoration:none;display:inline-flex;align-items:center;">Agente PHP</a>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="meta" id="meta">Sin conexión</div>
          <div class="crumbs" id="crumbs"></div>
        </div>
        <div class="tools">
          <button type="button" class="tool" id="btnBack">Regresar</button>
          <button type="button" class="tool" id="btnRefresh">Actualizar</button>
          <button type="button" class="tool" id="btnAll">Seleccionar todo</button>
          <button type="button" class="tool" id="btnNone">Limpiar selección</button>
        </div>
      </div>
      <div class="file-list" id="fileList" role="list"></div>
      <div class="panel-foot">
        <button type="button" class="primary" id="btnDelete" disabled>Eliminar seleccionados</button>
        <div class="status" id="status" aria-live="polite"></div>
      </div>
    </section>
  </div>

  <div class="modal-backdrop" id="modal" hidden>
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <h2 id="modalTitle">Confirmar eliminación</h2>
      <p id="modalText">Esta acción es permanente.</p>
      <div class="modal-list" id="modalList"></div>
      <div class="modal-actions">
        <button type="button" class="btn-cancel" id="btnCancel">Cancelar</button>
        <button type="button" class="btn-danger" id="btnConfirm">Confirmar eliminación</button>
      </div>
    </div>
  </div>

  <script>
    const DEFAULT_PUBLIC = "https://oal-file-control.onrender.com";
    const apiUrlInput = document.getElementById("apiUrl");
    const fileListEl = document.getElementById("fileList");
    const metaEl = document.getElementById("meta");
    const crumbsEl = document.getElementById("crumbs");
    const statusEl = document.getElementById("status");
    const btnDelete = document.getElementById("btnDelete");
    const modal = document.getElementById("modal");
    const modalText = document.getElementById("modalText");
    const modalList = document.getElementById("modalList");
    const btnCancel = document.getElementById("btnCancel");
    const btnConfirm = document.getElementById("btnConfirm");

    let remoteUrl = localStorage.getItem("oal_remote_url") || "";
    let remoteToken = "oal-lab-clean";
    let currentPath = localStorage.getItem("oal_current_path") || "";
    let folders = [];
    let files = [];
    let selected = new Set();

    function normalizeBase(url) {
      return (url || "").trim();
    }

    function filesUrl(pathValue, refresh = false) {
      const params = new URLSearchParams();
      if (pathValue) params.set("path", pathValue);
      if (remoteUrl) {
        params.set("remote", remoteUrl);
        params.set("token", remoteToken || "");
      }
      if (refresh) params.set("refresh", "1");
      const q = params.toString();
      return "/api/files" + (q ? `?${q}` : "");
    }

    function setStatus(text, kind = "") {
      statusEl.textContent = text || "";
      statusEl.className = "status" + (kind ? " " + kind : "");
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function updateDeleteButton() {
      const n = selected.size;
      btnDelete.disabled = n === 0;
      btnDelete.textContent = n ? `Eliminar seleccionados (${n})` : "Eliminar seleccionados";
      const btnBack = document.getElementById("btnBack");
      if (btnBack) btnBack.disabled = !currentPath;
    }

    function toggleSelected(key) {
      if (selected.has(key)) selected.delete(key);
      else selected.add(key);
      renderList();
      setStatus("");
    }

    function goBack() {
      if (!currentPath) return;
      const parts = currentPath.split("/").filter(Boolean);
      parts.pop();
      currentPath = parts.join("/");
      localStorage.setItem("oal_current_path", currentPath);
      loadFiles();
    }

    function renderCrumbs(items) {
      crumbsEl.innerHTML = "";
      (items || []).forEach((crumb) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "crumb" + (crumb.path === currentPath ? " active" : "");
        btn.textContent = crumb.name;
        btn.addEventListener("click", () => {
          currentPath = crumb.path || "";
          localStorage.setItem("oal_current_path", currentPath);
          loadFiles();
        });
        crumbsEl.appendChild(btn);
      });
    }

    function renderList() {
      fileListEl.innerHTML = "";
      if (!folders.length && !files.length) {
        fileListEl.innerHTML = '<div class="empty">Esta carpeta está vacía.</div>';
        updateDeleteButton();
        return;
      }

      folders.forEach((folder, index) => {
        const key = folder.path || folder.name;
        const row = document.createElement("div");
        row.className = "row folder";
        row.style.animationDelay = `${Math.min(index * 0.03, 0.25)}s`;
        if (selected.has(key)) row.classList.add("is-selected");

        row.innerHTML = `
          <span class="check" aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M3.5 8.2 6.4 11l6.1-6.4" stroke="#1a140c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span>
            <div class="name">${escapeHtml(folder.name)}</div>
            <div class="sub">Carpeta completa · marcar para borrar todo su contenido</div>
          </span>
          <span class="folder-actions">
            <button type="button" class="open-btn">Abrir</button>
            <span class="ext dir">carpeta</span>
          </span>
        `;

        row.querySelector(".check").addEventListener("click", (event) => {
          event.stopPropagation();
          toggleSelected(key);
        });
        row.querySelector(".name").parentElement.addEventListener("click", () => toggleSelected(key));
        row.querySelector(".open-btn").addEventListener("click", (event) => {
          event.stopPropagation();
          currentPath = folder.path;
          localStorage.setItem("oal_current_path", currentPath);
          loadFiles();
        });
        fileListEl.appendChild(row);
      });

      files.forEach((file, index) => {
        const row = document.createElement("div");
        row.className = "row file";
        row.style.animationDelay = `${Math.min((folders.length + index) * 0.03, 0.35)}s`;
        if (file.protected) row.classList.add("is-protected");
        else if (selected.has(file.path || file.name)) row.classList.add("is-selected");

        row.innerHTML = `
          <span class="check" aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M3.5 8.2 6.4 11l6.1-6.4" stroke="#1a140c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span>
            <div class="name">${escapeHtml(file.name)}</div>
            <div class="sub">${escapeHtml(file.size_label)}</div>
          </span>
          <span class="ext ${file.protected ? "lock" : ""}">
            ${file.protected ? "protegido" : escapeHtml(file.ext)}
          </span>
        `;

        if (!file.protected) {
          row.addEventListener("click", () => toggleSelected(file.path || file.name));
        }
        fileListEl.appendChild(row);
      });

      updateDeleteButton();
    }

    async function loadFiles(opts = {}) {
      const refresh = !!opts.refresh;
      setStatus(refresh ? "Descargando sitio…" : "Leyendo origen…");
      try {
        const res = await fetch(filesUrl(currentPath, refresh));
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
        folders = data.folders || [];
        files = data.files || [];
        currentPath = data.path || "";
        localStorage.setItem("oal_current_path", currentPath);
        selected = new Set(
          files.filter((f) => f.selected_default).map((f) => f.path || f.name)
        );
        const mode =
          data.provider === "netlify" || data.provider === "netlify-agent" ? "Netlify en vivo"
          : data.provider === "php-agent" ? "Remoto PHP"
          : (remoteUrl ? "Remoto" : "Local");
        metaEl.innerHTML =
          `<strong>${mode}</strong> · <strong>${data.folder_count || 0}</strong> carpetas · <strong>${data.file_count || 0}</strong> archivos · ~<strong>${escapeHtml(data.reclaimable_label || data.total_size_label || "0 B")}</strong>` +
          `<span class="path">${escapeHtml(data.label || data.folder || data.root || remoteUrl || "")}</span>`;
        renderCrumbs(data.breadcrumb || []);
        renderList();
        setStatus(
          remoteUrl
            ? ((data.provider === "netlify" || data.provider === "netlify-agent")
                ? `Conectado en vivo a ${remoteUrl}. Los borrados cambian el dominio real.`
                : `Conectado a ${remoteUrl}`)
            : "Storage local de File Clear",
          "ok"
        );
      } catch (err) {
        folders = [];
        files = [];
        renderList();
        metaEl.textContent = "No se pudo leer el origen";
        setStatus(err.message || "No se pudo conectar a esa URL.", "err");
      }
    }

    function connect(url) {
      remoteUrl = normalizeBase(url);
      remoteToken = "oal-lab-clean";
      localStorage.setItem("oal_remote_url", remoteUrl);
      localStorage.setItem("oal_remote_token", remoteToken);
      apiUrlInput.value = remoteUrl;
      currentPath = "";
      localStorage.setItem("oal_current_path", "");
      loadFiles({ refresh: true });
    }

    function openModal() {
      const names = [...selected];
      if (!names.length) return;
      modalText.textContent = remoteUrl
        ? `Se eliminarán ${names.length} elemento(s) del sitio EN VIVO (el dominio cambiará de verdad).`
        : `Se eliminarán ${names.length} elemento(s) del storage local.`;
      modalList.innerHTML = names.map((name) => escapeHtml(name)).join("<br>");
      modal.hidden = false;
      btnConfirm.focus();
    }

    function closeModal() {
      modal.hidden = true;
      btnDelete.focus();
    }

    async function confirmDelete() {
      const names = [...selected];
      btnConfirm.disabled = true;
      btnCancel.disabled = true;
      btnConfirm.textContent = "Procesando…";
      try {
        const res = await fetch("/api/eliminar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            files: names,
            path: currentPath,
            remote: remoteUrl || "",
            token: remoteToken || "",
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Error al eliminar");
        closeModal();
        const kind = data.deleted && data.deleted.length ? "ok" : "warn";
        const extra = data.freed_label ? ` · Liberado ${data.freed_label}` : "";
        setStatus((data.message || "Operación completada") + extra, kind);
        await loadFiles();
      } catch (err) {
        setStatus(err.message || "Error de comunicación con el origen.", "err");
      } finally {
        btnConfirm.disabled = false;
        btnCancel.disabled = false;
        btnConfirm.textContent = "Confirmar eliminación";
      }
    }

    document.getElementById("btnConnect").addEventListener("click", () => connect(apiUrlInput.value));
    document.getElementById("btnThis").addEventListener("click", () => connect(""));
    document.getElementById("btnRefresh").addEventListener("click", () => loadFiles({ refresh: true }));
    document.getElementById("btnAll").addEventListener("click", () => {
      selected = new Set([
        ...folders.map((f) => f.path || f.name),
        ...files.filter((f) => !f.protected).map((f) => f.path || f.name),
      ]);
      renderList();
    });
    document.getElementById("btnNone").addEventListener("click", () => {
      selected.clear();
      renderList();
    });
    document.getElementById("btnBack").addEventListener("click", goBack);
    apiUrlInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") connect(apiUrlInput.value);
    });

    btnDelete.addEventListener("click", openModal);
    btnCancel.addEventListener("click", closeModal);
    btnConfirm.addEventListener("click", confirmDelete);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeModal();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) closeModal();
    });

    apiUrlInput.value = remoteUrl;
    loadFiles();
  </script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send_html(self, status: int, html: str) -> None:
        self._send(status, html.encode("utf-8"), "text/html; charset=utf-8")

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_html(200, PAGE)
            return

        if path == "/agents/oal_agent.php":
            if not AGENT_FILE.is_file():
                self._send_json(404, {"error": "Agente no disponible"})
                return
            body = AGENT_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="oal_agent.php"',
            )
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/agents/netlify/oal-clean.js":
            agent = ROOT_DIR / "agents" / "netlify" / "oal-clean.js"
            if not agent.is_file():
                self._send_json(404, {"error": "Agente Netlify no disponible"})
                return
            body = agent.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="oal-clean.js"',
            )
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/agents/oal-lab-clean":
            marker = ROOT_DIR / "agents" / "oal-lab-clean"
            body = marker.read_bytes() if marker.is_file() else b"oal-lab-clean\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="oal-lab-clean"',
            )
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "public_url": PUBLIC_URL,
                    "storage": str(BASE_DIR),
                    "agent_token_default": AGENT_TOKEN,
                },
            )
            return

        if path == "/api/remote/ping":
            remote = (query.get("remote") or [""])[0]
            token = (query.get("token") or [""])[0] or ""
            try:
                data = _open_target(remote, token, "")
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "agent": data.get("provider") or data.get("agent_url") or "ok",
                        "root": data.get("root") or data.get("folder"),
                        "remote_url": remote,
                    },
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if path == "/api/files":
            rel = (query.get("path") or [""])[0]
            remote = (query.get("remote") or [""])[0].strip()
            token = (query.get("token") or [""])[0] or ""
            refresh = (query.get("refresh") or [""])[0] in {"1", "true", "yes"}
            try:
                if remote:
                    self._send_json(200, _open_target(remote, token, rel, refresh=refresh))
                else:
                    self._send_json(200, list_project_files(BASE_DIR, rel))
            except FileNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        self._send_json(404, {"error": "Ruta no encontrada"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/eliminar":
            payload = self._read_json_body()
            names = payload.get("files", [])
            current = payload.get("path", "")
            remote = str(payload.get("remote") or "").strip()
            token = str(payload.get("token") or "")
            if not isinstance(names, list):
                self._send_json(400, {"error": 'Envía {"files": ["archivo.ext"], "path": ""}'})
                return
            try:
                if remote:
                    result = _delete_target(remote, token, names, str(current or ""))
                else:
                    result = delete_selected_files(names, BASE_DIR, str(current or ""))
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)
            return

        self._send_json(404, {"error": "Ruta no encontrada"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    display_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    url = f"http://{display_host}:{PORT}/"
    print("File Clear")
    print(f"  Escuchando: {HOST}:{PORT}")
    print(f"  Local: {url}")
    print(f"  Público: {PUBLIC_URL}")
    print(f"  Archivos: {BASE_DIR}")
    print("Ctrl+C para detener")
    if OPEN_BROWSER:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
