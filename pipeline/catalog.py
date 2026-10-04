"""Keep one record per image file.

Scans the media folders in common.MEDIA_ROOTS. For an image that already has
a record (matched by image path), only the file facts are refreshed, and only
when they changed: catalog.image and catalog.source_metadata. Titles, dates, medium, notes and
every other field are left alone, because the records are the source of
truth and may hold hand edits.

For an image with no record, a new record is created from the file name and
its EXIF and IPTC fields, with catalog.kind set by the folder it lives in
("work" or "wip"; a record without catalog.kind is a finished work). New
records need a description pass (the editor, or `pipeline apply`).

Usage:  python3 -m pipeline catalog [--dry-run]
"""
import glob
import os
import sys
from datetime import datetime

from . import common as c
from .imagemeta import read_image, parse_description, parse_keywords, parse_date


def images_on_disk():
    out = []
    for root in c.MEDIA_ROOTS:
        for p in sorted(glob.glob(os.path.join(c.ROOT, root["glob"]))):
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in c.IMAGE_EXTS:
                out.append((c.rel(p), root["kind"]))
    return out


def new_record(image_rel, kind, meta):
    folder = image_rel.split("/")[-2] if kind == "work" else "wip"
    stem = os.path.splitext(os.path.basename(image_rel))[0]
    iptc = meta["source_metadata"]["iptc"]
    exif = meta["source_metadata"]["exif"]
    title = iptc["object_name"] or stem.replace("_", " ").replace("-", " ").strip()
    title = title[:1].upper() + title[1:]
    raw_desc = iptc["caption"] or exif["image_description"]
    desc = parse_description(raw_desc, folder, title)
    availability, size = parse_keywords(iptc["keywords"])
    date = parse_date(exif["datetime"] or "") or datetime.fromtimestamp(os.path.getmtime(os.path.join(c.ROOT, image_rel)))
    record_id = f"{c.slugify(folder)}/{c.slugify(title)}"
    return {
        "id": record_id,
        "schema_version": c.SCHEMA_VERSION,
        "catalog": {
            "kind": kind,
            "title": title,
            "series": folder,
            "series_slug": c.slugify(folder),
            "medium": desc["medium"],
            "surface": desc["surface"],
            "medium_source": desc["medium_source"],
            "description_raw": raw_desc,
            "caption": desc["caption"],
            "camera": desc["camera"],
            "date": date.isoformat(sep=" ", timespec="seconds"),
            "year": date.year,
            "availability": availability,
            "physical_size_in": size,
            "process_notes": None,
            "print_url": None,
            "print_note": None,
            "image": dict(meta["image"], path=image_rel),
            "source_metadata": meta["source_metadata"],
            "catalog_built": datetime.now().strftime("%Y-%m-%d"),
        },
        "measured": {},
        "described": {},
        "relations": [],
        "author": {"verified": False, "notes": None},
    }


def main(argv):
    dry = "--dry-run" in argv
    by_path = {}
    for p in c.record_files():
        rec = c.load_json(p)
        by_path[rec["catalog"]["image"]["path"]] = (p, rec)

    created, refreshed = [], 0
    seen = set()
    for image_rel, kind in images_on_disk():
        seen.add(image_rel)
        meta = read_image(os.path.join(c.ROOT, image_rel))
        if image_rel in by_path:
            path, rec = by_path[image_rel]
            cat = rec["catalog"]
            new_image = dict(meta["image"], path=image_rel)
            changed = cat.get("image") != new_image or cat.get("source_metadata") != meta["source_metadata"]
            if changed:
                cat["image"] = new_image
                cat["source_metadata"] = meta["source_metadata"]
                refreshed += 1
                if not dry:
                    c.save_json(path, c.ordered(rec))
        else:
            rec = new_record(image_rel, kind, meta)
            if os.path.exists(c.record_path(rec["id"])):
                print(f"ERROR {image_rel}: id {rec['id']} already used by another image", file=sys.stderr)
                return 1
            created.append(rec["id"])
            if not dry:
                c.save_record(rec)

    missing = sorted(set(by_path) - seen)
    for m in missing:
        print(f"WARNING record {by_path[m][1]['id']} points at a missing image: {m}", file=sys.stderr)
    for rid in created:
        print(f"new record {rid} (needs a description)")
    print(f"{len(seen)} images, {refreshed} records refreshed, {len(created)} created{' (dry run)' if dry else ''}")
    return 0
