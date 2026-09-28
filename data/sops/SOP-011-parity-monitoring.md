---
id: SOP-011
title: Perception Parity Monitoring Across Imagery Conditions
category: safety
applies_to: [safety-layer, perception-agent]
---

# SOP-011: Perception Parity Monitoring Across Imagery Conditions

## Scope
This SOP governs performance-parity monitoring of the VLM perception
service across measurable imagery conditions — it is not a social-bias
policy. The groups compared are properties of the image (brightness,
scene/class mix, resolution), not protected characteristics of people.

## Groups monitored
- **Brightness bins:** computed from mean pixel luminance, binned into
  low / medium / high.
- **Resolution bins:** by source image resolution (matches the sampled
  dataset's native buckets).
- **Scene/class mix:** whether the dominant labeled objects in the image
  are vehicles, pedestrians, or mixed.

## Threshold
If accuracy for any group falls more than **10 percentage points** below
the overall accuracy, and the group has at least 10 evaluated images, it is
flagged in the parity report as a gap requiring investigation before the
configuration is presented as production-ready.

## Required output
`docs/bias-report.md` must report per-group accuracy, sample counts, and
the gap versus overall accuracy, computed from an actual eval run — not
estimated. If a group has fewer than 10 samples, report it but mark the
result low-confidence rather than omitting it.
