## Readme

Visual portfolio website for Matt Crump, built from a structured data layer
over the artwork images.

## How it fits together

```
images/, wip/            the art files (source of truth for pixels)
data/artworks/           one JSON record per piece (source of truth for everything else)
pipeline/                Python: catalog new images, measure, validate, similarity, publish
data/public/             what the website may see, filtered by data/visibility.json
web/                     the Astro website, built from data/public and the images
tools/edit/              local browser editor for the records
```

The old Quarto site (`*.qmd`, `things/`, `playground/`, `_quarto.yml`,
`docs/`) is still here and still what GitHub Pages serves, until the new site
is switched on. See "Deploying" below.

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
Pages. It only runs when started by hand. To switch the live site over:

1. Settings > Pages > Source: choose "GitHub Actions".
2. Actions > Deploy web > Run workflow.

Old Quarto URLs such as `things/Scribble/Scribble_Picture_35.html` redirect
to the new pages. The site expects to live at `/things/`; set `SITE_BASE=/`
when building for a domain root.

See `PLAN.md` for the design and history of the data layer.
