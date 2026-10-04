#!/usr/bin/env python3
"""Layer 4: neighbours and a 2D map.

Reads every record and computes, for each piece, its nearest neighbours under
three measures, plus a 2D layout of the whole collection:

  tags    weighted Jaccard over the described tag facets
  text    TF-IDF cosine over description, impression, alt_text and process notes
  visual  distance over measured colour and structure features
          (plus embedding cosine when records carry measured.embedding)

Writes data/public/similarity.json:
  { "neighbours": { id: { "tags": [[id, score], ...], "text": [...], "visual": [...] } },
    "layout": { id: [x, y] },
    "weights": {...} }

Usage:  python3 -m pipeline similarity
"""
import glob
import json
import math
import os
import re
from collections import Counter

import numpy as np

from . import common as c

ROOT = c.ROOT
DATA_DIR = c.RECORDS
OUT_PATH = os.path.join(c.PUBLIC, "similarity.json")
K = 8

FACET_WEIGHTS = {
    "subjects": 1.0, "characters": 1.5, "elements": 0.6, "setting": 1.0,
    "composition": 0.8, "line": 0.8, "color_words": 0.6, "style": 1.2,
    "themes": 1.0, "mood": 0.7,
}

STOP = set("""a an the and or of in on at to with for by from as is are was were be been
this that these those it its into over under above below between among along near
there here where which who whose what when while than then so very just like one two
three four five six seven eight nine ten each every all any some no not only also
more most much many few left right top bottom centre center upper lower middle
front behind beside across through up down out off has have had his her their
them they he she we you your our image piece picture format square portrait
landscape digital drawing painting photograph photographed paper wood canvas
signed signature lower""".split())


def tokenize(text):
    words = re.findall(r"[a-z]+", (text or "").lower())
    return [w for w in words if len(w) > 2 and w not in STOP]


def hex_to_lab(h):
    r, g, b = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return np.array([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)])


def palette_distance(pa, pb):
    """Earth mover like distance between two weighted palettes, greedy."""
    if not pa or not pb:
        return 1.0
    la = [(hex_to_lab(p["hex"]), p["fraction"]) for p in pa]
    lb = [(hex_to_lab(p["hex"]), p["fraction"]) for p in pb]
    # symmetric nearest-colour average, weighted by fraction
    def one_way(src, dst):
        total = 0.0
        for c, w in src:
            total += w * min(np.linalg.norm(c - d) for d, _ in dst)
        return total
    return (one_way(la, lb) + one_way(lb, la)) / 2.0 / 100.0


