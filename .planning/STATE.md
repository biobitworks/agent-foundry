---
gsd_state_version: '1.0'
status: planning
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 5
  completed_plans: 5
  percent: 56
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-29)

**Core value:** Show where two runs of the same agent task first diverged, what caused it, and whether it can be replayed.
**Current focus:** Moddik local-simulation evidence demo (breakpoint 017); then Phase 5/6/7 (evidence lineage, checkpoint/replay, DuploCloud)

## Current Position

Phase: 5 of 9 (Evidence and lineage)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-09-29 — Phases 1-4 and 6 done; real replay verified (n=1)

Progress: [█████░░░░░] 56%

## Accumulated Context

### Decisions

- Governance artifacts under `provenance/` outrank `.planning/`.
- GSD tools pinned to @opengsd/gsd-core 1.15.0 (project-local); Node 26.7.0 via scoped guard bypass authorized by operator.

### Blockers

- Cloud providers: operator must approve credentials (session ANTHROPIC_* env not reused). Local Ollama works without credentials.
- magicSTUDIObox sync: `ssh` guarded in this workspace (HUMAN_ACTION_REQUIRED).
- DuploCloud runtime: not tested; devkit first run needs a work-domain email verification (HUMAN_ACTION_REQUIRED).

- Moddik demo (2026-09-29): see provenance/BREAKPOINT_MODDIK_LOCAL_DEMO_017.json. Live ASR NOT_TESTED; PLAUD real recording NOT_TESTED; account-linked PLAUD import needs operator OAuth.
