#!/usr/bin/env python3
"""Sauvola-binarize stretched gallery crops, then equalise script scale.

Same as `mole prep --binarize sauvola --stretch --normalize-scale profile`
(window 25, k=0.2, no --max-side). For the main gallery the target is the
corpus's own median script module (42.9 px on the 313 pages). Writes
images/zoned-sauvola/ plus scale.json.

``--batch addendum`` binarizes images/addendum/zoned-stretched/ and PINS the
target to the main gallery's ``scale.json`` — the addendum must land in the
frozen gallery's scale space, never re-measure its own median.

  ~/GitRepos/mole/.venv/bin/python code/15_sauvola.py
  ~/GitRepos/mole/.venv/bin/python code/15_sauvola.py --batch addendum
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

MOLE_SRC = Path.home() / "GitRepos" / "mole" / "src"


def _import_binarize_folder():
    try:
        from mole.prep.binarize import binarize_folder
        return binarize_folder
    except ImportError:
        if MOLE_SRC.is_dir() and str(MOLE_SRC) not in sys.path:
            sys.path.insert(0, str(MOLE_SRC))
        from mole.prep.binarize import binarize_folder
        return binarize_folder


def frozen_target(scale_json: Path) -> float:
    """The main gallery's script-module target (px) from its scale.json."""
    if not scale_json.is_file():
        raise SystemExit(f"missing {scale_json} — binarize the main gallery first")
    meta = json.loads(scale_json.read_text(encoding="utf-8")).get("meta") or {}
    target = meta.get("script_module_target")
    if not target:
        raise SystemExit(f"{scale_json} has no meta.script_module_target")
    return float(target)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--target-from", type=Path, default=None,
                    help="scale.json whose script_module_target to reuse "
                         "(default for --batch addendum: the main gallery's)")
    args = ap.parse_args()
    P = batch_paths(args.batch)
    SRC, OUT = P.stretched, P.sauvola
    if not any(SRC.glob("*.png")):
        raise SystemExit(f"missing stretched crops in {SRC} — run code/14_contrast_stretch.py")
    target_from = args.target_from
    if target_from is None and args.batch != "main":
        target_from = batch_paths("main").sauvola / "scale.json"
    target = frozen_target(target_from) if target_from else None
    if target:
        print(f"pinning script module target {target:.1f} px from {target_from}")
    binarize_folder = _import_binarize_folder()
    recs = binarize_folder(
        SRC,
        OUT,
        method="sauvola",
        window=25,
        k=0.2,
        max_side=None,
        qc_html=None,
        normalize_scale="profile",
        target_module=target,
        stretch=True,
    )
    scale_path = OUT / "scale.json"
    if scale_path.is_file():
        meta = json.loads(scale_path.read_text(encoding="utf-8")).get("meta") or {}
        target = meta.get("script_module_target")
        src = meta.get("target_source")
        print(f"wrote {len(recs)} → {OUT}")
        print(f"scale.json target {target:.1f} px  ({src})" if target else f"scale.json ({src})")
    else:
        print(f"wrote {len(recs)} → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
