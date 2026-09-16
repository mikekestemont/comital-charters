#!/usr/bin/env python3
"""Copy original Flanders photographs into data/raw/ (gitignored).

Default source is mole's gitignored ``data/flanders`` (KA_* + unidentified).
Also accepts a folder that already has ``hand/`` + ``unattributed/``, and
Robin's addendum spellings (``KA1``, ``KA12(?)``, ``Ongeïdentificeerd``).

  python code/00_copy_raw.py
  python code/00_copy_raw.py --src /path/that/contains/hand/and/unattributed
  python code/00_copy_raw.py --batch addendum      # → data/addendum/raw/

Hand folders and their tentative flag are written to ``<data>/hand_folders.csv``
because the raw tree itself is gitignored.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import ADDENDUM_SRC, add_batch_arg, batch_paths
from code.layout import DEFAULT_SRC, SourceLayout, copy_raw, discover_source, iter_images


def write_hand_folders(layout: SourceLayout, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hand_id", "source_folder", "tentative", "n_images"])
        for hand, folder in layout.hands.items():
            n = sum(1 for _ in iter_images(folder))
            w.writerow([hand, folder.name, int(hand in layout.tentative), n])
        if layout.unattributed is not None:
            n = sum(1 for _ in iter_images(layout.unattributed))
            w.writerow(["", layout.unattributed.name, 0, n])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--src", type=Path, default=None,
                    help="default: mole/data/flanders (main) or Robin's addendum folder")
    ap.add_argument("--dest", type=Path, default=None, help="default: the batch's raw folder")
    ap.add_argument("--force", action="store_true", help="overwrite existing copies")
    args = ap.parse_args()
    P = batch_paths(args.batch)
    src = args.src or (ADDENDUM_SRC if args.batch == "addendum" else DEFAULT_SRC)
    dest = args.dest or P.raw

    layout = discover_source(src)
    n_hand = sum(sum(1 for _ in iter_images(p)) for p in layout.hands.values())
    n_un = sum(1 for _ in iter_images(layout.unattributed)) if layout.unattributed else 0
    print(f"src     {src}")
    print(f"layout  {layout.kind}")
    print(f"hands   {', '.join(layout.hands) or '(none)'}")
    if layout.tentative:
        print(f"tentative hands (folder ends in '(?)'): {', '.join(sorted(layout.tentative))}")
    print(f"images  {n_hand} attributed  {n_un} unattributed")

    stats = copy_raw(src, dest, force=args.force)
    print(f"dest    {stats['dest']}")
    print(f"copied  {stats['copied']}  skipped {stats['skipped']}  "
          f"unattributed identical not copied {stats['unattributed_identical_skipped']}")
    hf = P.data / "hand_folders.csv"
    write_hand_folders(layout, hf)
    print(f"hands   → {hf.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
