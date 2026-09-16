"""Sibling grouping, duplicate paths, shelfmark collisions."""
from __future__ import annotations

from code.group import (
    annotate_rows,
    assign_main_documents,
    doc_groups_rows,
    folder_duplicates,
    labels_rows,
    shelfmark_collisions,
)
from code.layout import drop_unattributed_identical


def _row(path: str, folder: str, hand: str = "") -> dict:
    return {
        "relative_path": path,
        "filename": path.rsplit("/", 1)[-1],
        "folder": folder,
        "hand_id": hand,
        "abs_path": path,
    }


def test_lowest_scan_index_is_main_document():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_1/134_3_RAGent K21_98.jpeg", "hand/KA_1", "KA_1"),
        _row("hand/KA_1/134_2_RAGent K21_98.jpeg", "hand/KA_1", "KA_1"),
        _row("hand/KA_1/135_2_RAGent K21_107.jpeg", "hand/KA_1", "KA_1"),
    ]))
    by = {r["filename"]: r for r in rows}
    assert by["134_2_RAGent K21_98.jpeg"]["main_document"] == "1"
    assert by["134_2_RAGent K21_98.jpeg"]["reason"] == ""
    assert by["134_3_RAGent K21_98.jpeg"]["main_document"] == "0"
    assert by["134_3_RAGent K21_98.jpeg"]["reason"] == "sibling_scan_of=134_2_RAGent K21_98.jpeg"
    assert by["135_2_RAGent K21_107.jpeg"]["main_document"] == "1"
    groups = {g["doc_id"]: g for g in doc_groups_rows(rows)}
    assert groups["134"]["n_filenames"] == 2
    assert groups["134"]["keep_filename"] == "134_2_RAGent K21_98.jpeg"


def test_duplicate_path_prefers_attributed_copy():
    rows = assign_main_documents(annotate_rows([
        _row("unattributed/20_2_RABrugge_INV 14_15.jpeg", "unattributed", ""),
        _row("hand/KA_8/20_2_RABrugge_INV 14_15.jpeg", "hand/KA_8", "KA_8"),
    ]))
    by = {r["relative_path"]: r for r in rows}
    keep = by["hand/KA_8/20_2_RABrugge_INV 14_15.jpeg"]
    extra = by["unattributed/20_2_RABrugge_INV 14_15.jpeg"]
    assert keep["main_document"] == "1"
    assert extra["main_document"] == "0"
    assert extra["reason"] == "duplicate_path_of=hand/KA_8/20_2_RABrugge_INV 14_15.jpeg"
    dups = folder_duplicates(rows)
    assert dups[0]["filename"].startswith("20_2_")
    assert dups[0]["conflict"] == "0"


def test_drop_unattributed_identical_keeps_hand_conflicts(tmp_path):
    raw = tmp_path / "raw"
    hand = raw / "hand" / "KA_8" / "20_2_x.jpeg"
    unattr = raw / "unattributed" / "20_2_x.jpeg"
    conflict_a = raw / "hand" / "KA_8" / "30_2_y.jpeg"
    conflict_b = raw / "hand" / "KA_10" / "30_2_y.jpeg"
    for p, blob in (
        (hand, b"attr"),
        (unattr, b"attr"),
        (conflict_a, b"both"),
        (conflict_b, b"both"),
    ):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    dropped = drop_unattributed_identical(raw)
    assert [d["dropped_path"] for d in dropped] == ["unattributed/20_2_x.jpeg"]
    assert not unattr.exists()
    assert hand.exists()
    assert conflict_a.exists() and conflict_b.exists()


def test_hand_conflict_is_not_a_label():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_8/30_2_RABrugge_INV 120_7435 .jpeg", "hand/KA_8", "KA_8"),
        _row("hand/KA_10/30_2_RABrugge_INV 120_7435 .jpeg", "hand/KA_10", "KA_10"),
    ]))
    assert labels_rows(rows, verdicts={}) == []
    dups = folder_duplicates(rows)
    assert dups[0]["conflict"] == "1"


def test_hand_verdicts_label_folder_conflicts():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_8/30_2_RABrugge_INV 120_7435 .jpeg", "hand/KA_8", "KA_8"),
        _row("hand/KA_10/30_2_RABrugge_INV 120_7435 .jpeg", "hand/KA_10", "KA_10"),
        _row("hand/KA_8/47_1_SAGent_94_75.jpeg", "hand/KA_8", "KA_8"),
        _row("hand/KA_9/47_1_SAGent_94_75.jpg", "hand/KA_9", "KA_9"),
        _row("hand/KA_8/458_2_RAGent_K16_39.jpeg", "hand/KA_8", "KA_8"),
        _row("hand/KA_10/458_2_RAGent_K16_39.jpeg", "hand/KA_10", "KA_10"),
    ]))
    labels = {r["filename"]: r["hand_id"] for r in labels_rows(
        rows, verdicts={"30": "KA_10", "47": "KA_9", "458": "KA_10"},
    )}
    assert labels["30_2_RABrugge_INV 120_7435 .jpeg"] == "KA_10"
    assert labels["47_1_SAGent_94_75.jpeg"] == "KA_9"
    assert labels["47_1_SAGent_94_75.jpg"] == "KA_9"
    assert labels["458_2_RAGent_K16_39.jpeg"] == "KA_10"


def test_shelfmark_collision_is_listed_not_merged():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_1/134_2_RAGent K21_98.jpeg", "hand/KA_1", "KA_1"),
        _row("hand/KA_1/999_1_RAGent K21_98.jpeg", "hand/KA_1", "KA_1"),
    ]))
    coll = shelfmark_collisions(rows)
    assert len(coll) == 1
    assert set(coll[0]["doc_ids"].split("|")) == {"134", "999"}
    by = {r["filename"]: r for r in rows}
    assert by["134_2_RAGent K21_98.jpeg"]["main_document"] == "1"
    assert by["999_1_RAGent K21_98.jpeg"]["main_document"] == "1"


def test_same_scan_different_extension_is_duplicate_not_sibling():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_8/47_1_SAGent_94_75.jpeg", "hand/KA_8", "KA_8"),
        _row("hand/KA_9/47_1_SAGent_94_75.jpg", "hand/KA_9", "KA_9"),
    ]))
    roles = {r["relative_path"]: (r["main_document"], r["reason"]) for r in rows}
    mains = [p for p, (m, _) in roles.items() if m == "1"]
    assert len(mains) == 1
    extra = next(p for p, (m, _) in roles.items() if m == "0")
    assert roles[extra][1].startswith("duplicate_file_of=")
    assert labels_rows(rows, verdicts={}) == []


def test_missing_scan_index_groups_with_siblings():
    rows = assign_main_documents(annotate_rows([
        _row("hand/KA_6/493_AM Lille_PAT-155-2857.jpg", "hand/KA_6", "KA_6"),
        _row("hand/KA_6/493_2_AM Lille_PAT-155-2857.jpg", "hand/KA_6", "KA_6"),
    ]))
    by = {r["filename"]: r for r in rows}
    assert by["493_AM Lille_PAT-155-2857.jpg"]["scan_index"] == 1
    assert by["493_AM Lille_PAT-155-2857.jpg"]["main_document"] == "1"
    assert by["493_2_AM Lille_PAT-155-2857.jpg"]["reason"].startswith("sibling_scan_of=")
