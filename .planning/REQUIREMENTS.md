# Requirements: Agent Foundry

**Defined:** 2026-09-29
**Core Value:** Show where two runs of the same agent task first diverged, what caused it, and whether it can be replayed.

## v1 Requirements

All `PROPOSED` until demonstrated. Traceability to the official atoms is in
`provenance/requirements/AI_CONFERENCE_REQUIREMENTS.jsonl` (keys in parentheses).

### Events and recording (P0)

- [ ] **EVT-01**: A provider-neutral event schema covers Run, Agent, Model, Tool, Evidence, Decision, Failure, Abstention, Checkpoint and Artifact events (JSON Schema in `schemas/events/`).
- [ ] **EVT-02**: A run recorder writes append-only, ordered event logs with CONTENT_ID kept separate from OCCURRENCE_ID and RUN_ID.
- [ ] **EVT-03**: Failures and abstentions are recorded as first-class events and are never dropped (DEMO 7).

### Execution (P0)

- [ ] **EXE-01**: A canonical task definition is submitted once and executed under a controlled configuration (SHIP_WORKING_PRODUCT, EXECUTION_CRITERION).
- [ ] **EXE-02**: The same task runs as run A and run B differing only in a declared variable (model, provider, tool, evidence, or context).
- [ ] **EXE-03**: A deterministic fixture provider exists and is always labeled `fixture`, never presented as a real model run.

### Comparison (P0)

- [ ] **CMP-01**: Events from any provider normalize to the common schema.
- [ ] **CMP-02**: Comparison of CONTROL_RUN vs VARIANT_RUN reports the FIRST_DIVERGENCE with the earliest differing event and why it differs.
- [ ] **CMP-03**: If runs do not diverge the result is `DIVERGENCE=NULL`; a divergence is never manufactured.
- [ ] **CMP-04**: DOWNSTREAM_CHANGED_EVENTS and AFFECTED_CLAIMS are listed using declared dependencies only, not chronology.

### Run inspector UI (P0)

- [ ] **UI-01**: A developer can see both runs side by side with the first divergence marked (PRODUCT_CLARITY_CRITERION).
- [ ] **UI-02**: A developer can open any model/tool/evidence event and inspect its inputs and outputs.
- [ ] **UI-03**: Affected downstream output, failures and abstentions are visible in the UI.
- [ ] **UI-04**: The UI produces a developer-facing explanation of the divergence in plain language.

### Evidence and lineage (P1)

- [ ] **EVD-01**: Evidence and tool inputs are inspectable with source references.
- [ ] **EVD-02**: Occurrences reference FCO/FCG identities through `adapters/fcg/` without asserting causality from order.

### Checkpoint and replay (P1)

- [ ] **REP-01**: A HydraDG-compatible checkpoint descriptor is recorded before and after each phase and run.
- [ ] **REP-02**: A run can be replayed from a checkpoint; `replayable` is set only after a replay actually succeeds.

### DuploCloud (P1)

- [ ] **DUP-01**: DuploCloud materially participates in the demonstrated run (not only credential checks or HTTP 200). Source set: DUPLOCLOUD_REQUIREMENTS.

### Demo (P0-P1)

- [ ] **DEM-01**: Demo fixtures reproduce the control/variant pair offline.
- [ ] **DEM-02**: Failure and abstention controls can be triggered live.
- [ ] **DEM-03**: Rehearsed demo plus an evidence bundle (REAL_WORLD_VIABILITY_CRITERION, CUSTOMER_USEFULNESS_TEST, CUSTOMER_WILLINGNESS_TO_PAY_TEST): who the customer is and why they would pay.

## v2 Requirements

- **OLL-01** (P2): Local Ollarma comparator run on magicSTUDIObox (`OLLARMA_COMPARATOR` stays NOT_TESTED until executed).
- **VIS-01** (P2): Neo4j projection of run graphs.
- **SPN-01** (P2): Additional sponsor integrations, only if they participate in the live workflow.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Static comparison tables as demo | Official framing rejects them |
| Vendoring predecessor repos | Consumed via adapters with pinned commits |
| SIGNED / MMR claims | No signing or verified construction planned |

## Traceability

| Requirement | Phase | Status |
| --- | --- | --- |
| EVT-01, EVT-02, EVT-03 | 1 | Pending |
| EXE-01, EXE-02, EXE-03 | 2 | Pending |
| CMP-01, CMP-02, CMP-03, CMP-04 | 3 | Pending |
| UI-01, UI-02, UI-03, UI-04 | 4 | Pending |
| EVD-01, EVD-02 | 5 | Pending |
| REP-01, REP-02 | 6 | Pending |
| DUP-01 | 7 | Pending |
| DEM-01, DEM-02 | 8 | Pending |
| DEM-03 | 9 | Pending |
