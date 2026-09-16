#!/usr/bin/env python3
"""Seal Robin's addendum identifications as the stage-1 answer key.

Robin labeled the addendum before the software saw a single one of its
photographs; that is what makes it a prospective test. The key is written
once from the addendum manifest + hand_folders.csv and committed. The
software only ever sees the addendum as *unattributed* (see 16_stage1_pool.py)
and its proposals are scored against this file afterwards.

  status   confirmed    hand from a KA_n folder
           tentative    hand from a KA_n(?) folder (656 + 709, "mogelijk
                        eenzelfde hand, een 12e kanselarijhand", no
                        paleographic confirmation yet)
           unidentified Ongeïdentificeerd/

Charter 314 (main batch, data/holdout.csv) is the earlier known-miss holdout
and is appended so stage 1 scores both in one table.

  python code/04_answer_key.py --batch addendum
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths

FIELDS = ["doc_id", "filename", "hand_id", "status", "batch", "source", "note"]
SOURCE = "Robin Waeytens, addendum e-mail 2026-09 (KESTEMONT-WAEYTENS_Corpus-Margareta1270_Addendum)"
HOLDOUT = ROOT / "data" / "holdout.csv"


def tentative_hands(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["hand_id"] for r in csv.DictReader(fh)
                if r.get("hand_id") and r.get("tentative") == "1"}


def answer_rows(manifest: Path, tentative: set[str], batch: str) -> list[dict]:
    rows = []
    with manifest.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("main_document") != "1":
                continue
            hand = r.get("hand_id") or ""
            if not hand:
                status, note = "unidentified", ""
            elif hand in tentative:
                status = "tentative"
                note = "folder KA12(?): mogelijk eenzelfde hand (12e kanselarijhand?), nog niet paleografisch bevestigd"
            else:
                status, note = "confirmed", ""
            rows.append({
                "doc_id": r["doc_id"], "filename": r["filename"], "hand_id": hand,
                "status": status, "batch": batch, "source": SOURCE, "note": note,
            })
    rows.sort(key=lambda r: int(r["doc_id"]))
    return rows


def holdout_rows() -> list[dict]:
    if not HOLDOUT.is_file():
        return []
    out = []
    with HOLDOUT.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out.append({
                "doc_id": r["doc_id"], "filename": r["filename"],
                "hand_id": r["expected_hand_id"], "status": "confirmed", "batch": "main",
                "source": r.get("source", ""), "note": r.get("note", ""),
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--force", action="store_true", help="overwrite a sealed key")
    args = ap.parse_args()
    P = batch_paths(args.batch)
    out = args.out or P.data / "answer_key.csv"
    if out.is_file() and not args.force:
        raise SystemExit(f"{out.relative_to(ROOT)} already sealed — pass --force to rewrite it")
    rows = answer_rows(P.manifest, tentative_hands(P.data / "hand_folders.csv"), args.batch)
    rows += holdout_rows()
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"sealed {dt.date.today().isoformat()}  {len(rows)} charters → {out.relative_to(ROOT)}")
    print("  " + "  ".join(f"{k} {v}" for k, v in sorted(by_status.items())))


if __name__ == "__main__":
    main()
