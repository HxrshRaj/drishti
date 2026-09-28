"""Thin HTTP client the orchestrator uses to call the simulated
drone-gateway service — real HTTP calls (or, in tests, a real in-process
ASGI call into the same FastAPI app, still exercising its real logic) so
"agents calling APIs" is not a stub anywhere in this pipeline.
"""
from __future__ import annotations

import httpx

from app.config import settings


class GatewayError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class DroneGatewayClient:
    def __init__(self, client: httpx.Client | None = None, base_url: str | None = None):
        self._owns_client = client is None
        self.client = client or httpx.Client(base_url=base_url or settings.drone_gateway_url, timeout=30)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", {})
                code = detail.get("error", "unknown") if isinstance(detail, dict) else "unknown"
                msg = detail.get("detail", str(detail)) if isinstance(detail, dict) else str(detail)
            except Exception:
                code, msg = "unknown", resp.text
            raise GatewayError(code, msg)

    def list_sites(self) -> list[dict]:
        resp = self.client.get("/sites")
        self._raise_for_status(resp)
        return resp.json()

    def get_site(self, site_id: str) -> dict:
        resp = self.client.get(f"/sites/{site_id}")
        self._raise_for_status(resp)
        return resp.json()

    def get_fleet(self) -> list[dict]:
        resp = self.client.get("/fleet")
        self._raise_for_status(resp)
        return resp.json()["drones"]

    def goto(self, drone_id: str, mission_id: str, waypoint_id: str) -> dict:
        resp = self.client.post(f"/drones/{drone_id}/goto", json={"mission_id": mission_id, "waypoint_id": waypoint_id})
        self._raise_for_status(resp)
        return resp.json()

    def capture(self, drone_id: str, mission_id: str, waypoint_id: str) -> dict:
        resp = self.client.post(f"/drones/{drone_id}/capture", json={"mission_id": mission_id, "waypoint_id": waypoint_id})
        self._raise_for_status(resp)
        return resp.json()

    def rth(self, drone_id: str, mission_id: str, reason: str) -> dict:
        resp = self.client.post(f"/drones/{drone_id}/rth", json={"mission_id": mission_id, "reason": reason})
        self._raise_for_status(resp)
        return resp.json()

    def inject_failure(self, drone_id: str, failure_type: str) -> dict:
        resp = self.client.post("/admin/inject_failure", json={"drone_id": drone_id, "failure_type": failure_type})
        self._raise_for_status(resp)
        return resp.json()
