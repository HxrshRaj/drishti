---
id: SOP-004
title: Human Approval Gates for High-Risk Actions
category: safety
applies_to: [safety-layer, orchestration]
---

# SOP-004: Human Approval Gates for High-Risk Actions

## Which actions require approval
An action is **high-risk** and must pause for operator approval before
execution if any of the following hold:
1. It proposes entering a Class B restricted zone (SOP-001).
2. It proposes continuing a mission after battery has crossed the continue
   threshold (SOP-002) instead of returning to home.
3. It would act on (e.g. escalate publicly, include in an external-facing
   report, or trigger a follow-up mission for) a finding whose confidence is
   below 0.55, even if the verifier agent accepted it.
4. It is a `critical`-severity finding (SOP-003) being marked resolved or
   dismissed.

## Approval record
Every gate produces an approval request with: action description, risk
level, proposing agent, supporting evidence (finding id, SOP citations),
and a status of `pending`. An operator decision (`approve` / `reject` /
`modify`) is written back with operator id, free-text rationale (optional),
and a UTC timestamp. The mission workflow may not proceed past the gate
until a decision is recorded.

## Timeout behavior
If no decision is recorded within the configured timeout (default: no
auto-timeout in the demo — the mission stays paused), the mission remains
in `awaiting_approval` state. Auto-approving on timeout is explicitly
disallowed for `critical` actions.

## Modify
A `modify` decision must include a replacement action (e.g. a different
waypoint, a lower-altitude re-capture) which itself becomes a new proposed
action subject to the same risk classification.
