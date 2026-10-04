# Plan: a descriptive data layer for the art

This is a working plan for turning the image collection on this site into a
structured, searchable database of artworks. Nothing in the existing Quarto
site has to change for the first steps. The JSON layer sits beside it.

## What is here now

- `images/<series>/` holds 169 finished pieces in 13 series (Scribble 48,
  airbrush 20, Superland 19, crowds 13, towns 13, characters 12, cactuses 11,
  Colorlands 8, Desertland 7, commissions 6, Magicbear 5, Generative 4,
  screenprints 3). Mix of jpg and jpeg, roughly 1000 to 2500 px, 77 MB total.
- `playground_images/` holds 56 Stable Diffusion variations of two pieces.
  `wip/` holds 9 process snapshots.
- `make_qmds.R` reads EXIF (title, description, create date) and writes one
  `things/<series>/<Title>.qmd` per image. The series folder becomes the
  Quarto category. The EXIF description is really the medium ("oil on wood",
  "airbrush on paper", "Digital Work"). 19 pages carry hand written process
  notes. 14 have no description at all.
- `index.qmd` is a Quarto grid listing over `things/`, filterable only by
  series. Quarto already emits `docs/listings.json` and `docs/search.json`,
  so the site has a tiny machine readable layer already, but it only knows
  titles and series.
- Build tooling is R and Quarto. Neither is installed in this cloud session,
  but Python 3.11 with Pillow and numpy is, so image analysis can run here.

## The idea in one picture

```
images/*.jpg                         (pixels: the art itself, unchanged)
   │
   ├─ 1. catalog     ─► data/artworks/<id>.json   facts: file, series, medium, date, size
   ├─ 2. measured    ─►   (same record)           palette, hue/saturation, line density, hash
   ├─ 3. described   ─►   (same record)           tags + prose written by looking at each piece
   └─ 4. related     ─► data/similarity.json      nearest neighbours by look and by description
                                 │
                                 ▼
                     5. interfaces: Quarto explore page (static JS), tag filters,
                        "more like this", a 2D map, later a dynamic app if wanted
```

Each artwork gets one JSON file. One file per piece keeps git diffs readable
and lets you hand edit a single record. A build step concatenates them into
`data/artworks.json` for the website.

## Layer 1. Catalog (deterministic)

A Python script `scripts/build_catalog.py` walks `images/`, reads EXIF with
Pillow, reads the matching qmd front matter and any process notes, and
writes the factual core of each record.

- Stable `id`: a slug from the series and title, for example
  `scribble/scribble-picture-01` or `colorlands/meeting-of-the-mountains`.
  Image files are not renamed. The record points at them.
- Fields: title, series, medium (from EXIF description, normalised so
  "DIgital Work" and "Digital Work" are one value), surface, year, exact date,
  pixel size, aspect, orientation, file path, page URL, process notes text,
  any location text that is already in the description ("Canal St").

This replaces nothing. `make_qmds.R` keeps working. Later the Python script
could also generate the qmd pages, so there is one pipeline, but that is
optional.

## Layer 2. Measured visual features (deterministic, runs here)

Cheap features computed from pixels with Pillow and numpy, no machine
learning needed:

- a 6 colour palette (k-means in a perceptual colour space), plus dominant
  hue family and whether the piece is monochrome;
- mean saturation and value, contrast, warm/cool balance;
- a line density proxy (edge pixel ratio) that separates the thick black
  outline work from the airbrush pieces;
- busyness (local variance), which separates crowded all over compositions
  from pieces with a clear figure and ground;
- a perceptual hash for duplicate and near duplicate detection, which also
  links the playground variants to their source pieces;
- a 256 px thumbnail per piece under `data/thumbs/` so the explore page does
  not load 77 MB.

Optional later: CLIP or SigLIP embeddings for true visual similarity. That
needs PyTorch, which is heavy for this session. The plan writes the script
so you can run it locally in a few minutes, and the explore page treats the
embedding columns as optional.

## Layer 3. Qualitative description (the main work)

I look at every image and write a structured description. This is the layer
you asked for. Proposed facets, each a short list of tags from a controlled
vocabulary plus free text where it helps:

| facet | what it captures | example tags |
|---|---|---|
| `subjects` | what is depicted | creature, bear, cactus, mountain, skyscraper, crowd, faceless figure, vehicle |
| `recurring_motifs` | your own repeated forms | volcano ball lake, magic bear, scribble people, ringed planet, speech bubble letters |
| `setting` | where it is | invented landscape, NYC street, interior, no place |
| `composition` | how it is built | all over, horizon, central figure, stacked, grid, isolated object |
| `line` | mark quality | thick black outline, white highlight line, airbrush gradient, no outline, scribble |
| `color` | palette character in words | candy, pastel, earth, grayscale, bleached, high contrast |
| `style_references` | lineages you are drawing on | graffiti, cartoon, cubism, outsider art, print making, photo collage |
| `text_in_image` | lettering present and what it says | yes, "curious bear cant stop", signature only |
| `mood` | emotional read | playful, crowded, calm, uneasy, celebratory |
| `narrative` | one or two sentences of what seems to be happening | "A blue bear floats above a jumble of lettering..." |
| `description` | one paragraph, neutral and concrete | for search and for people who cannot see the image |
| `alt_text` | one sentence | for accessibility on the site |
| `relations` | links to other pieces | source photo of, variation of, same characters as |
| `confidence` | how sure the tagging is | high, medium, low |
| `author` | your corrections and notes | `verified: false` until you look at it |

