# CLAUDE.md

Guidance for Claude sessions working on this repository: Matt Crump's art
portfolio ("things"), built as a structured data layer over the artwork images
with an Astro website on top. Read `README.md` for commands and `PLAN.md` for
the full history and decisions.

## Status and what comes next

As of 2026-10-04 this repo lives at `CrumpLabSandbox/things` (a sandbox fork)
and deploys a static Astro build to GitHub Pages at
https://crumplabsandbox.github.io/things/ on every push to master.

**Planned, not started:** move the project into a private repository in the
main `CrumpLab` GitHub organisation and run it on Matt's Coolify server. That
work happens from the new repository, not here. See "Move to CrumpLab and
Coolify" in `PLAN.md`. If you are a session in the sandbox repo, do not start
the move.

## How the project fits together

```
images/<series>/, wip/   art files; the pixels' source of truth
data/artworks/<series>/<slug>.json
                         one record per piece; the source of truth for everything else
pipeline/                Python package: python3 -m pipeline build
data/public/             what the website may see (filtered by data/visibility.json)
web/                     Astro site, built from data/public and the image folders
tools/edit/              local browser editor for records (node tools/edit/server.js)
Quarto-Old/              archived Quarto site; nothing in it is built
```

A record has blocks with clear owners:

- `catalog`: facts. The pipeline's `catalog` step only creates records for new
  images and refreshes file facts (size, EXIF, IPTC). It never overwrites
  titles, dates, notes or anything Matt edited.
- `measured`: pixel features and the thumbnail, written by `pipeline measure`.
- `described`: alt text, description, impression and ten tag facets, from the
  describing pass and the editor. Tags must be in `data/vocabulary.json`.
  `pipeline validate --adopt` adds new tags.
- `relations`: lineage links between records.
- `author`: Matt's own fields (`verified`, `notes`, `hidden`). Never write here
  unless Matt asks.

`catalog.kind` is `work` (images/) or `wip` (wip/). Process sequences are in
`data/projects.json`. The Stable Diffusion playground is
`data/playground.json`, which holds no artwork records.

## Working agreements with Matt

- **Commit and push straight to master. No branches, no pull requests.** Matt
  chose this. On GitHub, every push deploys the site.
- **Visibility decides what is public.** Only fields listed in
  `data/visibility.json` reach `data/public/` and the site. Descriptions and
  impressions are deliberately excluded for now. Shop fields (`print_url`,
  `print_note`) are excluded because Matt no longer sells prints on Shopify.
  Do not reintroduce Shopify anywhere.
- **Do not publish Matt's email address** or other personal contact details.
  The site's contact route is the links section on the about page.
- **Sold work** is `catalog.availability == "sold"` and drives the commissions
  page.
- Records are hand-edited data. Prefer targeted edits through
  `pipeline.common.save_record` over regenerating. `pipeline quarto-import
  works --overwrite` destroys edits and should only run if Matt asks.
- Visual similarity with CLIP (`pipeline embed`) is deferred. Do not
  prioritise it.

## Commands

```
python3 -m pipeline build        # catalog, measure, validate, similarity, public
python3 -m pipeline validate     # --adopt to accept new tags
node tools/edit/server.js        # editor at http://localhost:8787
cd web && npm install            # once
cd web && npm run dev            # http://localhost:4321/things/
cd web && npx astro check        # type check; keep at 0 errors
cd web && npx astro build        # static site in web/dist
```

Python needs Pillow and numpy (`requirements.txt`). Node 22 is used in CI.

## Verify before pushing

1. `python3 -m pipeline build` exits 0 and validate reports no problems.
2. `cd web && npx astro check` shows 0 errors and `npx astro build` completes.
3. Load the changed pages in a browser (Playwright with Chromium at
   `/opt/pw-browsers/chromium` in cloud sessions) at 1440 px and 390 px wide.
   Check for failed requests, script errors, broken images and sideways
   scrolling.

## Lessons from earlier sessions

- **Base path.** The site is built for `/things/`. Use the helpers in
  `web/src/lib/urls.ts` (`href`, `asset`, `workUrl`...) for every link and
  image URL. `SITE_BASE=/` builds for a domain root.
- **Repo images.** Repo image folders are served by
  `web/src/integrations/repo-assets.mjs`: a Vite `configureServer` middleware
  in dev, and a copy into `dist/` at build. Middleware added through
  `astro:server:setup` runs after Astro's own handlers and never sees these
  requests. The same integration writes redirect pages for every old Quarto
  URL.
- **Resized images.** `web/src/lib/images.ts` globs the image folders so pages
  can use `astro:assets` `<Image>`. A new image folder must be added there and
  in `astro.config.mjs` `dirs`.
- **Gallery.** The gallery is a justified flex layout, driven by a `--a`
  aspect ratio custom property on each tile. Do not switch back to CSS
  columns: they read top to bottom and break newest-first ordering.
- **Stopping servers.** In cloud shells, `pkill -f "astro ..."` also matches
  the shell running the command and kills it (exit 144), so later commands in
  the same call never run. Stop servers by PID in a separate call
  (`kill $(pgrep -f "astro.mjs preview")`).
- **Dates.** Many records carry file dates, not the year a piece was made
  (towns signed 2011 show as 2019). A `year_made` field is planned. Check with
  Matt before changing dates.
- **Review edits.** Matt said he reviewed records in the editor, but as of
  2026-10-04 no record has `author.verified` set. If his edits arrive, run
  `python3 -m pipeline build` and let the edits win any conflict in
  `data/artworks/`. Files in `data/public/` are generated and can always be
  rebuilt.
