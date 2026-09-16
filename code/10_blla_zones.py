#!/usr/bin/env python3
"""Kraken BLLA text zones on data/raw/ (gallery: main_document=1).

Keep the largest region (bbox area), not the union. Do not binarize.
Resume-safe: data/zones_blla.jsonl is appended after each page.

Kraken lives in the sluis env on this machine:

  conda activate sluis
  python code/10_blla_zones.py --device mps
  python code/10_blla_zones.py --device mps --batch addendum
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import logging
import os
import sys
import warnings
from pathlib import Path

from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths
from code.zones import (
    crop_largest,
    jsonl_records,
    region_records,
    unique_jsonl,
    zoned_path,
)

# Batch paths; `configure()` switches them (13_apply_ls_zones.py does so too).
P = batch_paths("main")


def configure(batch: str) -> None:
    global P
    P = batch_paths(batch)

logging.getLogger("kraken").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*Polygonizer.*")


def gallery_rows(all_pages: bool) -> list[dict]:
    rows = list(csv.DictReader(P.manifest.open(encoding="utf-8")))
    if all_pages:
        return rows
    return [r for r in rows if r.get("main_document") == "1"]


def compile_manifests() -> None:
    entries = unique_jsonl(P.zones_jsonl)
    images = {}
    csv_rows = []
    for rel, rec in sorted(entries.items()):
        images[rel] = {
            "bbox": rec["bbox"],
            "size": rec["size"],
            "fell_back": rec["fell_back"],
            "detections": rec["detections"],
            "polygon": rec.get("polygon"),
            "n_regions": rec.get("n_regions", 0),
            "main_document": rec.get("main_document"),
            "filename": rec.get("filename"),
        }
        b = rec["bbox"] or [None, None, None, None]
        csv_rows.append({
            "relative_path": rel,
            "filename": rec.get("filename", ""),
            "main_document": rec.get("main_document"),
            "fell_back": int(rec["fell_back"]),
            "n_regions": rec.get("n_regions", 0),
            "x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3],
            "width": rec["size"][0], "height": rec["size"][1],
        })
    meta = {
        "detector": "blla",
        "model": "kraken/blla.mlmodel",
        "rule": "largest-region-by-bbox-area",
        "source": P.raw.relative_to(ROOT).as_posix(),
        "crop_dir": P.zoned.relative_to(ROOT).as_posix(),
        "batch": P.name,
        "n": len(images),
    }
    P.zones_json.parent.mkdir(parents=True, exist_ok=True)
    P.zones_json.write_text(json.dumps({"meta": meta, "images": images}, indent=2), encoding="utf-8")
    with P.zones_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()) if csv_rows else ["relative_path"])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"zones.json {P.zones_json.relative_to(ROOT)}  ({len(images)} pages)")
    print(f"zones.csv  {P.zones_csv.relative_to(ROOT)}")


def jpeg_b64(im: Image.Image, long=260, quality=70) -> str:
    t = im.copy()
    t.thumbnail((long, long))
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def draw_overlay(path: Path, rec: dict, long=320) -> Image.Image:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    scale = long / max(w, h)
    disp = im.resize((max(1, round(w * scale)), max(1, round(h * scale))))
    draw = ImageDraw.Draw(disp)
    for d in rec.get("detections") or []:
        x0, y0, x1, y1 = [c * scale for c in d[2:6]]
        draw.rectangle((x0, y0, x1, y1), outline="#ff9f1c", width=2)
    if rec.get("bbox"):
        x0, y0, x1, y1 = [c * scale for c in rec["bbox"]]
        draw.rectangle((x0, y0, x1, y1), outline="#39d353", width=4)
    return disp


def build_qc(limit: int | None = None) -> None:
    recs = jsonl_records(P.zones_jsonl)
    recs.sort(key=lambda r: (
        -int(r.get("n_regions") or 0),
        int(r.get("fell_back") or 0),
        r.get("relative_path") or "",
    ))
    if limit:
        recs = recs[:limit]
    payload = []
    for rec in recs:
        src = P.raw / rec["relative_path"]
        crop = zoned_path(P.zoned, rec["relative_path"])
        overlay = draw_overlay(src, rec) if src.is_file() else Image.new("RGB", (32, 32), 32)
        crop_im = Image.open(crop).convert("RGB") if crop.is_file() else overlay
        payload.append({
            "name": rec["relative_path"],
            "n": rec.get("n_regions", 0),
            "fell_back": rec.get("fell_back", False),
            "main": rec.get("main_document"),
            "bbox": rec.get("bbox"),
            "overlay": jpeg_b64(overlay),
            "crop": jpeg_b64(crop_im),
        })
    html = r"""<!DOCTYPE html>
