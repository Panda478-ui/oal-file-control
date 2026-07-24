/**
 * File Clear — agente Netlify (borrado REAL en el dominio)
 *
 * INSTALACIÓN (una sola vez en TU sitio Netlify):
 * 1) Crea la carpeta: netlify/functions/
 * 2) Copia este archivo como: netlify/functions/oal-clean.js
 * 3) En Netlify → Site configuration → Environment variables:
 *      NETLIFY_AUTH_TOKEN = (Personal Access Token de tu cuenta Netlify)
 *    Ese token se queda EN Netlify, no en File Clear.
 * 4) Vuelve a publicar el sitio (Deploy).
 * 5) En https://oal-file-control.onrender.com pega solo la URL del sitio y Conectar.
 *
 * Clave del agente: oal-lab-clean (no hace falta pegar tokens en el panel).
 */

const API = "https://api.netlify.com/api/v1";
const AGENT_KEY = "oal-lab-clean";

function json(status, body) {
  return {
    statusCode: status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type, X-OAL-Token",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Cache-Control": "no-store",
    },
    body: JSON.stringify(body),
  };
}

function humanSize(n) {
  const units = ["B", "KB", "MB", "GB"];
  let size = Number(n) || 0;
  for (const u of units) {
    if (size < 1024 || u === units[units.length - 1]) {
      return u === "B" ? `${Math.round(size)} ${u}` : `${size.toFixed(1)} ${u}`;
    }
    size /= 1024;
  }
  return `${n} B`;
}

function extOf(name) {
  if (!name.includes(".") || name.startsWith(".")) return (name.replace(/^\./, "") || "FILE").toUpperCase();
  return name.split(".").pop().toUpperCase();
}

function normPath(value) {
  const parts = String(value || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean);
  return "/" + parts.join("/");
}

function authorized(event, body) {
  const headers = event.headers || {};
  const q = event.queryStringParameters || {};
  const token = String(
    q.token ||
      headers["x-oal-token"] ||
      headers["X-OAL-Token"] ||
      (body && body.token) ||
      ""
  ).trim();
  return token === AGENT_KEY;
}

async function api(method, path, token, payload, rawBody, contentType) {
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    "User-Agent": "File-Clear-Netlify-Agent/1.0",
  };
  let body;
  if (payload !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(payload);
  } else if (rawBody !== undefined) {
    headers["Content-Type"] = contentType || "application/octet-stream";
    body = rawBody;
  }
  const res = await fetch(API + path, { method, headers, body });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const msg = data.message || data.error || text || res.statusText;
    throw new Error(`Netlify HTTP ${res.status}: ${msg}`);
  }
  return data;
}

