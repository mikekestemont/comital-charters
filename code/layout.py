"""Discover and copy the Flanders hand / unattributed folder layout."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from code.names import is_image_name

HAND_DIR_NAMES = ("hand", "hands", "attributed")
# Compared case-insensitively; Robin's addendum spells it "Ongeïdentificeerd".
UNATTR_DIR_NAMES = ("unattributed", "unidentified", "unlabelled", "unlabeled",
                    "ongeïdentificeerd", "ongeidentificeerd")
# KA_8, KA8, KA12(?) → canonical KA_<n>; a trailing "(?)" marks the hand as
# tentative (Robin's "mogelijk … eenzelfde hand", not yet a confirmed scribe).
_HAND_DIR = re.compile(r"^KA_?(\d+)\s*(\(\?\))?$")

# mole/data/flanders on this machine: KA_* next to unidentified/, no hand/ parent.
DEFAULT_SRC = Path.home() / "GitRepos" / "mole" / "data" / "flanders"


@dataclass
class SourceLayout:
    src: Path
    hands: dict[str, Path] = field(default_factory=dict)
    unattributed: Path | None = None
    kind: str = ""
    tentative: set[str] = field(default_factory=set)


def canonical_hand(folder_name: str) -> tuple[str, bool] | None:
    """``KA12(?)`` → ``("KA_12", True)``; ``KA_8`` → ``("KA_8", False)``; else None."""
    m = _HAND_DIR.match(folder_name.strip())
    if not m:
        return None
    return f"KA_{int(m.group(1))}", m.group(2) is not None


def is_image(path: Path) -> bool:
    return path.is_file() and is_image_name(path.name)


def iter_images(root: Path):
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if is_image(p):
                yield p


def _hand_folders(parent: Path, tentative: set[str] | None = None) -> dict[str, Path]:
    out = {}
    if not parent.is_dir():
        return out
    for p in sorted(parent.iterdir()):
        if not p.is_dir() or p.name.startswith("."):
            continue
        hand = canonical_hand(p.name)
        if hand is None:
            continue
        name, is_tentative = hand
        if name in out:
            raise ValueError(f"{parent}: {p.name} and {out[name].name} both map to {name}")
        out[name] = p
        if is_tentative and tentative is not None:
            tentative.add(name)
    return out


def _unattributed_dir(parent: Path) -> Path | None:
    if not parent.is_dir():
        return None
    # macOS hands back NFD names ("i" + combining diaeresis); compare in NFC.
    wanted = {unicodedata.normalize("NFC", n).casefold() for n in UNATTR_DIR_NAMES}
    for p in sorted(parent.iterdir()):
        if p.is_dir() and unicodedata.normalize("NFC", p.name).casefold() in wanted:
            return p
    return None


def _named_subdir(parent: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        p = parent / name
        if p.is_dir():
            return p
    return None


def discover_source(src: Path) -> SourceLayout:
    """Accept either ``hand/`` + ``unattributed/`` or mole's ``KA_*`` + ``unidentified/``."""
    src = src.resolve()
    if not src.is_dir():
        raise FileNotFoundError(src)

    nested_hand = _named_subdir(src, HAND_DIR_NAMES)
    if nested_hand is not None:
        tentative: set[str] = set()
        hands = _hand_folders(nested_hand, tentative)
        unattr = _unattributed_dir(src) or _unattributed_dir(nested_hand)
        if hands or unattr is not None:
            return SourceLayout(src=src, hands=hands, unattributed=unattr,
                                kind="hand_unattributed", tentative=tentative)

    tentative = set()
    hands = _hand_folders(src, tentative)
    unattr = _unattributed_dir(src)
    if hands or unattr is not None:
        return SourceLayout(src=src, hands=hands, unattributed=unattr,
                            kind="ka_unidentified", tentative=tentative)

    raise ValueError(
        f"{src} has neither hand/+unattributed/ nor KA_* folders. "
        "Pass --src at the folder that actually contains the photographs."
    )