Mechanics:

- `data/vocabulary.json` defines the allowed tags per facet with a one line
  gloss. I seed it from a first pass over 20 or so images, then apply it to
  the rest and extend it only when something new appears. Free text fields
  stay free.
- Each record keeps `described_by` and `described_on` so later passes can be
  told apart from the first.
- A validator script checks every record against the schema and vocabulary
  so a typo in a tag cannot silently split a category.
- Order of work: catalog first, then description in series batches, so the
  series level patterns (what makes a Superland a Superland) are written down
  once in `data/series.json` and each piece only records how it differs.

## Layer 4. Relationships

Computed from layers 2 and 3 and saved as `data/similarity.json`:

- tag similarity: Jaccard over tag sets, weighted by facet;
- text similarity: TF-IDF cosine over description and narrative;
- visual similarity: distance over palette and the measured features, or
  embedding cosine when embeddings exist;
- for every piece, the top 8 neighbours under each measure, so the site can
  show "looks like" and "reads like" side by side, which is the interesting
  comparison;
- a 2D layout (UMAP or MDS, precomputed) so the whole collection can be shown
  as a map.

## Layer 5. Interfaces

Version 1 stays static and lives inside the Quarto site:

- `explore.qmd`: a page that loads `data/artworks.json` in the browser and
  offers tag facets as filters, a text search over descriptions, and a
  thumbnail grid. Observable JS blocks in Quarto do this without a server.
- Each artwork page gets a "similar pieces" strip and its tags, injected
  from the JSON at render time or by client side JS.
- A map page: the 2D layout with thumbnails, hover for title and tags.
- Optional: write the tags back into each qmd as Quarto categories so the
  existing listing page filters by them too. Easy, but it makes the
  category sidebar long.

Version 2, only if version 1 feels limiting: a small dynamic app. Natural
language queries over the descriptions, embedding search, or a chat style
"show me pieces that feel like this one but calmer". That needs a server
or an API key in the browser. The JSON layer is the same either way, which
is why it is worth building first.

## Repository layout after step 1

```
data/
  schema.json          record structure
  vocabulary.json      allowed tags per facet
  series.json          one entry per series
  artworks/            one JSON per piece
  artworks.json        built, all records
  similarity.json      built, neighbours and 2D layout
  thumbs/              built, 256 px previews
scripts/
  build_catalog.py     layer 1
  measure_images.py    layer 2
  validate.py          schema and vocabulary checks
  build_similarity.py  layer 4
  compile.py           writes artworks.json
explore.qmd            layer 5, version 1
```

## Suggested order

1. Agree on the questions below.
2. Build the catalog and measured features for all 169 pieces (one session).
3. Describe one series end to end (Colorlands, 8 pieces) and show you the
   records, so the vocabulary and tone get fixed before the long tail.
4. Describe the remaining 161, series by series.
5. Similarity and the explore page.
6. Decide whether playground and wip images join the database.

## Decisions (answered 2026-10-04)

1. Scope: the 169 finished pieces in `images/`. Playground and wip later, as relations.
2. Voice: both a neutral description and an interpretive reading, in separate
   fields. Be creative. When describing one piece reveals a new aspect or
   relation, it is fine to add that facet and apply it across the other pieces,
   within reason, so the schema can grow but should not balloon. Facets named:
   color descriptions, general impressions, overall style, format and
   materials, recurring themes, characters, elements.
3. Vocabulary: let it emerge from a first pass, then Matt corrects it.
4. Source of truth: JSON as a parallel layer beside the qmds. Each record also
   carries everything the current qmd structure knows (title, series, medium,
   date, process notes). Most described fields will not be shown on the site,
   and which ones are shown must be controllable.
5. Language: any mix of Python, R and JavaScript. Experimental; use what works.
6. Similarity: measured pixel features now. A CLIP embedding script to run
   locally later.
7. Interface: a static explore page inside the Quarto site.
8. Quarto categories: leave the qmd files untouched.
9. Editing tool: a small Node server plus an HTML page, run locally. Shows the
   image and a form for every field, saves back to the JSON file.
10. Publishing: a per-field visibility list in one config file. The build
    writes a public `artworks.json` with only the listed fields. Full records
    stay in the repo.

## Revised layout

```
data/
  schema.json            record structure and field glosses
  vocabulary.json        allowed tags per facet, grows during the first pass
  series.json            one entry per series
  visibility.json        which fields the public build includes
  artworks/<id>.json     one full record per piece, the editable source
  thumbs/<id>.jpg        built, 256 px previews for the explore page
  public/artworks.json   built, visible fields only, read by explore.qmd
  public/similarity.json built, neighbours and 2D layout
scripts/
  build_catalog.py       layer 1, creates or refreshes the factual fields
  measure_images.py      layer 2, palette and structure features, thumbnails
  validate.py            schema and vocabulary checks
  build_similarity.py    layer 4
  build_public.py        applies visibility.json, writes data/public/
  embed_clip.py          optional, run locally, adds embeddings
tools/
  edit/server.js         local editing tool, node tools/edit/server.js
  edit/index.html        image plus form, saves back to data/artworks/
explore.qmd              layer 5
```

