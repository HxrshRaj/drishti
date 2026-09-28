"""Parity (performance-across-imagery-conditions) computation for Phase 5.4
/ SOP-011. This is a performance-parity check across measurable image
properties (brightness, resolution, scene/class mix) — NOT social-bias
detection; the groups compared are properties of the photograph, not of
people. Pure functions here are unit-testable without loading any model;
benchmarks/eval_perception.py calls these on real VLM predictions.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

VEHICLE_CLASSES = {"car", "van", "truck", "bus", "motor", "bicycle", "tricycle", "awning-tricycle"}
PERSON_CLASSES = {"people", "pedestrian"}

GAP_THRESHOLD_PP = 10.0  # SOP-011
MIN_GROUP_SAMPLES = 10  # SOP-011


def brightness_bin(image: Image.Image) -> str:
    arr = np.asarray(image.convert("L"), dtype=np.float32)
    mean_luminance = float(arr.mean())
    if mean_luminance < 85:
        return "low"
    if mean_luminance < 170:
        return "medium"
    return "high"


def resolution_bin(width: int, height: int) -> str:
    pixels = width * height
    if pixels < 720 * 480:
        return "low_res"
    if pixels <= 1280 * 720:
        return "mid_res"
    return "high_res"


def scene_mix(gt_labels: set[str]) -> str:
    has_vehicle = bool(gt_labels & VEHICLE_CLASSES)
    has_person = bool(gt_labels & PERSON_CLASSES)
    if has_vehicle and has_person:
        return "mixed"
    if has_vehicle:
        return "vehicle_only"
    if has_person:
        return "person_only"
    return "other"


def is_correct(finding_type: str, gt_labels: set[str]) -> bool:
    """A finding is scored correct if its coarse category (vehicle /
    personnel / nothing) matches what's actually in the ground truth
    labels for that image. This is a coarse presence-detection accuracy
    metric, matched to what the VLM is actually asked to report (see
    docs/data.md for why VisDrone's traffic/pedestrian classes are what's
    available, not structural-defect labels).
    """
    ft = finding_type.lower()
    has_vehicle = bool(gt_labels & VEHICLE_CLASSES)
    has_person = bool(gt_labels & PERSON_CLASSES)

    predicts_vehicle = "vehicle" in ft or "car" in ft or "van" in ft or "truck" in ft
    predicts_person = "person" in ft or "personnel" in ft or "people" in ft or "pedestrian" in ft
    predicts_nothing = ft in ("no_finding", "none", "nothing")

    if predicts_nothing:
        return not has_vehicle and not has_person
    if predicts_vehicle and has_vehicle:
        return True
    if predicts_person and has_person:
        return True
    if predicts_vehicle and predicts_person:
        return has_vehicle or has_person
    return False


@dataclass
class ParityGroupResult:
    group_key: str
    group_value: str
    n: int
    accuracy: float
    low_confidence_note: bool


def compute_parity_report(records: list[dict]) -> dict:
    """records: [{"finding_type": str, "gt_labels": list[str],
    "brightness_bin": str, "resolution_bin": str, "scene_mix": str}, ...]
    """
    n = len(records)
    overall_correct = sum(1 for r in records if is_correct(r["finding_type"], set(r["gt_labels"])))
    overall_accuracy = overall_correct / n if n else 0.0

    groups: dict[str, dict[str, list[bool]]] = {"brightness_bin": {}, "resolution_bin": {}, "scene_mix": {}}
    for r in records:
        correct = is_correct(r["finding_type"], set(r["gt_labels"]))
        for group_key in groups:
            groups[group_key].setdefault(r[group_key], []).append(correct)

    group_results = []
    flags = []
    for group_key, values in groups.items():
        for value, corrects in values.items():
            acc = sum(corrects) / len(corrects)
            low_conf = len(corrects) < MIN_GROUP_SAMPLES
            group_results.append(ParityGroupResult(group_key, value, len(corrects), acc, low_conf).__dict__)
            gap_pp = (overall_accuracy - acc) * 100
            if gap_pp > GAP_THRESHOLD_PP and not low_conf:
                flags.append({
                    "group_key": group_key, "group_value": value, "accuracy": acc,
                    "gap_pp": round(gap_pp, 1), "n": len(corrects),
                })

    return {
        "n_total": n, "overall_accuracy": overall_accuracy,
        "group_results": group_results, "flags": flags,
        "gap_threshold_pp": GAP_THRESHOLD_PP, "min_group_samples": MIN_GROUP_SAMPLES,
    }
