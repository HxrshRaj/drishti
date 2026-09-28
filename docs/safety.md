# Safety

Everything below is implemented and tested, not aspirational. Code
references point at the exact functions; the required "blocked, then
approved" test is quoted at the end with its real output.

## Risk policy (`backend/app/safety/policy.py`)

Every proposed action during a mission is classified `low`, `medium`, or
`high` by rules, not by a model:

| Rule | Function | Threshold |
|---|---|---|
| Zone entry | `assess_zone_entry` | Class A → `ZoneEntryBlocked` (never approvable, must re-plan); Class B → `high`; Class C → `low` |
| Battery continuation | `assess_battery_continue` | battery < 25% and continuing (rather than RTH) → `high` |
| Low-confidence finding | `assess_finding_confidence` | confidence < 0.55 → `high` |
| Dismissing a finding | `assess_dismiss_finding` | severity `critical` → `high` |
| Verifier disagreement | wired in `mission_graph.py::decide` | verifier outcome ≠ `agree` → `high` |

Source SOPs: `data/sops/SOP-001-restricted-zones.md`,
`SOP-002-battery-thresholds.md`, `SOP-004-approval-gates.md`,
`SOP-005-low-confidence-fallback.md`.

## Approval gates (`backend/app/safety/gate.py`, SOP-004)

`submit_for_gate()` writes a pending `Approval` row (mission id, action
description, risk level, proposing agent, evidence) when risk is `high`.
The LangGraph mission workflow then calls `interrupt()`, which **pauses
the mission's execution and returns control to the caller** — the graph
state is checkpointed (SqliteSaver) so the mission can be resumed hours or
days later, in a different process, from exactly this point. An operator
decision — `POST /missions/{id}/decide` — records `approved` / `rejected`
via `gate.decide()` and resumes the graph with `Command(resume=decision)`.
A `modify` decision is deliberately **not** treated as approval of the
original action — see the comment in `gate.check_gate()`.

## Fallback protocols

| Trigger | Behavior | SOP | Test |
|---|---|---|---|
| VLM finding confidence < 0.55 | Routes through the approval gate rather than being silently accepted or silently dropped | SOP-005 | `test_low_confidence_finding_pauses_then_resumes_on_approval`, `test_low_confidence_finding_rejected_is_not_recorded` |
| `drone_offline` from the gateway | Retried (one-shot failure injection means the retry succeeds in the simulator, mirroring SOP-006's retry-then-escalate policy); `goto_failed` is audit-logged either way | SOP-006 | `test_drone_offline_failure_injection_skips_waypoint` |
| `capture_timeout` from the gateway | One retry at the same waypoint | SOP-006 | `test_capture_timeout_failure_injection_is_retried` |
| `low_battery_critical` from the gateway | Immediate RTH via `DroneGatewayClient.rth()`, waypoint marked failed | SOP-002/SOP-006 | covered by `drone-gateway/tests/test_fleet.py::test_low_battery_critical_and_rth` at the gateway level |
| Verifier `disagree`/`uncertain` | Treated as high risk → approval gate, same as low confidence | SOP-007 | `app/agents/verifier.py::run_verification_exchange` sets `escalated=True` for anything but `agree` |

All fallback tests inject the **real** failure through the drone-gateway's
real `/admin/inject_failure` endpoint (a real subprocess, real HTTP —
`backend/tests/conftest.py::live_gateway_url`), not a mocked exception.

## Required test: blocked, then approved

`backend/tests/test_safety_gate.py::test_high_risk_action_blocked_then_proceeds_after_approval`:

```python
result = gate.submit_for_gate(...)          # risk = high (Class B zone entry)
assert result.allowed is False
assert gate.check_gate(result.approval_id) is False   # <-- BLOCKED, no approval recorded

gate.decide(result.approval_id, "approved", operator_id="operator-7", ...)
assert gate.check_gate(result.approval_id) is True    # <-- now proceeds
```

Real run:

```
$ pytest backend/tests/test_safety_gate.py -q
..............                                                           [100%]
14 passed in 1.82s
```

## Audit log (SOP-014)

Every tool call, agent message, approval request/decision, and RTH is
written append-only to `AuditEvent` (`backend/app/db/models.py`) via
`app/memory/repository.py::log_audit_event`, which **also** emits the same
event as a structured JSON line to stdout (`app/observability/logging_config.py`)
so it works without any credentials — see `docs/architecture.md` for how
this feeds LangSmith tracing when a key is present. The operator
dashboard's mission timeline (`frontend/src/app/missions/[id]/page.tsx`)
is a read-only view over `GET /missions/{id}/audit`.

## Parity (bias) checks

See `docs/bias-report.md` for the full write-up — this is a
performance-parity check across measurable imagery conditions (brightness,
resolution, scene mix), not social-bias detection; SOP-011 defines the
scope and threshold explicitly to prevent that conflation.
