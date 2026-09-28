---
id: SOP-006
title: Drone and Capture Failure Handling (Return-to-Home)
category: flight-ops
applies_to: [drone-gateway, orchestration]
---

# SOP-006: Drone and Capture Failure Handling

## Failure types (as simulated by the drone gateway)
- `drone_offline`: fleet status reports the drone unreachable.
- `capture_timeout`: an image capture request does not complete within
  8 simulated seconds.
- `low_battery_critical`: battery below the critical threshold (SOP-002).
- `zone_violation`: a waypoint reclassified into Class A mid-mission
  (SOP-001).

## Required response
For every failure type above, the orchestrator must issue a
**return-to-home (RTH)** command to the drone gateway and mark the current
waypoint `failed:<failure_type>` rather than retrying indefinitely.

## Retry policy
- `drone_offline`: retry the status check up to 3 times with backoff
  (1s, 2s, 4s simulated) before declaring the drone unreachable and
  escalating to the operator; do not issue RTH to a drone that cannot be
  reached — instead flag it `manual_recovery_required`.
- `capture_timeout`: one retry at the same waypoint; a second timeout is
  treated as a hard failure and moves to the next waypoint (does not
  trigger fleet-wide RTH by itself).
- `low_battery_critical` and `zone_violation`: no retry — RTH is
  immediate.

## Audit requirement
Every RTH, whatever the trigger, is logged with: trigger type, drone id,
mission id, waypoint id, and timestamp. This is the same audit log used for
approval decisions (SOP-004) so operators can review flight safety events
and human decisions together.
