"""Parse Flanders photograph names.

Grammar (majority):

    134_2_RAGent K21_98.jpeg
    │   │  │      └─ shelfmark
    │   │  └─ repository
    │   └─ scan index of this charter
    └─ inventory number = doc_id

A minority omit the scan index (``493_AM Lille_PAT-155-2857.jpg``). Those are
treated as scan 1. Sibling grouping is by ``doc_id`` only — same
repository+shelfmark with different leading numbers is a collision for review,
not an automatic merge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Longest prefix first. Spellings as they appear in filenames, mapped to a
# canonical repository label used for collision keys.
_REPO_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Archief Grootseminarie Brugge", "Archief Grootseminarie Brugge"),
    ("Bisschoppelijk Archief Brugge", "Bisschoppelijk Archief Brugge"),
    ("ADN Lille", "ADN Lille"),
    ("ADNLille", "ADN Lille"),
    ("AM Lille", "AM Lille"),
    ("AMDouai", "AM Douai"),
    ("ADA Troyes", "ADA Troyes"),
    ("ANParijs", "AN Paris"),
    ("RA Bergen", "RA Bergen"),
    ("RAKortrijk", "RA Kortrijk"),
    ("RABrugge", "RA Brugge"),
    ("RAGent", "RA Gent"),
    ("SABrugge", "SA Brugge"),
    ("SAGent", "SA Gent"),
    ("ARA", "ARA"),
)

_STEM_SCAN = re.compile(r"^(\d+)_(\d+)_(.+)$")
_STEM_NOSCAN = re.compile(r"^(\d+)_(.+)$")
_NOTE = re.compile(r"\s*\(([^)]+)\)\s*$")
_SPACE = re.compile(r"[\s._]+")


@dataclass(frozen=True)
class ParsedName:
    filename: str
    doc_id: str
    scan_index: int
    scan_explicit: bool
    repository: str
    shelfmark: str
    note: str
    rest: str
    ok: bool

    @property
    def collision_key(self) -> str:
        if not self.ok or not self.repository or not self.shelfmark:
            return ""
        return f"{_norm_key(self.repository)}|{_norm_key(self.shelfmark)}"


def is_image_name(name: str) -> bool:
    from pathlib import Path

    p = Path(name)
    return (not p.name.startswith(".")) and p.suffix.lower() in IMAGE_SUFFIXES


def parse_filename(name: str) -> ParsedName:
    """Split a Flanders photograph basename into doc / scan / repository / shelfmark."""
    from pathlib import Path

    filename = Path(name).name
    stem = Path(filename).stem
    m = _STEM_SCAN.match(stem)
    if m:
        doc_id, scan_s, rest = m.group(1), m.group(2), m.group(3)
        scan_index, scan_explicit = int(scan_s), True
    else:
        m = _STEM_NOSCAN.match(stem)
        if not m:
            return ParsedName(
                filename=filename,
                doc_id="",
                scan_index=1,
                scan_explicit=False,
                repository="",
                shelfmark="",
                note="",
                rest=stem,
                ok=False,
            )
        doc_id, rest = m.group(1), m.group(2)
        scan_index, scan_explicit = 1, False

    note = ""
    body = rest
    nm = _NOTE.search(body)
    if nm:
        note = nm.group(1).strip()
        body = body[: nm.start()]
    body = body.rstrip(" ._")
    repository, shelfmark = _split_repo_shelf(body)
    return ParsedName(
        filename=filename,
        doc_id=doc_id,
        scan_index=scan_index,
        scan_explicit=scan_explicit,
        repository=repository,
        shelfmark=shelfmark.rstrip(" ._"),
        note=note,
        rest=rest,
        ok=True,
    )


def _split_repo_shelf(rest: str) -> tuple[str, str]:
    compact = rest.lstrip(" _")
    lower = compact.lower()
    best: tuple[str, str] | None = None
    best_n = -1
    for prefix, canonical in _REPO_PREFIXES:
        pl = prefix.lower()
        if lower.startswith(pl) and len(pl) > best_n:
            tail = compact[len(pl) :].lstrip(" _")
            best = (canonical, tail)
            best_n = len(pl)
    if best is not None:
        return best
    m = re.match(r"^([^0-9]+)(.*)$", compact)
    if m:
        return m.group(1).rstrip(" _"), m.group(2).lstrip(" _")
    return "", compact


def _norm_key(value: str) -> str:
    s = _NOTE.sub("", value)
    s = _SPACE.sub(" ", s).strip().lower()
    return s