def dest_paths(dest: Path, layout: SourceLayout) -> tuple[dict[str, Path], Path]:
    hand_dest = {name: dest / "hand" / name for name in layout.hands}
    unattr_dest = dest / "unattributed"
    return hand_dest, unattr_dest


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # APFS clonefile when available: full copy semantically, no extra 1.4G.
    try:
        subprocess.run(["cp", "-c", str(src), str(dst)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        shutil.copy2(src, dst)


def copy_raw(src: Path, dest: Path, force: bool = False) -> dict:
    """Copy originals into dest/hand/<KA_*>/ and dest/unattributed/.

    An unattributed file that is byte-identical to a hand-folder photograph
    is not copied (the attributed path is enough). Sibling scans still copy.
    """
    layout = discover_source(src)
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    copied, skipped, not_copied = 0, 0, 0
    attributed: dict[str, Path] = {}
    for hand, folder in layout.hands.items():
        target_dir = dest / "hand" / hand
        for img in iter_images(folder):
            rel = img.relative_to(folder)
            target = target_dir / rel
            if target.exists() and not force:
                skipped += 1
            else:
                _copy_file(img, target)
                copied += 1
            attributed.setdefault(img.name, target)
    if layout.unattributed is not None:
        target_dir = dest / "unattributed"
        for img in iter_images(layout.unattributed):
            keep = attributed.get(img.name)
            if keep is not None and keep.is_file() and file_digest(img) == file_digest(keep):
                not_copied += 1
                continue
            rel = img.relative_to(layout.unattributed)
            target = target_dir / rel
            if target.exists() and not force:
                skipped += 1
                continue
            _copy_file(img, target)
            copied += 1
    return {
        "kind": layout.kind,
        "hands": sorted(layout.hands),
        "tentative": sorted(layout.tentative),
        "copied": copied,
        "skipped": skipped,
        "unattributed_identical_skipped": not_copied,
        "dest": str(dest),
    }


def list_copied_rows(raw_root: Path) -> list[dict]:
    """One row per image under data/raw with folder + optional hand_id."""
    raw_root = raw_root.resolve()
    rows = []
    hand_root = raw_root / "hand"
    if hand_root.is_dir():
        for hand, folder in _hand_folders(hand_root).items():
            for img in iter_images(folder):
                rel = img.relative_to(raw_root).as_posix()
                rows.append({
                    "relative_path": rel,
                    "filename": img.name,
                    "folder": f"hand/{hand}",
                    "hand_id": hand,
                    "abs_path": str(img),
                })
    unattr = raw_root / "unattributed"
    if unattr.is_dir():
        for img in iter_images(unattr):
            rel = img.relative_to(raw_root).as_posix()
            rows.append({
                "relative_path": rel,
                "filename": img.name,
                "folder": "unattributed",
                "hand_id": "",
                "abs_path": str(img),
            })
    rows.sort(key=lambda r: (r["folder"], r["filename"], r["relative_path"]))
    return rows


def drop_unattributed_identical(raw_root: Path) -> list[dict]:
    """Delete unattributed files that match a KA_* copy byte-for-byte.

    Two attributed copies (KA_8 vs KA_10) are left in place.
    """
    raw_root = raw_root.resolve()
    rows = list_copied_rows(raw_root)
    by_fn: dict[str, list[dict]] = {}
    for r in rows:
        by_fn.setdefault(r["filename"], []).append(r)
    dropped: list[dict] = []
    for fn, copies in sorted(by_fn.items()):
        attributed = [r for r in copies if r.get("hand_id")]
        unattr = [r for r in copies if not r.get("hand_id")]
        if not attributed or not unattr:
            continue
        attr_hash = {r["relative_path"]: file_digest(Path(r["abs_path"])) for r in attributed}
        hashes = set(attr_hash.values())
        for r in unattr:
            path = Path(r["abs_path"])
            if not path.is_file():
                continue
            digest = file_digest(path)
            if digest not in hashes:
                continue
            keep = next(a for a in attributed if attr_hash[a["relative_path"]] == digest)
            path.unlink()
            dropped.append({
                "filename": fn,
                "dropped_path": r["relative_path"],
                "kept_path": keep["relative_path"],
                "hand_id": keep["hand_id"],
                "sha256": digest,
            })
    return dropped
