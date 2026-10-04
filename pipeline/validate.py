#!/usr/bin/env python3
"""Check every record against the schema shape and the vocabulary.

Reports: missing blocks, unknown tags per facet, relations pointing at ids
that do not exist, and duplicate ids. Exit code 1 if anything is wrong.

Usage:  python3 -m pipeline validate
        python3 -m pipeline validate --adopt   # add unknown tags to vocabulary.json
"""
import glob
import json
import os
import sys
from collections import Counter

from . import common as c

ROOT = c.ROOT
DATA_DIR = c.RECORDS
VOCAB_PATH = c.VOCAB_PATH

FACETS = c.FACETS
RELATION_TYPES = c.RELATION_TYPES
CONFIDENCE = c.CONFIDENCE


def load_vocab():
    if not os.path.exists(VOCAB_PATH):
        return {"version": 0, "facets": {f: [] for f in FACETS}}
    return json.load(open(VOCAB_PATH, encoding="utf-8"))


def vocab_tags(vocab, facet):
    return {t["tag"] for t in vocab["facets"].get(facet, [])}


def main(argv=()):
    adopt = "--adopt" in argv
    vocab = load_vocab()
    records = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*", "*.json"))):
        records.append((p, json.load(open(p, encoding="utf-8"))))

    problems = []
    ids = Counter(r["id"] for _, r in records)
    for rid, n in ids.items():
        if n > 1:
            problems.append(f"duplicate id {rid}")
    known_ids = set(ids)

    unknown = {f: Counter() for f in FACETS}
    described_count = 0
    for p, r in records:
        rel = os.path.relpath(p, ROOT)
        for block in ("catalog", "measured", "described", "relations", "author"):
            if block not in r:
                problems.append(f"{rel}: missing block {block}")
        expected = os.path.join(DATA_DIR, r["id"] + ".json")
        if os.path.abspath(p) != os.path.abspath(expected):
            problems.append(f"{rel}: id {r['id']} does not match its path")
        d = r.get("described") or {}
        if d:
            described_count += 1
            for f in FACETS:
                tags = d.get(f, [])
                if not isinstance(tags, list):
                    problems.append(f"{rel}: described.{f} is not a list")
                    continue
                for t in tags:
                    if t not in vocab_tags(vocab, f):
                        unknown[f][t] += 1
            if d.get("confidence") not in CONFIDENCE:
                problems.append(f"{rel}: described.confidence must be high, medium or low")
            for key in ("alt_text", "description", "impression"):
                if not d.get(key):
                    problems.append(f"{rel}: described.{key} is empty")
        for item in r.get("relations", []):
            if item.get("type") not in RELATION_TYPES:
                problems.append(f"{rel}: relation type {item.get('type')!r} unknown")
            if item.get("target") not in known_ids:
                problems.append(f"{rel}: relation target {item.get('target')!r} not found")

    for f in FACETS:
        for t, n in unknown[f].most_common():
            if adopt:
                vocab["facets"].setdefault(f, []).append({"tag": t, "gloss": ""})
            else:
                problems.append(f"unknown {f} tag {t!r} used {n} times")

    if adopt:
        for f in FACETS:
            vocab["facets"][f] = sorted(vocab["facets"].get(f, []), key=lambda x: x["tag"])
        with open(VOCAB_PATH, "w", encoding="utf-8") as fh:
            json.dump(vocab, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        added = sum(len(c) for c in unknown.values())
        print(f"adopted {added} tags into vocabulary.json")

    print(f"{len(records)} records, {described_count} described")
    for line in problems:
        print("PROBLEM", line)
    return 1 if problems else 0

