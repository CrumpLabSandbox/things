#!/usr/bin/env node
/* Local editing tool for the artwork records.

   Run from the repo root:   node tools/edit/server.js
   Then open               http://localhost:8787

   Serves tools/edit/index.html, the images and thumbnails, and a tiny JSON
   API that reads and writes data/artworks/<id>.json. Nothing else. No
   dependencies beyond Node itself. After editing, rebuild the public data:
       python3 scripts/validate.py && python3 scripts/build_public.py
*/
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const DATA = path.join(ROOT, "data", "artworks");
const PORT = Number(process.env.PORT || 8787);
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png" };

function listRecords() {
  const out = [];
  for (const series of fs.readdirSync(DATA)) {
    const dir = path.join(DATA, series);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith(".json")) continue;
      const rec = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
      out.push({ id: rec.id, title: rec.catalog.title, series: rec.catalog.series, year: rec.catalog.year, date: rec.catalog.date,
        thumbnail: rec.measured && rec.measured.thumbnail, verified: !!(rec.author && rec.author.verified), described: !!(rec.described && rec.described.description) });
    }
  }
  out.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  return out;
}

function recordPath(id) {
  if (!/^[a-z0-9-]+\/[a-z0-9-]+$/.test(id)) throw new Error("bad id");
  return path.join(DATA, id + ".json");
}

function send(res, code, body, type) {
  res.writeHead(code, { "Content-Type": type || "application/json", "Cache-Control": "no-store" });
  res.end(body);
}

function serveStatic(res, rel) {
  const file = path.normalize(path.join(ROOT, rel));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return send(res, 404, "not found", "text/plain");
  const ext = path.extname(file).toLowerCase();
  res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream", "Cache-Control": "no-store" });
  fs.createReadStream(file).pipe(res);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  try {
    if (url.pathname === "/" || url.pathname === "/index.html") return serveStatic(res, "tools/edit/index.html");
    if (url.pathname === "/api/list") return send(res, 200, JSON.stringify(listRecords()));
    if (url.pathname === "/api/vocabulary") return serveStatic(res, "data/vocabulary.json");
    if (url.pathname === "/api/schema") return serveStatic(res, "data/schema.json");
    if (url.pathname === "/api/record" && req.method === "GET") {
      const p = recordPath(url.searchParams.get("id") || "");
      if (!fs.existsSync(p)) return send(res, 404, JSON.stringify({ error: "no such record" }));
      return send(res, 200, fs.readFileSync(p));
    }
    if (url.pathname === "/api/record" && req.method === "POST") {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        try {
          const rec = JSON.parse(body);
          const p = recordPath(rec.id);
          if (!fs.existsSync(p)) return send(res, 404, JSON.stringify({ error: "no such record" }));
          fs.writeFileSync(p, JSON.stringify(rec, null, 2) + "\n");
          send(res, 200, JSON.stringify({ ok: true }));
        } catch (e) { send(res, 400, JSON.stringify({ error: String(e.message) })); }
      });
      return;
    }
    if (url.pathname.startsWith("/images/") || url.pathname.startsWith("/data/thumbs/")) return serveStatic(res, decodeURIComponent(url.pathname));
    send(res, 404, "not found", "text/plain");
  } catch (e) { send(res, 500, JSON.stringify({ error: String(e.message) })); }
});

server.listen(PORT, () => console.log("edit tool at http://localhost:" + PORT + "  (records in " + DATA + ")"));
