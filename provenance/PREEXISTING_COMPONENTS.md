# Pre-existing components (declared BEFORE Hack Day feature work)

Baseline established 2026-09-29 (UTC) on magicPRObox, before any Agent Foundry
feature code and before any development framework was installed.
Identities live in `SOURCE_COMMITS.json`. This file states *roles and boundaries*.

Hashes establish identity, not truth. Nothing here upgrades any state.

| Component | Role in Agent Foundry | Consumed via | Status of consumption |
| --- | --- | --- | --- |
| HydraDG | state / memory / checkpoint / bounded recovery engine | `adapters/hydradg/` | NOT_IMPLEMENTED (PROPOSED) |
| Glasswork | evaluation / comparison engine | `adapters/glasswork/` | NOT_IMPLEMENTED (PROPOSED) |
| Ollarma | local model execution / routing layer | `adapters/ollarma/` | NOT_TESTED |
| FCO/FCG (`fractal-custody-objects`) | evidence / lineage / transformation / claim-custody | `adapters/fcg/` | NOT_IMPLEMENTED (PROPOSED) |
| DuploCloud (`duplocloud/devkit`, `duplocloud/mcp`) | external Hack Day execution substrate | `integrations/duplocloud/` | NOT_TESTED |
| GSD Core (`open-gsd/gsd-core`) | external development workflow accelerator ONLY | `integrations/gsd/` | see `GSD_UPSTREAM_LOCK.json` |
| LongHorizon | sibling prior work; NOT a dependency; NOT imported | none | UNKNOWN local checkout; license UNKNOWN |

## Agent Foundry is NEW

Agent Foundry (`Debug your AI agents like software.`) is a new developer-facing
reliability/debugging product. Its own code begins at the first commit AFTER this
baseline. Anything in the predecessors above that is reused later must be
consumed through an adapter or explicitly imported with a recorded commit + license.

## What GSD is not

Not canonical provenance, not a replacement for FCO/FCG, HydraDG or Glasswork,
not the product, not a source of historical truth. `.planning/` is operational
planning state; it may be content-addressed and referenced by FCOs but is not the FCG.

## Known predecessor caveats (observed, not resolved)

- Local HydraDG, Ollarma, FCO/FCG checkouts are NOT at origin/main and have uncommitted entries.
  Bootstrap did not mutate them. Any adapter must pin a specific commit and record dirtiness.
- Local Glasswork checkout lives under a `_folded_from_home_*` scratchpad path (== origin/main, 1 dirty entry).
- The enclosing `/Users/byron/projects/active` git repo is dirty and has an unrelated
  `origin` (BioComputingUP/MobiDB-lite). Agent Foundry has its OWN repo; the parent was not touched.
