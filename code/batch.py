"""Where one batch of photographs lives on disk.

``main`` is the 313-charter gallery frozen for mole (``data/raw``, ``images/``).
``addendum`` is Robin's second delivery (32 charters, 2026-09), kept apart so
the frozen gallery, its zones and its Sauvola scale are never touched:

    data/addendum/raw/hand/KA_*/…      data/addendum/*.csv
    data/addendum/raw/unattributed/…   images/addendum/zoned*/

Every pipeline script takes ``--batch {main,addendum}`` and reads its paths
from here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ("main", "addendum")

# Robin's addendum folder as delivered (sits under data/, gitignored).
ADDENDUM_SRC = ROOT / "data" / "KESTEMONT-WAEYTENS_Corpus-Margareta1270_Addendum"


@dataclass(frozen=True)
class BatchPaths:
    name: str
    data: Path          # CSVs, zones, LS import/export
    raw: Path           # hand/KA_*/ + unattributed/
    images: Path        # zoned/, zoned-stretched/, zoned-sauvola/
    outputs: Path       # QC HTML
    ls_project: str     # Label Studio project title

    @property
    def manifest(self) -> Path:
        return self.data / "manifest.csv"

    @property
    def zones_jsonl(self) -> Path:
        return self.data / "zones_blla.jsonl"

    @property
    def zones_json(self) -> Path:
        return self.data / "zones.json"

    @property
    def zones_csv(self) -> Path:
        return self.data / "zones.csv"

    @property
    def ls_import(self) -> Path:
        return self.data / "ls_zones_import.json"

    @property
    def ls_export(self) -> Path:
        return self.data / "ls_zones_export.json"

    @property
    def zoned(self) -> Path:
        return self.images / "zoned"

    @property
    def stretched(self) -> Path:
        return self.images / "zoned-stretched"

    @property
    def sauvola(self) -> Path:
        return self.images / "zoned-sauvola"

    @property
    def zone_review(self) -> Path:
        return self.outputs / "zone_review.html"

    @property
    def raw_prefix(self) -> str:
        """Repo-relative prefix of raw photographs, as Label Studio sees them."""
        return self.raw.relative_to(ROOT).as_posix() + "/"


def batch_paths(name: str = "main") -> BatchPaths:
    if name == "main":
        return BatchPaths(
            name="main",
            data=ROOT / "data",
            raw=ROOT / "data" / "raw",
            images=ROOT / "images",
            outputs=ROOT / "outputs",
            ls_project="comital",
        )
    if name == "addendum":
        return BatchPaths(
            name="addendum",
            data=ROOT / "data" / "addendum",
            raw=ROOT / "data" / "addendum" / "raw",
            images=ROOT / "images" / "addendum",
            outputs=ROOT / "outputs" / "addendum",
            ls_project="comital-addendum",
        )
    raise ValueError(f"unknown batch {name!r}; expected one of {BATCHES}")


def add_batch_arg(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--batch", choices=BATCHES, default="main",
                    help="which delivery of photographs (default: main gallery)")
