#!/usr/bin/env python3
"""Group sibling scans from filenames. Files stay on disk; flags go in CSVs.

Writes:
  data/manifest.csv
  data/doc_groups.csv
  data/labels.csv
  data/doc_ids.csv
  data/shelfmark_collisions.csv
  data/folder_duplicates.csv
  data/dropped_unattributed.csv

`data/hand_verdicts.csv` (if present) overrides folder attribution for
charters that sit in more than one KA_* folder.

``--batch addendum`` does the same for data/addendum/raw → data/addendum/.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.group import (
    annotate_rows,
    assign_main_documents,
    doc_groups_rows,
    doc_ids_rows,
    folder_duplicates,
    labels_rows,
    shelfmark_collisions,
)
from code.batch import add_batch_arg, batch_paths
from code.layout import drop_unattributed_identical, list_copied_rows

MANIFEST_FIELDS = [
    "relative_path", "filename", "folder", "hand_id", "doc_id", "scan_index",
    "scan_explicit", "repository", "shelfmark", "note", "main_document",
    "reason", "parse_ok", "collision_key",
]


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {len(rows):5d} → {path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--raw", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    P = batch_paths(args.batch)
    args.raw = args.raw or P.raw
    args.out = args.out or P.data
    if not (args.raw / "hand").is_dir() and not (args.raw / "unattributed").is_dir():
        raise SystemExit(f"missing {args.raw}/hand or unattributed — run code/00_copy_raw.py first")

    dropped = drop_unattributed_identical(args.raw)
    if dropped:
        print(f"dropped {len(dropped)} unattributed copies identical to a hand folder")
    rows = assign_main_documents(annotate_rows(list_copied_rows(args.raw)))
    n_main = sum(1 for r in rows if r["main_document"] == "1")
    n_sib = sum(1 for r in rows if r["reason"].startswith("sibling_scan_of="))
    n_dup = sum(1 for r in rows if r["reason"].startswith("duplicate_path_of="))
    n_file = sum(1 for r in rows if r["reason"].startswith("duplicate_file_of="))
    labels = labels_rows(rows)
    groups = doc_groups_rows(rows)
    multi = [g for g in groups if int(g["n_filenames"]) > 1]
    coll = shelfmark_collisions(rows)
    dups = folder_duplicates(rows)

    print(f"files {len(rows)}  main_document=1 {n_main}  sibling extras {n_sib}  "
          f"path copies {n_dup}  file copies {n_file}")
    print(f"docs {len(groups)}  multi-scan {len(multi)}  labels {len(labels)}  "
          f"shelfmark collisions {len(coll)}  folder dups {len(dups)}")
    _write(args.out / "manifest.csv", rows, MANIFEST_FIELDS)
    _write(args.out / "doc_groups.csv", groups,
           ["doc_id", "n_files", "n_filenames", "n_scans", "keep_filename",
            "drop_filenames", "hands", "repository", "shelfmark", "main_relative_path"])
    _write(args.out / "labels.csv", labels, ["filename", "hand_id"])
    _write(args.out / "doc_ids.csv", doc_ids_rows(rows), ["filename", "doc_id"])
    _write(args.out / "shelfmark_collisions.csv", coll,
           ["collision_key", "repository", "shelfmark", "doc_ids", "n_docs", "filenames"])
    _write(args.out / "folder_duplicates.csv", dups,
           ["filename", "n_copies", "folders", "hands", "conflict"])
    _write(args.out / "dropped_unattributed.csv", dropped,
           ["filename", "dropped_path", "kept_path", "hand_id", "sha256"])


if __name__ == "__main__":
    main()
