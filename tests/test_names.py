"""Filename grammar for Flanders photographs."""
from __future__ import annotations

from code.names import parse_filename


def test_example_sibling_pair():
    a = parse_filename("134_2_RAGent K21_98.jpeg")
    b = parse_filename("134_3_RAGent K21_98.jpeg")
    assert a.ok and b.ok
    assert a.doc_id == b.doc_id == "134"
    assert a.scan_index == 2 and b.scan_index == 3
    assert a.repository == b.repository == "RA Gent"
    assert a.shelfmark == b.shelfmark == "K21_98"
    assert a.collision_key == b.collision_key
    c = parse_filename("135_2_RAGent K21_107.jpeg")
    assert c.doc_id == "135"
    assert c.doc_id != a.doc_id


def test_underscore_and_space_variants():
    a = parse_filename("129_2_RAGent_K78_409.jpeg")
    assert a.repository == "RA Gent"
    assert a.shelfmark == "K78_409"
    b = parse_filename("10_1_ADN Lille_ B1517_895bis.JPG")
    assert b.repository == "ADN Lille"
    assert "B1517" in b.shelfmark
    c = parse_filename("30_2_RABrugge_INV 120_7435 .jpeg")
    assert c.repository == "RA Brugge"


def test_trailing_note_and_double_dot():
    a = parse_filename("123_1_RAGent K32_19bis (FACSIMILE).jpeg")
    assert a.doc_id == "123"
    assert a.note.lower() == "facsimile"
    assert "K32_19bis" in a.shelfmark
    b = parse_filename("12_2_RAGent_K72_14 (Groot).jpeg")
    assert b.note.lower() == "groot"
    c = parse_filename("84_2_RAGent_K6_9..jpeg")
    assert c.doc_id == "84"
    assert c.shelfmark.startswith("K6_9")


def test_missing_scan_index_is_scan_one():
    a = parse_filename("493_AM Lille_PAT-155-2857.jpg")
    assert a.ok
    assert a.doc_id == "493"
    assert a.scan_index == 1
    assert a.scan_explicit is False
    assert a.repository == "AM Lille"


def test_adnlille_alias_and_long_repo():
    a = parse_filename("22_1_ADNLille_B 396_970.jpeg")
    assert a.repository == "ADN Lille"
    b = parse_filename(
        "575_3_Archief Grootseminarie Brugge_Fonds Ten Duinen-Ter Doest_325.jpeg"
    )
    assert b.repository == "Archief Grootseminarie Brugge"
    assert "Ten Duinen" in b.shelfmark


def test_same_shelfmark_different_doc_is_collision_key():
    a = parse_filename("134_2_RAGent K21_98.jpeg")
    b = parse_filename("999_1_RAGent K21_98.jpeg")
    assert a.doc_id != b.doc_id
    assert a.collision_key == b.collision_key != ""


def test_unparsed_garbage():
    p = parse_filename("not-a-charter.jpeg")
    assert p.ok is False
    assert p.doc_id == ""
