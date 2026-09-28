---
id: SOP-003
title: Finding Severity Classification
category: perception
applies_to: [perception-agent, verifier-agent, reporting-crew]
---

# SOP-003: Finding Severity Classification

## Severity levels
Every accepted finding must be tagged with exactly one severity level:

- **critical:** presents immediate risk to people, assets, or continued
  operation (e.g. unauthorized personnel in a Class A/B zone, fire or smoke,
  structural collapse indicators). Triggers an immediate operator alert
  regardless of mission stage.
- **major:** requires attention within the current operating shift but is
  not an immediate hazard (e.g. unauthorized vehicle parked in a restricted
  zone, blocked access route, visible equipment damage).
- **minor:** worth recording for the inspection report but does not require
  same-shift action (e.g. routine vehicle/personnel presence in an
  unrestricted zone, minor housekeeping issues).
- **informational:** context-only observations with no action implied.

## Confidence-severity interaction
A finding's severity is assessed independently of the VLM's confidence
score. A low-confidence "critical" classification is not downgraded — it is
instead routed through the low-confidence fallback (SOP-005) before being
accepted, so a real critical issue is never silently dropped for being
uncertain.

## Escalation mapping
- `critical` → immediate operator alert + approval gate if any related
  action (e.g. continued flight over the area) is proposed.
- `major` → included in the next report; queued for operator review within
  the shift.
- `minor` / `informational` → included in the report only.
