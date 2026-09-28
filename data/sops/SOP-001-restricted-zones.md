---
id: SOP-001
title: Restricted Zone Entry and No-Fly Boundaries
category: airspace
applies_to: [mission-planner, safety-layer]
---

# SOP-001: Restricted Zone Entry and No-Fly Boundaries

## Purpose
Defines how the simulated fleet must treat restricted airspace and ground
exclusion zones during inspection missions.

## Zone classes
- **Class A (no-fly):** active substations, helipads, and any zone flagged
  `no_fly` in the site map. No waypoint may be planned inside a Class A
  polygon under any condition.
- **Class B (restricted):** zones requiring operator approval before entry
  (e.g. above occupied structures, near perimeter fencing, construction
  zones with personnel present). Entry is a **high-risk action** and must
  pause for human approval (see SOP-004).
- **Class C (caution):** zones with elevated risk but no approval
  requirement (e.g. near tree lines, low-visibility corridors). Log entry
  and reduce speed/altitude per site guidance.

## Rules
1. Mission planning must check every waypoint against the current zone map
   before dispatch.
2. A Class A violation is never auto-approved and is not eligible for
   operator override; the mission must re-plan around it.
3. A Class B entry requires an approval record (operator id, decision,
   timestamp) before the drone gateway will accept the waypoint.
4. If a zone map update arrives mid-mission that reclassifies the drone's
   current position as Class A, the drone must return-to-home immediately
   (see SOP-006).

## Escalation
Repeated Class B requests for the same waypoint across missions should be
flagged to the site owner — it likely indicates the zone map is stale.
