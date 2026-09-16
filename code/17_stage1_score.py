#!/usr/bin/env python3
"""Stage 1: score mole's proposals for the addendum against the sealed key.

Input is the `mole embed` output for images/stage1-pool/ (the .npy plus its
.mapping.json), made with the FROZEN fine-tuned checkpoint and the gallery's
codebook. Hand scores are computed with mole's own ``hand_score_matrix``
(top-2 mean per hand, sibling scans excluded) and calibrated the same way as
the review sheet, so what is scored here is exactly what the false-negatives
tab shows Robin — no second matcher.

Writes outputs/stage1/<embeddings-stem>.scores.csv (one row per focus charter:
proposed hand, calibrated P, rank of Robin's hand, nearest charters, and
``on_sheet``: whether mole's own selection — join-z filter, per-hand cap of
8, ``--limit`` — puts it on the false-negatives tab Robin receives) and
prints:

  * confirmed charters   Top-1 / Top-3 by hand, plus counts (24 + holdout 314)
  * tentative KA_12      656 and 709: nearest hand each, and whether they are
                         each other's nearest cross-document neighbour
  * unidentified         the proposal and its P, for Robin to check

  python code/17_stage1_score.py ~/mole/outputs/comital/stage1.npy
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import batch_paths

MOLE_SRC = Path.home() / "GitRepos" / "mole" / "src"
POOL = ROOT / "images" / "stage1-pool"
OUT_DIR = ROOT / "outputs" / "stage1"


def _mole():
    try:
        from mole.review import suggest
    except ImportError:
        if MOLE_SRC.is_dir() and str(MOLE_SRC) not in sys.path:
            sys.path.insert(0, str(MOLE_SRC))
        from mole.review import suggest
    return suggest


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_pool(pool: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    labels = {r["filename"]: r["hand_id"] for r in read_csv(pool / "labels.csv")}
    doc_ids = {r["filename"]: r["doc_id"] for r in read_csv(pool / "doc_ids.csv")}
    focus = [l.strip() for l in (pool / "focus.txt").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    return labels, doc_ids, focus


def load_key(path: Path) -> dict[str, dict]:
    return {r["doc_id"]: r for r in read_csv(path)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("embeddings", type=Path, help="mole embed .npy of images/stage1-pool")
    ap.add_argument("--pool", type=Path, default=POOL)
    ap.add_argument("--key", type=Path, default=batch_paths("addendum").data / "answer_key.csv")
    ap.add_argument("--neighbors", type=int, default=5)
    ap.add_argument("--limit", type=int, default=25,
                    help="the --limit the review sheet was built with (mole default 25)")
    args = ap.parse_args()
    sg = _mole()

    X, meta, rows = sg._load(args.embeddings)
    names = [Path(r["image"]).name for r in rows]
    labels, doc_ids, focus = load_pool(args.pool)
    key = load_key(args.key)
    unknown = [n for n in names if n not in doc_ids]
    if unknown:
        raise SystemExit(f"{len(unknown)} embedded images are not in the pool, e.g. {unknown[0]}")
    if set(focus) - set(names):
        raise SystemExit("embedding does not cover every focus charter")

    hand_of = np.asarray([labels.get(n, "") for n in names], dtype=object)
    doc_arr = np.asarray([doc_ids[n] for n in names], dtype=object)
    is_labeled = np.asarray([bool(h) for h in hand_of], dtype=bool)
    labeled = np.where(is_labeled)[0]
    members = {h: np.where(hand_of == h)[0] for h in sorted({h for h in hand_of if h})}

    Xn = sg._l2(X)
    sim = (Xn @ Xn.T).astype(np.float32)
    scores, hands = sg.hand_score_matrix(sim, members, doc_arr)
    cal = sg._calibrate(scores, hands, labeled, hand_of)

    # mole's own false-negatives selection, as build_review() does it
    unlabeled = np.where(~is_labeled)[0]
    attrib = sg._attributions(scores, hands, unlabeled, names, members, limit=None)
    for a in attrib:
        a["calibrated_p"] = sg._apply_calibration(cal, a["score"])
    attrib.sort(key=lambda d: (
        -(d["calibrated_p"] if d["calibrated_p"] is not None else -1.0), -d["score"]))
    on_sheet = {a["document"] for a in
                sg._per_hand_take(attrib, sg.ATTRIB_PER_HAND_CAP)[:args.limit]}

    # nearest cross-document neighbours (never a scan of the same charter)
    idx_of = {n: i for i, n in enumerate(names)}
    def neighbours(i: int, k: int) -> list[tuple[str, float]]:
        row = sim[i].copy()
        row[doc_arr == doc_arr[i]] = -np.inf
        order = np.argsort(-row)[:k]
        return [(names[j], float(row[j])) for j in order]

    out_rows = []
    for n in focus:
        i = idx_of[n]
        doc = doc_ids[n]
        truth = key.get(doc, {})
        row = scores[i]
        order = [j for j in np.argsort(-row) if np.isfinite(row[j])]
        ranked = [hands[j] for j in order]
        top = ranked[0] if ranked else ""
        p = sg._apply_calibration(cal, float(row[order[0]])) if ranked else None
        true_hand = truth.get("hand_id", "")
        rank = (ranked.index(true_hand) + 1) if true_hand in ranked else ""
        nn = neighbours(i, args.neighbors)
        out_rows.append({
            "doc_id": doc, "filename": n, "batch": truth.get("batch", ""),
            "status": truth.get("status", "not in key"), "robin_hand": true_hand,
            "proposed_hand": top, "proposed_score": f"{float(row[order[0]]):.4f}" if ranked else "",
            "calibrated_p": f"{p:.3f}" if p is not None else "",
            "runner_up": ranked[1] if len(ranked) > 1 else "",
            "margin": f"{float(row[order[0]] - row[order[1]]):.4f}" if len(ranked) > 1 else "",
            "rank_of_robin_hand": rank,
            "on_sheet": int(n in on_sheet),
            "nearest": " | ".join(f"{doc_ids[m]}:{labels.get(m) or '?'}:{s:.3f}" for m, s in nn),
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"{args.embeddings.stem}.scores.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    # ---- report
    conf = [r for r in out_rows if r["status"] == "confirmed"]
    by_hand: dict[str, list[dict]] = defaultdict(list)
    for r in conf:
        by_hand[r["robin_hand"]].append(r)
    print(f"stage 1 — {args.embeddings.name}  ({len(names)} charters, "
          f"{len(labeled)} labeled, model {meta.get('model_id') or meta.get('checkpoint') or '?'})")
    print(f"\nconfirmed ({len(conf)}: {len(conf) - 1} addendum + holdout 314)")
    print(f"  {'hand':6s} {'n':>3s} {'top1':>5s} {'top3':>5s}   misses")
    t1 = t3 = 0
    for h in sorted(by_hand, key=lambda s: int(s.split('_')[1])):
        rs = by_hand[h]
        h1 = sum(1 for r in rs if r["rank_of_robin_hand"] == 1)
        h3 = sum(1 for r in rs if r["rank_of_robin_hand"] and r["rank_of_robin_hand"] <= 3)
        t1 += h1; t3 += h3
        miss = ", ".join(f"{r['doc_id']}→{r['proposed_hand']}" for r in rs
                         if r["rank_of_robin_hand"] != 1)
        print(f"  {h:6s} {len(rs):3d} {h1:5d} {h3:5d}   {miss}")
    print(f"  {'all':6s} {len(conf):3d} {t1:5d} {t3:5d}   "
          f"Top-1 {t1/len(conf):.2f}  Top-3 {t3/len(conf):.2f}")
    n_sheet = sum(r["on_sheet"] for r in out_rows)
    print(f"\non the review sheet (per-hand cap {sg.ATTRIB_PER_HAND_CAP}, --limit {args.limit}): "
          f"{n_sheet} of {len(out_rows)} focus charters; off it: "
          + ", ".join(r["doc_id"] for r in out_rows if not r["on_sheet"]))

    tent = [r for r in out_rows if r["status"] == "tentative"]
    if tent:
        print(f"\ntentative KA_12 ({len(tent)}) — a hand the gallery does not contain")
        for r in tent:
            print(f"  {r['doc_id']}: nearest hand {r['proposed_hand']} "
                  f"(P={r['calibrated_p'] or '-'}, margin {r['margin']}); nearest charters {r['nearest']}")
        docs = {r["doc_id"] for r in tent}
        for r in tent:
            i = idx_of[r["filename"]]
            nn = [doc_ids[m] for m, _ in neighbours(i, len(names))]
            others = [d for d in docs if d != r["doc_id"]]
            for o in others:
                print(f"  {r['doc_id']} → {o}: rank {nn.index(o) + 1} of {len(nn)} cross-document neighbours")

    unid = [r for r in out_rows if r["status"] == "unidentified"]
    if unid:
        print(f"\nunidentified ({len(unid)}) — proposals for Robin")
        for r in unid:
            print(f"  {r['doc_id']}: {r['proposed_hand']} (P={r['calibrated_p'] or '-'}, "
                  f"margin {r['margin']}), runner-up {r['runner_up']}")
    print(f"\n→ {out_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
