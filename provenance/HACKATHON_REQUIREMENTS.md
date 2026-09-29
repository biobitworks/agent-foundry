# Hack Day requirements

> **SUPERSEDED IN PART (2026-09-29).** The official source has since been retrieved and atomized into
> `requirements/AI_CONFERENCE_REQUIREMENTS.jsonl` (OFFICIAL_EVENT_SOURCE) and
> `requirements/DUPLOCLOUD_REQUIREMENTS.jsonl` (OPERATOR_STATED). These sets are distinct and must not be merged.
> The list below remains the operator-stated product plan from baseline commit `ff8120d`.
> "Official rules NOT_RETRIEVED" no longer holds for the AI Conference page. What that page still does
> NOT specify (judges, rubric weights, deadlines) is in `requirements/AI_CONFERENCE_SOURCE_OBSERVATION.json`.

Event: AI Conference Hack Day, 2026-09-29.

## Provenance of this list

`OPERATOR_STATED` — taken from the operator's bootstrap prompt
(AGENT_FOUNDRY_GSD_BOOTSTRAP_002). Official event rules/judging criteria:
`NOT_RETRIEVED` / `UNKNOWN`. Do not treat this list as the organizers' rules.

## Operator-stated requirements

- R1 Provider-neutral event schema + run recorder.
- R2 Canonical task executed under two providers with event capture.
- R3 Comparison producing CONTROL_RUN, VARIANT_RUN, FIRST_DIVERGENCE,
  DOWNSTREAM_CHANGED_EVENTS, AFFECTED_CLAIMS. If no divergence: `DIVERGENCE=NULL` (never manufactured).
- R4 Evidence lineage (FCO/FCG) + source inspection.
- R5 Checkpoint/replay via HydraDG-compatible descriptors; replayability claimed only after an actual replay succeeds.
- R6 Run inspector UI.
- R7 Meaningful DuploCloud participation in the demonstrated workflow
  (a credential check or HTTP 200 alone is insufficient).
- R8 Demo fixtures + failure/abstention controls; rehearsal + evidence bundle.

## Minimum live path (walking skeleton)

canonical task → provider A → event capture → provider B → event capture →
comparison → first divergence → inspect evidence → UI

## State classification

All requirements: `PROPOSED`. Nothing implemented at baseline.
