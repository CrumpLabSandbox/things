#!/usr/bin/env python3
"""Layer 2: measured visual features and thumbnails.

For every record in data/artworks/, open the image, compute cheap pixel
features with numpy (no machine learning), write them into the record's
"measured" block, and save a 256 px thumbnail to data/thumbs/<id>.jpg.

Only the "measured" block is owned by this script; everything else in the
record is preserved.

Usage:  python3 scripts/measure_images.py           # all records
        python3 scripts/measure_images.py --force   # recompute even if present
        python3 scripts/measure_images.py <id> ...  # only these ids
"""
import glob
import json
import os
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "artworks")
THUMB_DIR = os.path.join(ROOT, "data", "thumbs")
ANALYSIS_SIZE = 512
THUMB_SIZE = 256
PALETTE_K = 6

HUE_NAMES = ["red", "orange", "yellow", "yellow-green", "green", "teal",
             "cyan", "blue", "indigo", "purple", "magenta", "pink"]


# ---------------------------------------------------------------- colour maths

def srgb_to_linear(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_lab(rgb):
    """rgb: (n,3) uint8 -> (n,3) Lab floats. D65 white point."""
    lin = srgb_to_linear(rgb.astype(np.float64))
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[:, 1] - 16
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def rgb_to_hsv(rgb):
    """rgb (n,3) in 0..255 -> h in degrees, s and v in 0..1."""
    rgb = rgb.astype(np.float64) / 255.0
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    d = mx - mn
    v = mx
    s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    h = np.zeros_like(mx)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    nz = d > 1e-9
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    return h * 60.0, s, v


def kmeans(points, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    # k-means++ seeding
    centers = [points[rng.integers(len(points))]]
    for _ in range(1, k):
        d2 = np.min(((points[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), axis=1)
        probs = d2 / d2.sum()
        centers.append(points[rng.choice(len(points), p=probs)])
    centers = np.array(centers, dtype=np.float64)
    for _ in range(iters):
        dist = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        labels = dist.argmin(axis=1)
        new = np.array([points[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
                        for i in range(k)])
        if np.allclose(new, centers, atol=1e-3):
            break
        centers = new
    dist = ((points[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
    labels = dist.argmin(axis=1)
    return centers, labels


def to_hex(rgb):
    r, g, b = [int(round(float(x))) for x in rgb]
    return "#{:02x}{:02x}{:02x}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


# ---------------------------------------------------------------- features

def sobel_magnitude(gray):
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    ky = kx.T
    pad = np.pad(gray, 1, mode="edge")
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    for i in range(3):
        for j in range(3):
            sl = pad[i:i + gray.shape[0], j:j + gray.shape[1]]
            gx += kx[i, j] * sl
            gy += ky[i, j] * sl
    return np.hypot(gx, gy)


def block_std(gray, block=16):
    h, w = gray.shape
    h2, w2 = h // block * block, w // block * block
    g = gray[:h2, :w2].reshape(h2 // block, block, w2 // block, block)
    return float(g.std(axis=(1, 3)).mean())


def dct_matrix(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2.0 / n)
    m[0, :] /= np.sqrt(2.0)
    return m


def phash(gray_img):
    g = np.asarray(gray_img.resize((32, 32), Image.LANCZOS), dtype=np.float64)
    d = dct_matrix(32)
    coeffs = d @ g @ d.T
    low = coeffs[:8, :8].flatten()[1:]
    bits = low > np.median(low)
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return "{:016x}".format(value)


def border_is_white(rgb, frac=0.02):
    h, w, _ = rgb.shape
    bh, bw = max(1, int(h * frac)), max(1, int(w * frac))
    strips = [rgb[:bh], rgb[-bh:], rgb[:, :bw], rgb[:, -bw:]]
    vals = np.concatenate([s.reshape(-1, 3) for s in strips]).astype(np.float64)
    bright = (vals.min(axis=1) > 235).mean()
    return bool(bright > 0.9)


def measure(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((ANALYSIS_SIZE, ANALYSIS_SIZE), Image.LANCZOS)
    rgb = np.asarray(im)
    pixels = rgb.reshape(-1, 3)

    # colour
    h, s, v = rgb_to_hsv(pixels)
    lab = rgb_to_lab(pixels)
    L = lab[:, 0] / 100.0
    chroma = np.hypot(lab[:, 1], lab[:, 2])

    # Hasler and Suesstrunk colourfulness
    rg = pixels[:, 0].astype(float) - pixels[:, 1]
    yb = 0.5 * (pixels[:, 0].astype(float) + pixels[:, 1]) - pixels[:, 2]
    colorfulness = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))

    saturated = s > 0.15
    hue_hist = np.zeros(12)
    if saturated.any():
        bins = (np.floor(((h[saturated] + 15) % 360) / 30)).astype(int)
        hue_hist = np.bincount(bins, minlength=12).astype(float)
        hue_hist /= hue_hist.sum()
    dominant = [HUE_NAMES[i] for i in np.argsort(-hue_hist)[:3] if hue_hist[i] > 0.08]

    hs = h[saturated] if saturated.any() else np.array([])
    warm = float(((hs < 75) | (hs >= 300)).mean()) if hs.size else 0.0

    # palette by k-means in Lab, sampled for speed
    rng = np.random.default_rng(0)
    sample = pixels[rng.choice(len(pixels), size=min(20000, len(pixels)), replace=False)]
    centers, labels = kmeans(rgb_to_lab(sample), PALETTE_K)
    # convert centers back by taking the mean RGB of each cluster
    palette = []
    for i in range(PALETTE_K):
        mask = labels == i
        if not mask.any():
            continue
        palette.append({"hex": to_hex(sample[mask].mean(axis=0)),
                        "fraction": round(float(mask.mean()), 4)})
    palette.sort(key=lambda p: -p["fraction"])

    # structure
    gray = np.asarray(im.convert("L"), dtype=np.float64) / 255.0
    edges = sobel_magnitude(gray)
    edge_density = float((edges > 0.5).mean())
    busyness = block_std(gray)

    mean_sat = float(s.mean())
    measured = {
        "palette": palette,
        "hue_histogram": [round(float(x), 4) for x in hue_hist],
        "dominant_hues": dominant,
        "warm_fraction": round(warm, 4),
        "mean_saturation": round(mean_sat, 4),
        "mean_value": round(float(v.mean()), 4),
        "mean_lightness": round(float(L.mean()), 4),
        "contrast": round(float(L.std()), 4),
        "colorfulness": round(colorfulness, 2),
        "mean_chroma": round(float(chroma.mean()), 2),
        "is_monochrome": bool(mean_sat < 0.08 and colorfulness < 12),
        "dark_fraction": round(float((L < 0.2).mean()), 4),
        "light_fraction": round(float((L > 0.9).mean()), 4),
        "edge_density": round(edge_density, 4),
        "busyness": round(busyness, 4),
        "has_white_border": border_is_white(rgb),
        "phash": phash(im.convert("L")),
        "analysis_size": list(im.size),
        "measured_on": datetime.now().strftime("%Y-%m-%d"),
    }
    return measured


def save_thumb(path, out_path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, "JPEG", quality=82, optimize=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*", "*.json")))
    done = 0
    for p in paths:
        rec = json.load(open(p, encoding="utf-8"))
        if args and rec["id"] not in args:
            continue
        if rec.get("measured") and not force:
            continue
        image_path = os.path.join(ROOT, rec["catalog"]["image"]["path"])
        rec["measured"] = measure(image_path)
        thumb_rel = os.path.join("data", "thumbs", rec["id"] + ".jpg")
        save_thumb(image_path, os.path.join(ROOT, thumb_rel))
        rec["measured"]["thumbnail"] = thumb_rel
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
            f.write("\n")
        done += 1
        print(rec["id"], rec["measured"]["dominant_hues"], "edges", rec["measured"]["edge_density"])
    print(f"measured {done} of {len(paths)}")


if __name__ == "__main__":
    main()
