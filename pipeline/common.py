"""Shared paths, constants and record I/O for the pipeline."""
import glob
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RECORDS = os.path.join(DATA, "artworks")
PUBLIC = os.path.join(DATA, "public")
THUMBS = os.path.join(DATA, "thumbs")
VOCAB_PATH = os.path.join(DATA, "vocabulary.json")
PROJECTS_PATH = os.path.join(DATA, "projects.json")

SCHEMA_VERSION = 1

# Media folders the catalog scans, and the record kind each one produces.
# images/<series>/<file> holds finished work; wip/<file> holds process images.
MEDIA_ROOTS = [
    {"glob": "images/*/*", "kind": "work"},
    {"glob": "wip/*", "kind": "wip"},
]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

FACETS = ["subjects", "characters", "elements", "setting", "composition",
          "line", "color_words", "style", "themes", "mood"]
RELATION_TYPES = {"variation_of", "source_of", "same_characters", "same_scene",
                  "series_pair", "revisits", "step_toward", "near_duplicate"}
CONFIDENCE = {"high", "medium", "low"}
BLOCK_ORDER = ["id", "schema_version", "catalog", "measured", "described",
               "relations", "author"]


def rel(path):
    return os.path.relpath(path, ROOT)


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "untitled"


def record_path(record_id):
    return os.path.join(RECORDS, record_id + ".json")


def record_files():
    return sorted(glob.glob(os.path.join(RECORDS, "*", "*.json")))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, indent=2):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def load_records():
    """All records as a list, sorted by id."""
    return sorted((load_json(p) for p in record_files()), key=lambda r: r["id"])


def ordered(record):
    """Stable top-level key order for readable diffs."""
    out = {k: record[k] for k in BLOCK_ORDER if k in record}
    for k, v in record.items():
        out.setdefault(k, v)
    return out


def save_record(record):
    save_json(record_path(record["id"]), ordered(record))


def load_vocab():
    if not os.path.exists(VOCAB_PATH):
        return {"version": 0, "facets": {f: [] for f in FACETS}}
    return load_json(VOCAB_PATH)
