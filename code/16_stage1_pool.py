#!/usr/bin/env python3
"""Assemble the stage-1 pool: frozen gallery + addendum, addendum UNLABELED.

One flat mole dataset folder, ``images/stage1-pool/``:

    313 gallery PNGs   (images/zoned-sauvola, labels as frozen: 209 hands)
     32 addendum PNGs  (images/addendum/zoned-sauvola, pinned to the same
                        42.9 px script module)  → NO label, whatever Robin said
    labels.csv         gallery labels only (PNG basenames, mole convention)
    doc_ids.csv        explicit, both batches (addendum names do not follow the
                       <n>_<scan>_… grammar mole's flanders rule expects)
    pool.csv           provenance: filename, doc_id, batch, label shown to mole
    focus.txt          the charters stage 1 is about: 32 addendum + holdout 314
    pool.json          counts, sources, date

`mole embed` (frozen fine-tuned checkpoint, ``--codebook-from`` the gallery
codebook) and `mole review` run on this folder on the GPU box; the false-
negatives tab then proposes a hand for each unlabeled addendum charter, and
17_stage1_score.py compares those proposals with data/addendum/answer_key.csv.

  python code/16_stage1_pool.py
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import batch_paths
from code.zones import zoned_name

POOL = ROOT / "images" / "stage1-pool"
HOLDOUT = ROOT / "data" / "holdout.csv"


def _copy(src: Path, dst: Path) -> None:
    try:
        subprocess.run(["cp", "-c", str(src), str(dst)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        shutil.copy2(src, dst)


def gallery_rows(batch: str) -> list[dict]:
    """main_document=1 rows of a batch's manifest, with the PNG name they became."""
    P = batch_paths(batch)
    out = []
    with P.manifest.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("main_document") != "1":
                continue
            png = P.sauvola / zoned_name(r["relative_path"])
            out.append({"filename": png.name, "src": png, "doc_id": r["doc_id"],
                        "hand_id": r.get("hand_id") or "", "batch": batch})
    return out


def main_labels() -> dict[str, str]:
    """Frozen gallery labels keyed by PNG name (hand_verdicts already applied)."""
    out = {}
    with (ROOT / "data" / "labels.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out[zoned_name(r["filename"])] = r["hand_id"]
    return out


def focus_names(addendum: list[dict], main: list[dict]) -> list[str]:
    names = [r["filename"] for r in addendum]
    if HOLDOUT.is_file():
        with HOLDOUT.open(encoding="utf-8", newline="") as fh:
            hold = {r["doc_id"] for r in csv.DictReader(fh)}
        names += [r["filename"] for r in main if r["doc_id"] in hold]
    return names


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=POOL)
    ap.add_argument("--force", action="store_true", help="rebuild an existing pool")
    args = ap.parse_args()
    out = args.out
    if out.exists():
        if not args.force:
            raise SystemExit(f"{out.relative_to(ROOT)} exists — pass --force to rebuild")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    main_rows = gallery_rows("main")
    add_rows = gallery_rows("addendum")
    labels = main_labels()
    missing = [r["src"] for r in main_rows + add_rows if not r["src"].is_file()]
    if missing:
        raise SystemExit(f"{len(missing)} Sauvola PNGs missing, e.g. {missing[0]}")
    clash = {r["filename"] for r in main_rows} & {r["filename"] for r in add_rows}
    if clash:
        raise SystemExit(f"gallery/addendum filename clash: {sorted(clash)[:5]}")

    pool_rows = []
    for r in main_rows + add_rows:
        _copy(r["src"], out / r["filename"])
        shown = labels.get(r["filename"], "") if r["batch"] == "main" else ""
        pool_rows.append({"filename": r["filename"], "doc_id": r["doc_id"],
                          "batch": r["batch"], "label_shown": shown,
                          "hand_in_folder": r["hand_id"]})

    with (out / "labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "hand_id"])
        for r in pool_rows:
            if r["label_shown"]:
                w.writerow([r["filename"], r["label_shown"]])
    with (out / "doc_ids.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "doc_id"])
        for r in pool_rows:
            w.writerow([r["filename"], r["doc_id"]])
    with (out / "pool.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pool_rows[0].keys()))
        w.writeheader()
        w.writerows(pool_rows)
    focus = focus_names(add_rows, main_rows)
    (out / "focus.txt").write_text("\n".join(focus) + "\n", encoding="utf-8")

    scale_main = json.loads((batch_paths("main").sauvola / "scale.json").read_text())["meta"]
    scale_add = json.loads((batch_paths("addendum").sauvola / "scale.json").read_text())["meta"]
    n_lab = sum(1 for r in pool_rows if r["label_shown"])
    meta = {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "purpose": "stage 1 — prospective validation; addendum charters carry no label",
        "n_images": len(pool_rows), "n_main": len(main_rows), "n_addendum": len(add_rows),
        "n_labeled": n_lab, "n_unlabeled": len(pool_rows) - n_lab, "n_focus": len(focus),
        "script_module_target_main": scale_main.get("script_module_target"),
        "script_module_target_addendum": scale_add.get("script_module_target"),
        "addendum_target_source": scale_add.get("target_source"),
        "answer_key": "data/addendum/answer_key.csv",
    }
    if scale_add.get("script_module_target") != scale_main.get("script_module_target"):
        raise SystemExit("addendum was not binarized at the gallery's script-module target "
                         "— rerun code/15_sauvola.py --batch addendum")
    (out / "pool.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"pool → {out.relative_to(ROOT)}: {len(pool_rows)} PNGs "
          f"({len(main_rows)} gallery + {len(add_rows)} addendum), "
          f"{n_lab} labeled, {len(focus)} focus charters, "
          f"script module {scale_main.get('script_module_target'):.1f} px")


if __name__ == "__main__":
    main()
