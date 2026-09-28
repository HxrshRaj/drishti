from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DroneStatus(str, Enum):
    idle = "idle"
    charged = "charged"
    flying = "flying"
    capturing = "capturing"
    returning = "returning"
    offline = "offline"
    maintenance = "maintenance"


class WeatherFlag(str, Enum):
    clear = "clear"
    moderate = "moderate"
    severe = "severe"


class ZoneClass(str, Enum):
    A = "A"  # no-fly
    B = "B"  # restricted, needs approval
    C = "C"  # caution


class Zone(BaseModel):
    zone_id: str
    zone_class: ZoneClass
    label: str
    # axis-aligned box in the site's local waypoint-index coordinate space
    x_min: float
    x_max: float
    y_min: float
    y_max: float


class Waypoint(BaseModel):
    waypoint_id: str
    site_id: str
    x: float
    y: float
    altitude_m: float
    zone_id: str | None = None


class Site(BaseModel):
    site_id: str
    name: str
    weather: WeatherFlag = WeatherFlag.clear
    zones: list[Zone] = Field(default_factory=list)
    waypoints: list[Waypoint] = Field(default_factory=list)


class Drone(BaseModel):
    drone_id: str
    site_id: str
    status: DroneStatus
    battery_pct: float
    position: tuple[float, float] = (0.0, 0.0)
    home: tuple[float, float] = (0.0, 0.0)
    ambient_c: float = 18.0


class GotoRequest(BaseModel):
    mission_id: str
    waypoint_id: str


class GotoResponse(BaseModel):
    drone_id: str
    waypoint_id: str
    status: DroneStatus
    battery_pct: float
    event: str


class CaptureRequest(BaseModel):
    mission_id: str
    waypoint_id: str


class Detection(BaseModel):
    label: str
    bbox_xywh_px: list[float]
    truncation: int = 0
    occlusion: int = 0


class CaptureResponse(BaseModel):
    drone_id: str
    waypoint_id: str
    image_url: str
    image_file: str
    width: int
    height: int
    ground_truth_detections: list[Detection]
    battery_pct: float
    status: DroneStatus


class RthRequest(BaseModel):
    mission_id: str
    reason: str


class RthResponse(BaseModel):
    drone_id: str
    status: DroneStatus
    battery_pct: float
    position: tuple[float, float]


class InjectFailureRequest(BaseModel):
    drone_id: str
    failure_type: str  # drone_offline | capture_timeout | low_battery_critical | none


class FleetStatusResponse(BaseModel):
    drones: list[Drone]


class ErrorResponse(BaseModel):
    error: str
    detail: str
