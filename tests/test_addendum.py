"""Robin's addendum layout (KA1, KA12(?), Ongeïdentificeerd) and the stage-1 key."""
from __future__ import annotations

import csv
import unicodedata
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from code.batch import ROOT, batch_paths
from code.layout import canonical_hand, copy_raw, discover_source


def _touch(path: Path, blob: bytes = b"fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


@pytest.mark.parametrize("folder, expected", [
    ("KA_8", ("KA_8", False)),
    ("KA8", ("KA_8", False)),
    ("KA12(?)", ("KA_12", True)),
    ("KA_12 (?)", ("KA_12", True)),
    ("KA1", ("KA_1", False)),
    ("unidentified", None),
    ("KA_8_old", None),
])
def test_canonical_hand(folder, expected):
    assert canonical_hand(folder) == expected


def test_discover_addendum_spellings(tmp_path: Path):
    _touch(tmp_path / "KA1" / "667_SAGent_Bijloke_E40 (1).JPG")
    _touch(tmp_path / "KA12(?)" / "656_RAGent_GW2_684_1.jpg")
    # macOS returns folder names in NFD; the match must survive that
    nfd = unicodedata.normalize("NFD", "Ongeïdentificeerd")
    _touch(tmp_path / nfd / "665_1_RABergen_ AEM.08.001_27.jpg")
    _touch(tmp_path / "KA1" / ".DS_Store")
    layout = discover_source(tmp_path)
    assert layout.kind == "ka_unidentified"
    assert set(layout.hands) == {"KA_1", "KA_12"}
    assert layout.tentative == {"KA_12"}
    assert layout.unattributed is not None


def test_copy_canonicalises_hand_folders(tmp_path: Path):
    src, dest = tmp_path / "src", tmp_path / "raw"
    _touch(src / "KA8" / "486_AM Lille_PAT-118_2156_2.jpeg", b"a")
    _touch(src / "KA12(?)" / "709_x.jpeg", b"b")
    _touch(src / "Ongeïdentificeerd" / "676_y.JPG", b"c")
    stats = copy_raw(src, dest)
    assert stats["copied"] == 3
    assert stats["tentative"] == ["KA_12"]
    assert (dest / "hand" / "KA_8" / "486_AM Lille_PAT-118_2156_2.jpeg").is_file()
    assert (dest / "hand" / "KA_12" / "709_x.jpeg").is_file()
    assert (dest / "unattributed" / "676_y.JPG").is_file()
    assert not (dest / "hand" / "KA12(?)").exists()


def test_two_folders_one_hand_raises(tmp_path: Path):
    _touch(tmp_path / "KA8" / "a.jpg")
    _touch(tmp_path / "KA_8" / "b.jpg")
    with pytest.raises(ValueError):
        discover_source(tmp_path)


def test_batch_paths_keep_main_frozen():
    main, add = batch_paths("main"), batch_paths("addendum")
    assert main.raw == ROOT / "data" / "raw"
    assert add.raw == ROOT / "data" / "addendum" / "raw"
    assert add.sauvola == ROOT / "images" / "addendum" / "zoned-sauvola"
    assert add.raw_prefix == "data/addendum/raw/"
    assert main.raw_prefix == "data/raw/"
    assert main.ls_project != add.ls_project
    with pytest.raises(ValueError):
        batch_paths("stage2")


def test_answer_key_statuses(tmp_path: Path):
    mod = SourceFileLoader("answer_key", str(ROOT / "code" / "04_answer_key.py")).load_module()
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["relative_path", "filename", "hand_id", "doc_id", "main_document"])
        w.writeheader()
        w.writerow({"relative_path": "hand/KA_8/486.jpg", "filename": "486.jpg", "hand_id": "KA_8", "doc_id": "486", "main_document": "1"})
        w.writerow({"relative_path": "hand/KA_12/656.jpg", "filename": "656.jpg", "hand_id": "KA_12", "doc_id": "656", "main_document": "1"})
        w.writerow({"relative_path": "unattributed/665.jpg", "filename": "665.jpg", "hand_id": "", "doc_id": "665", "main_document": "1"})
        w.writerow({"relative_path": "hand/KA_8/486_2.jpg", "filename": "486_2.jpg", "hand_id": "KA_8", "doc_id": "486", "main_document": "0"})
    rows = mod.answer_rows(manifest, {"KA_12"}, "addendum")
    assert [(r["doc_id"], r["hand_id"], r["status"]) for r in rows] == [
        ("486", "KA_8", "confirmed"),
        ("656", "KA_12", "tentative"),
        ("665", "", "unidentified"),
    ]


def test_sealed_key_matches_robins_folders():
    """The committed key must agree with Robin's delivery: 32 + holdout 314."""
    key = ROOT / "data" / "addendum" / "answer_key.csv"
    if not key.is_file():
        pytest.skip("answer key not sealed")
    with key.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    add = [r for r in rows if r["batch"] == "addendum"]
    assert len(add) == 32
    by = {r["status"]: sum(1 for x in add if x["status"] == r["status"]) for r in add}
    assert by == {"confirmed": 24, "tentative": 2, "unidentified": 6}
    assert {r["doc_id"] for r in add if r["status"] == "tentative"} == {"656", "709"}
    assert sum(1 for r in add if r["hand_id"] == "KA_8") == 17
    hold = [r for r in rows if r["batch"] == "main"]
    assert [(r["doc_id"], r["hand_id"]) for r in hold] == [("314", "KA_8")]
