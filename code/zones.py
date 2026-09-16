"""Main-text zone helpers (Kraken BLLA + Label Studio rectangles)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None


def poly_bbox(poly) -> list[int]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def area_bbox(b) -> int:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def region_records(seg) -> list[dict]:
    out = []
    for rtype, rlist in (seg.regions or {}).items():
        for r in rlist:
            poly = [(int(x), int(y)) for x, y in r.boundary]
            if len(poly) < 3:
                continue
            tags = r.tags or {}
            t = tags.get("type") or rtype or "region"
            if isinstance(t, (list, tuple)):
                t = t[0] if t else rtype
            bbox = poly_bbox(poly)
            out.append({
                "label": str(t),
                "bbox": bbox,
                "area": area_bbox(bbox),
                "polygon": poly,
            })
    return out


def crop_largest(im: Image.Image, poly, out_path: Path) -> None:
    """Mask polygon onto white, crop to AABB, save grayscale RGB PNG."""
    w, h = im.size
    poly = [(max(0, min(int(x), w - 1)), max(0, min(int(y), h - 1))) for x, y in poly]
    gray = im.convert("L")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    box = gray.crop((x0, y0, x1, y1))
    m = mask.crop((x0, y0, x1, y1))
    out = Image.composite(box, Image.new("L", box.size, 255), m)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.convert("RGB").save(out_path, "PNG", compress_level=1)


def rect_pct(bbox, w, h) -> dict:
    x0, y0, x1, y1 = bbox
    return {
        "x": 100.0 * x0 / w,
        "y": 100.0 * y0 / h,
        "width": 100.0 * (x1 - x0) / w,
        "height": 100.0 * (y1 - y0) / h,
        "rotation": 0,
        "rectanglelabels": ["MainZone"],
    }


def ls_rect_to_bbox(val: dict, w: int, h: int) -> list[int]:
    x0 = val["x"] / 100.0 * w
    y0 = val["y"] / 100.0 * h
    x1 = x0 + val["width"] / 100.0 * w
    y1 = y0 + val["height"] / 100.0 * h
    return [int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))]


def zoned_name(relative_path: str) -> str:
    """Flat PNG name for a crop (basename only; gallery filenames are unique)."""
    return Path(relative_path).with_suffix(".png").name


def zoned_path(zoned_root: Path, relative_path: str) -> Path:
    return zoned_root / zoned_name(relative_path)


def unique_jsonl(path: Path) -> dict[str, dict]:
    last: dict[str, dict] = {}
    if not path.is_file():
        return last
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        rec = json.loads(line)
        last[rec["relative_path"]] = rec
    return last


def jsonl_records(path: Path) -> list[dict]:
    last = unique_jsonl(path)
    return [last[k] for k in sorted(last)]
