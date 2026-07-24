"""
OAL File Control — eliminación controlada de archivos del proyecto.

Uso local:
  py -3 app.py
  Abrir: http://127.0.0.1:5000/

Producción (Render):
  HOST=0.0.0.0 PORT=10000 python app.py
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from delete_files import delete_selected_files, list_project_files

HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
ROOT_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", str(ROOT_DIR / "storage"))).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BASE_DIR = STORAGE_DIR
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1" if HOST in {"127.0.0.1", "localhost"} else "0") == "1"

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
      --bg-2: #161a22;
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
    html, body { min-height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Instrument Sans", sans-serif;
      background:
        radial-gradient(1200px 600px at 50% -20%, rgba(196, 165, 116, 0.09), transparent 55%),
        radial-gradient(800px 500px at 100% 100%, rgba(90, 110, 140, 0.08), transparent 50%),
        linear-gradient(180deg, #0c0e13 0%, var(--bg) 45%, #12151c 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.4;
      background:
        linear-gradient(90deg, transparent 0 48%, rgba(255,255,255,0.015) 50%, transparent 52% 100%),
        repeating-linear-gradient(
          0deg,
          transparent,
          transparent 96px,
          rgba(255, 255, 255, 0.015) 96px,
          rgba(255, 255, 255, 0.015) 97px
        );
    }

    .frame {
      width: min(780px, 94vw);
      margin: 0 auto;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 3rem 0 3.5rem;
      position: relative;
      z-index: 1;
      animation: enter 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    @keyframes enter {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes fade {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes modalIn {
      from { opacity: 0; transform: translateY(10px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .brand-block { margin-bottom: 2rem; }

    .brand-mark {
      display: inline-flex;
      align-items: center;
      gap: 0.55rem;
      margin-bottom: 1rem;
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    .brand-mark::before {
      content: "";
      width: 1.5rem;
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

    .brand em {
      font-style: italic;
      color: var(--accent);
    }

    .lede {
      margin: 0.9rem 0 0;
      max-width: 38ch;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.5;
      font-weight: 400;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 4px;
      background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
      overflow: hidden;
      animation: enter 0.7s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .panel-head {
      display: flex;
      flex-wrap: wrap;
      gap: 0.85rem;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 1.15rem;
      border-bottom: 1px solid var(--line);
      background: rgba(0, 0, 0, 0.18);
    }

    .meta {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.4;
    }

    .meta strong {
      color: var(--text);
      font-weight: 600;
    }

    .path {
      display: block;
      margin-top: 0.2rem;
      font-size: 0.78rem;
      color: rgba(154, 163, 178, 0.75);
      word-break: break-all;
    }

    .tools {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }

    .tool {
      border: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      border-radius: 3px;
      padding: 0.42rem 0.75rem;
      font: 500 0.8rem "Instrument Sans", sans-serif;
      cursor: pointer;
      transition: color 0.2s, border-color 0.2s, background 0.2s;
    }

    .tool:hover {
      color: var(--text);
      border-color: var(--line-strong);
      background: var(--surface);
    }

    .file-list {
      max-height: min(48vh, 440px);
      overflow: auto;
      scrollbar-width: thin;
      scrollbar-color: rgba(196, 165, 116, 0.35) transparent;
    }

    .file-row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 0.9rem;
      align-items: center;
      padding: 0.95rem 1.15rem;
      border-bottom: 1px solid var(--line);
      cursor: pointer;
      transition: background 0.18s;
      animation: enter 0.45s ease both;
    }

    .file-row:last-child { border-bottom: 0; }

    .file-row:hover { background: rgba(255, 255, 255, 0.025); }

    .file-row.is-selected {
      background: rgba(196, 165, 116, 0.07);
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .file-row.is-protected {
      opacity: 0.48;
      cursor: not-allowed;
    }

    .file-row.is-protected:hover { background: transparent; }

    .check {
      width: 1.05rem;
      height: 1.05rem;
      border: 1.5px solid rgba(154, 163, 178, 0.55);
      border-radius: 2px;
      display: grid;
      place-items: center;
      transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
    }

    .file-row.is-selected .check {
      background: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--focus);
    }

    .check svg {
      width: 0.7rem;
      height: 0.7rem;
      opacity: 0;
      transform: scale(0.7);
      transition: opacity 0.12s, transform 0.12s;
    }

    .file-row.is-selected .check svg {
      opacity: 1;
      transform: scale(1);
    }

    .file-name {
      font-size: 0.98rem;
      font-weight: 600;
      letter-spacing: -0.015em;
      word-break: break-all;
    }

    .file-sub {
      margin-top: 0.18rem;
      color: var(--muted);
      font-size: 0.8rem;
    }

    .ext {
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 2px;
      padding: 0.28rem 0.45rem;
      white-space: nowrap;
    }

    .ext.lock {
      color: var(--accent);
      border-color: rgba(196, 165, 116, 0.35);
    }

    .panel-foot {
      display: flex;
      flex-wrap: wrap;
      gap: 0.85rem;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 1.15rem;
      border-top: 1px solid var(--line);
      background: rgba(0, 0, 0, 0.16);
    }

    .primary {
      border: 0;
      border-radius: 3px;
      padding: 0.85rem 1.2rem;
      background: linear-gradient(180deg, #d1b184, var(--accent-deep));
      color: #1a140c;
      font: 650 0.92rem "Instrument Sans", sans-serif;
      letter-spacing: -0.01em;
      cursor: pointer;
      transition: filter 0.18s, transform 0.18s, opacity 0.18s;
    }

    .primary:hover:not(:disabled) {
      filter: brightness(1.06);
      transform: translateY(-1px);
    }

    .primary:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      transform: none;
    }

    .status {
      min-height: 1.3rem;
      color: var(--muted);
      font-size: 0.88rem;
    }

    .status.ok { color: var(--ok); }
    .status.warn { color: var(--warn); }
    .status.err { color: var(--danger); }

    .empty {
      padding: 2.4rem 1.2rem;
      text-align: center;
      color: var(--muted);
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: grid;
      place-items: center;
      padding: 1rem;
      background: rgba(8, 10, 14, 0.78);
      backdrop-filter: blur(10px);
      animation: fade 0.2s ease both;
    }

    .modal-backdrop[hidden] { display: none; }

    .modal {
      width: min(460px, 100%);
      border: 1px solid rgba(217, 92, 92, 0.28);
      border-radius: 4px;
      background:
        radial-gradient(420px 160px at 0% 0%, var(--danger-bg), transparent 55%),
        linear-gradient(180deg, #1a1e27, #13161d);
      padding: 1.4rem 1.35rem 1.25rem;
      box-shadow: 0 30px 70px rgba(0, 0, 0, 0.5);
      animation: modalIn 0.22s ease both;
    }

    .modal h2 {
      margin: 0 0 0.4rem;
      font-family: "Instrument Serif", serif;
      font-size: 1.55rem;
      font-weight: 400;
      letter-spacing: -0.02em;
    }

    .modal p {
      margin: 0 0 1rem;
      color: var(--muted);
      line-height: 1.45;
      font-size: 0.95rem;
    }

    .modal-list {
      margin: 0 0 1.2rem;
      padding: 0.75rem 0.85rem;
      max-height: 170px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 3px;
      background: rgba(0, 0, 0, 0.25);
      font-size: 0.88rem;
      line-height: 1.55;
    }

    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.55rem;
    }

    .btn-cancel,
    .btn-danger {
      border-radius: 3px;
      padding: 0.7rem 1rem;
      font: 600 0.88rem "Instrument Sans", sans-serif;
      cursor: pointer;
    }

    .btn-cancel {
      border: 1px solid var(--line-strong);
      background: transparent;
      color: var(--text);
    }

    .btn-danger {
      border: 0;
      background: linear-gradient(180deg, #e07070, #c24a4a);
      color: #fff;
    }

    .btn-danger:disabled,
    .btn-cancel:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    @media (max-width: 640px) {
      .panel-head, .panel-foot { align-items: stretch; flex-direction: column; }
      .primary { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="frame">
    <header class="brand-block">
      <div class="brand-mark">Sistema local</div>
      <h1 class="brand">OAL <em>File Control</em></h1>
      <p class="lede">Seleccione los archivos de la carpeta <em>storage</em> que desea eliminar. Se admite cualquier tipo de archivo.</p>
    </header>

    <section class="panel" aria-label="Listado de archivos">
      <div class="panel-head">
        <div class="meta" id="meta">Cargando inventario…</div>
        <div class="tools">
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
    const fileListEl = document.getElementById("fileList");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const btnDelete = document.getElementById("btnDelete");
    const modal = document.getElementById("modal");
    const modalText = document.getElementById("modalText");
    const modalList = document.getElementById("modalList");
    const btnCancel = document.getElementById("btnCancel");
    const btnConfirm = document.getElementById("btnConfirm");

    let files = [];
    let selected = new Set();
    let folderPath = "";

    function setStatus(text, kind = "") {
      statusEl.textContent = text || "";
      statusEl.className = "status" + (kind ? " " + kind : "");
    }

    function selectableFiles() {
      return files.filter((f) => !f.protected);
    }

    function updateDeleteButton() {
      const n = selected.size;
      btnDelete.disabled = n === 0;
      btnDelete.textContent = n
        ? `Eliminar seleccionados (${n})`
        : "Eliminar seleccionados";
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function renderFiles() {
      fileListEl.innerHTML = "";

      if (!files.length) {
        fileListEl.innerHTML = '<div class="empty">No hay archivos en este directorio.</div>';
        updateDeleteButton();
        return;
      }

      files.forEach((file, index) => {
        const row = document.createElement("div");
        row.className = "file-row";
        row.style.animationDelay = `${Math.min(index * 0.03, 0.3)}s`;
        row.setAttribute("role", "listitem");

        if (file.protected) row.classList.add("is-protected");
        else if (selected.has(file.name)) row.classList.add("is-selected");

        row.innerHTML = `
          <span class="check" aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M3.5 8.2 6.4 11l6.1-6.4" stroke="#1a140c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span>
            <div class="file-name">${escapeHtml(file.name)}</div>
            <div class="file-sub">${escapeHtml(file.size_label)}</div>
          </span>
          <span class="ext ${file.protected ? "lock" : ""}">
            ${file.protected ? "protegido" : escapeHtml(file.ext)}
          </span>
        `;

        if (!file.protected) {
          row.tabIndex = 0;
          row.addEventListener("click", () => {
            if (selected.has(file.name)) selected.delete(file.name);
            else selected.add(file.name);
            renderFiles();
            setStatus("");
          });
          row.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              row.click();
            }
          });
        }

        fileListEl.appendChild(row);
      });

      updateDeleteButton();
    }

    async function loadFiles() {
      setStatus("Actualizando inventario…");
      try {
        const res = await fetch("/api/files");
        const data = await res.json();
        files = data.files || [];
        folderPath = data.folder || "";
        selected = new Set(
          files.filter((f) => f.selected_default).map((f) => f.name)
        );
        metaEl.innerHTML =
          `<strong>${data.deletable_count ?? data.count}</strong> eliminables · ~<strong>${escapeHtml(data.reclaimable_label)}</strong>` +
          `<span class="path">${escapeHtml(folderPath)}</span>`;
        renderFiles();
        setStatus("");
      } catch (err) {
        setStatus("No se pudo leer el directorio del proyecto.", "err");
      }
    }

    function openModal() {
      const names = [...selected];
      if (!names.length) return;
      modalText.textContent = `Se eliminarán ${names.length} archivo(s) de forma permanente.`;
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
          body: JSON.stringify({ files: names }),
        });
        const data = await res.json();
        closeModal();
        const kind = data.deleted && data.deleted.length ? "ok" : "warn";
        const extra = data.freed_label ? ` · Liberado ${data.freed_label}` : "";
        setStatus((data.message || "Operación completada") + extra, kind);
        await loadFiles();
      } catch (err) {
        setStatus("Error de comunicación con el servidor.", "err");
      } finally {
        btnConfirm.disabled = false;
        btnCancel.disabled = false;
        btnConfirm.textContent = "Confirmar eliminación";
      }
    }

    document.getElementById("btnRefresh").addEventListener("click", loadFiles);
    document.getElementById("btnAll").addEventListener("click", () => {
      selected = new Set(selectableFiles().map((f) => f.name));
      renderFiles();
    });
    document.getElementById("btnNone").addEventListener("click", () => {
      selected.clear();
      renderFiles();
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

    loadFiles();
  </script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/":
            self._send_html(200, PAGE)
            return

        if path == "/api/files":
            self._send_json(200, list_project_files(BASE_DIR))
            return

        self._send_json(404, {"error": "Ruta no encontrada"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/eliminar":
            payload = self._read_json_body()
            names = payload.get("files", [])
            if not isinstance(names, list):
                self._send_json(400, {"error": 'Envía {"files": ["archivo.ext"]}'})
                return
            self._send_json(200, delete_selected_files(names, BASE_DIR))
            return

        self._send_json(404, {"error": "Ruta no encontrada"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    display_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    url = f"http://{display_host}:{PORT}/"
    print("OAL File Control")
    print(f"  Escuchando: {HOST}:{PORT}")
    print(f"  Abrir: {url}")
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
