"""
OAL File Control — panel web para limpiar archivos y carpetas.

URL principal: https://oal-file-control.onrender.com

Uso local + túnel:
  iniciar-tunel.bat
  Luego pega la URL del túnel en el panel de Render.
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from delete_files import delete_selected_files, list_project_files

HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", str(ROOT_DIR / "storage"))).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = STORAGE_DIR
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1" if HOST in {"127.0.0.1", "localhost"} else "0") == "1"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://oal-file-control.onrender.com")

PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OAL File Control</title>
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
      width: min(860px, 94vw);
      margin: 0 auto;
      padding: 2.5rem 0 3rem;
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
      gap: 0.55rem;
      margin-bottom: 0.85rem;
      color: var(--accent);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    .brand-mark::before {
      content: "";
      width: 1.4rem;
      height: 1px;
      background: var(--accent);
    }
    .brand {
      margin: 0;
      font-family: "Instrument Serif", serif;
      font-size: clamp(2.5rem, 7vw, 3.6rem);
      font-weight: 400;
      letter-spacing: -0.03em;
      line-height: 0.95;
    }
    .brand em { font-style: italic; color: var(--accent); }
    .lede {
      margin: 0.85rem 0 1.4rem;
      max-width: 46ch;
      color: var(--muted);
      line-height: 1.5;
    }
    .connect {
      display: grid;
      gap: 0.65rem;
      margin-bottom: 1rem;
      padding: 1rem;
      border: 1px solid var(--line);
      border-radius: 4px;
      background: rgba(0,0,0,0.18);
    }
    .connect label {
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }
    .connect-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 0.5rem;
    }
    .connect input {
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 3px;
      background: rgba(255,255,255,0.03);
      color: var(--text);
      padding: 0.75rem 0.85rem;
      font: 500 0.92rem "Instrument Sans", sans-serif;
    }
    .connect input:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--focus);
    }
    .hint {
      margin: 0;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.4;
    }
    .hint a { color: var(--accent); }
    .panel {
      border: 1px solid var(--line);
      border-radius: 4px;
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
      overflow: hidden;
    }
    .panel-head, .panel-foot {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
      padding: 0.95rem 1.1rem;
      border-color: var(--line);
      background: rgba(0,0,0,0.16);
    }
    .panel-head { border-bottom: 1px solid var(--line); }
    .panel-foot { border-top: 1px solid var(--line); }
    .meta { color: var(--muted); font-size: 0.86rem; line-height: 1.4; }
    .meta strong { color: var(--text); }
    .path { display: block; margin-top: 0.2rem; font-size: 0.76rem; color: rgba(154,163,178,0.8); word-break: break-all; }
    .tools, .crumbs { display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .tool, .crumb {
      border: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      border-radius: 3px;
      padding: 0.4rem 0.7rem;
      font: 500 0.8rem "Instrument Sans", sans-serif;
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
      max-height: min(52vh, 480px);
      overflow: auto;
      scrollbar-width: thin;
      scrollbar-color: rgba(196,165,116,0.35) transparent;
    }
    .row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 0.85rem;
      align-items: center;
      padding: 0.9rem 1.1rem;
      border-bottom: 1px solid var(--line);
      transition: background 0.18s;
      animation: enter 0.4s ease both;
    }
    .row:last-child { border-bottom: 0; }
    .row.file { cursor: pointer; }
    .row.file:hover { background: rgba(255,255,255,0.025); }
    .row.file.is-selected {
      background: rgba(196,165,116,0.07);
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .row.folder { cursor: pointer; }
    .row.folder:hover { background: rgba(255,255,255,0.03); }
    .row.is-protected { opacity: 0.48; cursor: not-allowed; }
    .check {
      width: 1.05rem;
      height: 1.05rem;
      border: 1.5px solid rgba(154,163,178,0.55);
      border-radius: 2px;
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
    .folder-icon {
      width: 1.05rem;
      height: 1.05rem;
      border-radius: 2px;
      background: linear-gradient(135deg, rgba(196,165,116,0.35), rgba(196,165,116,0.08));
      border: 1px solid rgba(196,165,116,0.35);
    }
    .name { font-weight: 600; letter-spacing: -0.015em; word-break: break-all; }
    .sub { margin-top: 0.15rem; color: var(--muted); font-size: 0.8rem; }
    .ext {
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 2px;
      padding: 0.28rem 0.45rem;
      white-space: nowrap;
    }
    .ext.lock { color: var(--accent); border-color: rgba(196,165,116,0.35); }
    .ext.dir { color: #9ec0ff; border-color: rgba(158,192,255,0.3); }
    .primary, .secondary {
      border-radius: 3px;
      padding: 0.78rem 1.05rem;
      font: 650 0.9rem "Instrument Sans", sans-serif;
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
    .status { min-height: 1.25rem; color: var(--muted); font-size: 0.86rem; }
    .status.ok { color: var(--ok); }
    .status.warn { color: var(--warn); }
    .status.err { color: var(--danger); }
    .empty { padding: 2.2rem 1rem; text-align: center; color: var(--muted); }
    .modal-backdrop {
      position: fixed; inset: 0; z-index: 50;
      display: grid; place-items: center; padding: 1rem;
      background: rgba(8,10,14,0.78);
      backdrop-filter: blur(10px);
      animation: fade 0.2s ease both;
    }
    .modal-backdrop[hidden] { display: none; }
    .modal {
      width: min(460px, 100%);
      border: 1px solid rgba(217,92,92,0.28);
      border-radius: 4px;
      background:
        radial-gradient(420px 160px at 0% 0%, var(--danger-bg), transparent 55%),
        linear-gradient(180deg, #1a1e27, #13161d);
      padding: 1.35rem;
      animation: modalIn 0.22s ease both;
    }
    .modal h2 {
      margin: 0 0 0.4rem;
      font-family: "Instrument Serif", serif;
      font-size: 1.5rem;
      font-weight: 400;
    }
    .modal p { margin: 0 0 1rem; color: var(--muted); line-height: 1.45; }
    .modal-list {
      margin: 0 0 1.15rem;
      padding: 0.75rem 0.85rem;
      max-height: 170px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 3px;
      background: rgba(0,0,0,0.25);
      font-size: 0.88rem;
      line-height: 1.55;
    }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.55rem; }
    .btn-cancel, .btn-danger {
      border-radius: 3px;
      padding: 0.7rem 1rem;
      font: 600 0.88rem "Instrument Sans", sans-serif;
      cursor: pointer;
    }
    .btn-cancel { border: 1px solid var(--line-strong); background: transparent; color: var(--text); }
    .btn-danger { border: 0; background: linear-gradient(180deg, #e07070, #c24a4a); color: #fff; }
    @media (max-width: 720px) {
      .connect-row { grid-template-columns: 1fr; }
      .panel-head, .panel-foot { flex-direction: column; align-items: stretch; }
      .primary { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="frame">
    <div class="brand-mark">Panel central</div>
    <h1 class="brand">OAL <em>File Control</em></h1>
    <p class="lede">Conecta una URL de origen (Render, túnel local u otra instancia) y limpia archivos navegando por sus carpetas.</p>

    <section class="connect">
      <label for="apiUrl">URL del origen</label>
      <div class="connect-row">
        <input id="apiUrl" type="url" placeholder="https://oal-file-control.onrender.com o URL del túnel">
        <button type="button" class="secondary" id="btnConnect">Conectar</button>
        <button type="button" class="secondary" id="btnThis">Este servidor</button>
      </div>
      <p class="hint">
        Panel principal: <a href="https://oal-file-control.onrender.com" target="_blank" rel="noopener">oal-file-control.onrender.com</a>.
        Para limpiar tu PC, ejecuta <code>iniciar-tunel.bat</code> y pega aquí la URL del túnel.
      </p>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="meta" id="meta">Sin conexión</div>
          <div class="crumbs" id="crumbs"></div>
        </div>
        <div class="tools">
          <button type="button" class="tool" id="btnUp">Subir</button>
          <button type="button" class="tool" id="btnRefresh">Actualizar</button>
          <button type="button" class="tool" id="btnAll">Seleccionar archivos</button>
          <button type="button" class="tool" id="btnNone">Limpiar</button>
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

    let apiBase = localStorage.getItem("oal_api_base") || "";
    let currentPath = localStorage.getItem("oal_current_path") || "";
    let folders = [];
    let files = [];
    let selected = new Set();

    function normalizeBase(url) {
      const value = (url || "").trim().replace(/\/+$/, "");
      return value;
    }

    function api(path) {
      const base = normalizeBase(apiBase);
      if (!base) return path;
      return base + path;
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
        const row = document.createElement("div");
        row.className = "row folder";
        row.style.animationDelay = `${Math.min(index * 0.03, 0.25)}s`;
        row.innerHTML = `
          <span class="folder-icon" aria-hidden="true"></span>
          <span>
            <div class="name">${escapeHtml(folder.name)}</div>
            <div class="sub">Abrir carpeta</div>
          </span>
          <span class="ext dir">carpeta</span>
        `;
        row.addEventListener("click", () => {
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
          row.addEventListener("click", () => {
            const key = file.path || file.name;
            if (selected.has(key)) selected.delete(key);
            else selected.add(key);
            renderList();
            setStatus("");
          });
        }
        fileListEl.appendChild(row);
      });

      updateDeleteButton();
    }

    async function loadFiles() {
      setStatus("Leyendo origen…");
      try {
        const query = currentPath ? `?path=${encodeURIComponent(currentPath)}` : "";
        const res = await fetch(api(`/api/files${query}`));
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        folders = data.folders || [];
        files = data.files || [];
        currentPath = data.path || "";
        localStorage.setItem("oal_current_path", currentPath);
        selected = new Set(
          files.filter((f) => f.selected_default).map((f) => f.path || f.name)
        );
        metaEl.innerHTML =
          `<strong>${data.folder_count || 0}</strong> carpetas · <strong>${data.file_count || 0}</strong> archivos · ~<strong>${escapeHtml(data.reclaimable_label || "0 B")}</strong>` +
          `<span class="path">${escapeHtml(data.folder || data.root || "")}</span>`;
        renderCrumbs(data.breadcrumb || []);
        renderList();
        setStatus(apiBase ? `Conectado a ${apiBase}` : "Conectado a este servidor", "ok");
      } catch (err) {
        folders = [];
        files = [];
        renderList();
        metaEl.textContent = "No se pudo leer el origen";
        setStatus("Error de conexión. Revisa la URL del origen o el túnel.", "err");
      }
    }

    function connect(url) {
      apiBase = normalizeBase(url);
      localStorage.setItem("oal_api_base", apiBase);
      apiUrlInput.value = apiBase;
      currentPath = "";
      localStorage.setItem("oal_current_path", "");
      loadFiles();
    }

    function openModal() {
      const names = [...selected];
      if (!names.length) return;
      modalText.textContent = `Se eliminarán ${names.length} archivo(s) del origen conectado.`;
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
        const res = await fetch(api("/api/eliminar"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ files: names, path: currentPath }),
        });
        const data = await res.json();
        closeModal();
        const kind = data.deleted && data.deleted.length ? "ok" : "warn";
        const extra = data.freed_label ? ` · Liberado ${data.freed_label}` : "";
        setStatus((data.message || "Operación completada") + extra, kind);
        await loadFiles();
      } catch (err) {
        setStatus("Error de comunicación con el origen.", "err");
      } finally {
        btnConfirm.disabled = false;
        btnCancel.disabled = false;
        btnConfirm.textContent = "Confirmar eliminación";
      }
    }

    document.getElementById("btnConnect").addEventListener("click", () => connect(apiUrlInput.value));
    document.getElementById("btnThis").addEventListener("click", () => connect(""));
    document.getElementById("btnRefresh").addEventListener("click", loadFiles);
    document.getElementById("btnAll").addEventListener("click", () => {
      selected = new Set(files.filter((f) => !f.protected).map((f) => f.path || f.name));
      renderList();
    });
    document.getElementById("btnNone").addEventListener("click", () => {
      selected.clear();
      renderList();
    });
    document.getElementById("btnUp").addEventListener("click", () => {
      if (!currentPath) return;
      const parts = currentPath.split("/").filter(Boolean);
      parts.pop();
      currentPath = parts.join("/");
      localStorage.setItem("oal_current_path", currentPath);
      loadFiles();
    });
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

    apiUrlInput.value = apiBase;
    if (!apiBase && location.hostname.includes("onrender.com")) {
      apiUrlInput.placeholder = "Pega aquí la URL del túnel a tu PC";
    } else if (!apiBase) {
      apiUrlInput.placeholder = DEFAULT_PUBLIC + " o URL del túnel";
    }
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

        if path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "public_url": PUBLIC_URL,
                    "storage": str(BASE_DIR),
                },
            )
            return

        if path == "/api/files":
            rel = (query.get("path") or [""])[0]
            try:
                self._send_json(200, list_project_files(BASE_DIR, rel))
            except FileNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            return

        self._send_json(404, {"error": "Ruta no encontrada"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/eliminar":
            payload = self._read_json_body()
            names = payload.get("files", [])
            current = payload.get("path", "")
            if not isinstance(names, list):
                self._send_json(400, {"error": 'Envía {"files": ["archivo.ext"], "path": ""}'})
                return
            try:
                result = delete_selected_files(names, BASE_DIR, str(current or ""))
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)
            return

        self._send_json(404, {"error": "Ruta no encontrada"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    display_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    url = f"http://{display_host}:{PORT}/"
    print("OAL File Control")
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
