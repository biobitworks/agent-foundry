# Agent Foundry: product brief (input to GSD; NOT canonical provenance)

> **Post-submission status note (2026-09-29):** this brief was the planning input. The boundary below describes intended adapters; HydraDG, Glasswork, Ollarma and FCO/FCG bridges are **NOT_IMPLEMENTED/NOT_TESTED** as adapters, and DuploCloud did not participate in the demonstrated workflow. See the README for the executed state.

**Tagline:** Debug your AI agents like software.

Agent Foundry is a provider-neutral developer reliability and debugging product for AI agents.

Its central question is:

> "Why did this AI agent behave differently, where did the run first diverge, what evidence/tools
> influenced it, and can the behavior be replayed under another provider?"

Primary customer problem: *why did this AI agent's answer change after I changed its model, provider,
tools, evidence, or execution context?*

One-line explanation: Agent Foundry shows developers where an AI-agent run first diverged, what model,
tool, or evidence caused the change, and whether the behavior can be reproduced or replayed.

## Boundary (GSD must not redefine this)

Pre-existing systems are consumed through adapters, never re-implemented here:

- HydraDG: checkpoints / recovery (`adapters/hydradg/`)
- Glasswork: comparison / evaluation (`adapters/glasswork/`)
- Ollarma: local model execution (`adapters/ollarma/`)
- FCO/FCG: canonical evidence / lineage (`adapters/fcg/`)
- DuploCloud: external Hack Day execution substrate (`integrations/duplocloud/`)
- GSD Core: development workflow accelerator ONLY (`integrations/gsd/`)

Where GSD planning artifacts disagree with `provenance/`, `provenance/` wins.
`.planning/` is operational planning state, not the canonical FCG.

## Context

AI Conference Hack Day, 2026-09-29, Pier 48, San Francisco. Official criteria (see
`provenance/requirements/AI_CONFERENCE_REQUIREMENTS.jsonl`): execution, product clarity, real-world
viability (would a customer use it, would they pay). The goal is the first version of a real business,
not a disposable prototype. Ship ONE complete developer workflow before adding breadth.

## The one workflow (demo must SHOW it)

developer submits canonical task, run A executes, run B executes, provider-neutral event normalization,
first-divergence localization, tool/evidence/model inspection, affected downstream claims,
checkpoint/replay, developer-facing explanation.

Not substitutes: diagrams, API connectivity, sponsor logos, credential validation, HTTP 200s, static tables.

## Judge-visible acceptance

1. Same task under two controlled configurations.
2. Runs differ (if not: `DIVERGENCE=NULL`, never manufactured).
3. Earliest meaningful divergence identified.
4. Relevant model/tool/evidence event inspectable.
5. Downstream affected output visible.
6. A checkpoint or run replayed (claimed only after an actual replay succeeds).
7. Failures and abstentions visible, not silently discarded.

Each demo run produces: `CONTROL_RUN`, `VARIANT_RUN`, `FIRST_DIVERGENCE`, `DOWNSTREAM_CHANGED_EVENTS`, `AFFECTED_CLAIMS`.

## Priority (P0 first; P2 rises only if it materially participates in the live workflow)

- P0: run/event schema; canonical task execution; two-run comparison; first-divergence localization; usable run-inspector UI
- P1: evidence/tool inspection; checkpoint/replay; DuploCloud execution integration
- P2: local Ollarma comparator; Neo4j projection; additional sponsor integrations

## Roadmap shape (vertical phases, walking skeleton first)

1. Provider-neutral event schema + run recorder (P0)
2. Two-provider canonical-task execution (P0)
3. Comparison + first-divergence localization (P0)
4. Run inspector UI (P0, pulled forward)
5. Evidence/tool inspection + FCO/FCG lineage (P1)
6. HydraDG-compatible checkpoint/replay (P1)
7. DuploCloud integration participating in the live run (P1)
8. Demo fixtures + failure/abstention controls
9. Demo rehearsal + evidence bundle

## Constraints

- Preserve state vocabulary: PROPOSED, IMPLEMENTED, EXECUTED, OBSERVED, SUPPORTED, FAILED, NULL, NEGATIVE, DEFERRED, NOT_TESTED, UNKNOWN, NOT_COMPUTED. Never upgrade without evidence.
- Hashes establish identity, not truth. No SIGNED / MMR claims without an actual operation and verification.
- Keep CONTENT_ID separate from OCCURRENCE_ID, RUN_ID, PHASE_ID. No causal claims from chronology alone.
- Python 3 is available; keep dependencies minimal. Secrets never committed.
- AI_CONFERENCE_REQUIREMENTS and DUPLOCLOUD_REQUIREMENTS stay separate sets.
