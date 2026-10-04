// Serve folders from the repo root as static files, without copying them into
// web/public. In dev a middleware streams them; at build they are copied into
// the output. Also writes redirect pages for the old Quarto URLs after build.
import fs from "node:fs";
import path from "node:path";

const MIME = {
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
  ".gif": "image/gif", ".svg": "image/svg+xml", ".json": "application/json", ".pdf": "application/pdf",
};

function copyDir(src, dest, filter) {
  let n = 0;
  if (!fs.existsSync(src)) return 0;
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) n += copyDir(s, d, filter);
    else if (!filter || filter(s)) { fs.copyFileSync(s, d); n++; }
  }
  return n;
}

function redirectPage(to) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>` +
    `<meta http-equiv="refresh" content="0; url=${to}"><link rel="canonical" href="${to}">` +
    `<meta name="robots" content="noindex"></head><body><p>This page moved to <a href="${to}">${to}</a>.</p></body></html>`;
}

// Old Quarto page path -> new page path (both relative to the site base).
function legacyRedirects(repo) {
  const read = (f) => JSON.parse(fs.readFileSync(path.join(repo, "data", "public", f), "utf8"));
  const map = {
    "explore.html": "explore/",
    "playground.html": "playground/",
    "prints.html": "commissions/",
    "prints/index.html": "commissions/",
    "about.html": "about/",
    "blog.html": "blog/",
    "wip.html": "process/",
  };
  for (const r of read("artworks.json")) {
    const old = r.catalog?.page?.html;
    if (old && old.startsWith("things/")) map[old] = `work/${r.id}/`;
  }
  for (const g of read("playground.json").groups) {
    for (const item of g.items) map[`playground/${g.id}/${item.title.replace(/ /g, "_")}.html`] = `playground/#${encodeURIComponent(item.id)}`;
  }
  return map;
}

export default function repoAssets({ repo, dirs }) {
  let base = "/";
  // Only media files are served or copied from these folders.
  const isAsset = (f) => Boolean(MIME[path.extname(f).toLowerCase()]);
  return {
    name: "repo-assets",
    hooks: {
      "astro:config:setup": ({ config, updateConfig }) => {
        base = config.base.endsWith("/") ? config.base : config.base + "/";
        // A Vite plugin's configureServer middleware runs before Astro's own
        // handlers, so repo files are served in dev under the site base.
        updateConfig({
          vite: {
            plugins: [{
              name: "repo-assets-dev",
              configureServer(server) {
                server.middlewares.use((req, res, next) => {
                  const url = decodeURIComponent((req.url || "").split("?")[0]);
                  const rel = url.startsWith(base) ? url.slice(base.length) : url.replace(/^\/+/, "");
                  if (!dirs.some((d) => rel.startsWith(d + "/"))) return next();
                  const file = path.join(repo, rel);
                  if (!file.startsWith(repo) || !fs.existsSync(file) || fs.statSync(file).isDirectory() || !isAsset(file)) return next();
                  res.setHeader("Content-Type", MIME[path.extname(file).toLowerCase()]);
                  fs.createReadStream(file).pipe(res);
                });
              },
            }],
          },
        });
      },
      "astro:config:done": ({ config }) => {
        base = config.base.endsWith("/") ? config.base : config.base + "/";
      },
      "astro:build:done": ({ dir, logger }) => {
        const out = new URL(dir).pathname;
        let total = 0;
        for (const d of dirs) total += copyDir(path.join(repo, d), path.join(out, d), isAsset);
        logger.info(`copied ${total} repo asset files`);

        // Redirects from the old Quarto URLs to the new pages.
        let n = 0;
        for (const [from, to] of Object.entries(legacyRedirects(repo))) {
          const target = path.join(out, from);
          if (fs.existsSync(target)) continue; // never clobber a real page
          fs.mkdirSync(path.dirname(target), { recursive: true });
          fs.writeFileSync(target, redirectPage(base + to));
          n++;
        }
        logger.info(`wrote ${n} redirect pages for old URLs`);
      },
    },
  };
}
