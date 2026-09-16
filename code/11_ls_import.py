#!/usr/bin/env python3
"""Build a Label Studio import JSON from BLLA zones.

Each task is a raw photograph with one pre-drawn MainZone rectangle (the
largest BLLA region). Import as annotations so pages start 'done'; edit and
Update only the ones that need it. Do not Skip empties.

Requires Label Studio started with local-file serving from this repo:

  export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
  export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=$PWD
  conda activate bayes
  label-studio start

Then: create project → paste data/ls_config.xml → Import
data/ls_zones_import.json  (``--batch addendum``: project "comital-addendum",
data/addendum/ls_zones_import.json)

In the project: Settings → Cloud Storage → Add Source Storage
  Type: Local files
  Absolute local path: $PWD/data
  Treat selection as: Files
  Save. Do not Sync.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths
from code.zones import jsonl_records, rect_pct

DOC_ROOT = ROOT


def repo_rel(relative_path: str, raw_prefix: str = "data/raw/") -> str:
    rel = relative_path if relative_path.startswith("data/") else f"{raw_prefix}{relative_path}"
    return (DOC_ROOT / rel).resolve().relative_to(DOC_ROOT.resolve()).as_posix()


def main() -> None:
    ap = argparse.ArgumentParser()
    add_batch_arg(ap)
    ap.add_argument("--all", action="store_true", help="include main_document=0 as well")
    args = ap.parse_args()
    P = batch_paths(args.batch)
    if not P.zones_jsonl.is_file():
        raise SystemExit(f"missing {P.zones_jsonl}")
    recs = jsonl_records(P.zones_jsonl)
    if not args.all:
        recs = [r for r in recs if str(r.get("main_document")) == "1"]
    tasks = []
    n_empty = 0
    for rec in recs:
        rel = repo_rel(rec["relative_path"], P.raw_prefix)
        w, h = rec["size"]
        result = []
        if rec.get("bbox") and not rec.get("fell_back"):
            result.append({
                "original_width": w,
                "original_height": h,
                "image_rotation": 0,
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "origin": "prediction",
                "value": rect_pct(rec["bbox"], w, h),
            })
        else:
            n_empty += 1
        tasks.append({
            "data": {
                "image": f"/data/local-files/?d={rel}",
                "filename": rel,
                "main_document": rec.get("main_document"),
                "n_regions": rec.get("n_regions", 0),
                "fell_back": rec.get("fell_back", False),
            },
            "annotations": [{"result": result}],
        })
    P.ls_import.parent.mkdir(parents=True, exist_ok=True)
    P.ls_import.write_text(json.dumps(tasks, indent=None), encoding="utf-8")
    print(f"tasks {len(tasks)}  with box {len(tasks)-n_empty}  empty/fallback {n_empty}")
    print(f"wrote {P.ls_import}")
    print(f"label config: {ROOT / 'data' / 'ls_config.xml'}   LS project title: {P.ls_project}")


if __name__ == "__main__":
    main()
