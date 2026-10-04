#!/usr/bin/env python3
"""Layer 1: build or refresh the factual block of every artwork record.

Walks images/<series>/<file>, pairs each image with its generated Quarto page
in things/<series>/<Title>.qmd, reads EXIF and IPTC from the file, and writes
data/artworks/<series-slug>/<title-slug>.json.

Only the "catalog" block of each record is owned by this script. Any other
block ("measured", "described", "relations", "author") is preserved as is, so
re-running after hand edits is safe.

Usage:  python3 scripts/build_catalog.py            # refresh all
        python3 scripts/build_catalog.py --dry-run  # report, write nothing
"""
import glob
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

from PIL import Image, ExifTags, IptcImagePlugin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(ROOT, "images")
THINGS_DIR = os.path.join(ROOT, "things")
DATA_DIR = os.path.join(ROOT, "data", "artworks")
SITE_URL = "https://crumplab.com/things"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------- helpers

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "untitled"


def read_front_matter(path):
    """Return (front_matter_dict, body_text) for a simple Quarto page."""
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
    """Split a page body into named sections.

    Returns dict with process_notes (text or None), print_url (first link in
    a Buy Print section, or None) and print_note (remaining text there).
    Text before any heading is treated as process notes too.
    """
    sections = {"process": [], "print": [], "other": []}
    current = "process"
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("![]("):
            continue
        m = re.match(r"^#+\s*(.*)$", s)
        if m:
            name = m.group(1).strip().lower()
            if "process" in name:
                current = "process"
            elif "print" in name:
                current = "print"
            else:
                current = "other"
                sections[current].append(s)
            continue
        sections[current].append(s)

    def tidy(lines):
        text = "\n".join(lines).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text or None

    print_text = tidy(sections["print"]) or ""
    url = re.search(r"https?://[^\s<>)\]]+", print_text)
    print_note = re.sub(r"<?https?://[^\s<>)\]]+>?", "", print_text)
    print_note = re.sub(r"\[\]\(\)", "", print_note).strip() or None
    process = tidy(sections["process"] + ([""] + sections["other"] if sections["other"] else []))
    return {
        "process_notes": process,
        "print_url": url.group(0) if url else None,
        "print_note": print_note,
    }


