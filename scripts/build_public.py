#!/usr/bin/env python3
"""Compile the public data files the website reads.

Reads every record in data/artworks/, keeps only the fields listed in
data/visibility.json, and writes:

  data/public/artworks.json    list of trimmed records
  data/public/vocabulary.json  tag glosses for the facets that are public
  data/public/series.json      copy of data/series.json if present

Usage:  python3 scripts/build_public.py
"""
import glob
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(DATA_DIR, "public")


def pick(record, path):
    """Return the value at dotted path, or a sentinel when absent."""
    cur = record
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True


def place(target, path, value):
    parts = path.split(".")
    cur = target
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def main():
    vis = json.load(open(os.path.join(DATA_DIR, "visibility.json"), encoding="utf-8"))
    include = vis["include"]
    hide_hidden = vis.get("exclude_when_author_hidden", True)

    out = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "artworks", "*", "*.json"))):
        rec = json.load(open(p, encoding="utf-8"))
        if hide_hidden and rec.get("author", {}).get("hidden"):
            continue
        trimmed = {}
        for path in include:
            value, found = pick(rec, path)
            if found:
                place(trimmed, path, value)
        out.append(trimmed)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "artworks.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")

    vocab_path = os.path.join(DATA_DIR, "vocabulary.json")
    if os.path.exists(vocab_path):
        vocab = json.load(open(vocab_path, encoding="utf-8"))
        public_facets = {p.split(".")[1] for p in include if p.startswith("described.")}
        vocab["facets"] = {k: v for k, v in vocab["facets"].items() if k in public_facets}
        with open(os.path.join(OUT_DIR, "vocabulary.json"), "w", encoding="utf-8") as f:
            json.dump(vocab, f, indent=1, ensure_ascii=False)
            f.write("\n")

    series_path = os.path.join(DATA_DIR, "series.json")
    if os.path.exists(series_path):
        shutil.copy(series_path, os.path.join(OUT_DIR, "series.json"))

    print(f"wrote {len(out)} public records to data/public/artworks.json")


if __name__ == "__main__":
    main()
