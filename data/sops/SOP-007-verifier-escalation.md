---
id: SOP-007
title: Perception-Verifier Disagreement and Escalation
category: perception
applies_to: [perception-agent, verifier-agent]
---

# SOP-007: Perception-Verifier Disagreement and Escalation

## Roles
The **Perception agent** proposes a finding from VLM output. The
**Verifier agent** independently reviews the same image plus the proposed
finding, cross-checking it against retrieved SOPs and site memory
(prior findings at this waypoint), and returns one of: `agree`,
`disagree`, or `uncertain`.

## Resolution
- `agree`: the finding proceeds to severity classification (SOP-003) and,
  if applicable, the approval gate (SOP-004).
- `disagree`: the finding is not accepted as proposed. If the verifier
  supplies an alternative finding type with its own confidence, that
  alternative is proposed as a new candidate and re-verified once. Two
  consecutive `disagree` results on the same waypoint escalate to human
  review rather than looping a third time.
- `uncertain`: treated the same as a low-confidence finding under SOP-005
  (fallback re-capture, then escalate).

## Logging
The full perception-verifier message exchange (both proposal and
challenge, including citations either agent used) is logged verbatim in
the mission trace, not just the final resolution — this is what makes a
disagreement debuggable after the fact.

## Escalation payload
When escalating to a human, include both agents' reasoning so the operator
is not just told "disagreement" but can see why.