async function waitDeploy(siteId, deployId, token) {
  for (let i = 0; i < 80; i++) {
    const d = await api("GET", `/sites/${siteId}/deploys/${deployId}`, token);
    if (d.state === "ready" || d.state === "current") return d;
    if (d.state === "error" || d.state === "rejected") {
      throw new Error(`Deploy falló: ${d.state}`);
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error("Timeout esperando deploy Netlify");
}

function listView(files, rel) {
  const prefix = rel ? `/${rel}` : "";
  const folders = new Set();
  const fileRows = [];

  for (const item of files) {
    const full = normPath(item.path || item.id || "");
    if (full === "/") continue;

    let rest;
    if (prefix) {
      if (full === prefix) continue;
      if (!full.startsWith(prefix + "/")) continue;
      rest = full.slice(prefix.length + 1);
    } else {
      rest = full.replace(/^\//, "");
    }
    if (!rest) continue;
    if (rest.includes("/")) {
      folders.add(rest.split("/")[0]);
      continue;
    }
    const size = Number(item.size) || 0;
    fileRows.push({
      name: rest,
      type: "file",
      path: rel ? `${rel}/${rest}` : rest,
      size,
      size_label: humanSize(size),
      ext: extOf(rest),
      protected: false,
      selected_default: false,
    });
  }

  const folderRows = [...folders].sort().map((name) => ({
    name,
    type: "folder",
    path: rel ? `${rel}/${name}` : name,
    protected: false,
  }));

  fileRows.sort((a, b) => a.name.localeCompare(b.name));
  const crumbs = [{ name: "Inicio", path: "" }];
  if (rel) {
    const built = [];
    for (const part of rel.split("/")) {
      built.push(part);
      crumbs.push({ name: part, path: built.join("/") });
    }
  }
  const total = fileRows.reduce((s, f) => s + (f.size || 0), 0);
  return {
    ok: true,
    provider: "netlify-agent",
    agent: "oal-clean",
    path: rel || "",
    parent: rel ? rel.split("/").slice(0, -1).join("/") : null,
    breadcrumb: crumbs,
    folders: folderRows,
    files: fileRows,
    folder_count: folderRows.length,
    file_count: fileRows.length,
    reclaimable_label: humanSize(total),
  };
}

async function deleteLive(siteId, publicUrl, token, names, rel) {
  const current = await api("GET", `/sites/${siteId}/files`, token);
  const remove = new Set();
  for (const name of names || []) {
    let item = String(name || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    if (!item) continue;
    let full =
      rel && !item.startsWith(rel + "/") && item !== rel
        ? `/${rel}/${item}`
        : `/${item}`;
    remove.add(normPath(full));
  }

  const keep = {};
  const shaToPath = {};
  const deleted = [];
  for (const item of current) {
    const full = normPath(item.path || item.id || "");
    const sha = String(item.sha || "").trim();
    if (full === "/" || !sha) continue;
    const drop = [...remove].some(
      (t) => full === t || full.startsWith(t.replace(/\/$/, "") + "/")
    );
    if (drop) {
      deleted.push(full);
      continue;
    }
    keep[full] = sha;
    shaToPath[sha] = full;
  }

  if (!deleted.length) {
    return {
      ok: false,
      deleted: [],
      errors: (names || []).map((n) => ({ file: n, error: "No encontrado" })),
      message: "Nada para borrar en el deploy actual.",
    };
  }
  if (!Object.keys(keep).length) {
    throw new Error("No se puede dejar el sitio vacío. Deja al menos un archivo.");
  }

  const deploy = await api("POST", `/sites/${siteId}/deploys`, token, {
    files: keep,
    draft: false,
  });
  const deployId = deploy.id;
  for (const sha of deploy.required || []) {
    const filePath = shaToPath[sha];
    if (!filePath) throw new Error(`Falta archivo requerido ${sha.slice(0, 8)}`);
    const pub = publicUrl.replace(/\/$/, "") + filePath;
    const res = await fetch(pub);
    if (!res.ok) throw new Error(`No pude re-subir ${filePath}`);
    const buf = Buffer.from(await res.arrayBuffer());
    const uploadPath = encodeURI(filePath.replace(/^\//, ""));
    await api(
      "PUT",
      `/deploys/${deployId}/files/${uploadPath}`,
      token,
      undefined,
      buf,
      "application/octet-stream"
    );
  }

  const ready = await waitDeploy(siteId, deployId, token);
  return {
    ok: true,
    provider: "netlify-agent",
    deleted,
    errors: [],
    remaining: Object.keys(keep).length,
    deploy_id: deployId,
    deploy_state: ready.state,
    message: `Borrado real en Netlify: ${deleted.length} elemento(s).`,
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return json(204, {});
  }

  let body = {};
  if (event.body) {
    try {
      body = JSON.parse(event.isBase64Encoded
        ? Buffer.from(event.body, "base64").toString("utf8")
        : event.body);
    } catch {
      body = {};
    }
  }

  if (!authorized(event, body)) {
    return json(401, {
      error: "No autorizado. Usa token=oal-lab-clean",
    });
  }

  const authToken = process.env.NETLIFY_AUTH_TOKEN || process.env.OAL_NETLIFY_TOKEN;
  const siteId = process.env.SITE_ID || process.env.OAL_SITE_ID;
  const publicUrl =
    process.env.URL || process.env.DEPLOY_PRIME_URL || process.env.OAL_SITE_URL || "";

  if (!authToken) {
    return json(500, {
      error:
        "Falta NETLIFY_AUTH_TOKEN en las variables de entorno del sitio Netlify (Site configuration → Environment variables).",
    });
  }
  if (!siteId) {
    return json(500, {
      error: "No se encontró SITE_ID. Redeploya la function en Netlify.",
    });
  }

  const q = event.queryStringParameters || {};
  const action = q.action || body.action || "files";

  try {
    if (action === "ping") {
      return json(200, {
        ok: true,
        agent: "oal-clean",
        provider: "netlify-agent",
        version: "1.0",
        site_id: siteId,
        auth: AGENT_KEY,
      });
    }

    if (action === "files" && event.httpMethod === "GET") {
      const rel = String(q.path || "").replace(/^\/+|\/+$/g, "");
      const files = await api("GET", `/sites/${siteId}/files`, authToken);
      const view = listView(files, rel);
      view.root = publicUrl || siteId;
      view.folder = publicUrl || "/";
      view.label = `Netlify en vivo · ${siteId}`;
      view.remote_url = publicUrl;
      return json(200, view);
    }

    if (action === "eliminar" && event.httpMethod === "POST") {
      const names = body.files || [];
      const rel = String(body.path || "").replace(/^\/+|\/+$/g, "");
      if (!Array.isArray(names)) {
        return json(400, { error: 'Envía {"files":["archivo"],"path":""}' });
      }
      const result = await deleteLive(siteId, publicUrl, authToken, names, rel);
      return json(200, result);
    }

    return json(404, { error: "Acción no encontrada. Usa action=files|eliminar|ping" });
  } catch (err) {
    return json(400, { error: err.message || String(err) });
  }
};
