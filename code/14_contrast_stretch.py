#!/usr/bin/env python3
"""Percentile stretch on gallery zone crops (p2→20, p98→255).

Same mapping as sluis stage 14. Writes images/zoned-stretched/ as a flat
folder of PNG basenames. Interior polygon only; white AABB fill is ignored.

  python code/14_contrast_stretch.py
  python code/14_contrast_stretch.py --batch addendum
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths
from code.zones import zoned_path

P_LO, P_HI = 2.0, 98.0
OUT_LO, OUT_HI = 20, 255
MIN_SPAN = 8


def interior_mask(gray: np.ndarray, rec: dict) -> np.ndarray:
    h, w = gray.shape
    bbox = rec.get("bbox") or [0, 0, w, h]
    x0, y0, x1, y1 = (int(v) for v in bbox)
    poly = rec.get("polygon") or [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    pts = [(int(x) - x0, int(y) - y0) for x, y in poly]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.asarray(m) == 255


def stretch_array(gray: np.ndarray, interior: np.ndarray) -> np.ndarray:
    pix = gray[interior]
    if int(pix.size) < 100:
        return gray.copy()
    lo, hi = np.percentile(pix, [P_LO, P_HI])
    span = float(hi - lo)
    out = gray.copy()
    if span < MIN_SPAN:
        return out
    scale = (OUT_HI - OUT_LO) / span
    mapped = np.clip(np.round(OUT_LO + (gray.astype(np.float32) - lo) * scale), 0, 255)
    out[interior] = mapped[interior].astype(np.uint8)
    return out


def gallery_keys(zones: dict, zoned: Path) -> list[str]:
    keys = []
    for rel, rec in zones.items():
        if str(rec.get("main_document")) != "1":
            continue
        if zoned_path(zoned, rel).is_file():
            keys.append(rel)
    return sorted(keys)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    args = ap.parse_args()
    P = batch_paths(args.batch)
    if not P.zones_json.is_file():
        raise SystemExit(f"missing {P.zones_json}")
    zones = json.loads(P.zones_json.read_text(encoding="utf-8"))["images"]
    keys = gallery_keys(zones, P.zoned)
    if not keys:
        raise SystemExit(f"no gallery crops in {P.zoned}")
    OUT = P.stretched
    n = 0
    for i, rel in enumerate(keys, 1):
        rec = zones[rel]
        src = zoned_path(P.zoned, rel)
        gray = np.asarray(Image.open(src).convert("L"))
        out = stretch_array(gray, interior_mask(gray, rec))
        dest = zoned_path(OUT, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(out).convert("RGB").save(dest, "PNG", compress_level=1)
        n += 1
        if i % 50 == 0 or i == len(keys):
            print(f"  stretched {i}/{len(keys)}")
    print(f"wrote {n} → {OUT}  (p2→{OUT_LO}, p98→{OUT_HI})")


if __name__ == "__main__":
    sys.exit(main())
