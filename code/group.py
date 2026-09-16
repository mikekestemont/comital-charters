"""Sibling-scan grouping from parsed Flanders names (sluis main_document analogue)."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from code.names import parse_filename

VERDICTS = Path(__file__).resolve().parents[1] / "data" / "hand_verdicts.csv"


def load_hand_verdicts(path: Path | None = None) -> dict[str, str]:
    """Colleague (or later) hand calls: doc_id → KA_*."""
    src = path or VERDICTS
    if not src.is_file():
        return {}
    out: dict[str, str] = {}
    with src.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            doc = (row.get("doc_id") or "").strip()
            hand = (row.get("hand_id") or "").strip()
            if doc and hand:
                out[doc] = hand
    return out


def annotate_rows(raw_rows: list[dict]) -> list[dict]:
    """Attach parse fields; does not yet set main_document."""
    out = []
    for raw in raw_rows:
        parsed = parse_filename(raw["filename"])
        row = dict(raw)
        row.update({
            "doc_id": parsed.doc_id,
            "scan_index": parsed.scan_index,
            "scan_explicit": "1" if parsed.scan_explicit else "0",
            "repository": parsed.repository,
            "shelfmark": parsed.shelfmark,
            "note": parsed.note,
            "rest": parsed.rest,
            "parse_ok": "1" if parsed.ok else "0",
            "collision_key": parsed.collision_key,
            "main_document": "",
            "reason": "",
        })
        out.append(row)
    return out


def _copy_rank(row: dict) -> tuple:
    # Prefer an attributed path over unattributed when the same file is copied twice.
    attributed = 0 if row.get("hand_id") else 1
    return (attributed, row["folder"], row["relative_path"])


def assign_main_documents(rows: list[dict]) -> list[dict]:
    """Keep lowest scan index as main_document=1; extras stay on disk.

    Duplicate copies of the same filename in another folder are flagged
    ``duplicate_path_of=<kept relative_path>``, not deleted.
    """
    by_doc: dict[str, list[dict]] = defaultdict(list)
    orphans: list[dict] = []
    for r in rows:
        if r.get("parse_ok") != "1" or not r.get("doc_id"):
            r["main_document"] = "1"
            r["reason"] = "unparsed"
            orphans.append(r)
            continue
        by_doc[r["doc_id"]].append(r)

    for members in by_doc.values():
        by_fn: dict[str, list[dict]] = defaultdict(list)
        for r in members:
            by_fn[r["filename"]].append(r)

        kept_files: list[dict] = []
        for copies in by_fn.values():
            copies_sorted = sorted(copies, key=_copy_rank)
            keep = copies_sorted[0]
            kept_files.append(keep)
            for extra in copies_sorted[1:]:
                extra["main_document"] = "0"
                extra["reason"] = f"duplicate_path_of={keep['relative_path']}"

        # Same scan, different spelling/extension (47_1.jpg vs 47_1.jpeg): not a sibling.
        by_scan: dict[int, list[dict]] = defaultdict(list)
        for r in kept_files:
            by_scan[int(r["scan_index"])].append(r)
        unique_scans: list[dict] = []
        for copies in by_scan.values():
            copies_sorted = sorted(copies, key=_copy_rank)
            keep = copies_sorted[0]
            unique_scans.append(keep)
            for extra in copies_sorted[1:]:
                extra["main_document"] = "0"
                extra["reason"] = f"duplicate_file_of={keep['filename']}"

        unique_scans.sort(key=lambda r: (int(r["scan_index"]), r["filename"], r["relative_path"]))
        main = unique_scans[0]
        main["main_document"] = "1"
        main["reason"] = ""
        for extra in unique_scans[1:]:
            extra["main_document"] = "0"
            extra["reason"] = f"sibling_scan_of={main['filename']}"
    return rows


def filename_hand_map(rows: list[dict]) -> dict[str, str]:
    """Unambiguous folder attribution.

    Drop a filename when it sits in two KA_* folders, or when its doc_id
    appears under more than one hand (47_1.jpg in KA_9 vs 47_1.jpeg in KA_8).
    """
    folders: dict[str, set[str]] = defaultdict(set)
    doc_hands: dict[str, set[str]] = defaultdict(set)
    fn_doc: dict[str, str] = {}
    for r in rows:
        hid = (r.get("hand_id") or "").strip()
        if hid:
            folders[r["filename"]].add(hid)
            if r.get("doc_id"):
                doc_hands[r["doc_id"]].add(hid)
        if r.get("doc_id"):
            fn_doc[r["filename"]] = r["doc_id"]
    conflict_docs = {d for d, hands in doc_hands.items() if len(hands) > 1}
    out = {}
    for fn, hands in folders.items():
        if len(hands) != 1:
            continue
        if fn_doc.get(fn) in conflict_docs:
            continue
        out[fn] = next(iter(hands))
    return out


def labels_rows(rows: list[dict], verdicts: dict[str, str] | None = None) -> list[dict]:
    hands = filename_hand_map(rows)
    if verdicts is None:
        verdicts = load_hand_verdicts()
    for r in rows:
        doc = (r.get("doc_id") or "").strip()
        if doc in verdicts:
            hands[r["filename"]] = verdicts[doc]
    seen = set()
    out = []
    for r in sorted(rows, key=lambda x: x["filename"]):
        fn = r["filename"]
        if fn in seen or fn not in hands:
            continue
        seen.add(fn)
        out.append({"filename": fn, "hand_id": hands[fn]})
    return out


def doc_ids_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in sorted(rows, key=lambda x: x["filename"]):
        fn = r["filename"]
        if fn in seen or r.get("parse_ok") != "1":
            continue
        seen.add(fn)
        out.append({"filename": fn, "doc_id": r["doc_id"]})
    return out


def doc_groups_rows(rows: list[dict]) -> list[dict]:
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("parse_ok") == "1" and r.get("doc_id"):
            by_doc[r["doc_id"]].append(r)
    out = []
    for doc_id, members in sorted(by_doc.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0]):
        mains = [r for r in members if r.get("main_document") == "1"]
        keep = mains[0] if mains else sorted(members, key=lambda r: int(r["scan_index"]))[0]
        unique_fn = sorted({r["filename"] for r in members})
        drop = [fn for fn in unique_fn if fn != keep["filename"]]
        hands = sorted({r["hand_id"] for r in members if r.get("hand_id")})
        out.append({
            "doc_id": doc_id,
            "n_files": len(members),
            "n_filenames": len(unique_fn),
            "n_scans": len({int(r["scan_index"]) for r in members}),
            "keep_filename": keep["filename"],
            "drop_filenames": "|".join(drop),
            "hands": "|".join(hands),
            "repository": keep.get("repository", ""),
            "shelfmark": keep.get("shelfmark", ""),
            "main_relative_path": keep["relative_path"],
        })
    return out


def shelfmark_collisions(rows: list[dict]) -> list[dict]:
    """Same repository+shelfmark, different doc_id — do not auto-merge."""
    by_key: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = r.get("collision_key") or ""
        if not key or r.get("parse_ok") != "1":
            continue
        by_key[key].add(r["doc_id"])
        samples[key].append(r)
    out = []
    for key, docs in sorted(by_key.items()):
        if len(docs) < 2:
            continue
        members = samples[key]
        out.append({
            "collision_key": key,
            "repository": members[0]["repository"],
            "shelfmark": members[0]["shelfmark"],
            "doc_ids": "|".join(sorted(docs, key=lambda d: int(d) if d.isdigit() else d)),
            "n_docs": len(docs),
            "filenames": "|".join(sorted({r["filename"] for r in members})),
        })
    return out


def folder_duplicates(rows: list[dict]) -> list[dict]:
    by_fn: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_fn[r["filename"]].append(r)
    out = []
    for fn, copies in sorted(by_fn.items()):
        if len(copies) < 2:
            continue
        folders = sorted({r["folder"] for r in copies})
        hands = sorted({r["hand_id"] for r in copies if r.get("hand_id")})
        out.append({
            "filename": fn,
            "n_copies": len(copies),
            "folders": "|".join(folders),
            "hands": "|".join(hands),
            "conflict": "1" if len(hands) > 1 else "0",
        })
    return out
