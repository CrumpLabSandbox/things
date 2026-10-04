#!/usr/bin/env python3
"""Compile the public data files the website reads.

Reads every record in data/artworks/, keeps only the fields listed in
data/visibility.json, and writes:

  data/public/artworks.json    list of trimmed records
  data/public/vocabulary.json  tag glosses for the facets that are public
  data/public/series.json      copy of data/series.json
  data/public/projects.json    copy of data/projects.json (process sequences)
  data/public/playground.json  copy of data/playground.json

Usage:  python3 -m pipeline public
"""
import os
import shutil

from . import common as c

ROOT = c.ROOT
DATA_DIR = c.DATA
OUT_DIR = c.PUBLIC


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


def main(argv=()):
    vis = c.load_json(os.path.join(DATA_DIR, "visibility.json"))
    include = vis["include"]
    hide_hidden = vis.get("exclude_when_author_hidden", True)

    out = []
    hidden = set()
    for rec in c.load_records():
        if hide_hidden and rec.get("author", {}).get("hidden"):
            hidden.add(rec["id"])
            continue
        trimmed = {}
        for path in include:
            value, found = pick(rec, path)
            if found:
                place(trimmed, path, value)
        out.append(trimmed)
    # drop relations that point at hidden records
    for r in out:
        if "relations" in r:
            r["relations"] = [x for x in r["relations"] if x.get("target") not in hidden]
    c.save_json(os.path.join(OUT_DIR, "artworks.json"), out, indent=1)

    vocab = c.load_vocab()
    public_facets = {p.split(".")[1] for p in include if p.startswith("described.")}
    vocab["facets"] = {k: v for k, v in vocab["facets"].items() if k in public_facets}
    c.save_json(os.path.join(OUT_DIR, "vocabulary.json"), vocab, indent=1)

    for name in ("series.json", "projects.json", "playground.json"):
        src = os.path.join(DATA_DIR, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT_DIR, name))

    print(f"wrote {len(out)} public records to data/public/artworks.json ({len(hidden)} hidden)")
    return 0
