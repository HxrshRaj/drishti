---
id: SOP-009
title: Inspection Report Format
category: reporting
applies_to: [reporting-crew]
---

# SOP-009: Inspection Report Format

## Required sections
Every mission report produced by the reporting crew (Analyst + Report
Writer) must contain:

1. **Mission summary:** site, operator goal, start/end time, number of
   waypoints visited, number skipped, and why (link to SOP-006 failure
   codes where applicable).
2. **Findings table:** one row per accepted finding — id, waypoint,
   finding type, severity (SOP-003), confidence, verifier outcome
   (SOP-007), image reference.
3. **Quantitative summary:** counts by severity and by finding type,
   computed by the Analyst agent's pandas tool over the findings table, not
   estimated by the Report Writer from prose.
4. **Approval log excerpt:** any approval-gate decisions (SOP-004) made
   during this mission, verbatim.
5. **Comparison to prior visit:** if persistent memory has a prior mission
   for this site, note what changed (new findings, resolved findings,
   recurring findings) — this is the report's use of the memory layer.

## Style rules
- Severity and confidence are always reported as given by the agents —
  the Report Writer may not soften ("likely fine") or amplify
  ("definitely a hazard") language beyond what the data supports.
- Every claim in the narrative sections must be traceable to a row in the
  findings table or the approval log; no free invention of observations.