<meta charset="utf-8">
<title>Zone review (BLLA, largest region)</title>
<style>
  :root { --fg:#eee; --mut:#9a9a9a; --acc:#e66; --bg:#111; }
  body { margin: 0; font: 14px/1.4 system-ui, sans-serif; background: var(--bg); color: var(--fg); }
  header { position: sticky; top: 0; z-index: 2; background: #1a1a1a; border-bottom: 1px solid #333;
           padding: 12px 20px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  h1 { font-size: 16px; margin: 0; }
  .sub { color: var(--mut); font-size: 13px; }
  button { background: #333; color: var(--fg); border: 1px solid #555; border-radius: 6px;
           padding: 6px 12px; cursor: pointer; font: inherit; }
  #sheet { padding: 16px 20px 64px; }
  .card { display: grid; grid-template-columns: 220px 1fr 1fr; gap: 12px; align-items: start;
          padding: 12px 0; border-bottom: 1px solid #2a2a2a; cursor: pointer; }
  .card.on { background: #281414; outline: 1px solid var(--acc); }
  .card img { width: 100%; max-width: 320px; display: block; border-radius: 4px; background: #222; }
  .meta { font: 12px ui-monospace, monospace; color: var(--mut); }
  .meta b { color: var(--fg); font-size: 14px; }
  .tag { display: inline-block; margin-top: 8px; padding: 2px 8px; border-radius: 999px; font-size: 11px; }
  .tag.ok { background: #333; }
  .tag.bad { background: var(--acc); color: #111; font-weight: 600; }
  .tag.fb { background: #3a3a00; color: #ee8; }
  .lbl { font-size: 11px; color: var(--mut); margin-bottom: 4px; }
</style>
<header>
  <div>
    <h1>Zone review — Kraken BLLA, largest region</h1>
    <div class="sub">Green box = kept zone. Orange = other BLLA regions (discarded).
      Click / Space = <b>correct later</b>. Unmarked = accept. j / k move.
      Sorted: most regions first, then fallbacks. Fine correction is in Label Studio.</div>
  </div>
  <div class="sub" id="stats"></div>
  <button type="button" id="export">Export CSV</button>
  <button type="button" id="clear">Clear marks</button>
</header>
<div id="sheet"></div>
<script>
const ITEMS = __PAYLOAD__;
const KEY = "comital-zones-blla-v1-__BATCH__";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { marks = {}; }
let focus = 0;
function save() { localStorage.setItem(KEY, JSON.stringify(marks)); stats(); }
function isOn(n) { return !!marks[n]; }
function stats() {
  const m = ITEMS.filter(it => isOn(it.name)).length;
  document.getElementById("stats").textContent = m + " marked correct / " + ITEMS.length + " shown";
}
function render() {
  const sheet = document.getElementById("sheet");
  sheet.innerHTML = ITEMS.map((it, i) => {
    const on = isOn(it.name);
    const fb = it.fell_back ? "<span class='tag fb'>full-page fallback</span> " : "";
    const tag = on ? "<span class='tag bad'>CORRECT later</span>" : "<span class='tag ok'>accept largest</span>";
    const bb = (it.bbox || []).join(",");
    return `<div class="card ${on?"on":""}" data-i="${i}" id="c${i}">
      <div class="meta"><b>${it.name}</b><br>regions ${it.n} · gallery ${it.main}${fb}<br>bbox [${bb}]<br>${tag}</div>
      <div><div class="lbl">page (green = kept)</div><img src="data:image/jpeg;base64,${it.overlay}"></div>
      <div><div class="lbl">cutout</div><img src="data:image/jpeg;base64,${it.crop}"></div>
    </div>`;
  }).join("");
  sheet.querySelectorAll(".card").forEach(el => el.addEventListener("click", () => toggle(+el.dataset.i)));
  highlight(); stats();
}
function toggle(i) {
  const n = ITEMS[i].name;
  if (marks[n]) delete marks[n]; else marks[n] = 1;
  focus = i; save();
  const el = document.getElementById("c"+i);
  el.classList.toggle("on", isOn(n));
  const tag = el.querySelector(".tag.ok, .tag.bad");
  if (tag && !tag.classList.contains("fb")) {
    tag.className = "tag " + (isOn(n) ? "bad" : "ok");
    tag.textContent = isOn(n) ? "CORRECT later" : "accept largest";
  }
}
function highlight() {
  document.querySelectorAll(".card").forEach((el, i) => {
    el.style.boxShadow = i === focus ? "inset 3px 0 0 #6ae" : "";
  });
}
function goto(i) {
  focus = Math.max(0, Math.min(ITEMS.length - 1, i));
  highlight();
  document.getElementById("c"+focus).scrollIntoView({block: "nearest"});
}
document.getElementById("export").onclick = () => {
  const lines = ["relative_path,correct,n_regions,fell_back,main_document,bbox"];
  ITEMS.forEach(it => lines.push([JSON.stringify(it.name), isOn(it.name)?1:0, it.n, it.fell_back?1:0, it.main,
    (it.bbox||[]).join(" ")].join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n")], {type: "text/csv"}));
  a.download = "zone_decisions.csv";
  a.click();
};
document.getElementById("clear").onclick = () => {
  if (!confirm("Clear all correction marks?")) return;
  marks = {}; save(); render();
};
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); goto(focus + 1); }
  if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); goto(focus - 1); }
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(focus); }
});
render();
</script>
"""
    P.zone_review.parent.mkdir(parents=True, exist_ok=True)
    html = html.replace("__BATCH__", P.name).replace("__PAYLOAD__", json.dumps(payload))
    P.zone_review.write_text(html, encoding="utf-8")
    print(f"review → {P.zone_review.relative_to(ROOT)}  "
          f"({P.zone_review.stat().st_size/1e6:.1f} MB, {len(payload)} pages)")


def pick_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def run(limit: int | None, device: str, qc_every: int, all_pages: bool) -> None:
    from kraken import blla
    from kraken.lib import vgsl
    from tqdm import tqdm

    if not P.manifest.is_file():
        raise SystemExit(f"missing {P.manifest} — run code/02_group_docs.py first")
    rows = gallery_rows(all_pages)
    todo_meta = []
    done = set(unique_jsonl(P.zones_jsonl))
    for r in rows:
        rel = r["relative_path"]
        src = P.raw / rel
        if not src.is_file():
            continue
        if rel in done:
            continue
        todo_meta.append(r)
        if limit and len(todo_meta) >= limit:
            break
    print(f"gallery {len(rows)}  already {len(done)}  todo {len(todo_meta)}  device {device}")
    if not todo_meta:
        compile_manifests()
        build_qc()
        return

    import kraken as _k
    model_path = Path(_k.__file__).parent / "blla.mlmodel"
    seg_model = vgsl.TorchVGSLModel.load_model(str(model_path))
    print(f"loaded {model_path}")

    P.zoned.mkdir(parents=True, exist_ok=True)
    P.zones_jsonl.parent.mkdir(parents=True, exist_ok=True)
    n_done = 0
    with P.zones_jsonl.open("a", encoding="utf-8") as fh:
        for r in tqdm(todo_meta, desc="BLLA", unit="page"):
            rel = r["relative_path"]
            src = P.raw / rel
            im = Image.open(src).convert("RGB")
            w, h = im.size
            recs = []
            err = ""
            try:
                seg = blla.segment(im, model=seg_model, device=device, raise_on_error=False)
                recs = region_records(seg)
            except Exception as e:
                err = str(e)
            recs.sort(key=lambda rec: -rec["area"])
            fell_back = not recs
            if fell_back:
                poly = [(0, 0), (w, 0), (w, h), (0, h)]
                bbox = [0, 0, w, h]
            else:
                poly = recs[0]["polygon"]
                bbox = recs[0]["bbox"]
            crop_largest(im, poly, zoned_path(P.zoned, rel))
            row = {
                "relative_path": rel,
                "filename": r["filename"],
                "size": [w, h],
                "bbox": bbox,
                "polygon": poly,
                "fell_back": fell_back,
                "n_regions": len(recs),
                "detections": [[rec["label"], 1.0, *rec["bbox"]] for rec in recs],
                "main_document": r.get("main_document"),
                "error": err,
            }
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            n_done += 1
            if qc_every and n_done % qc_every == 0:
                compile_manifests()
                try:
                    build_qc(limit=80)
                except Exception:
                    pass

    compile_manifests()
    build_qc()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_batch_arg(ap)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--device", default="auto", help="auto|cpu|mps|cuda:0")
    ap.add_argument("--all", action="store_true", help="every file, not only main_document=1")
    ap.add_argument("--qc-only", action="store_true")
    ap.add_argument("--qc-every", type=int, default=40)
    ap.add_argument("--qc-limit", type=int, default=None)
    args = ap.parse_args()
    configure(args.batch)
    os.chdir(ROOT)
    if args.qc_only:
        compile_manifests()
        build_qc(limit=args.qc_limit)
        return
    run(limit=args.limit, device=pick_device(args.device),
        qc_every=args.qc_every, all_pages=args.all)


if __name__ == "__main__":
    main()
