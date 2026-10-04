"""Reading facts out of image files: size, EXIF, IPTC, and the conventions
used in this collection's metadata (medium strings, sale keywords)."""
import os
import re
from datetime import datetime

from PIL import Image, ExifTags, IptcImagePlugin


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _clean(v):
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, str):
        v = v.strip("\x00").strip()
    return v or None


def orientation(w, h):
    if abs(w - h) <= max(w, h) * 0.03:
        return "square"
    return "landscape" if w > h else "portrait"


def read_image(path):
    """Size, file facts, and the EXIF and IPTC fields this collection uses."""
    im = Image.open(path)
    w, h = im.size
    exif = {ExifTags.TAGS.get(k, str(k)): v for k, v in im.getexif().items()}
    iptc = {k: _decode(v) for k, v in (IptcImagePlugin.getiptcinfo(im) or {}).items()}
    keywords = iptc.get((2, 25)) or []
    if isinstance(keywords, str):
        keywords = [keywords]
    return {
        "image": {
            "width": w,
            "height": h,
            "aspect": round(w / h, 4),
            "orientation": orientation(w, h),
            "bytes": os.path.getsize(path),
            "format": im.format,
        },
        "source_metadata": {
            "exif": {
                "software": _clean(exif.get("Software")),
                "camera_make": _clean(exif.get("Make")),
                "camera_model": _clean(exif.get("Model")),
                "datetime": _clean(exif.get("DateTime")),
                "image_description": _clean(exif.get("ImageDescription")),
            },
            "iptc": {
                "object_name": _clean(iptc.get((2, 5))),
                "caption": _clean(iptc.get((2, 120))),
                "keywords": [_clean(k) for k in keywords if _clean(k)],
                "date_created": _clean(iptc.get((2, 55))),
                "copyright": _clean(iptc.get((2, 116))),
            },
        },
    }


# Medium strings found in the EXIF description field, mapped to (medium, surface).
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
    "Scribble": ("digital", None),
    "Generative": ("digital", None),
    "Colorlands": ("digital", None),
    "screenprints": ("screen print", "paper"),
}


def parse_description(desc, series, title):
    """Split a description string into medium, surface, camera and caption."""
    out = {"medium": None, "surface": None, "camera": None, "caption": None,
           "medium_source": None}
    text = (desc or "").strip()
    if text.upper() == "NA":
        text = ""
    lowered = text.lower()
    if lowered.startswith("digital"):
        out["medium"], out["medium_source"] = "digital", "description"
        if "xh2" in lowered or "fuji" in lowered:
            out["camera"] = "Fujifilm X-H2"
        extras = [p.strip() for p in text.split(",")[1:] if not re.search(r"xh2|fuji", p, re.I)]
        if extras:
            out["caption"] = ", ".join(extras)
        return out
    if lowered in MEDIUM_MAP:
        out["medium"], out["surface"] = MEDIUM_MAP[lowered]
        out["medium_source"] = "description"
        return out
    if text:
        out["caption"] = text
    t = (title or "").lower()
    if t.startswith("gouache"):
        out["medium"], out["surface"], out["medium_source"] = "gouache", "paper", "title"
    elif t.startswith("marker"):
        out["medium"], out["surface"], out["medium_source"] = "marker", "paper", "title"
    elif series in SERIES_DEFAULT_MEDIUM:
        out["medium"], out["surface"] = SERIES_DEFAULT_MEDIUM[series]
        out["medium_source"] = "series"
    return out


def parse_keywords(keywords):
    """IPTC keywords in this collection hold sale status and size in inches."""
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
