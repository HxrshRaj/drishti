---
id: SOP-005
title: Low-Confidence Finding Fallback
category: perception
applies_to: [perception-agent, orchestration, drone-gateway]
---

# SOP-005: Low-Confidence Finding Fallback

## Trigger
Any VLM finding with confidence below **0.55** triggers this fallback
before the finding may be accepted or included in a report.

## Steps
1. **Re-capture from an alternate waypoint.** The orchestrator requests a
   second capture from a waypoint offset by approximately 3-5 meters
   laterally (simulated) from the original, or a different altitude band if
   the site map defines one, and re-runs perception.
2. **Combine evidence.** If the second capture's finding agrees (same
   finding type, confidence >= 0.55), accept with the higher-confidence
   result and note in the audit log that fallback re-capture was used.
3. **Escalate to human.** If the second capture is also below 0.55, or
   disagrees with the first, the finding is marked `unresolved_low_confidence`
   and routed to the approval queue for a human decision rather than being
   silently discarded or silently accepted.
4. A finding must never be auto-accepted below 0.55 confidence, and must
   never be auto-discarded below 0.55 confidence — both are treated as
   silent failure modes this SOP exists to prevent.

## Retry budget
At most **one** re-capture attempt per finding under this SOP. If the
drone cannot re-capture (e.g. battery below continue threshold, gateway
reports `capture_timeout`), skip directly to human escalation.
