---
id: SOP-002
title: Battery Thresholds and Power Management
category: flight-ops
applies_to: [drone-gateway, mission-planner, safety-layer]
---

# SOP-002: Battery Thresholds and Power Management

## Thresholds
- **Mission start minimum: 40%.** A mission may not be dispatched if the
  assigned drone's battery is below 40%.
- **Continue threshold: 25%.** Below 25% state of charge, the drone must
  abandon the current waypoint queue and initiate return-to-home (RTH).
- **Critical threshold: 15%.** Below 15%, RTH is executed at maximum speed
  regardless of remaining findings, and the event is logged as a
  high-severity operational alert.
- **Reserve margin:** every mission plan must budget an estimated-return
  cost of at least 10 percentage points of battery on top of the RTH
  threshold, so route planning should not schedule the last waypoint at
  exactly 25%.

## Cold-weather derating
Below 5°C ambient (as reported by the drone telemetry mock), all thresholds
above are raised by 10 percentage points (e.g. continue threshold becomes
35%) because cold reduces effective cell capacity.

## Fallback behavior
If battery drops below the continue threshold while capturing an image at a
waypoint, the capture is allowed to finish (typically < 2 seconds) before
RTH begins. If battery drops below the critical threshold mid-capture, RTH
preempts the capture immediately and the waypoint is marked `skipped_low_battery`.

## Reporting
Every RTH triggered by a battery threshold must be recorded in the audit
log with the exact battery percentage and threshold that fired.