def main(argv=()):
    records = [json.load(open(p, encoding="utf-8"))
               for p in sorted(glob.glob(os.path.join(DATA_DIR, "*", "*.json")))]
    ids = [r["id"] for r in records]
    n = len(records)
    idx = {rid: i for i, rid in enumerate(ids)}

    # ---- tag similarity (weighted Jaccard per facet, averaged)
    tag_sim = np.zeros((n, n))
    facet_sets = {f: [set(r["described"].get(f, [])) for r in records] for f in FACET_WEIGHTS}
    total_w = sum(FACET_WEIGHTS.values())
    for i in range(n):
        for j in range(i + 1, n):
            s = 0.0
            for f, w in FACET_WEIGHTS.items():
                a, b = facet_sets[f][i], facet_sets[f][j]
                if a or b:
                    s += w * len(a & b) / len(a | b)
                else:
                    s += 0
            tag_sim[i, j] = tag_sim[j, i] = s / total_w

    # ---- text similarity (TF-IDF cosine)
    docs = []
    for r in records:
        d = r["described"]
        text = " ".join([d.get("description", ""), d.get("impression", ""),
                         d.get("alt_text", ""), r["catalog"].get("process_notes") or "",
                         r["catalog"].get("title", "")])
        docs.append(Counter(tokenize(text)))
    df = Counter()
    for doc in docs:
        df.update(doc.keys())
    vocab = {w: i for i, w in enumerate(sorted(df))}
    tfidf = np.zeros((n, len(vocab)))
    for i, doc in enumerate(docs):
        total = sum(doc.values()) or 1
        for w, c in doc.items():
            tfidf[i, vocab[w]] = (c / total) * math.log((1 + n) / (1 + df[w]))
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1
    tfidf /= norms
    text_sim = tfidf @ tfidf.T
    np.fill_diagonal(text_sim, 0)

    # ---- visual similarity
    feat_keys = ["mean_saturation", "mean_lightness", "contrast", "colorfulness",
                 "edge_density", "busyness", "dark_fraction", "light_fraction", "warm_fraction"]
    feats = np.array([[r["measured"].get(k, 0.0) for k in feat_keys] for r in records], dtype=float)
    hue = np.array([r["measured"].get("hue_histogram", [0] * 12) for r in records], dtype=float)
    feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-9)
    feat_d = np.linalg.norm(feats[:, None, :] - feats[None, :, :], axis=-1)
    feat_d /= feat_d.max() or 1
    hue_d = 0.5 * np.abs(hue[:, None, :] - hue[None, :, :]).sum(-1)
    pal_d = np.zeros((n, n))
    pals = [r["measured"].get("palette", []) for r in records]
    for i in range(n):
        for j in range(i + 1, n):
            pal_d[i, j] = pal_d[j, i] = palette_distance(pals[i], pals[j])
    pal_d /= pal_d.max() or 1
    visual_d = 0.45 * feat_d + 0.25 * hue_d + 0.30 * pal_d
    # same aspect/orientation bonus
    orient = [r["catalog"]["image"]["orientation"] for r in records]
    for i in range(n):
        for j in range(n):
            if orient[i] != orient[j]:
                visual_d[i, j] += 0.05
    visual_sim = 1 - visual_d / (visual_d.max() or 1)
    np.fill_diagonal(visual_sim, 0)

    embeddings = [r["measured"].get("embedding") for r in records]
    has_emb = all(e is not None for e in embeddings)
    if has_emb:
        E = np.array(embeddings, dtype=float)
        E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
        emb_sim = E @ E.T
        np.fill_diagonal(emb_sim, 0)
        visual_sim = 0.5 * visual_sim + 0.5 * emb_sim

    # ---- neighbours
    def top(sim_row, i):
        order = np.argsort(-sim_row)
        return [[ids[j], round(float(sim_row[j]), 4)] for j in order if j != i][:K]

    neighbours = {}
    for i, rid in enumerate(ids):
        neighbours[rid] = {
            "tags": top(tag_sim[i], i),
            "text": top(text_sim[i], i),
            "visual": top(visual_sim[i], i),
        }

    # ---- 2D layout: classical MDS on a blended distance
    blend = 0.4 * (1 - tag_sim) + 0.3 * (1 - text_sim) + 0.3 * (1 - visual_sim)
    np.fill_diagonal(blend, 0)
    D2 = blend ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    vals, vecs = np.linalg.eigh(B)
    order = np.argsort(-vals)[:2]
    coords = vecs[:, order] * np.sqrt(np.maximum(vals[order], 0))
    coords -= coords.min(axis=0)
    coords /= coords.max(axis=0) + 1e-9
    layout = {rid: [round(float(x), 4), round(float(y), 4)] for rid, (x, y) in zip(ids, coords)}

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out = {
        "about": "Nearest neighbours per piece under tag, text and visual similarity, and a 2D MDS layout of the collection. Built by scripts/build_similarity.py.",
        "k": K,
        "has_embeddings": has_emb,
        "weights": {"facets": FACET_WEIGHTS, "layout": {"tags": 0.4, "text": 0.3, "visual": 0.3}},
        "neighbours": neighbours,
        "layout": layout,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote neighbours for {n} pieces to data/public/similarity.json (embeddings: {has_emb})")
    return 0

