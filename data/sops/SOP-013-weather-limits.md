---
id: SOP-013
title: Simulated Weather Operating Limits
category: flight-ops
applies_to: [drone-gateway, mission-planner]
---

# SOP-013: Simulated Weather Operating Limits

## Weather flags
The drone gateway exposes a simulated weather flag per site:
`clear`, `moderate`, `severe`.

## Rules
- `clear`: no restriction.
- `moderate`: maximum altitude band is reduced by one level; waypoint
  count per mission is capped at 8 instead of the normal 12 (SOP-008).
- `severe`: no new missions may be dispatched. A mission already in
  progress must complete its current waypoint (if capture is underway)
  and then execute RTH (SOP-006), skipping remaining waypoints as
  `skipped_weather`.

## Rationale
These limits are simulated for demo purposes to give the safety layer and
fallback tests something concrete to react to; they are not calibrated to
any real aircraft's operating envelope.
