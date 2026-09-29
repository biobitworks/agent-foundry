---
gsd_state_version: '1.0'
status: planning
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-29)

**Core value:** Show where two runs of the same agent task first diverged, what caused it, and whether it can be replayed.
**Current focus:** Phase 5/6/7 (evidence lineage, checkpoint/replay, DuploCloud)

## Current Position

Phase: 5 of 9 (Evidence and lineage)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-09-29 — Phases 1-4 done; real local-model runs captured; inspector UI verified

Progress: [████░░░░░░] 44%

## Accumulated Context

### Decisions

- Governance artifacts under `provenance/` outrank `.planning/`.
- GSD tools pinned to @opengsd/gsd-core 1.15.0 (project-local); Node 26.7.0 via scoped guard bypass authorized by operator.

### Blockers

- Cloud providers: operator must approve credentials (session ANTHROPIC_* env not reused). Local Ollama works without credentials.
- magicSTUDIObox sync: `ssh` guarded in this workspace (HUMAN_ACTION_REQUIRED).
- DuploCloud runtime: not tested; devkit first run needs a work-domain email verification (HUMAN_ACTION_REQUIRED).
