---
id: SOP-012
title: Multi-Drone Deconfliction
category: flight-ops
applies_to: [drone-gateway, mission-planner]
---

# SOP-012: Multi-Drone Deconfliction

## Rule
When more than one simulated drone is active at the same site, the mission
planner must not assign two drones to waypoints within 15 simulated meters
of each other within the same 2-minute window, to model a minimum
separation requirement.

## Handling conflicts
If a requested waypoint would violate separation, the planner delays the
second drone's arrival (re-orders its waypoint queue) rather than rejecting
the mission outright. If no non-conflicting ordering exists within the
mission's time budget, the conflicting waypoint is dropped and flagged
`deconfliction_dropped` on the mission record.

## Priority
A drone already mid-capture at a waypoint has priority; an arriving drone
must hold (simulated hover) until the capture completes or a 5-second
simulated timeout elapses, whichever is first.
