# Demo acceptance and build priority

> **Post-submission status note (2026-09-29):** this file is a planning-time requirement list, not an achievement claim. DuploCloud did **not** participate in the demonstrated Moddik workflow (thin extension smoke only; its agent lane failed authentication). See the README and `provenance/` for what executed.

Source: operator-stated, derived from `provenance/requirements/AI_CONFERENCE_REQUIREMENTS.jsonl`
(official criteria: execution, product clarity, real-world viability: could a customer use it, would they pay).
Everything here is `PROPOSED` until demonstrated.

Primary customer problem: *why did this AI agent's answer change after I changed its model, provider, tools, evidence, or execution context?*

## Workflow the live demo must SHOW

task, run A, run B, event normalization, first-divergence localization, tool/evidence/model inspection,
affected downstream claims, checkpoint/replay, developer-facing explanation.

Not substitutes: architecture diagrams, API connectivity, sponsor logos, credential validation, HTTP 200s, static comparison tables.

## Judge-visible acceptance (all NOT_TESTED)

1. Same task under two controlled configurations.
2. Resulting runs differ. If they do not: `DIVERGENCE=NULL`, never manufactured.
3. Earliest meaningful divergence identified.
4. Relevant model/tool/evidence event inspectable.
5. Downstream affected output visible.
6. A checkpoint or run replayed. Replayability is claimed only after a real replay succeeds.
7. Failures and abstentions visible, not silently discarded.

## Priority

Evidence may reorder. A P2 item rises only if it materially participates in the live workflow.

| P | Item | Original phase |
| --- | --- | --- |
| P0 | run/event schema | 1 |
| P0 | canonical task execution | 2 |
| P0 | two-run comparison | 2-3 |
| P0 | first-divergence localization | 3 |
| P0 | usable run-inspector UI | 6 (pulled forward) |
| P1 | evidence/tool inspection | 4 |
| P1 | checkpoint/replay | 5 |
| P1 | DuploCloud execution integration | 7 |
| P2 | local Ollarma comparator | none |
| P2 | Neo4j projection | none |
| P2 | additional sponsor integrations | none |

Consequence: the UI (phase 6) is P0 and moves ahead of evidence lineage (4) and checkpoint/replay (5).
DuploCloud (7) is P1 and must participate in the demonstrated run, not merely connect.
