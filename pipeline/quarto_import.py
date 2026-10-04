"""Legacy import from the Quarto site.

The records were first built from the Quarto pages in things/<series>/*.qmd.
The records are now the source of truth, so this is only needed to pull
content out of the old site, never during a normal build.

  python3 -m pipeline quarto-import playground
      Write data/playground.json from playground/<folder>/*.qmd: one entry per
      Stable Diffusion variation with its source piece, prompt and notes.

  python3 -m pipeline quarto-import works --overwrite
      Rebuild the catalog block of every finished work from its qmd page.
      This overwrites titles, dates, medium and notes in the records, so it
      discards any hand edits to those fields. Refuses to run without
      --overwrite.
"""
import glob
import os
import re
import sys

from . import common as c
from .imagemeta import read_image, parse_description, parse_keywords, parse_date

SITE_URL = "https://crumplab.com/things"


def read_front_matter(path):
    raw = open(path, encoding="utf-8").read()
    parts = raw.split("---", 2)
    fm_text, body = parts[1], parts[2] if len(parts) > 2 else ""
    fm = {}
    for line in fm_text.splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def split_body(body):
    """Process notes, print link and print note from a page body."""
    sections = {"process": [], "print": [], "other": []}
    current = "process"
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("![]("):
            continue
        m = re.match(r"^#+\s*(.*)$", s)
        if m:
            name = m.group(1).strip().lower()
            current = "process" if "process" in name else "print" if "print" in name else "other"
            if current == "other":
                sections[current].append(s)
            continue
        sections[current].append(s)

    def tidy(lines):
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines).strip())
        return text or None

    print_text = tidy(sections["print"]) or ""
    url = re.search(r"https?://[^\s<>)\]]+", print_text)
    note = re.sub(r"<?https?://[^\s<>)\]]+>?", "", print_text)
    note = re.sub(r"\[\]\(\)", "", note).strip() or None
    process = tidy(sections["process"] + ([""] + sections["other"] if sections["other"] else []))
    return {"process_notes": process, "print_url": url.group(0) if url else None, "print_note": note}


# ---------------------------------------------------------------- playground

PLAYGROUND_SOURCES = {
    "meeting_mountains": "colorlands/meeting-of-the-mountains",
    "volcano_ball_lake": "commissions/the-cliffs-of-volcano-ball-lake",
    "volcano_2": "commissions/the-cliffs-of-volcano-ball-lake",
}


def import_playground():
    groups = {}
    for qmd in sorted(glob.glob(os.path.join(c.ROOT, "playground", "*", "*.qmd"))):
        fm, body = read_front_matter(qmd)
        folder = os.path.basename(os.path.dirname(qmd))
        image = fm.get("image", "").replace("../../", "")
        if not os.path.exists(os.path.join(c.ROOT, image)):
            print(f"WARNING missing image for {qmd}", file=sys.stderr)
            continue
        notes = split_body(body)["process_notes"] or ""
        prompt = re.search(r"Prompt:\s*(.+?)\s*$", notes, re.S)
        notes_plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", notes)
        date = parse_date(fm.get("date", ""))
        meta = read_image(os.path.join(c.ROOT, image))["image"]
        g = groups.setdefault(folder, {"id": folder, "source": PLAYGROUND_SOURCES.get(folder),
                                       "description": fm.get("description"), "items": []})
        g["items"].append({
            "id": f"{folder}/{c.slugify(os.path.splitext(os.path.basename(image))[0])}",
            "title": fm.get("title"),
            "image": image,
            "width": meta["width"],
            "height": meta["height"],
            "date": date.isoformat(sep=" ") if date else None,
            "prompt": prompt.group(1).strip().rstrip(".") if prompt else None,
            "notes": notes_plain or None,
        })
    for g in groups.values():
        g["items"].sort(key=lambda x: (x["date"] or "", x["title"] or ""))
        notes = {i["notes"] for i in g["items"]}
        g["notes"] = notes.pop() if len(notes) == 1 else None
    out = {
        "about": "Stable Diffusion variations of finished pieces, imported from the Quarto playground pages. Not artwork records; each group points at its source record.",
        "groups": sorted(groups.values(), key=lambda g: g["id"]),
    }
    c.save_json(os.path.join(c.DATA, "playground.json"), out)
    n = sum(len(g["items"]) for g in out["groups"])
    print(f"wrote {n} playground items in {len(out['groups'])} groups to data/playground.json")
    return 0


# ---------------------------------------------------------------- works

def import_works(overwrite):
    if not overwrite:
        print("Refusing: this rewrites catalog fields from the old qmd pages and discards hand edits. "
              "Pass --overwrite if that is really what you want.", file=sys.stderr)
        return 1
    by_path = {r["catalog"]["image"]["path"]: r for r in c.load_records()}
    n = 0
    for qmd in sorted(glob.glob(os.path.join(c.ROOT, "things", "*", "*.qmd"))):
        fm, body = read_front_matter(qmd)
        image_rel = fm.get("image", "").replace("../../", "")
        rec = by_path.get(image_rel)
        if rec is None:
            print(f"WARNING no record for {image_rel}; run `pipeline catalog` first", file=sys.stderr)
            continue
        series = image_rel.split("/")[1]
        title = fm.get("title", "").strip()
        if not title or title.upper() == "NA":
            title = os.path.splitext(os.path.basename(image_rel))[0].replace("_", " ").title()
        meta = read_image(os.path.join(c.ROOT, image_rel))
        desc = parse_description(fm.get("description"), series, title)
        availability, size = parse_keywords(meta["source_metadata"]["iptc"]["keywords"])
        date = parse_date(fm.get("date", ""))
        sections = split_body(body)
        page_rel = c.rel(qmd)
        page_html = page_rel[:-4] + ".html"
        rec["catalog"].update({
            "title": title, "series": series, "series_slug": c.slugify(series),
            "medium": desc["medium"], "surface": desc["surface"], "medium_source": desc["medium_source"],
            "description_raw": None if (fm.get("description") or "NA").upper() == "NA" else fm.get("description"),
            "caption": desc["caption"], "camera": desc["camera"],
            "date": date.isoformat(sep=" ") if date else None, "year": date.year if date else None,
            "availability": availability, "physical_size_in": size,
            **sections,
            "page": {"qmd": page_rel, "html": page_html, "url": f"{SITE_URL}/{page_html}"},
        })
        c.save_record(rec)
        n += 1
    print(f"rewrote the catalog block of {n} records from the Quarto pages")
    return 0


def main(argv):
    if not argv or argv[0] not in ("playground", "works"):
        print(__doc__)
        return 1
    if argv[0] == "playground":
        return import_playground()
    return import_works("--overwrite" in argv)
