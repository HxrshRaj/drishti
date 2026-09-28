from __future__ import annotations

import math
import random
import time

from app.catalog import CANDIDATES_PER_WAYPOINT, SITE_IDS, WAYPOINTS_PER_SITE, ImageRecord, assign_to_sites, load_catalog
from app.models import Drone, DroneStatus, Site, Waypoint, WeatherFlag, Zone, ZoneClass


class GatewayError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_sites() -> dict[str, Site]:
    """Lay waypoints out on a simple 5x2 grid per site and carve out one
    Class A (no-fly), one Class B (restricted), and the rest Class C zones.
    """
    sites: dict[str, Site] = {}
    for site_id in SITE_IDS:
        zones = [
            Zone(zone_id=f"{site_id}-zone-a", zone_class=ZoneClass.A,
                 label="active equipment yard (no-fly)", x_min=3.5, x_max=5.5, y_min=0.5, y_max=1.5),
            Zone(zone_id=f"{site_id}-zone-b", zone_class=ZoneClass.B,
                 label="perimeter fence / occupied structure (restricted)", x_min=1.5, x_max=3.5, y_min=0.5, y_max=1.5),
            Zone(zone_id=f"{site_id}-zone-c", zone_class=ZoneClass.C,
                 label="tree line / low-visibility corridor (caution)", x_min=-0.5, x_max=1.5, y_min=-0.5, y_max=2.5),
        ]
        waypoints = []
        for i in range(WAYPOINTS_PER_SITE):
            x = float(i % 5)
            y = float(i // 5)
            zone_id = None
            for z in zones:
                if z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max:
                    zone_id = z.zone_id
                    break
            waypoints.append(Waypoint(
                waypoint_id=f"WP-{i + 1:02d}", site_id=site_id,
                x=x, y=y, altitude_m=30.0, zone_id=zone_id,
            ))
        sites[site_id] = Site(site_id=site_id, name=site_id.replace("-", " ").title(),
                               weather=WeatherFlag.clear, zones=zones, waypoints=waypoints)
    return sites


class FleetSimulator:
    """In-memory simulated drone fleet. Not connected to any real hardware."""

    GOTO_BATTERY_COST_PER_UNIT_DIST = 1.5
    CAPTURE_BATTERY_COST = 1.0

    def __init__(self):
        self.sites = _build_sites()
        records = load_catalog()
        self.image_assignment = assign_to_sites(records)
        self.catalog_size = len(records)

        self.drones: dict[str, Drone] = {}
        for i, site_id in enumerate(SITE_IDS):
            drone_id = f"drone-{i + 1:02d}"
            self.drones[drone_id] = Drone(
                drone_id=drone_id, site_id=site_id, status=DroneStatus.idle,
                battery_pct=100.0, position=(0.0, 0.0), home=(0.0, 0.0),
                ambient_c=18.0,
            )

        # one-shot failure overrides, keyed by drone_id -> failure_type
        self._failure_overrides: dict[str, str] = {}
        # per-(drone_id, waypoint_id) capture counters, for cycling candidates
        self._capture_counts: dict[tuple[str, str], int] = {}
        self.events: list[dict] = []

    # -- admin ----------------------------------------------------------
    def inject_failure(self, drone_id: str, failure_type: str) -> None:
        if drone_id not in self.drones:
            raise GatewayError("unknown_drone", f"no such drone {drone_id}")
        if failure_type == "none":
            self._failure_overrides.pop(drone_id, None)
        else:
            self._failure_overrides[drone_id] = failure_type
        self._log("failure_injected", drone_id, {"failure_type": failure_type})

    def set_weather(self, site_id: str, weather: WeatherFlag) -> None:
        if site_id not in self.sites:
            raise GatewayError("unknown_site", f"no such site {site_id}")
        self.sites[site_id].weather = weather

    def _log(self, event: str, drone_id: str, payload: dict) -> None:
        self.events.append({"ts": time.time(), "event": event, "drone_id": drone_id, "payload": payload})

    def _waypoint(self, site_id: str, waypoint_id: str) -> Waypoint:
        site = self.sites.get(site_id)
        if site is None:
            raise GatewayError("unknown_site", f"no such site {site_id}")
        for wp in site.waypoints:
            if wp.waypoint_id == waypoint_id:
                return wp
        raise GatewayError("unknown_waypoint", f"no such waypoint {waypoint_id} at {site_id}")

    def _consume_override(self, drone_id: str) -> str | None:
        return self._failure_overrides.pop(drone_id, None)

    # -- actions ----------------------------------------------------------
    def goto(self, drone_id: str, mission_id: str, waypoint_id: str) -> Drone:
        drone = self._require_drone(drone_id)
        override = self._consume_override(drone_id)
        if override == "drone_offline":
            drone.status = DroneStatus.offline
            self._log("goto_failed", drone_id, {"reason": "drone_offline", "waypoint_id": waypoint_id})
            raise GatewayError("drone_offline", f"{drone_id} is unreachable")

        wp = self._waypoint(drone.site_id, waypoint_id)
        dist = math.hypot(wp.x - drone.position[0], wp.y - drone.position[1])
        cost = max(0.5, dist * self.GOTO_BATTERY_COST_PER_UNIT_DIST)

        if override == "low_battery_critical":
            drone.battery_pct = min(drone.battery_pct, 12.0)

        drone.status = DroneStatus.flying
        drone.position = (wp.x, wp.y)
        drone.battery_pct = max(0.0, round(drone.battery_pct - cost, 2))
        drone.status = DroneStatus.idle
        self._log("goto", drone_id, {"waypoint_id": waypoint_id, "battery_pct": drone.battery_pct, "cost": cost})
        return drone

    def capture(self, drone_id: str, mission_id: str, waypoint_id: str) -> tuple[Drone, ImageRecord]:
        drone = self._require_drone(drone_id)
        override = self._consume_override(drone_id)
        if override == "capture_timeout":
            self._log("capture_failed", drone_id, {"reason": "capture_timeout", "waypoint_id": waypoint_id})
            raise GatewayError("capture_timeout", f"capture at {waypoint_id} timed out")
        if override == "low_battery_critical":
            drone.battery_pct = min(drone.battery_pct, 12.0)
            self._log("capture_failed", drone_id, {"reason": "low_battery_critical", "waypoint_id": waypoint_id})
            raise GatewayError("low_battery_critical", f"battery {drone.battery_pct}% below critical threshold")

        candidates = self.image_assignment.get(drone.site_id, {}).get(waypoint_id, [])
        if not candidates:
            raise GatewayError("no_imagery", f"no catalog imagery assigned to {waypoint_id} — did you run benchmarks/fetch_dataset.py?")

        key = (drone_id, waypoint_id)
        n = self._capture_counts.get(key, 0)
        record = candidates[n % len(candidates)]
        self._capture_counts[key] = n + 1

        drone.status = DroneStatus.capturing
        drone.battery_pct = max(0.0, round(drone.battery_pct - self.CAPTURE_BATTERY_COST, 2))
        drone.status = DroneStatus.idle
        self._log("capture", drone_id, {"waypoint_id": waypoint_id, "image_file": record.file, "battery_pct": drone.battery_pct})
        return drone, record

    def rth(self, drone_id: str, mission_id: str, reason: str) -> Drone:
        drone = self._require_drone(drone_id)
        self._consume_override(drone_id)
        drone.status = DroneStatus.returning
        drone.position = drone.home
        drone.status = DroneStatus.idle
        self._log("rth", drone_id, {"reason": reason, "battery_pct": drone.battery_pct})
        return drone

    def _require_drone(self, drone_id: str) -> Drone:
        drone = self.drones.get(drone_id)
        if drone is None:
            raise GatewayError("unknown_drone", f"no such drone {drone_id}")
        return drone

    def fleet_status(self) -> list[Drone]:
        return list(self.drones.values())

    def reset_battery(self, drone_id: str, pct: float = 100.0) -> Drone:
        drone = self._require_drone(drone_id)
        drone.battery_pct = pct
        drone.status = DroneStatus.charged
        return drone
