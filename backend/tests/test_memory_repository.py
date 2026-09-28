from app.memory import repository as repo


def test_create_mission_and_status_transition():
    mid = repo.create_mission(site_id="meridian-substation", operator_goal="routine sweep")
    assert mid
    repo.set_mission_status(mid, "running")
    repo.set_mission_status(mid, "completed", ended=True)


def test_record_and_query_unresolved_findings():
    mid = repo.create_mission(site_id="harbor-industrial-park", operator_goal="check zone B")
    fid = repo.record_finding(
        mission_id=mid, site_id="harbor-industrial-park", waypoint_id="WP-03",
        image_file="x.jpg", finding_type="vehicle_presence", location_description="near gate",
        severity="major", confidence=0.8,
    )
    unresolved = repo.get_unresolved_findings("harbor-industrial-park")
    assert any(f.id == fid for f in unresolved)

    repo.resolve_finding(fid)
    unresolved_after = repo.get_unresolved_findings("harbor-industrial-park")
    assert not any(f.id == fid for f in unresolved_after)


def test_second_mission_sees_first_missions_open_findings():
    """This is the persistent-memory contract SOP-010 requires: a new
    mission at the same site can retrieve what a prior mission left open.
    """
    site = "north-ridge-corridor"
    mission1 = repo.create_mission(site_id=site, operator_goal="first sweep")
    repo.record_finding(
        mission_id=mission1, site_id=site, waypoint_id="WP-07", image_file="a.jpg",
        finding_type="personnel_presence", location_description="fence line",
        severity="major", confidence=0.7,
    )
    repo.set_mission_status(mission1, "completed", ended=True)

    mission2 = repo.create_mission(site_id=site, operator_goal="follow-up sweep")
    carried_over = repo.get_unresolved_findings(site, exclude_mission_id=mission2)
    assert len(carried_over) == 1
    assert carried_over[0].mission_id == mission1

    priors = repo.get_prior_missions(site, exclude_mission_id=mission2)
    assert any(m.id == mission1 for m in priors)


def test_approval_lifecycle():
    mid = repo.create_mission(site_id="meridian-substation", operator_goal="sweep")
    aid = repo.create_approval_request(
        mission_id=mid, action_description="enter zone B at WP-05", risk_level="high",
        proposing_agent="orchestrator", evidence={"finding_id": "abc"},
    )
    pending = repo.get_pending_approvals(mission_id=mid)
    assert len(pending) == 1
    assert pending[0].status == "pending"

    decided = repo.decide_approval(aid, "approved", operator_id="operator-1", rationale="looks fine")
    assert decided.status == "approved"
    assert decided.operator_id == "operator-1"
    assert decided.decided_at is not None

    pending_after = repo.get_pending_approvals(mission_id=mid)
    assert len(pending_after) == 0


def test_audit_log_records_events():
    mid = repo.create_mission(site_id="meridian-substation", operator_goal="sweep")
    repo.log_audit_event("goto", actor="orchestrator", payload={"waypoint_id": "WP-01"}, mission_id=mid)
    repo.log_audit_event("capture", actor="orchestrator", payload={"waypoint_id": "WP-01"}, mission_id=mid)

    events = repo.get_audit_log(mission_id=mid)
    assert len(events) == 2
    assert {e.event_type for e in events} == {"goto", "capture"}
