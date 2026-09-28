---
id: SOP-010
title: Persistent Memory Retention and Use
category: knowledge
applies_to: [memory-layer, orchestration]
---

# SOP-010: Persistent Memory Retention and Use

## What is stored
Per site, persistent memory retains: past mission summaries, every accepted
finding (with waypoint, type, severity, confidence, timestamp, and whether
it was later marked resolved), and every approval-gate decision.

## Retention
Findings and mission summaries are retained indefinitely in the demo
(no automatic deletion), since inspection history is the primary value of
the memory layer. A future production deployment should define a retention
window per site policy — this demo does not implement automatic pruning.

## How new missions use memory
1. During mission planning, the orchestrator queries memory for this
   site's open (`unresolved`) findings from the most recent prior mission
   and includes them in the mission plan as waypoints to re-check.
2. During verification (SOP-007), the Verifier agent may cite a matching
   prior finding at the same waypoint as supporting or contradicting
   evidence.
3. During reporting (SOP-009), the report includes a comparison to the
   prior visit.

## Consistency rule
A new finding at a waypoint with a prior `unresolved` finding of the same
type should be linked (not duplicated) unless its severity or location
materially differs, in which case both are kept and cross-referenced.
