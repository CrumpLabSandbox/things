# CLAUDE.md

Guidance for Claude sessions working on Matt Crump's art portfolio ("things"):
a structured data layer over the artwork images, with an Astro website on top.
`README.md` has the commands and `PLAN.md` the full history and decisions.
This file is the handoff: read it first.

## Where things stand (2026-10-05)

- **Repositories.** The new site was built in the sandbox fork
  `CrumpLabSandbox/things`. Its GitHub Actions workflow deploys a static build
  to GitHub Pages at https://crumplabsandbox.github.io/things/ on every push
  to master. The project is moving into `CrumpLab/things`, the original repo,
  to become private and run on Matt's Coolify server. If the repo you are in
  still holds the old Quarto site at its root, the new work has not been
  brought over yet. Bring it over from `CrumpLabSandbox/things`.
- **Coolify crashes.** Coolify crashed on every redeploy. The likely cause is
  that the Astro build resizes every image with sharp on all cores at once.
  Here a full build took about 1 minute of wall time, about 3 minutes of CPU
  time, and wrote 142 MB of resized images. Matt's server cannot absorb that
  spike alongside the sites it runs.
- **Decision: build locally, deploy prebuilt.** Matt now works locally. He
  builds and tests on his own machine and pushes something ready to GitHub.
  Coolify only picks up the finished output and never builds the site. See
  "Deploying" below.

## Working agreements with Matt

- **Commit and push straight to master. No branches, no pull requests,**
  except the deploy branch below. Matt chose this.
- **Visibility decides what is public.** Only fields listed in
  `data/visibility.json` reach `data/public/` and the site. Descriptions and
  impressions are deliberately excluded for now. Shop fields (`print_url`,
  `print_note`) are excluded, and Shopify must not come back: Matt no longer
  sells prints there.
- **Do not publish Matt's email address** or other personal contact details.
  The contact route is the links section on the about page (`about/#contact`).
- **Sold work** is `catalog.availability == "sold"` and drives the commissions
  page.
- **Records are hand-edited data.** Prefer targeted edits through
  `pipeline.common.save_record` over regenerating.
  `pipeline quarto-import works --overwrite` destroys edits; run it only if
  Matt asks.
- **`author` fields belong to Matt** (`verified`, `notes`, `hidden`). Never
  write them unless he asks.
- **Visual similarity with CLIP** (`pipeline embed`) is deferred. Do not
  prioritise it.
- **Check dates with Matt** before changing any.

## How the project fits together

```
images/<series>/, wip/   art files; the pixels' source of truth
playground_images/       Stable Diffusion variations (playground page)
imgs/, blog_images/      site and blog images
data/artworks/<series>/<slug>.json
                         one record per piece; source of truth for everything else
data/vocabulary.json     allowed tags per facet, with glosses
data/series.json, data/projects.json, data/playground.json
data/visibility.json     which fields are public
pipeline/                Python package: python3 -m pipeline build
data/public/             generated; what the website may read
data/thumbs/             generated 256 px thumbnails
web/                     Astro site, built from data/public and the image folders
tools/edit/              local browser editor for records
Quarto-Old/              archived Quarto site; nothing in it is built
```

Each record has blocks with clear owners:

- `catalog`: facts. `pipeline catalog` only creates records for new images
  and refreshes file facts (size, EXIF, IPTC). It never overwrites titles,
  dates or notes.
- `measured`: pixel features and the thumbnail (`pipeline measure`).
- `described`: alt text, description, impression and ten tag facets. Tags
  must be in the vocabulary; `pipeline validate --adopt` adds new ones.
- `relations`: lineage links between records.
- `author`: Matt's own fields.

`catalog.kind` is `work` (images/) or `wip` (wip/). The eight Volcano Ball
Lake process records are `wip/volcano-ball-lake-01-...` to `-08-...`.

