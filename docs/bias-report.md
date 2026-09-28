# Parity Report

**Scope note (SOP-011):** this is a performance-parity check of the
perception model across *measurable properties of the photograph* —
brightness, resolution, and scene/class mix computed from pixel data and
VisDrone's own object labels. It is **not** social-bias detection; no
attribute of a person is used as a grouping variable anywhere in this
report or its code (`benchmarks/parity.py`).

## Method

`benchmarks/build_parity_report.py` reuses the real 20-image VLM run from
`benchmarks/manual_check.py --n 20 --seed 3` (the same run
`docs/benchmarks.md` reports latency from — the expensive model call only
happens once) and computes, per image:

- **brightness_bin**: mean grayscale pixel luminance, binned low (<85) /
  medium (85–170) / high (≥170) of 255.
- **resolution_bin**: source image pixel count, binned low/mid/high-res.
- **scene_mix**: whether VisDrone's ground-truth labels for that image
  include vehicle classes, person classes, or both.
- **correctness**: `benchmarks/parity.py::is_correct` — coarse
  presence-detection match between the VLM's `finding_type` and the
  image's ground-truth classes (vehicle vs. personnel vs. neither).

A group is flagged if its accuracy is more than 10 percentage points below
overall accuracy **and** has at least 10 samples (SOP-011's stated
threshold — a smaller group's gap is reported but marked
`low_confidence_note` rather than flagged, since 1–7 samples isn't enough
to trust a gap estimate).

Reproduce: `python benchmarks/build_parity_report.py`

## Results (real, from the run above)

| group | value | n | accuracy | |
|---|---|---|---|---|
| brightness | medium | 12 | 100.0% | |
| brightness | low | 7 | 100.0% | low sample |
| brightness | high | 1 | 100.0% | low sample |
| resolution | high_res | 19 | 100.0% | |
| resolution | mid_res | 1 | 100.0% | low sample |
| scene mix | mixed (vehicle+person) | 10 | 100.0% | |
| scene mix | vehicle_only | 10 | 100.0% | |

**Overall accuracy: 100.0% (20/20). No groups flagged.**

## Read this honestly, not triumphantly

A 100% accuracy number with zero parity gaps looks like a clean result.
It is real — reproducible from the exact run above — but it is a weak
signal for two concrete, checkable reasons, not a general endorsement of
the model:

1. **The accuracy metric itself is coarse and the sample is small and
   imbalanced.** `is_correct` only checks whether the predicted category
   (vehicle / personnel / neither) matches ground truth at a coarse level,
   and all 20 sampled images contain at least one vehicle (VisDrone is a
   traffic dataset — this is expected, see `docs/data.md`). A finding of
   "vehicle_presence" is correct on essentially every image in this
   sample by construction, and `docs/benchmarks.md` documents directly
   that the model *did* default to `vehicle_presence` on 18/20 images
   regardless of what else was in frame.
2. **Most groups are under the 10-sample confidence threshold.** Only
   `brightness=medium` (n=12), `resolution=high_res` (n=19), and both
   `scene_mix` groups (n=10 each) clear it; `brightness=low` (n=7),
   `brightness=high` (n=1), and `resolution=mid_res` (n=1) are reported
   but explicitly marked low-confidence — an accuracy of "100%" on a
   single image is not evidence of anything.

**What this report actually demonstrates working:** the parity-checking
*mechanism* — brightness/resolution/scene binning, the gap-vs-threshold
comparison, and the low-sample-size guard — runs end-to-end on real
predictions and would surface a real gap if the sample contained one. It
does not yet demonstrate the model is free of imagery-condition bias,
because this sample doesn't have enough low-light / high-resolution /
vehicle-free images to stress-test that. A larger, more deliberately
stratified sample (in particular: more low-light images, and images with
no vehicles at all) is the natural next step and is called out here
rather than glossed over — see `docs/limitations.md`.