Scripts never overwrite hand edited or described fields. The catalog script
refreshes only the factual block of each record and leaves the rest alone.

## Status (end of first session, 2026-10-04)

Done and pushed on this branch:

- Layer 1 and 2: all 169 pieces have catalog and measured blocks and a 256 px
  thumbnail.
- Layer 3: all 169 pieces have a described block (alt text, neutral
  description, interpretive impression, ten tag facets, text in image, format
  notes, free tags, confidence) and 60 hand written relations between pieces.
  `data/vocabulary.json` holds the resulting 1049 tags with glosses for the
  recurring characters and core styles. Nothing is verified yet.
- Layer 4: `data/public/similarity.json` with eight neighbours per piece under
  tag, text and visual measures, plus a 2D MDS map.
- Layer 5: `explore.qmd` plus `explore/explore.js` and `explore.css`, added to
  the sidebar. Facet filters, search, sort, grid and map views, a detail panel
  with palette, tags, relations and three "similar" strips.
- The local editor in `tools/edit/`.

## How to run things

See README.md. In short: `python3 -m pipeline build` after adding images or
editing records, `node tools/edit/server.js` to edit, `cd web && npm run dev`
for the site.

## Things to look at first

1. The vocabulary. Open `data/vocabulary.json` or filter in the explore page.
   Tags I was unsure about are in the `free_tags` of each record rather than
   the facets.
2. Desertland has one piece whose page had no title, now `desertland/fiona`,
   and one with only a 256 px source image (`land-shape`), marked low
   confidence.
3. Dates. Several pieces are signed a year earlier than the file date (the
   Colorlands say 2021, the towns say 2011 but the files say 2019). The
   catalog keeps the file date; the signed year is in `format_notes` and
   `free_tags` as `signed 2011` and so on. A `year_made` field could be added
   once you confirm which is right.
4. Relations are sparse on purpose. The similarity neighbours do most of the
   work; hand relations are for lineage (source of, revisits, variation of).

## Second session (2026-10-04): new architecture

Matt finished the review pass and asked for work in progress records and a
move away from Quarto.

- **Pipeline.** `scripts/` became the `pipeline/` package with one entry
  point, `python3 -m pipeline build`. The records are now the source of
  truth: the catalog step only creates records for new image files and
  refreshes file facts (size, EXIF, IPTC); it never rewrites titles, dates or
  notes. Reading the old qmd pages survives as `pipeline quarto-import`, which
  refuses to overwrite records without `--overwrite`.
- **Kinds of record.** `catalog.kind` is `work` (images/) or `wip` (wip/).
  The eight Volcano Ball Lake process images have full records, ids
  `wip/volcano-ball-lake-01-...` to `-08-...`, with `catalog.project` and
  `catalog.step`, captions taken from the old work in progress page, and
  `variation_of` and `step_toward` relations.
- **Projects.** `data/projects.json` lists process sequences: the 2021
  commission, the eight steps, then the 2023 finished piece.
- **Playground.** The 56 Stable Diffusion variations are not artwork
  records. `data/playground.json` holds them by group, with source piece and
  prompt, imported from the Quarto playground pages.
- **Website.** `web/` is an Astro static site. Pages: works (home), series
  index and one page per series, one page per record (including wip),
  process index and one page per project, explore (the faceted browser and
  map), playground, blog (Markdown, converted from the qmd posts), prints,
  about. Every record page shows only fields present in `data/public`, so
  `data/visibility.json` decides what is on the site. Images are resized at
  build time. Old Quarto URLs get redirect pages.
- **Why Astro.** Static output that GitHub Pages can host for free, no
  framework lock-in for the browser code (the explore page is still plain
  JavaScript), build-time image optimisation, and room to add server
  routes later (natural language search, a hosted editor) with an adapter
  instead of a rewrite.

Open items:

1. Switch GitHub Pages to the new site (see README, Deploying).
2. Decide when to delete the Quarto sources and `docs/`.
3. Description and impression text are excluded by visibility.json, so record
   pages show image, facts, notes, palette, tags, relations and similar
   pieces. Add `described.description` to the list to show the prose.
4. The Cliffs at another volcano ball lake process note still says "Currently
   shown on the work in progress page", which is now the process page.

## Prints page becomes Commissions (2026-10-04)

Matt no longer sells prints through Shopify. The `prints` page is now
`commissions/`, listing every record with `catalog.availability` set to
"sold", grouped by series, with a note that prints and commissions may be
available and a link to the contact links on the about page. The shop fields
`catalog.print_url` and `catalog.print_note` stay in the records but are no
longer in `data/visibility.json`, so nothing about the shop reaches the site.
Old `prints.html` and `prints/` URLs redirect to the new page.