def decode_iptc(value):
    if isinstance(value, list):
        return [decode_iptc(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def read_image_metadata(path):
    im = Image.open(path)
    width, height = im.size
    exif = im.getexif()
    exif_named = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
    iptc = {k: decode_iptc(v) for k, v in (IptcImagePlugin.getiptcinfo(im) or {}).items()}

    keywords = iptc.get((2, 25)) or []
    if isinstance(keywords, str):
        keywords = [keywords]

    def clean(v):
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        if isinstance(v, str):
            v = v.strip("\x00").strip()
        return v or None

    return {
        "width": width,
        "height": height,
        "bytes": os.path.getsize(path),
        "format": im.format,
        "exif": {
            "software": clean(exif_named.get("Software")),
            "camera_make": clean(exif_named.get("Make")),
            "camera_model": clean(exif_named.get("Model")),
            "datetime": clean(exif_named.get("DateTime")),
            "image_description": clean(exif_named.get("ImageDescription")),
        },
        "iptc": {
            "object_name": clean(iptc.get((2, 5))),
            "caption": clean(iptc.get((2, 120))),
            "keywords": [clean(k) for k in keywords if clean(k)],
            "date_created": clean(iptc.get((2, 55))),
            "copyright": clean(iptc.get((2, 116))),
        },
    }


# Known medium strings from the EXIF description field, mapped to
# (medium, surface). Anything else is treated as a caption, not a medium.
MEDIUM_MAP = {
    "airbrush on paper": ("airbrush", "paper"),
    "oil on canvas": ("oil", "canvas"),
    "oil on wood": ("oil", "wood panel"),
    "oil on wood panel": ("oil", "wood panel"),
    "marker on wood": ("marker", "wood panel"),
    "acryclic on wood": ("acrylic", "wood panel"),
    "acrylic on wood": ("acrylic", "wood panel"),
    "ink on paper": ("ink", "paper"),
    "vinyl on paper": ("vinyl", "paper"),
    "spraypaint on canvas": ("spray paint", "canvas"),
    "pen and ink and airbrush on paper": ("pen, ink and airbrush", "paper"),
    "digital": ("digital", None),
    "digital work": ("digital", None),
}

SERIES_DEFAULT_MEDIUM = {
    # Used when the description carries no medium. Inferred from the series
    # and confirmed against the images; overridable by hand in the record.
    "Scribble": ("digital", None),
    "Generative": ("digital", None),
    "Colorlands": ("digital", None),
    "screenprints": ("screen print", "paper"),
}


def parse_description(desc, series, title):
    """Split the EXIF description into medium, surface, camera, caption.

    Returns dict with keys medium, surface, camera, caption, medium_source.
    """
    out = {"medium": None, "surface": None, "camera": None, "caption": None,
           "medium_source": None}
    text = (desc or "").strip()
    if text.upper() == "NA":
        text = ""

    lowered = text.lower()
    # Digital pieces: "Digital Work, XH2 Fuji, Canal St" or "Digital FujiFiilm XH2"
    if lowered.startswith("digital"):
        out["medium"] = "digital"
        out["medium_source"] = "description"
        if "xh2" in lowered or "fuji" in lowered:
            out["camera"] = "Fujifilm X-H2"
        parts = [p.strip() for p in text.split(",")]
        extras = [p for p in parts[1:] if not re.search(r"xh2|fuji", p, re.I)]
        if extras:
            out["caption"] = ", ".join(extras)
        return out

    if lowered in MEDIUM_MAP:
        out["medium"], out["surface"] = MEDIUM_MAP[lowered]
        out["medium_source"] = "description"
        return out

    # Not a medium string: keep it as a caption and infer the medium.
    if text:
        out["caption"] = text
    t = title.lower()
    if t.startswith("gouache"):
        out["medium"], out["surface"] = "gouache", "paper"
        out["medium_source"] = "title"
    elif t.startswith("marker"):
        out["medium"], out["surface"] = "marker", "paper"
        out["medium_source"] = "title"
    elif series in SERIES_DEFAULT_MEDIUM:
        out["medium"], out["surface"] = SERIES_DEFAULT_MEDIUM[series]
        out["medium_source"] = "series"
    return out


def parse_keywords(keywords):
    """IPTC keywords here hold sale status and physical size in inches."""
    availability, size = None, None
    for k in keywords:
        kl = k.lower().strip()
        if kl == "sold":
            availability = "sold"
        elif kl == "nfs":
            availability = "not for sale"
        elif re.match(r"^\d+\s*[wh]?\s*x\s*\d+\s*[wh]?$", kl):
            size = re.sub(r"\s+", " ", k.strip())
    return availability, size


def parse_date(value):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y:%m:%d %H:%M:%S",
                "%Y/%m/%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------- main

def collect_pages():
    """Map image path (relative to ROOT) to its Quarto page."""
    pages = {}
    for qmd in glob.glob(os.path.join(THINGS_DIR, "*", "*.qmd")):
        fm, body = read_front_matter(qmd)
        image = fm.get("image", "").replace("../../", "")
        pages[image] = (qmd, fm, body)
    return pages


def build_record(image_rel, qmd, fm, body, existing):
    series = image_rel.split("/")[1]
    title = fm.get("title", "").strip()
    if not title or title.upper() == "NA":
        title = os.path.splitext(os.path.basename(image_rel))[0].replace("_", " ").title()
    series_slug = slugify(series)
    record_id = f"{series_slug}/{slugify(title)}"

    meta = read_image_metadata(os.path.join(ROOT, image_rel))
    desc = parse_description(fm.get("description"), series, title)
    availability, physical_size = parse_keywords(meta["iptc"]["keywords"])
    date = parse_date(fm.get("date", ""))

    sections = split_body(body)
    w, h = meta["width"], meta["height"]
    if abs(w - h) <= max(w, h) * 0.03:
        orientation = "square"
    elif w > h:
        orientation = "landscape"
    else:
        orientation = "portrait"

    page_rel = os.path.relpath(qmd, ROOT)
    page_html = page_rel[:-4] + ".html"

    catalog = {
        "title": title,
        "series": series,
        "series_slug": series_slug,
        "medium": desc["medium"],
        "surface": desc["surface"],
        "medium_source": desc["medium_source"],
        "description_raw": None if (fm.get("description") or "NA").upper() == "NA" else fm.get("description"),
        "caption": desc["caption"],
        "camera": desc["camera"],
        "date": date.isoformat(sep=" ") if date else None,
        "year": date.year if date else None,
        "availability": availability,
        "physical_size_in": physical_size,
        "process_notes": sections["process_notes"],
        "print_url": sections["print_url"],
        "print_note": sections["print_note"],
        "image": {
            "path": image_rel,
            "width": w,
            "height": h,
            "aspect": round(w / h, 4),
            "orientation": orientation,
            "bytes": meta["bytes"],
            "format": meta["format"],
        },
        "page": {
            "qmd": page_rel,
            "html": page_html,
            "url": f"{SITE_URL}/{page_html}",
        },
        "source_metadata": {
            "exif": meta["exif"],
            "iptc": meta["iptc"],
        },
        "catalog_built": datetime.now().strftime("%Y-%m-%d"),
    }

    record = dict(existing) if existing else {}
    record["id"] = record_id
    record["schema_version"] = SCHEMA_VERSION
    record["catalog"] = catalog
    record.setdefault("measured", {})
    record.setdefault("described", {})
    record.setdefault("relations", [])
    record.setdefault("author", {"verified": False, "notes": None})
    # Keep a stable key order for readable diffs.
    ordered = {k: record[k] for k in
               ["id", "schema_version", "catalog", "measured", "described",
                "relations", "author"]}
    for k, v in record.items():
        ordered.setdefault(k, v)
    return record_id, ordered


def main():
    dry_run = "--dry-run" in sys.argv
    pages = collect_pages()
    images = sorted(
        os.path.relpath(p, ROOT)
        for p in glob.glob(os.path.join(IMAGES_DIR, "*", "*"))
        if os.path.isfile(p)
    )
    ids = {}
    written = 0
    for image_rel in images:
        if image_rel not in pages:
            print(f"WARNING no page for {image_rel}", file=sys.stderr)
            continue
        qmd, fm, body = pages[image_rel]
        out_path = None
        existing = None
        # Find an existing record by image path so title edits do not orphan it.
        for p in glob.glob(os.path.join(DATA_DIR, "*", "*.json")):
            rec = json.load(open(p, encoding="utf-8"))
            if rec.get("catalog", {}).get("image", {}).get("path") == image_rel:
                existing, out_path = rec, p
                break
        record_id, record = build_record(image_rel, qmd, fm, body, existing)
        if existing:
            record_id = existing["id"]
            record["id"] = record_id
        if record_id in ids:
            print(f"ERROR duplicate id {record_id}: {image_rel} and {ids[record_id]}", file=sys.stderr)
            sys.exit(1)
        ids[record_id] = image_rel
        if out_path is None:
            out_path = os.path.join(DATA_DIR, record_id + ".json")
        if dry_run:
            print(record_id, "<-", image_rel)
            continue
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")
        written += 1
    print(f"{len(ids)} records, {written} written")


if __name__ == "__main__":
    main()
