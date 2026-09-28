---
id: SOP-014
title: Audit Log Requirements
category: safety
applies_to: [orchestration, safety-layer, drone-gateway]
---

# SOP-014: Audit Log Requirements

## What must be logged
Every one of the following is an audit event, written immutably (append
only, never edited) with a UTC timestamp:
- Every tool call an agent makes (drone gateway calls, vector store
  queries, pandas analysis calls), with inputs and a reference to the
  output (not necessarily the full output, to keep the log readable).
- Every agent-to-agent message in the Perception-Verifier exchange
  (SOP-007).
- Every approval-gate request and decision (SOP-004).
- Every RTH and its trigger (SOP-006).
- Every fallback invocation (SOP-005) and its outcome.

## Access
The audit log is read-only from the frontend; there is no UI path to edit
or delete entries. The operator dashboard's mission timeline is a filtered
view over this log.

## Format
Structured JSON lines, one event per line, with at minimum: `timestamp`,
`event_type`, `mission_id`, `actor` (agent name or `operator:<id>`), and
`payload`. This is the same structured logging referenced by SOP-009's
approval-log excerpt and by the LangSmith/observability layer.
