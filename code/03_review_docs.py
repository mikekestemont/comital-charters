#!/usr/bin/env python3
"""HTML review of multi-scan charters (sluis neardup_review.html analogue).

Siblings are already decided from the filename (lowest scan index kept).
This page is for visual confirmation, plus folder-duplicate / hand-conflict
copies. Pixels are never deleted.

  python code/03_review_docs.py
  open outputs/doc_review.html
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.csv"
OUT_HTML = ROOT / "outputs" / "doc_review.html"
THUMB = 280


def jpeg_b64(path: Path, long=THUMB, quality=72) -> str:
    im = Image.open(path).convert("RGB")
    im.thumbnail((long, long))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    args = ap.parse_args()
    if not args.manifest.is_file():
        raise SystemExit(f"missing {args.manifest} — run code/02_group_docs.py first")

    rows = list(csv.DictReader(args.manifest.open(encoding="utf-8")))
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("parse_ok") == "1" and r.get("doc_id"):
            by_doc[r["doc_id"]].append(r)

    groups = []
    for doc_id, members in sorted(by_doc.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0]):
        n_fn = len({m["filename"] for m in members})
        n_path = len(members)
        if n_fn < 2 and n_path < 2:
            continue
        members = sorted(members, key=lambda r: (int(r["scan_index"]), r["folder"], r["filename"]))
        items = []
        for r in members:
            path = args.raw / r["relative_path"]
            thumb = jpeg_b64(path) if path.is_file() else ""
            items.append({
                "name": r["filename"],
                "path": r["relative_path"],
                "folder": r["folder"],
                "hand": r.get("hand_id") or "",
                "scan": int(r["scan_index"]),
                "repo": r.get("repository") or "",
                "shelf": r.get("shelfmark") or "",
                "note": r.get("note") or "",
                "reason": r.get("reason") or "",
                "role": "keep" if r.get("main_document") == "1" else "drop",
                "thumb": thumb,
            })
        keep = next((r["filename"] for r in members if r.get("main_document") == "1"), members[0]["filename"])
        groups.append({
            "id": f"doc-{doc_id}",
            "doc_id": doc_id,
            "n": len(members),
            "n_filenames": n_fn,
            "keep": keep,
            "repo": members[0].get("repository") or "",
            "shelf": members[0].get("shelfmark") or "",
            "hands": "|".join(sorted({r["hand_id"] for r in members if r.get("hand_id")})),
            "items": items,
        })

    html = r"""<!DOCTYPE html>
<meta charset="utf-8">
<title>Comital sibling-scan review</title>
<style>
  :root { --fg:#eee; --mut:#9a9a9a; --acc:#6ae; --bg:#111; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.4 system-ui, sans-serif; background: var(--bg); color: var(--fg); }
  header { position: sticky; top: 0; z-index: 2; background: #1a1a1a; border-bottom: 1px solid #333;
           padding: 12px 20px; }
  h1 { font-size: 16px; margin: 0; font-weight: 600; }
  .sub { color: var(--mut); font-size: 13px; margin-top: 4px; }
  #sheet { padding: 16px 20px 64px; }
  .card { padding: 14px 0; border-bottom: 1px solid #2a2a2a; }
  .meta { font: 12px ui-monospace, monospace; color: var(--mut); margin-bottom: 8px; }
  .meta b { color: var(--fg); font-size: 14px; }
  .thumbs { display: flex; gap: 10px; flex-wrap: wrap; }
  .thumbs figure { margin: 0; width: min(280px, 30vw); }
  .thumbs img { width: 100%; display: block; border-radius: 4px; background: #222; }
  .thumbs figcaption { font: 11px ui-monospace, monospace; color: var(--mut); margin-top: 4px; }
  .k { color: #8c8; }
  .d { color: #c88; }
</style>
<header>
  <h1>Sibling-scan review</h1>
  <div class="sub">Grouped by inventory number in the filename. Lowest scan index is
    <span class="k">KEEP</span> (main_document=1). Other photographs stay on disk as
    <span class="d">sibling_scan_of</span> / <span class="d">duplicate_path_of</span>.
    __N__ groups.</div>
</header>
<div id="sheet"></div>
<script>
const ITEMS = __PAYLOAD__;
const sheet = document.getElementById("sheet");
sheet.innerHTML = ITEMS.map(it => {
  const figs = it.items.map(p => {
    const role = p.role === "keep" ? "k" : "d";
    const lab = p.role === "keep" ? "KEEP" : (p.reason || "drop");
    const img = p.thumb
      ? "<img src='data:image/jpeg;base64," + p.thumb + "'>"
      : "<div style='height:80px;background:#222'></div>";
    return "<figure>" + img + "<figcaption><span class='" + role + "'>" + lab + "</span><br>"
      + p.name + "<br>" + p.folder + (p.hand ? " · " + p.hand : "")
      + "<br>scan " + p.scan
      + (p.note ? " · " + p.note : "") + "</figcaption></figure>";
  }).join("");
  return "<div class='card'><div class='meta'><b>doc " + it.doc_id + "</b> · "
    + it.n + " files / " + it.n_filenames + " names · " + it.repo + " " + it.shelf
    + (it.hands ? " · " + it.hands : "")
    + "<br>keep " + it.keep + "</div><div class='thumbs'>" + figs + "</div></div>";
}).join("");
</script>
"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        html.replace("__PAYLOAD__", json.dumps(groups)).replace("__N__", str(len(groups))),
        encoding="utf-8",
    )
    print(f"groups {len(groups)}")
    print(f"review → {args.out}  ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
