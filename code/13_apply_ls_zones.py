#!/usr/bin/env python3
"""Apply a Label Studio export back onto zones + recrop.

LS rectangles are percentages. Pixel boxes are taken from the full-resolution
photograph in data/raw/. Edited boxes replace bbox and become a 4-corner
polygon. Then recrop.

  python code/12_ls_export.py
  python code/13_apply_ls_zones.py --export data/ls_zones_export.json
  python code/13_apply_ls_zones.py --batch addendum   # default export of that batch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths
from code.zones import crop_largest, ls_rect_to_bbox, unique_jsonl, zoned_path


def task_relative_path(task: dict, raw_prefix: str = "data/raw/") -> str | None:
    data = task.get("data") or task
    rel = (data.get("relative_path") or "").strip()
    if rel:
        return rel
    fn = data.get("filename") or ""
    if raw_prefix in fn.replace("\\", "/"):
        return fn.replace("\\", "/").split(raw_prefix, 1)[1]
    img = data.get("image") or ""
    if raw_prefix in img:
        return img.split(raw_prefix, 1)[-1].split("?")[0]
    return None


def regions_from_task(task: dict) -> list[dict]:
    anns = task.get("annotations") or []
    if not anns and "label" in task:
        return [r for r in (task.get("label") or []) if "width" in r]
    result = []
    for ann in anns:
        if ann.get("was_cancelled"):
            continue
        for item in ann.get("result") or []:
            val = item.get("value") or {}
            if "width" in val and "height" in val:
                result.append(val)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--export", type=Path, default=None, help="default: the batch's LS export")
    args = ap.parse_args()
    P = batch_paths(args.batch)
    args.export = args.export or P.ls_export
    export = json.loads(args.export.read_text(encoding="utf-8"))
    if not isinstance(export, list):
        raise SystemExit("expected a JSON list (JSON-MIN or full export)")
    by = unique_jsonl(P.zones_jsonl)
    changed = 0
    for task in export:
        rel = task_relative_path(task, P.raw_prefix)
        if not rel or rel not in by:
            continue
        rec = by[rel]
        w, h = rec["size"]
        regs = regions_from_task(task)
        if not regs:
            rec["fell_back"] = True
            rec["bbox"] = [0, 0, w, h]
            rec["polygon"] = [[0, 0], [w, 0], [w, h], [0, h]]
        else:
            boxes = [ls_rect_to_bbox(v, w, h) for v in regs]
            bbox = max(boxes, key=lambda b: max(0, b[2] - b[0]) * max(0, b[3] - b[1]))
            rec["fell_back"] = False
            rec["bbox"] = bbox
            x0, y0, x1, y1 = bbox
            rec["polygon"] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        src = P.raw / rel
        if src.is_file():
            im = Image.open(src).convert("RGB")
            crop_largest(im, rec["polygon"], zoned_path(P.zoned, rel))
        by[rel] = rec
        changed += 1
    P.zones_jsonl.write_text("".join(json.dumps(by[k]) + "\n" for k in sorted(by)), encoding="utf-8")
    from importlib.machinery import SourceFileLoader
    blla = SourceFileLoader("blla_zones", str(ROOT / "code" / "10_blla_zones.py")).load_module()
    blla.configure(P.name)
    blla.compile_manifests()
    print(f"updated {changed} pages from {args.export}")
    print(f"rewrote {P.zones_jsonl}")


if __name__ == "__main__":
    main()
