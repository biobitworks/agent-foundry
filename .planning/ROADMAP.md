# Roadmap: Agent Foundry

## Overview

Build a vertical walking skeleton first: canonical task, run A, run B, event capture, comparison,
first divergence, inspection, UI. Then add evidence lineage, checkpoint/replay, and DuploCloud
participation, then harden the demo. Ordering follows the official P0/P1/P2 priorities.

## Phases

- [ ] **Phase 1: Event schema and run recorder** - Provider-neutral event schema plus an append-only recorder (P0)
- [ ] **Phase 2: Two-run canonical task execution** - Same task under two controlled configurations, events captured (P0)
- [ ] **Phase 3: Comparison and first divergence** - Normalize, compare, localize the earliest divergence (P0)
- [ ] **Phase 4: Run inspector UI** - Side-by-side runs, divergence marker, event inspector, explanation (P0)
- [ ] **Phase 5: Evidence and lineage** - Evidence/tool inspection, FCO/FCG references (P1)
- [ ] **Phase 6: Checkpoint and replay** - HydraDG-compatible descriptors, real replay (P1)
- [ ] **Phase 7: DuploCloud integration** - DuploCloud participates in the live run (P1)
- [ ] **Phase 8: Demo fixtures and controls** - Offline fixtures, failure/abstention controls
- [ ] **Phase 9: Rehearsal and evidence bundle** - Rehearsed demo, customer/willingness-to-pay narrative, bundle

## Phase Details

### Phase 1: Event schema and run recorder
**Goal**: Any agent run can be recorded as an ordered, append-only event log in a provider-neutral schema.
**Depends on**: Nothing (first phase)
**Requirements**: EVT-01, EVT-02, EVT-03
**Success Criteria** (what must be TRUE):
  1. Event JSON Schemas validate sample events of every declared type.
  2. A recorded run is an ordered JSONL log with distinct CONTENT_ID, OCCURRENCE_ID and RUN_ID.
  3. A failure and an abstention event are recorded and read back intact.
**Plans**: TBD

### Phase 2: Two-run canonical task execution
**Goal**: One canonical task is executed as run A and run B under controlled configurations with events captured.
**Depends on**: Phase 1
**Requirements**: EXE-01, EXE-02, EXE-03
**Success Criteria** (what must be TRUE):
  1. Submitting the canonical task produces two recorded runs that differ in exactly one declared variable.
  2. Each run is labeled with its real provider or `fixture`.
  3. A provider failure is recorded, not hidden.
**Plans**: TBD

### Phase 3: Comparison and first divergence
**Goal**: Two runs are normalized and compared; the earliest meaningful divergence is reported with evidence.
**Depends on**: Phase 2
**Requirements**: CMP-01, CMP-02, CMP-03, CMP-04
**Success Criteria** (what must be TRUE):
  1. Comparison outputs CONTROL_RUN, VARIANT_RUN, FIRST_DIVERGENCE, DOWNSTREAM_CHANGED_EVENTS, AFFECTED_CLAIMS.
  2. Identical runs yield `DIVERGENCE=NULL`.
  3. Downstream impact uses declared dependencies only.
**Plans**: TBD

### Phase 4: Run inspector UI
**Goal**: A developer sees the whole workflow in a browser and can explain the divergence.
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. Side-by-side runs with the first divergence marked.
  2. Clicking an event shows its model/tool/evidence details.
  3. Failures, abstentions and affected outputs are visible.
  4. A plain-language explanation is shown.
**Plans**: TBD

### Phase 5: Evidence and lineage
**Goal**: Evidence and tool inputs are inspectable and reference FCO/FCG identities.
**Depends on**: Phase 4
**Requirements**: EVD-01, EVD-02
**Success Criteria** (what must be TRUE):
  1. Each evidence event shows its source reference.
  2. FCO/FCG references are attached without asserting causality from order.
**Plans**: TBD

### Phase 6: Checkpoint and replay
**Goal**: A run can be replayed from a checkpoint.
**Depends on**: Phase 4
**Requirements**: REP-01, REP-02
**Success Criteria** (what must be TRUE):
  1. Checkpoint descriptors exist before/after each phase and run.
  2. A replay executes and its outcome is compared with the original; `replayable` is set only on success.
**Plans**: TBD

### Phase 7: DuploCloud integration
**Goal**: DuploCloud materially participates in the demonstrated run.
**Depends on**: Phase 2
**Requirements**: DUP-01
**Success Criteria** (what must be TRUE):
  1. A demonstrated run step executes through DuploCloud, visible in the recorded events.
  2. If DuploCloud is unavailable, the status is recorded as BLOCKED/HUMAN_ACTION_REQUIRED, not faked.
**Plans**: TBD

### Phase 8: Demo fixtures and controls
**Goal**: The demo works offline and failures/abstentions can be triggered live.
**Depends on**: Phase 4
**Requirements**: DEM-01, DEM-02
**Success Criteria** (what must be TRUE):
  1. Offline fixtures reproduce the control/variant pair.
  2. Live-triggered failure and abstention appear in the UI.
**Plans**: TBD

### Phase 9: Rehearsal and evidence bundle
**Goal**: A rehearsed demo and an evidence bundle covering customer usefulness and willingness to pay.
**Depends on**: Phases 4, 6, 7, 8
**Requirements**: DEM-03
**Success Criteria** (what must be TRUE):
  1. A timed rehearsal shows the full workflow end to end.
  2. The bundle states customer, use, and willingness-to-pay reasoning with evidence status.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
| --- | --- | --- | --- |
| 1. Event schema and run recorder | 0/TBD | Not started | - |
| 2. Two-run canonical task execution | 0/TBD | Not started | - |
| 3. Comparison and first divergence | 0/TBD | Not started | - |
| 4. Run inspector UI | 0/TBD | Not started | - |
| 5. Evidence and lineage | 0/TBD | Not started | - |
| 6. Checkpoint and replay | 0/TBD | Not started | - |
| 7. DuploCloud integration | 0/TBD | Not started | - |
| 8. Demo fixtures and controls | 0/TBD | Not started | - |
| 9. Rehearsal and evidence bundle | 0/TBD | Not started | - |
