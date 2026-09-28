"""Thin service layer wiring MissionState + the compiled LangGraph mission
graph to mission_ids used as LangGraph thread_ids, so a FastAPI route can
start a mission, observe it pause at an interrupt, and resume it later.
"""
from __future__ import annotations

from langgraph.types import Command

from app.memory import repository as repo
from app.orchestration.gateway_client import DroneGatewayClient
from app.orchestration.mission_graph import MissionGraphDeps, build_mission_graph, get_checkpointer


def _deps(max_waypoints: int, perceive_fn, verify_fn, report_fn, gateway_base_url: str | None) -> MissionGraphDeps:
    gateway = DroneGatewayClient(base_url=gateway_base_url) if gateway_base_url else DroneGatewayClient()
    return MissionGraphDeps(gateway=gateway, max_waypoints=max_waypoints,
                             perceive_fn=perceive_fn, verify_fn=verify_fn, report_fn=report_fn)


def _graph(deps: MissionGraphDeps):
    return build_mission_graph(deps, get_checkpointer())


def start_mission(site_id: str, operator_goal: str, max_waypoints: int = 3,
                   perceive_fn=None, verify_fn=None, report_fn=None, gateway_base_url: str | None = None) -> dict:
    mission_id = repo.create_mission(site_id=site_id, operator_goal=operator_goal)
    deps = _deps(max_waypoints, perceive_fn, verify_fn, report_fn, gateway_base_url)
    graph = _graph(deps)
    config = {"configurable": {"thread_id": mission_id}}

    result = graph.invoke({
        "mission_id": mission_id, "site_id": site_id, "operator_goal": operator_goal,
    }, config=config)

    return _summarize(mission_id, result)


def resume_mission(mission_id: str, decision: str, max_waypoints: int = 3,
                    perceive_fn=None, verify_fn=None, report_fn=None, gateway_base_url: str | None = None) -> dict:
    deps = _deps(max_waypoints, perceive_fn, verify_fn, report_fn, gateway_base_url)
    graph = _graph(deps)
    config = {"configurable": {"thread_id": mission_id}}

    result = graph.invoke(Command(resume=decision), config=config)
    return _summarize(mission_id, result)


def _summarize(mission_id: str, result: dict) -> dict:
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        return {"mission_id": mission_id, "status": "awaiting_approval", "interrupt": payload}
    return {
        "mission_id": mission_id, "status": result.get("status", "unknown"),
        "findings": result.get("findings", []), "report": result.get("report"),
    }
