"""Simulated drone fleet gateway.

This service does not control any real drone or robot. It simulates fleet
state, flight, image capture (served from a licensed aerial-imagery
catalog), and injectable failures so the orchestration layer's fallback
protocols can be exercised against real HTTP calls and real error
conditions, without needing physical hardware.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.fleet import FleetSimulator, GatewayError
from app.models import (
    CaptureRequest, CaptureResponse, Detection, ErrorResponse, FleetStatusResponse,
    GotoRequest, GotoResponse, InjectFailureRequest, RthRequest, RthResponse, Site, WeatherFlag,
)

app = FastAPI(
    title="Drishti Drone Gateway (Simulated)",
    description="Simulated drone fleet gateway — no real drones are controlled by this service.",
    version="0.1.0",
)

fleet = FleetSimulator()


@app.get("/health")
def health():
    return {"status": "ok", "simulated": True, "fleet_size": len(fleet.drones), "catalog_size": fleet.catalog_size}


@app.get("/fleet", response_model=FleetStatusResponse)
def get_fleet():
    return FleetStatusResponse(drones=fleet.fleet_status())


@app.get("/sites", response_model=list[Site])
def list_sites():
    return list(fleet.sites.values())


@app.get("/sites/{site_id}", response_model=Site)
def get_site(site_id: str):
    site = fleet.sites.get(site_id)
    if site is None:
        raise HTTPException(404, detail=f"no such site {site_id}")
    return site


@app.post("/sites/{site_id}/weather")
def set_weather(site_id: str, weather: WeatherFlag):
    try:
        fleet.set_weather(site_id, weather)
    except GatewayError as e:
        raise HTTPException(404, detail=e.detail) from e
    return {"site_id": site_id, "weather": weather}


@app.post("/drones/{drone_id}/goto", response_model=GotoResponse)
def goto(drone_id: str, req: GotoRequest):
    try:
        drone = fleet.goto(drone_id, req.mission_id, req.waypoint_id)
    except GatewayError as e:
        raise HTTPException(_status_for(e.code), detail={"error": e.code, "detail": e.detail}) from e
    return GotoResponse(drone_id=drone_id, waypoint_id=req.waypoint_id, status=drone.status,
                         battery_pct=drone.battery_pct, event="goto_complete")


@app.post("/drones/{drone_id}/capture", response_model=CaptureResponse)
def capture(drone_id: str, req: CaptureRequest):
    try:
        drone, record = fleet.capture(drone_id, req.mission_id, req.waypoint_id)
    except GatewayError as e:
        raise HTTPException(_status_for(e.code), detail={"error": e.code, "detail": e.detail}) from e
    return CaptureResponse(
        drone_id=drone_id, waypoint_id=req.waypoint_id,
        image_url=f"/images/{record.file}", image_file=record.file,
        width=record.width, height=record.height,
        ground_truth_detections=[Detection(**d) for d in record.detections],
        battery_pct=drone.battery_pct, status=drone.status,
    )


@app.post("/drones/{drone_id}/rth", response_model=RthResponse)
def rth(drone_id: str, req: RthRequest):
    try:
        drone = fleet.rth(drone_id, req.mission_id, req.reason)
    except GatewayError as e:
        raise HTTPException(_status_for(e.code), detail={"error": e.code, "detail": e.detail}) from e
    return RthResponse(drone_id=drone_id, status=drone.status, battery_pct=drone.battery_pct, position=drone.position)


@app.post("/drones/{drone_id}/reset")
def reset(drone_id: str, battery_pct: float = 100.0):
    try:
        drone = fleet.reset_battery(drone_id, battery_pct)
    except GatewayError as e:
        raise HTTPException(404, detail=e.detail) from e
    return drone


@app.post("/admin/inject_failure")
def inject_failure(req: InjectFailureRequest):
    try:
        fleet.inject_failure(req.drone_id, req.failure_type)
    except GatewayError as e:
        raise HTTPException(404, detail=e.detail) from e
    return {"drone_id": req.drone_id, "failure_type": req.failure_type}


@app.get("/admin/events")
def get_events(limit: int = 100):
    return fleet.events[-limit:]


@app.get("/images/{filename}")
def get_image(filename: str):
    path = settings.data_images_dir / filename
    if not path.exists():
        raise HTTPException(404, detail=f"no such image {filename}")
    return FileResponse(path)


def _status_for(code: str) -> int:
    return {
        "unknown_drone": 404, "unknown_site": 404, "unknown_waypoint": 404, "no_imagery": 404,
        "drone_offline": 503, "capture_timeout": 504, "low_battery_critical": 409,
    }.get(code, 400)
