"""hand/ + unattributed/ versus mole's KA_* + unidentified/ layout."""
from __future__ import annotations

from pathlib import Path

import pytest

from code.layout import discover_source


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake")


def test_discover_ka_unidentified(tmp_path: Path):
    _touch(tmp_path / "KA_8" / "134_2_RAGent K21_98.jpeg")
    _touch(tmp_path / "KA_1" / "136_2_RAGent K21_122.jpeg")
    _touch(tmp_path / "unidentified" / "106_3_RAGent_K6_3.jpeg")
    layout = discover_source(tmp_path)
    assert layout.kind == "ka_unidentified"
    assert set(layout.hands) == {"KA_1", "KA_8"}
    assert layout.unattributed is not None
    assert layout.unattributed.name == "unidentified"


def test_discover_hand_unattributed(tmp_path: Path):
    _touch(tmp_path / "hand" / "KA_8" / "134_2_RAGent K21_98.jpeg")
    _touch(tmp_path / "unattributed" / "106_3_RAGent_K6_3.jpeg")
    layout = discover_source(tmp_path)
    assert layout.kind == "hand_unattributed"
    assert "KA_8" in layout.hands
    assert layout.unattributed.name == "unattributed"


def test_discover_missing_raises(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    with pytest.raises(ValueError):
        discover_source(tmp_path)
