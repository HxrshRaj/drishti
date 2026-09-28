---
id: SOP-008
title: Pre-Flight Inspection Checklist
category: flight-ops
applies_to: [mission-planner, drone-gateway]
---

# SOP-008: Pre-Flight Inspection Checklist

Before a mission is dispatched to the drone gateway, the mission planner
must confirm all of the following (each becomes a structured check in the
mission record):

1. **Battery** >= 40% (SOP-002).
2. **Fleet status** for the assigned drone is `idle` or `charged`, not
   `maintenance` or `offline`.
3. **Zone map** loaded for the target site is dated within the last 30
   simulated days; if stale, proceed but flag `zone_map_stale` on the
   mission record (does not block dispatch, but is surfaced to the
   operator).
4. **Weather flag** (simulated) is not `severe`; `moderate` requires the
   mission to reduce planned altitude by one band; `clear` requires no
   change.
5. **Waypoint count** does not exceed 12 per mission (keeps simulated
   battery budget realistic against SOP-002 thresholds).
6. **SOP retrieval** for the target site succeeded (at least one relevant
   SOP chunk retrieved) — if retrieval returns nothing, the mission may
   still proceed but is flagged `no_sop_context`, since operating with no
   site guidance is itself worth a human noticing.

## Failure handling
Any check above that is a hard blocker (1 and 2) prevents dispatch and
returns a structured reason to the caller. Soft flags (3, 4 partial, 6) are
attached to the mission record and do not block dispatch.
