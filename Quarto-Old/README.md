# Quarto-Old

The original Quarto version of the site, archived on 2026-10-04 when the site
moved to the Astro build in `web/`. Nothing here is built or deployed.

What is in here:

- `_quarto.yml`, `*.qmd`, `styles.css`: the site config and top level pages
- `things/`: one generated page per artwork (made by `make_qmds.R`)
- `playground/`: one generated page per Stable Diffusion variation (made by `playground_make_qmds.R`)
- `blog/`: the two blog posts as qmd, with their covers
- `explore/`: the first explore page, written for Quarto
- `prints/`: images for the old prints page
- `docs/`: the last rendered Quarto site, which GitHub Pages used to serve
- `Things.Rproj`: the RStudio project file

The pages still point at `images/`, `imgs/`, `playground_images/` and `wip/`
as if they sat beside them at the repo root, so rendering from this folder as
is will show broken images. To render it, copy the folder back to the root of
a scratch checkout and run `quarto render` there.

Content that still matters was carried into the new structure: titles, dates,
medium and process notes are in `data/artworks/`, playground prompts are in
`data/playground.json`, and the blog posts are in `web/src/content/blog/`.
`python3 -m pipeline quarto-import` can still read these pages.
