# comital-charters

Dataset construction for the Flanders comital-charter photographs first used
in a preliminary [mole](https://github.com/mikekestemont/mole) run as
`flanders-set-bin` (383 images, 11 hands `KA_*`, 266 labeled; `KA_8` is ~53%
of labels). Sibling photographs of the same charter are flagged the way
[sluis](https://github.com/mikekestemont/sluis) did: `main_document` in the
manifest, files stay on disk.

## Environment

Conda env `comital`, Python 3.10. Tracked files: `environment.yml`,
`requirements.txt`.

```bash
conda env create -f environment.yml
conda activate comital
```

## Source photographs

Originals live in mole's gitignored `data/flanders` (not `flanders-set-bin`,
which is Sauvola prep). On disk that folder is `KA_1/`…`KA_11/` plus
`unidentified/` — there is no parent `hand/` directory. `code/00_copy_raw.py`
maps that layout to:

```
data/raw/hand/KA_8/…
data/raw/unattributed/…
```

`data/raw/` is gitignored. `--src` can also point at a folder that already
contains `hand/` + `unattributed/`. If a photograph already sits in a `KA_*`
hand folder, the byte-identical copy in `unattributed/` is not kept
(`data/dropped_unattributed.csv`). Sibling scans of the same charter still
stay on disk.

## Filename grammar

```
134_2_RAGent K21_98.jpeg
│   │  │      └─ shelfmark
│   │  └─ repository (Rijksarchief Gent)
│   └─ scan index of this charter
└─ inventory number = doc_id
```

`134_2_…` and `134_3_…` are two photos of charter 134 (mole
`--cross-doc-only` / sluis `neardup_of=`). Lowest scan index is
`main_document=1`; extras are `main_document=0`,
`reason=sibling_scan_of=<kept file>`. Same repository+shelfmark with
different leading numbers is **not** merged; it is listed in
`data/shelfmark_collisions.csv`.

A handful of names omit the scan index (`493_AM Lille_PAT-155-2857.jpg`);
those count as scan 1.

## Pipeline

From repo root, `conda activate comital`:

```bash
python code/00_copy_raw.py
python code/01_inventory.py
python code/02_group_docs.py
python code/03_review_docs.py
open outputs/doc_review.html
pytest
```

| # | script | what it does |
|---|---|---|
| 00 | `00_copy_raw.py` | Copy originals into `data/raw/` |
| 01 | `01_inventory.py` | Print folder / name structure |
| 02 | `02_group_docs.py` | Manifest, doc groups, labels, collisions |
| 03 | `03_review_docs.py` | HTML of multi-scan charters |
| 04 | `04_answer_key.py` | Seal Robin's addendum labels (stage 1) |
| 10 | `10_blla_zones.py` | Kraken BLLA, largest region |
| 11 | `11_ls_import.py` | Label Studio import JSON |
| 12 | `12_ls_export.py` | Dump local LS sqlite |
| 13 | `13_apply_ls_zones.py` | Apply corrected boxes, recrop |
| 14 | `14_contrast_stretch.py` | p2→20, p98→255 → `images/zoned-stretched/` |
| 15 | `15_sauvola.py` | Sauvola + corpus-median script scale → `images/zoned-sauvola/` |
| 16 | `16_stage1_pool.py` | Gallery + addendum (unlabeled) as one mole folder |
| 17 | `17_stage1_score.py` | Score mole's addendum proposals against the sealed key |

Scripts 00–02 and 10–15 take `--batch {main,addendum}` (`code/batch.py`);
the default is the frozen 313-charter gallery.

## Main text zones (BLLA + Label Studio)

Gallery is `main_document=1` (313 charters). Sibling extras stay on disk but
are not zoned unless you pass `--all`. Do not binarize. Kraken is already in
the `sluis` env:

```bash
conda activate sluis
python code/10_blla_zones.py --device mps
```

Resume-safe (`data/zones_blla.jsonl`). Crops go to `images/zoned/`. HTML QC:
`outputs/zone_review.html`.

Review boxes in Label Studio the same way as sluis (one MainZone rectangle,
pages start annotated, edit and Update the misses). Label Studio on this
machine is the `bayes` env. It must serve files from **this** repo (restart
if a sluis session is using a different document root):

```bash
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="$PWD"
conda activate bayes
label-studio start
```

```bash
conda activate comital
python code/11_ls_import.py
```

New project → paste `data/ls_config.xml` → Import `data/ls_zones_import.json`.
Then **Settings → Cloud Storage → Add Source Storage**: Local files, absolute
path `$PWD/data`, treat as Files. Save; do not Sync (that would duplicate
tasks). After corrections:

```bash
python code/12_ls_export.py
python code/13_apply_ls_zones.py --export data/ls_zones_export.json
~/GitRepos/mole/.venv/bin/python code/14_contrast_stretch.py
~/GitRepos/mole/.venv/bin/python code/15_sauvola.py
```

Stretch and Sauvola write flat folders `images/zoned-stretched/` and
`images/zoned-sauvola/` (PNG basename only; `data/raw/` keeps the original
hand folders).

## Script-scale (unlike sluis)

Sluis gallery Sauvola stayed at **native resolution**: same window/k/stretch
(`25` / `0.2` / percentile stretch), **no** `--max-side` and **no** script-module
normalization. `--max-side 1513` was only applied to Büdingen queries, as a
page-size cap, not letter-size equalization.

Here the gallery is resampled so every page’s **script module** (body height
of the writing, from mole’s folded row-ink `profile`) hits **this corpus’s
own median**, then Sauvola is run again. That is `mole prep --normalize-scale
profile` with `target_module=None` — not a pooled sluis/leroy median, and
still no `--max-side`. The measured target on this run was **42.9 px**
(`auto:195 pages`). Per-page factors and that target live in
`images/zoned-sauvola/scale.json` (`meta.script_module_target`).

On mike this freeze is **`~/mole/data/comital`** (313 PNGs + `labels.csv` +
`scale.json`). Do not confuse it with the legacy `flanders-set` /
`flanders-set-bin` folders — those stay on disk unused.

First SSL eval (epoch ~10 vs raven-raw, VLAD-100, `--cross-doc-only`) did
**not** use `--vlad-intra-norm`. Try it later: mole found ~+0.09 macro on
the old Flanders set because of KA_8 skew; same skew is still here. Re-embed
with the flag; do not refit the codebook. Reports live in
`~/mole/outputs/comital/`.

Hand-folder collisions (byte-identical photos in two `KA_*` folders) were
resolved by colleagues; files stay on disk in both places, labels come from
`data/hand_verdicts.csv`:

| charter | shelfmark | hand |
|---|---|---|
| 30 | RA Brugge, INV 120_7435 | `KA_10` |
| 47 | Stadsarchief Gent, 94_75 | `KA_9` |
| 458 | RA Gent, K16_39 | `KA_10` |

Gallery freeze still keeps one copy (`main_document=1`).

Robin’s review of an earlier similarity dump found several photographs that
had been copied into `KA_8` as well as `unidentified/`. Those `KA_8` copies
are gone from the originals (charters 20, 22, 575, 576, 582, 608). Charter
314 is a true `KA_8` match he confirmed after the dump (`data/holdout.csv`)
and stays unattributed so the matcher can be tested on a known miss.

Charter 314 (ADN Lille 31H63_974) is a true `KA_8` match Robin confirmed
after an earlier similarity dump and is left **unattributed** on purpose
(`data/holdout.csv`) so the matcher can be tested on a known miss. Do not
fold it into a hand folder. Photographs that sat in both `unidentified/`
and `KA_8/` without Robin’s identification were moved back to
`unidentified/` in the original `flanders` tree.

## Addendum (Robin, 2026-09) — stage 1: prospective validation

Robin's second delivery sits in
`data/KESTEMONT-WAEYTENS_Corpus-Margareta1270_Addendum/` (gitignored, as
delivered): **32 charters, doc ids 486–712, none of them in the 313-charter
gallery, one photograph each**. His folders spell hands `KA1`, `KA8`,
`KA12(?)`, and the rest `Ongeïdentificeerd`; `code/layout.py` canonicalises
those to `KA_1`, `KA_8`, `KA_12` (flagged *tentative*) and `unattributed`
(matching in NFC — macOS hands the `ï` back decomposed).

| what Robin says | n | hands |
|---|---|---|
| identified | 24 | KA_8 ×17, KA_1 ×2, KA_10 ×2, KA_2, KA_9, KA_11 |
| "mogelijk eenzelfde hand (een 12e kanselarijhand!)", unconfirmed | 2 | 656, 709 → `KA_12`, tentative |
| ongeïdentificeerd | 6 | 665, 676, 689, 704, 705, 706 |

Addendum filenames use a different grammar (scan index trailing, `…_58_1.jpg`;
` (1)` download suffix on the Bijloke files; `RABergen_ AEM.`). Doc ids parse
correctly and each charter occurs once, so grouping is right; the shelfmark /
collision-key columns of `data/addendum/manifest.csv` are cosmetically off and
were left alone.

### Why not simply fold them in

The leave-one-out numbers on the gallery (mAP 0.74, Top-1 0.94 after SSL
fine-tuning) are retrospective: the model was fine-tuned — without labels, but
still — on the very charters it is scored on. Robin labeled the addendum
**before the software saw a single photograph of it**, and the fine-tuned
checkpoint has never seen these images either. That is a prospective test we
can only run once: the moment the gallery is rebuilt and re-fine-tuned on 345
charters, it is gone. So the addendum is first scored *blind* (stage 1), and
only afterwards merged (stage 2, not yet decided).

### The sealed key

`data/addendum/answer_key.csv` (committed, written once by
`04_answer_key.py`; `--force` to rewrite) is Robin's identification per
charter with `status ∈ {confirmed, tentative, unidentified}`, plus holdout
charter 314 (`KA_8`, `data/holdout.csv`) so both known-miss tests are scored
in one table. The software never reads this file; `17_stage1_score.py`
compares against it afterwards.

### Preprocessing (done, same recipe as the gallery)

```bash
conda activate comital
python code/00_copy_raw.py --batch addendum          # → data/addendum/raw/, hand_folders.csv
python code/02_group_docs.py --batch addendum        # → data/addendum/manifest.csv …
python code/04_answer_key.py --batch addendum        # seal (once)
conda activate sluis
python code/10_blla_zones.py --device mps --batch addendum
conda activate comital
python code/11_ls_import.py --batch addendum         # LS project "comital-addendum"
python code/12_ls_export.py --batch addendum         # after box review
python code/13_apply_ls_zones.py --batch addendum
~/GitRepos/mole/.venv/bin/python code/14_contrast_stretch.py --batch addendum
~/GitRepos/mole/.venv/bin/python code/15_sauvola.py --batch addendum
python code/16_stage1_pool.py                        # → images/stage1-pool/
```

BLLA found a text region on all 32 (no fallbacks). Four zones cover < 20 % of
the page (663, 702, 703, 709) but are correct — small charters photographed on
a large table. The Label Studio pass (project `comital-addendum`) was done on
2026-09-16: 13 of 32 boxes adjusted (487, 656, 663, 665, 667, 669, 670, 671,
689, 704, 707, 708, 709), then 13–16 rerun.

**Sauvola for the addendum pins the script module to the gallery's 42.9 px**
(read from `images/zoned-sauvola/scale.json`, `target_source: given`), it does
not re-measure its own median — the addendum must land in the frozen
gallery's scale space. Result (after the box review): 32/32 measured, median
after 42.9, spread after 0.016 (gallery: 0.023). One page rescaled by ~0.5
(487, large script).

### The pool that goes to mole

`images/stage1-pool/` (gitignored, 76 MB) is one flat mole dataset: 313
gallery PNGs + 32 addendum PNGs, `labels.csv` = the frozen gallery's 209
labels and **nothing for the addendum**, an explicit `doc_ids.csv` (the
addendum names do not follow mole's `flanders` rule), `pool.csv` for
provenance, `focus.txt` = the 32 addendum charters + 314, and `pool.json`.
`16_stage1_pool.py` refuses to build if the two `scale.json` targets differ.

On the GPU box, with the **frozen** fine-tuned checkpoint and the codebook
fitted on the 313 gallery (no refit — fit-on-gallery / apply-on-addendum),
the same `--vlad-intra-norm` setting as the gallery embedding:

```bash
mole embed <finetuned.ckpt> data/stage1-pool outputs/comital/stage1.npy \
    --codebook-from <comital.codebook.npy> [--vlad-intra-norm]
mole review outputs/comital/stage1.npy --out outputs/comital/stage1.review.html \
    --no-false-positives --max-mb 0 --image-scope all
```

### What stage 1 reads off the review sheet

The review sheet is the same `mole review` HTML the Utrecht project uses,
so the two projects stay in sync; nothing is built beside it.

* **False negatives tab** — every addendum charter is "unattributed" to mole,
  so this tab is where its proposals appear. For the 24 confirmed charters
  (+ 314) `17_stage1_score.py` reports Top-1 / Top-3 per hand against the
  sealed key, using mole's own `hand_score_matrix` and calibration, so the
  score is exactly the number behind the tab, not a second matcher. For the
  6 unidentified charters the tab is simply Robin's review sheet, as with 314.
* **New hands tab** — the test for 656 / 709. A hand the gallery does not
  contain cannot be "attributed"; what the software can say is (a) are the two
  each other's nearest cross-document neighbour, and (b) do they sit far from
  every known hand (low calibrated P, small margin). Both agreeing with Robin
  is independent evidence for a 12th chancery hand; 656 landing with a high P
  on KA_8 is evidence against.

```bash
~/GitRepos/mole/.venv/bin/python code/17_stage1_score.py outputs/comital/stage1.npy
# → outputs/stage1/stage1.scores.csv + per-hand table
```

Report counts, not only percentages: 25 confirmed queries, so one miss moves
Top-1 by 4 points; 17 of the 24 are KA_8 again, and the KA_11 query is the
interesting one (3 gallery charters).

**The sheet stays as mole builds it (decided 2026-09-16).** `mole review`
caps the false-negatives tab at `ATTRIB_PER_HAND_CAP = 8` proposals per hand
and `--limit` overall, ranked by calibrated P over *all* unlabeled charters
(the 104 old unattributed gallery charters included), so not every one of the
17 KA_8 addendum charters will be on the sheet Robin receives. That is
accepted: the sheet is his review tool, not the scoreboard. The full stage-1
table comes from `17_stage1_score.py`, which reads the same score matrix
uncapped, and its `on_sheet` column replays mole's own selection (join-z
filter → calibrated-P sort → per-hand cap → `--limit`, pass the same
`--limit` the sheet was built with) so it is known which focus charters Robin
actually sees. No `--focus` option is added to mole for this.

### Stage 1 result (2026-09-16)

Embedding `outputs/stage1/stage1.ssl.final.npy` (server: `runs/comital_ssl_sauvola/checkpoint.pth`
step 40160, `--codebook-from comital.sauvola.ssl.final.codebook.npy`, no
intra-norm — the same configuration as the 0.74 / 0.65 / 0.94 gallery numbers).
`17_stage1_score.py` → `outputs/stage1/stage1.ssl.final.scores.csv`:

| | n | Top-1 | Top-3 |
|---|---|---|---|
| confirmed (24 addendum + 314) | 25 | **25** | 25 |
| of which KA_8 | 18 | 18 | 18 |
| KA_1 / KA_10 | 2 / 2 | 2 / 2 | |
| KA_2 / KA_9 / KA_11 | 1 each | 1 each | |

Six of the 25 have a calibrated P of only 0.67 (coarse isotonic steps), all
still top-1. 314 (the earlier known miss) is top-1 KA_8 at P = 1.00.

**656 / 709 (Robin's tentative KA_12):** each other's nearest cross-document
neighbour in the whole 345-charter pool (cosine 0.495; best gallery match for
either is ~0.31), and a cluster of exactly two at the finest FINCH / HDBSCAN
cut. Independent support for a twelfth hand. Mole's new-hands tab stays empty
because it reads the ARI-best FINCH level (L1, 14 clusters), where the pair is
absorbed into a 24-charter cluster with 14 labeled members — kept as is, per
the decision above; the evidence is in the scores table. Gallery charter 190
(unattributed) and addendum 708 (KA_8 per Robin) are the next neighbours of
both — worth a look.

**Unidentified six** (proposals, not on the sheet unless marked): 689 → KA_9
(P 1.00, on sheet), 706 → KA_1 (0.74), 705 → KA_4 (0.67, on sheet), 665 →
KA_1 (0.67), 676 → KA_11 (0.67, margin 0.006), 704 → KA_9 (0.67, margin
0.001 — a coin flip with KA_7).

Deliverables built on the laptop (the review code is uncommitted there, see
below): `outputs/stage1/stage1.ssl.final.review.html` (21 false-negative
cases, 15 of them addendum; 10 MB) and `stage1.ssl.final.viz.html` (map, 33
focus charters ringed, built with `mole viz --no-highlight-labels`, neighbour lines off; 10 MB). `mole review` / `mole viz` need the sidecar's
relative `data/stage1-pool/…` to resolve: `~/GitRepos/mole/data/stage1-pool`
is a symlink to `images/stage1-pool`, run from `~/GitRepos/mole`.

**Mole state:** the three-tab review sheet and `--no-highlight-labels` are
mole commit `9acb0d1` (2026-09-16). The server was still on `0077799` when
stage 1 ran — `git pull` there before building sheets server-side.

### Stage 2 (not decided)

Merging the addendum into the gallery — rebuild with 345 charters (a `batch`
column keeps provenance), re-fine-tune, rerun leave-one-out, then the Leroy
comparison — is deliberately not started. Nothing in stage 1 touches
`data/raw`, `images/zoned*`, `data/labels.csv` or the gallery's `scale.json`.
