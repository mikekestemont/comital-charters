"""Hold-out charter 314 stays unlabeled (Robin-confirmed KA_8 test case)."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _rows(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_holdout_314_stays_unattributed():
    hold = _rows("holdout.csv")
    assert len(hold) == 1
    row = hold[0]
    assert row["doc_id"] == "314"
    assert row["expected_hand_id"] == "KA_8"
    labeled = {r["filename"] for r in _rows("labels.csv")}
    assert row["filename"] not in labeled
    groups = {r["doc_id"]: r for r in _rows("doc_groups.csv")}
    assert groups["314"]["hands"] == ""
    assert groups["314"]["main_relative_path"].startswith("unattributed/")


def test_robin_rejected_ka8_copies_are_unattributed():
    groups = {r["doc_id"]: r for r in _rows("doc_groups.csv")}
    for doc in ("20", "22", "575", "576", "582", "608"):
        assert groups[doc]["hands"] == "", doc
        assert groups[doc]["main_relative_path"].startswith("unattributed/"), doc
    dropped = _rows("dropped_unattributed.csv")
    assert dropped == []
