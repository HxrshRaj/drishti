# Data

## Imagery: VisDrone2019-DET (sampled subset)

**Source:** [`Voxel51/VisDrone2019-DET`](https://huggingface.co/datasets/Voxel51/VisDrone2019-DET)
on the Hugging Face Hub — a [FiftyOne](https://github.com/voxel51/fiftyone)
re-packaging of the official **VisDrone2019-DET** benchmark released by the
AISKYEYE team, Lab of Machine Learning and Data Mining, Tianjin University,
China (repository: https://github.com/VisDrone/VisDrone-Dataset, paper:
Zhu et al., "Detection and Tracking Meet Drones Challenge," IEEE TPAMI 2021,
DOI [10.1109/TPAMI.2021.3119563](https://doi.org/10.1109/TPAMI.2021.3119563)).

**License:** the dataset card's tag says `cc-by-sa-3.0`, but the dataset
card's own copyright text is more specific and is what actually governs
use: **Creative Commons Attribution-NonCommercial-ShareAlike 3.0**
(CC BY-NC-SA 3.0) — attribution required, non-commercial use only,
derivatives must share alike. This repository (code MIT-licensed, imagery
and labels CC BY-NC-SA 3.0) is a non-commercial educational/portfolio
project, which is consistent with that license. **Do not use `data/images/`
or `data/labels/` for any commercial purpose.**

### Why VisDrone, and an honest caveat about domain fit

The build brief allowed VisDrone or DOTA as example choices for openly
licensed aerial imagery with usable labels. VisDrone's own annotations are
traffic/pedestrian object-detection classes (car, van, truck, bus,
pedestrian, people, bicycle, motor, tricycle, awning-tricycle) — it is a
**traffic and pedestrian surveillance** dataset, not an infrastructure-
defect inspection dataset (cracks, corrosion, vegetation encroachment on
towers, etc.). No openly-licensed public dataset combining real aerial
drone imagery with structural-defect labels and permissive redistribution
terms was readily available in the time budget for this project.

Given that, Drishti's perception layer is honestly scoped as a **site
monitoring / object-presence inspection** system rather than a structural-
defect detector: findings are framed as "unauthorized vehicle in a
restricted zone," "personnel presence in a caution zone," "congestion/
obstruction on an access route," etc. — all things VisDrone's real labels
support — rather than invented crack/corrosion findings the model was never
trained or evaluated on. This is called out again in `docs/limitations.md`.

### Sampling

Script: [`benchmarks/fetch_dataset.py`](../benchmarks/fetch_dataset.py).
Reproduce with:

```bash
python benchmarks/fetch_dataset.py --n 350 --seed 7 --min-detections 2
```

Procedure:
1. Download the FiftyOne label export (`samples.json`, ~8,629 samples across
   train/val/test) from the dataset repo.
2. Keep only samples with at least 2 detections in the 10 "real" classes
   above (excludes the dataset's `ignore_regions`/`others` catch-alls and
   near-empty frames, so the demo has meaningful findings to perceive).
3. Deterministically shuffle (seed 7) and take the first 350.
4. Download each sampled image and write per-image labels (class, pixel-
   space bounding box, truncation, occlusion, split) to
   `data/labels/labels.jsonl`.

### Resulting sample (actual counts from the run in this repo)

| | |
|---|---|
| Images | 350 |
| Split | train 264 / test 65 / val 21 |
| Detections (10 real classes) | 14,713 total |

Per-class detection counts:

| class | count |
|---|---|
| car | 7,798 |
| people | 1,906 |
| motor | 1,752 |
| van | 1,308 |
| bicycle | 680 |
| truck | 631 |
| bus | 385 |
| tricycle | 253 |

(Full machine-readable version: `data/labels/class_counts.json`.)

Class imbalance (car >> tricycle) is real and is carried into the parity
report (`docs/bias-report.md`) as a factor worth checking accuracy against,
alongside brightness/resolution bins.

### Files committed to this repo

`data/images/*.jpg` (350 files) and `data/labels/labels.jsonl` /
`class_counts.json` are committed directly (not fetched at CI/build time)
so a fresh clone reproduces every downstream result without depending on
Hugging Face being reachable. `data/raw_cache/` (the full 8,629-sample
label export, ~118MB) is *not* committed — it's a local cache the fetch
script uses to avoid re-downloading; delete it freely.

## Site knowledge base (SOPs)

`data/sops/*.md` — 14 short, self-authored, fictional SOP documents
(restricted zones, battery thresholds, severity classification, approval
gates, fallback protocols, failure/RTH handling, verifier escalation,
pre-flight checklist, report format, memory retention, parity monitoring,
multi-drone deconfliction, weather limits, audit logging). These are
original text written for this project, not sourced from any real
company's procedures, and are the corpus the RAG layer retrieves against
(see `docs/architecture.md` and the retrieval-quality numbers in
`docs/benchmarks.md`).
