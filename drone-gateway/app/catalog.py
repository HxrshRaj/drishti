"""Loads the sampled aerial-imagery catalog and deterministically assigns
images to fictional sites/waypoints so that "capturing" at a waypoint is
reproducible across runs (and so re-capture fallback tests can rely on a
waypoint having more than one candidate image).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

SITE_IDS = ["meridian-substation", "harbor-industrial-park", "north-ridge-corridor"]
WAYPOINTS_PER_SITE = 10
CANDIDATES_PER_WAYPOINT = 3


@dataclass
class ImageRecord:
    file: str
    split: str
    width: int
    height: int
    detections: list[dict]


def load_catalog() -> list[ImageRecord]:
    path = settings.data_labels_file
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            records.append(ImageRecord(
                file=d["file"], split=d["split"], width=d["width"],
                height=d["height"], detections=d["detections"],
            ))
    records.sort(key=lambda r: r.file)
    return records


def assign_to_sites(records: list[ImageRecord]) -> dict[str, dict[str, list[ImageRecord]]]:
    """Returns {site_id: {waypoint_id: [ImageRecord, ...]}}."""
    assignment: dict[str, dict[str, list[ImageRecord]]] = {}
    idx = 0
    n = len(records)
    for site_id in SITE_IDS:
        site_map: dict[str, list[ImageRecord]] = {}
        for wp_i in range(WAYPOINTS_PER_SITE):
            waypoint_id = f"WP-{wp_i + 1:02d}"
            candidates = []
            for _ in range(CANDIDATES_PER_WAYPOINT):
                if n == 0:
                    break
                candidates.append(records[idx % n])
                idx += 1
            site_map[waypoint_id] = candidates
        assignment[site_id] = site_map
    return assignment
