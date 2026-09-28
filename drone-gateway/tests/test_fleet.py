import pytest
from fastapi.testclient import TestClient

from app.main import app, fleet

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True
    assert body["fleet_size"] == 3


def test_fleet_status():
    r = client.get("/fleet")
    assert r.status_code == 200
    drones = r.json()["drones"]
    assert len(drones) == 3
    assert all(d["battery_pct"] == 100.0 for d in drones)


def test_sites_have_zones_and_waypoints():
    r = client.get("/sites")
    sites = r.json()
    assert len(sites) == 3
    for site in sites:
        assert len(site["waypoints"]) == 10
        assert len(site["zones"]) == 3
        classes = {z["zone_class"] for z in site["zones"]}
        assert classes == {"A", "B", "C"}


def test_goto_and_capture_happy_path():
    drone_id = "drone-01"
    r = client.post(f"/drones/{drone_id}/goto", json={"mission_id": "m1", "waypoint_id": "WP-06"})
    assert r.status_code == 200
    assert r.json()["status"] == "idle"

    r = client.post(f"/drones/{drone_id}/capture", json={"mission_id": "m1", "waypoint_id": "WP-06"})
    assert r.status_code == 200
    body = r.json()
    assert body["image_url"].startswith("/images/")
    assert body["width"] > 0 and body["height"] > 0


def test_capture_timeout_failure_injection():
    drone_id = "drone-02"
    client.post("/admin/inject_failure", json={"drone_id": drone_id, "failure_type": "capture_timeout"})
    r = client.post(f"/drones/{drone_id}/capture", json={"mission_id": "m2", "waypoint_id": "WP-01"})
    assert r.status_code == 504
    assert r.json()["detail"]["error"] == "capture_timeout"

    # override is one-shot: next capture should succeed
    r2 = client.post(f"/drones/{drone_id}/capture", json={"mission_id": "m2", "waypoint_id": "WP-01"})
    assert r2.status_code == 200


def test_drone_offline_failure_injection():
    drone_id = "drone-03"
    client.post("/admin/inject_failure", json={"drone_id": drone_id, "failure_type": "drone_offline"})
    r = client.post(f"/drones/{drone_id}/goto", json={"mission_id": "m3", "waypoint_id": "WP-02"})
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "drone_offline"


def test_low_battery_critical_and_rth():
    drone_id = "drone-01"
    client.post("/admin/inject_failure", json={"drone_id": drone_id, "failure_type": "low_battery_critical"})
    r = client.post(f"/drones/{drone_id}/capture", json={"mission_id": "m4", "waypoint_id": "WP-01"})
    assert r.status_code == 409

    r2 = client.post(f"/drones/{drone_id}/rth", json={"mission_id": "m4", "reason": "low_battery_critical"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "idle"
    assert r2.json()["position"] == [0.0, 0.0]


def test_recapture_cycles_through_candidate_images():
    drone_id = "drone-02"
    files = set()
    for _ in range(3):
        r = client.post(f"/drones/{drone_id}/capture", json={"mission_id": "m5", "waypoint_id": "WP-05"})
        files.add(r.json()["image_file"])
    assert len(files) >= 2, "expected re-capture at the same waypoint to cycle through multiple candidate images"


def test_unknown_drone_404():
    r = client.post("/drones/nope/goto", json={"mission_id": "m6", "waypoint_id": "WP-01"})
    assert r.status_code == 404
