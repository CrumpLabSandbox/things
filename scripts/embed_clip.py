#!/usr/bin/env python3
"""Optional: add CLIP image embeddings to every record's measured block.

Run this locally, not in the cloud session; it needs PyTorch and open_clip:

    pip install torch open_clip_torch pillow
    python3 scripts/embed_clip.py
    python3 scripts/build_similarity.py     # picks up the embeddings

Each record gets measured.embedding (a 512 float list) and
measured.embedding_model. Nothing else is touched. Re-running skips records
that already have an embedding unless --force is passed.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "artworks")
MODEL = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"


def main():
    try:
        import torch
        import open_clip
        from PIL import Image
    except ImportError as e:
        print(f"missing dependency: {e}. See the docstring for install steps.", file=sys.stderr)
        sys.exit(1)
    force = "--force" in sys.argv
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
    model = model.to(device).eval()
    done = 0
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*", "*.json"))):
        rec = json.load(open(p, encoding="utf-8"))
        if rec.get("measured", {}).get("embedding") and not force:
            continue
        img = Image.open(os.path.join(ROOT, rec["catalog"]["image"]["path"])).convert("RGB")
        with torch.no_grad():
            feats = model.encode_image(preprocess(img).unsqueeze(0).to(device))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        rec.setdefault("measured", {})["embedding"] = [round(float(x), 5) for x in feats[0].cpu()]
        rec["measured"]["embedding_model"] = f"open_clip {MODEL} {PRETRAINED}"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
            f.write("\n")
        done += 1
        print(rec["id"])
    print(f"embedded {done} records")


if __name__ == "__main__":
    main()
