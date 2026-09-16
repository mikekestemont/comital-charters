#!/usr/bin/env python3
"""Print folder and filename structure of data/raw (or --src)."""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.layout import DEFAULT_SRC, discover_source, iter_images, list_copied_rows
from code.names import parse_filename

RAW = ROOT / "data" / "raw"


def _print_source(src: Path) -> None:
    layout = discover_source(src)
    print(f"src     {src}")
    print(f"layout  {layout.kind}")
    print()
    print("folder                         images")
    total = 0
    for hand, folder in layout.hands.items():
        n = sum(1 for _ in iter_images(folder))
        total += n
        print(f"  hand/{hand:<22} {n:5d}")
    if layout.unattributed is not None:
        n = sum(1 for _ in iter_images(layout.unattributed))
        total += n
        print(f"  {layout.unattributed.name:<27} {n:5d}")
    print(f"  {'TOTAL':<27} {total:5d}")


def _print_names(rows: list[dict]) -> None:
    parsed = [(r, parse_filename(r["filename"])) for r in rows]
    ok = [p for _, p in parsed if p.ok]
    bad = [r["relative_path"] for r, p in parsed if not p.ok]
    scan_explicit = sum(1 for p in ok if p.scan_explicit)
    repos = Counter(p.repository for p in ok)
    scans = Counter(p.scan_index for p in ok)
    by_fn: dict[str, list[str]] = defaultdict(list)
    for r, _ in parsed:
        by_fn[r["filename"]].append(r["folder"])
    dups = {fn: folders for fn, folders in by_fn.items() if len(folders) > 1}

    print()
    print("filename grammar")
    print(f"  parsed {len(ok)} / {len(parsed)}  explicit scan-index {scan_explicit}")
    print(f"  unparsed {len(bad)}")
    for path in bad:
        print(f"    {path}")
    print()
    print("scan index")
    for k in sorted(scans):
        print(f"  {k}: {scans[k]}")
    print()
    print("repository")
    for repo, n in repos.most_common():
        print(f"  {n:4d}  {repo}")
    print()
    print(f"duplicate filenames across folders: {len(dups)}")
    for fn, folders in sorted(dups.items()):
        print(f"  {fn}")
        print(f"    {' | '.join(folders)}")

    print()
    print("sample names (first 3 per folder)")
    by_folder: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_folder[r["folder"]].append(r["filename"])
    for folder in sorted(by_folder):
        names = sorted(by_folder[folder])[:3]
        print(f"  {folder}")
        for n in names:
            p = parse_filename(n)
            print(f"    {n}")
            print(f"      doc={p.doc_id} scan={p.scan_index} repo={p.repository!r} "
                  f"shelf={p.shelfmark!r} note={p.note!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=None,
                    help="source folder (default: data/raw if present, else mole/data/flanders)")
    args = ap.parse_args()
    if args.src is not None:
        src = args.src
    elif (RAW / "hand").is_dir():
        src = RAW
    else:
        src = DEFAULT_SRC
    _print_source(src)
    if src.resolve() == RAW.resolve() or (src / "hand").is_dir():
        rows = list_copied_rows(src if (src / "hand").is_dir() else RAW)
    else:
        layout = discover_source(src)
        rows = []
        for hand, folder in layout.hands.items():
            for img in iter_images(folder):
                rows.append({
                    "relative_path": f"hand/{hand}/{img.name}",
                    "filename": img.name,
                    "folder": f"hand/{hand}",
                    "hand_id": hand,
                })
        if layout.unattributed is not None:
            for img in iter_images(layout.unattributed):
                rows.append({
                    "relative_path": f"unattributed/{img.name}",
                    "filename": img.name,
                    "folder": "unattributed",
                    "hand_id": "",
                })
    _print_names(rows)


if __name__ == "__main__":
    main()
