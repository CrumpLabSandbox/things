#!/usr/bin/env python3
"""Merge described blocks and relations from a batch file into the records.

The batch file is JSON: a list of objects, each with "id", a "described"
object, and optionally "relations" (a list). Existing described fields are
replaced by the batch; fields not present in the batch are kept. Relations
in the batch are added if an identical (type, target) pair is not already
present. The author block is never touched.

Usage:  python3 scripts/apply_described.py batch.json [batch2.json ...]
"""
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "artworks")
VOCAB_PATH = os.path.join(ROOT, "data", "vocabulary.json")

FIELD_ORDER = ["alt_text", "description", "impression", "subjects", "characters",
               "elements", "setting", "composition", "line", "color_words",
               "style", "themes", "mood", "text_in_image", "format_notes",
               "free_tags", "confidence", "described_by", "described_on",
               "vocabulary_version"]


def main():
    vocab_version = 0
    if os.path.exists(VOCAB_PATH):
        vocab_version = json.load(open(VOCAB_PATH, encoding="utf-8")).get("version", 0)
    today = datetime.now().strftime("%Y-%m-%d")
    applied = 0
    for batch_path in sys.argv[1:]:
        batch = json.load(open(batch_path, encoding="utf-8"))
        for item in batch:
            path = os.path.join(DATA_DIR, item["id"] + ".json")
            if not os.path.exists(path):
                print(f"ERROR no record for {item['id']}", file=sys.stderr)
                sys.exit(1)
            rec = json.load(open(path, encoding="utf-8"))
            described = dict(rec.get("described") or {})
            described.update(item.get("described", {}))
            described.setdefault("described_by", "claude")
            described["described_on"] = today
            described["vocabulary_version"] = vocab_version
            rec["described"] = {k: described[k] for k in FIELD_ORDER if k in described}
            for k, v in described.items():
                rec["described"].setdefault(k, v)
            existing = {(r["type"], r["target"]) for r in rec.get("relations", [])}
            for rel in item.get("relations", []):
                key = (rel["type"], rel["target"])
                if key not in existing:
                    rel.setdefault("source", "described")
                    rec.setdefault("relations", []).append(rel)
                    existing.add(key)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)
                f.write("\n")
            applied += 1
    print(f"applied {applied} described blocks")


if __name__ == "__main__":
    main()
