"""Copy KA_* + unidentified into data/raw/hand and data/raw/unattributed."""
from __future__ import annotations

from pathlib import Path

from code.layout import copy_raw, list_copied_rows


def _touch(path: Path, blob: bytes = b"fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def test_copy_maps_mole_layout(tmp_path: Path):
    src = tmp_path / "flanders"
    dest = tmp_path / "raw"
    _touch(src / "KA_8" / "134_2_RAGent K21_98.jpeg", b"a")
    _touch(src / "KA_8" / "134_3_RAGent K21_98.jpeg", b"b")
    _touch(src / "unidentified" / "106_3_RAGent_K6_3.jpeg", b"c")
    stats = copy_raw(src, dest)
    assert stats["copied"] == 3
    assert (dest / "hand" / "KA_8" / "134_2_RAGent K21_98.jpeg").read_bytes() == b"a"
    assert (dest / "unattributed" / "106_3_RAGent_K6_3.jpeg").read_bytes() == b"c"
    assert not (dest / "hand" / "unidentified").exists()
    rows = list_copied_rows(dest)
    assert {r["relative_path"] for r in rows} == {
        "hand/KA_8/134_2_RAGent K21_98.jpeg",
        "hand/KA_8/134_3_RAGent K21_98.jpeg",
        "unattributed/106_3_RAGent_K6_3.jpeg",
    }
    by = {r["relative_path"]: r for r in rows}
    assert by["hand/KA_8/134_2_RAGent K21_98.jpeg"]["hand_id"] == "KA_8"
    assert by["unattributed/106_3_RAGent_K6_3.jpeg"]["hand_id"] == ""


def test_copy_accepts_hand_unattributed_src(tmp_path: Path):
    src = tmp_path / "already"
    dest = tmp_path / "raw"
    _touch(src / "hand" / "KA_1" / "x.jpeg")
    _touch(src / "unattributed" / "y.jpeg")
    copy_raw(src, dest)
    assert (dest / "hand" / "KA_1" / "x.jpeg").is_file()
    assert (dest / "unattributed" / "y.jpeg").is_file()


def test_copy_skips_existing_unless_force(tmp_path: Path):
    src = tmp_path / "flanders"
    dest = tmp_path / "raw"
    _touch(src / "KA_8" / "a.jpeg", b"new")
    dest_file = dest / "hand" / "KA_8" / "a.jpeg"
    _touch(dest_file, b"old")
    stats = copy_raw(src, dest)
    assert stats["skipped"] == 1
    assert dest_file.read_bytes() == b"old"
    copy_raw(src, dest, force=True)
    assert dest_file.read_bytes() == b"new"


def test_copy_skips_unattributed_identical_to_hand(tmp_path: Path):
    src = tmp_path / "flanders"
    dest = tmp_path / "raw"
    _touch(src / "KA_8" / "20_2_x.jpeg", b"same")
    _touch(src / "unidentified" / "20_2_x.jpeg", b"same")
    _touch(src / "unidentified" / "only_unattr.jpeg", b"other")
    stats = copy_raw(src, dest)
    assert stats["unattributed_identical_skipped"] == 1
    assert (dest / "hand" / "KA_8" / "20_2_x.jpeg").is_file()
    assert not (dest / "unattributed" / "20_2_x.jpeg").exists()
    assert (dest / "unattributed" / "only_unattr.jpeg").is_file()