## Local setup

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # Pillow, numpy
cd web && npm install && cd ..             # Node 22
```

For browser checks, `cd web && npx playwright install chromium` once. In
Claude cloud sessions Chromium is already at `/opt/pw-browsers/chromium`.

## Everyday commands

```
python3 -m pipeline build        # catalog, measure, validate, similarity, public
python3 -m pipeline validate     # --adopt to accept new tags
node tools/edit/server.js        # editor at http://localhost:8787
cd web && npm run dev            # http://localhost:4321/things/
cd web && npx astro check        # type check; keep at 0 errors
cd web && npx astro build        # static site in web/dist
cd web && npx astro preview      # serve web/dist at http://localhost:4321/things/
```

Add new work by dropping images into `images/<series>/` or `wip/`. Then run
`pipeline build`, describe the pieces in the editor, and run
`pipeline build` again.

## Verify before pushing

1. `python3 -m pipeline build` exits 0 and validate reports no problems.
2. `cd web && npx astro check` shows 0 errors and `npx astro build`
   completes.
3. Load the changed pages from `npx astro preview` at 1440 px and 390 px wide.
   Check for failed requests, script errors, broken images and sideways
   scrolling.

## Deploying (the plan; not built yet)

Goal: Coolify never runs `astro build`. Everything heavy happens on Matt's
machine. The recommended shape:

1. **Build and test locally.** Run `pipeline build`, `astro check`,
   `astro build` and the checks above.
2. **Publish the output to a `deploy` branch.** It holds only `web/dist/` plus
   two small files: a `Dockerfile` (`FROM nginx:1.27-alpine`, then copy the
   site to `/usr/share/nginx/html/things` and the nginx config into
   `/etc/nginx/conf.d/default.conf`) and `nginx.conf`. The config:

   ```nginx
   server {
     listen 80;
     root /usr/share/nginx/html;
     location = / { return 302 /things/; }
     location /things/ { try_files $uri $uri/ =404; }
     location /things/_astro/ { expires 1y; add_header Cache-Control "public, immutable"; }
     error_page 404 /things/404.html;
   }
   ```

   Make `deploy` an orphan branch that is force-pushed as a single commit on
   each release. Otherwise every build (about 250 MB) piles up in the repo
   history. A small script such as `scripts/publish.sh` should do this using a
   git worktree.
3. **Point Coolify at the `deploy` branch** with the Dockerfile build pack.
   Its "build" is a file copy, with no image processing. Turn off any Coolify
   resource that builds from `master`.

The alternative is to build a Docker image locally and push it to
`ghcr.io/crumplab/things`, with Coolify pulling the image. That keeps git
small, but Coolify then needs registry access, since the package is private
with a private repo. A third option is a GitHub Actions workflow that builds
the image and calls Coolify's deploy webhook (`COOLIFY_WEBHOOK` and
`COOLIFY_TOKEN` secrets). Either way the server never builds. Matt chose
local builds, so prefer option 1 unless he says otherwise.

To soften the spike if Coolify must build anyway: cap the build's CPU and
memory in Coolify, or set `SHARP_CONCURRENCY=1`. Building gets slower.

Retire `.github/workflows/deploy-web.yml` (GitHub Pages) in the private repo.
Pages on private repos needs a paid plan, and the Coolify path replaces it.

## Open items, waiting on Matt

1. **Review edits.** Matt said he reviewed records in the editor, but as of
   2026-10-05 no record has `author.verified` set and none reached GitHub. If
   they turn up locally, commit them, then run `python3 -m pipeline build`.
   His edits win any conflict in `data/artworks/`. Files in `data/public/` are
   generated and can always be rebuilt.
2. **Year made.** Many records carry file dates rather than the year made
   (towns signed 2011 show as 2019; Colorlands signed 2021 show as 2022). The
   plan is to add `catalog.year_made` once Matt confirms the years. Timeline
   and character pages would then use it.
3. **Public URL.** crumplab.com/things (current base `/things/`) or a domain
   root (`SITE_BASE=/`). The old Quarto URL redirects only work if the
   `/things/...` paths are kept.
4. **Natural language search** (version 2). It needs a server route, for
   example `@astrojs/node` in the same image, that calls a language model
   over records' descriptions and tags. The API key goes in Coolify's
   environment, never in the repo. It needs cost and rate limits. The static
   first step, "Like this, but..." on artwork pages, is already live.
5. **Sales.** Checkout, payments and orders need the server. The payment
   provider is not chosen yet. Sold status still lands in
   `catalog.availability`.
6. **More process stories.** Matt will add `wip/` images per piece with
   captions. Each becomes a record per step plus an entry in
   `data/projects.json`, like Volcano Ball Lake.
7. **Small fixes.**
   - The process note on Cliffs at another volcano ball lake still says it is
     "shown on the work in progress page"; it should point to the process
     page.
   - The untitled spray-painted name canvas in commissions is not marked
     sold.
   - Decide whether to show descriptions publicly: add
     `described.description` to `data/visibility.json`.

## Lessons from earlier sessions

- **Base path.** The site is built for `/things/`. Use the helpers in
  `web/src/lib/urls.ts` (`href`, `asset`, `workUrl`...) for every link and
  image URL. `SITE_BASE=/` builds for a domain root.
- **Repo images.** Repo image folders are served by
  `web/src/integrations/repo-assets.mjs`: a Vite `configureServer` middleware
  in dev, and a copy into `dist/` at build. Middleware added through
  `astro:server:setup` runs after Astro's handlers and never sees these
  requests. The same integration writes redirect pages for every old Quarto
  URL.
- **Resized images.** `web/src/lib/images.ts` globs the image folders for
  `astro:assets` `<Image>`. Adding an image folder means updating it and the
  `dirs` list in `astro.config.mjs`. This resizing is the CPU-heavy part of
  the build.
- **Gallery.** The gallery is a justified flex layout, driven by a `--a`
  aspect ratio property on each tile. CSS columns read top to bottom and
  break newest-first order; don't go back to them.
- **"Like this, but..."** comes from `pipeline/similarity.py`
  (`like_this_but`): it writes `directions` into `similarity.json`, and
  `web/src/components/LikeThisBut.astro` renders it.
- **Color page.** Matches use CIE Lab distance, with lightness at half weight
  and a radius of 40. Tighter settings found almost nothing, because the
  palettes are cluster averages and come out duller than pure swatches.
- **Stopping servers in cloud shells.** `pkill -f "astro ..."` also matches
  the shell running the command and kills it (exit 144). Stop servers by PID
  in a separate call: `kill $(pgrep -f "astro.mjs preview")`.
