# Agent Foundry

## What This Is

Agent Foundry is a provider-neutral developer reliability and debugging product for AI agents.
**Tagline:** Debug your AI agents like software.

Its central question: "Why did this AI agent behave differently, where did the run first diverge,
what evidence/tools influenced it, and can the behavior be replayed under another provider?"

Source of truth for scope: `docs/PRODUCT_BRIEF.md`. Where this file disagrees with `provenance/`, `provenance/` wins.

## Core Value

Show a developer, in one live workflow, where two runs of the same agent task first diverged and what
model, tool, or evidence event caused it, and whether the behavior can be replayed.

## Context

- Event: The AI Conference 2026, Day ZERØ Hack Day, 2026-09-29, Pier 48 (Shed A and B), San Francisco.
- Official criteria (OFFICIAL_EVENT_SOURCE, `provenance/requirements/AI_CONFERENCE_REQUIREMENTS.jsonl`): execution, product clarity, real-world viability (would a customer use it, would they pay). Goal: first version of a real business, not a disposable prototype.
- Pre-existing systems are consumed through adapters: HydraDG (checkpoints), Glasswork (comparison), Ollarma (local execution), FCO/FCG (evidence/lineage).
- DuploCloud is the external execution substrate; GSD Core is a development accelerator only (not provenance, not product).
- `.planning/` is operational planning state, NOT the canonical FCG.

## Requirements

### Validated

(None yet. Nothing is implemented at this point.)

### Active

See `.planning/REQUIREMENTS.md`. All are hypotheses (`PROPOSED`) until demonstrated.

### Out of Scope

- Broad infrastructure before the walking skeleton works (event schema, two runs, compare, UI).
- Static comparison tables, architecture diagrams, or API-connectivity checks as a substitute for demonstrated behavior.
- Claiming SIGNED, MMR, or replayability without the actual operation and verification.
- Neo4j visualization and extra sponsor integrations (P2) unless they materially participate in the live workflow.
- Merging DuploCloud requirements into the AI Conference requirement set.

## Constraints

- **Time**: Hack Day is one day (2026-09-29, 09:00-18:00 PT). Vertical slices only.
- **Governance**: state vocabulary PROPOSED/IMPLEMENTED/EXECUTED/OBSERVED/SUPPORTED/FAILED/NULL/NEGATIVE/DEFERRED/NOT_TESTED/UNKNOWN/NOT_COMPUTED; never upgrade without evidence. No divergence means `DIVERGENCE=NULL`.
- **Identity**: CONTENT_ID separate from OCCURRENCE_ID, RUN_ID, PHASE_ID. Hashes give identity, not truth. No causal claims from chronology alone.
- **Secrets**: never committed; gitleaks before every phase commit.
- **Sync**: magicPRObox is canonical; magicSTUDIObox only fast-forwards from GitHub.
- **Tooling**: Python 3.13, no runtime dependencies unless justified; Node 26 only for GSD tooling.

## Key Decisions

| Decision | Rationale | Outcome |
| --- | --- | --- |
| Own git repo, not nested in `/Users/byron/projects/active` | Parent repo is dirty with an unrelated origin | Good |
| GSD not vendored; manifest + install state tracked | External tool, reinstall from pin | Good |
| UI (P0) pulled ahead of lineage and replay | Official criteria reward a demonstrated workflow | Pending |
| Research phase skipped in new-project | Brief is operator-authored and complete | Pending |

---
*Last updated: 2026-09-29 after initialization*
