## Readme

Visual portfolio website for Matt Crump, built from a structured data layer
over the artwork images.

## How it fits together

```
images/, wip/            the art files (source of truth for pixels)
playground_images/       Stable Diffusion variations shown on the playground page
imgs/, blog_images/      site and blog images
data/artworks/           one JSON record per piece (source of truth for everything else)
pipeline/                Python: catalog new images, measure, validate, similarity, publish
data/public/             what the website may see, filtered by data/visibility.json
web/                     the Astro website, built from data/public and the images
tools/edit/              local browser editor for the records
Quarto-Old/              the archived Quarto site
```

The old Quarto site is archived in `Quarto-Old/`. Nothing in it is built or
deployed.

## Everyday tasks

Add new work: drop images into `images/<series>/` (or `wip/` for process
shots), then

```
python3 -m pipeline build          # new records, measurements, similarity, public data
node tools/edit/server.js          # describe and tag the new pieces at http://localhost:8787
python3 -m pipeline build          # again after editing
```

Work on the website:

```
cd web
npm install                        # once
npm run dev                        # live preview at http://localhost:4321/things/
npm run build                      # static site in web/dist
```

Control what the site shows: edit `data/visibility.json`, then
`python3 -m pipeline public`. Hide a piece entirely by setting
`author.hidden` to true in the editor.

## Requirements

- Python 3.10+ with Pillow and numpy: `pip install -r requirements.txt`
- Node 20+ for the website and the editor
- Optional, for CLIP visual similarity: `pip install torch open_clip_torch`, then
  `python3 -m pipeline embed` and `python3 -m pipeline build`

## Deploying

`.github/workflows/deploy-web.yml` builds `web/` and publishes it to GitHub
Pages on every push to master (Settings > Pages > Source is "GitHub Actions").
It can also be run by hand from the Actions tab. The site is at
https://crumplabsandbox.github.io/things/.

Old Quarto URLs such as `things/Scribble/Scribble_Picture_35.html` redirect
to the new pages. The site expects to live at `/things/`; set `SITE_BASE=/`
when building for a domain root.

A move to a private repository in the CrumpLab organisation, served from
Coolify, is under way. The site will be built locally and only the finished
output deployed, because building on the server crashed it. See `CLAUDE.md`.

See `PLAN.md` for the design and history of the data layer, and `CLAUDE.md`
for guidance aimed at Claude sessions working on this repo.
