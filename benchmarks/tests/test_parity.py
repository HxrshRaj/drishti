from PIL import Image

from parity import (
    GAP_THRESHOLD_PP, brightness_bin, compute_parity_report, is_correct, resolution_bin, scene_mix,
)


def test_brightness_bin_boundaries():
    dark = Image.new("RGB", (10, 10), (10, 10, 10))
    mid = Image.new("RGB", (10, 10), (120, 120, 120))
    bright = Image.new("RGB", (10, 10), (240, 240, 240))
    assert brightness_bin(dark) == "low"
    assert brightness_bin(mid) == "medium"
    assert brightness_bin(bright) == "high"


def test_resolution_bin():
    assert resolution_bin(640, 360) == "low_res"
    assert resolution_bin(960, 540) == "mid_res"
    assert resolution_bin(1920, 1080) == "high_res"


def test_scene_mix():
    assert scene_mix({"car", "van"}) == "vehicle_only"
    assert scene_mix({"people"}) == "person_only"
    assert scene_mix({"car", "people"}) == "mixed"
    assert scene_mix(set()) == "other"


def test_is_correct_vehicle_prediction():
    assert is_correct("vehicle_presence", {"car"}) is True
    assert is_correct("vehicle_presence", {"people"}) is False


def test_is_correct_person_prediction():
    assert is_correct("personnel_presence", {"people"}) is True
    assert is_correct("personnel_presence", {"car"}) is False


def test_is_correct_no_finding():
    assert is_correct("no_finding", set()) is True
    assert is_correct("no_finding", {"car"}) is False


def test_compute_parity_report_flags_large_gap():
    records = []
    # group A: perfect accuracy, 15 samples
    for _ in range(15):
        records.append({"finding_type": "vehicle_presence", "gt_labels": ["car"],
                         "brightness_bin": "high", "resolution_bin": "mid_res", "scene_mix": "vehicle_only"})
    # group B: 0% accuracy, 15 samples -> should be flagged
    for _ in range(15):
        records.append({"finding_type": "no_finding", "gt_labels": ["car"],
                         "brightness_bin": "low", "resolution_bin": "mid_res", "scene_mix": "vehicle_only"})

    report = compute_parity_report(records)
    assert report["n_total"] == 30
    flagged_low = [f for f in report["flags"] if f["group_key"] == "brightness_bin" and f["group_value"] == "low"]
    assert len(flagged_low) == 1
    assert flagged_low[0]["gap_pp"] > GAP_THRESHOLD_PP


def test_compute_parity_report_low_sample_group_not_flagged():
    records = [{"finding_type": "vehicle_presence", "gt_labels": ["car"], "brightness_bin": "high",
                "resolution_bin": "mid_res", "scene_mix": "vehicle_only"} for _ in range(20)]
    records += [{"finding_type": "no_finding", "gt_labels": ["car"], "brightness_bin": "low",
                 "resolution_bin": "mid_res", "scene_mix": "vehicle_only"} for _ in range(3)]  # under MIN_GROUP_SAMPLES

    report = compute_parity_report(records)
    flagged_low = [f for f in report["flags"] if f["group_key"] == "brightness_bin" and f["group_value"] == "low"]
    assert flagged_low == []
