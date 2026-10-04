// @ts-check
import { defineConfig } from "astro/config";
import { fileURLToPath } from "node:url";
import repoAssets from "./src/integrations/repo-assets.mjs";

const REPO = fileURLToPath(new URL("..", import.meta.url));

// The site lives at https://crumplab.com/things. Override with SITE_BASE=/
// to serve from a domain root.
const base = process.env.SITE_BASE ?? "/things";

export default defineConfig({
  site: "https://crumplab.com",
  base,
  trailingSlash: "ignore",
  build: { format: "directory" },
  integrations: [
    repoAssets({
      repo: REPO,
      // Repo folders served as-is at the same path under the site base, so a
      // record's image path "images/Colorlands/Modular.jpg" is also its URL.
      dirs: ["images", "wip", "playground_images", "imgs", "prints", "data/thumbs", "data/public", "blog"],
    }),
  ],
  vite: {
    // Pages import images from the repo root (outside web/).
    server: { fs: { allow: [REPO] } },
  },
});
