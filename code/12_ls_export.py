#!/usr/bin/env python3
"""Dump the comital Label Studio project for 13_apply_ls_zones.py.

Reads the local Label Studio sqlite (project title 'comital'). Does not need
a browser export.

  python code/12_ls_export.py --out data/ls_zones_export.json
  python code/12_ls_export.py --batch addendum      # project 'comital-addendum'
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code.batch import add_batch_arg, batch_paths

LS_DB = Path.home() / "Library/Application Support/label-studio/label_studio.sqlite3"


def redact_ls_data(payload: dict, raw_prefix: str = "data/raw/") -> dict:
    if not isinstance(payload, dict):
        return payload
    payload = dict(payload)
    fn = payload.get("filename")
    if isinstance(fn, str) and fn:
        posix = fn.replace("\\", "/")
        if f"/{raw_prefix}" in posix:
            payload["filename"] = raw_prefix + posix.split(f"/{raw_prefix}", 1)[1]
        elif posix.startswith(raw_prefix):
            payload["filename"] = posix
        else:
            payload["filename"] = Path(fn).name
    rel = payload.get("relative_path")
    if isinstance(rel, str) and rel.startswith("/"):
        payload["relative_path"] = Path(rel).name
    return payload


def dump(db: Path, title: str, raw_prefix: str = "data/raw/") -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    row = con.execute("SELECT id FROM project WHERE title = ?", (title,)).fetchone()
    if not row:
        raise SystemExit(f"no Label Studio project titled {title!r} in {db}")
    pid = row[0]
    tasks = con.execute(
        """
        SELECT t.id, t.data, c.result, c.was_cancelled
        FROM task t
        JOIN task_completion c ON c.task_id = t.id
        WHERE t.project_id = ?
          AND c.id = (
              SELECT c2.id FROM task_completion c2
              WHERE c2.task_id = t.id
              ORDER BY c2.id DESC LIMIT 1
          )
        ORDER BY t.id
        """,
        (pid,),
    ).fetchall()
    out = []
    for tid, data, result, cancelled in tasks:
        payload = json.loads(data) if isinstance(data, str) else data
        res = json.loads(result) if isinstance(result, str) else (result or [])
        out.append({
            "id": tid,
            "data": redact_ls_data(payload, raw_prefix),
            "annotations": [{
                "was_cancelled": bool(cancelled),
                "result": res,
            }],
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    add_batch_arg(ap)
    ap.add_argument("--db", type=Path, default=LS_DB)
    ap.add_argument("--title", default=None, help="LS project title (default: the batch's)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    P = batch_paths(args.batch)
    args.title = args.title or P.ls_project
    args.out = args.out or P.ls_export
    tasks = dump(args.db, args.title, P.raw_prefix)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(tasks), encoding="utf-8")
    print(f"wrote {len(tasks)} tasks → {args.out}")


if __name__ == "__main__":
    main()
