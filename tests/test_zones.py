"""BLLA / Label Studio zone geometry (no kraken required)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from code.zones import (
    area_bbox,
    crop_largest,
    ls_rect_to_bbox,
    poly_bbox,
    rect_pct,
    unique_jsonl,
    zoned_path,
)


def test_rect_pct_roundtrip():
    bbox = [10, 20, 110, 220]
    pct = rect_pct(bbox, 200, 400)
    assert pct["rectanglelabels"] == ["MainZone"]
    back = ls_rect_to_bbox(pct, 200, 400)
    assert back == bbox


def test_poly_bbox_and_area():
    b = poly_bbox([(3, 8), (10, 1), (4, 9)])
    assert b == [3, 1, 10, 9]
    assert area_bbox(b) == 7 * 8


def test_crop_largest_masks_outside_polygon(tmp_path: Path):
    im = Image.new("RGB", (20, 20), (0, 0, 0))
    for x in range(20):
        for y in range(20):
            im.putpixel((x, y), (x * 10, y * 10, 0))
    out = tmp_path / "cut.png"
    crop_largest(im, [(5, 5), (15, 5), (15, 15), (5, 15)], out)
    cut = Image.open(out)
    assert cut.size == (10, 10)
    # corner of crop is on the polygon interior (not forced white)
    assert cut.getpixel((1, 1))[0] > 0


def test_import_and_apply_roundtrip(tmp_path: Path):
    jsonl = tmp_path / "zones_blla.jsonl"
    rec = {
        "relative_path": "hand/KA_8/demo.jpeg",
        "filename": "demo.jpeg",
        "size": [200, 100],
        "bbox": [10, 10, 90, 90],
        "polygon": [[10, 10], [90, 10], [90, 90], [10, 90]],
        "fell_back": False,
        "n_regions": 1,
        "detections": [["text", 1.0, 10, 10, 90, 90]],
        "main_document": "1",
    }
    jsonl.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    by = unique_jsonl(jsonl)
    assert list(by) == ["hand/KA_8/demo.jpeg"]
    pct = rect_pct(rec["bbox"], 200, 100)
    # reviewer shrinks the box
    pct["x"], pct["width"] = 20.0, 30.0
    new_bbox = ls_rect_to_bbox(pct, 200, 100)
    assert new_bbox[0] == 40 and new_bbox[2] == 100
    assert zoned_path(tmp_path / "zoned", rec["relative_path"]).name == "demo.png"
