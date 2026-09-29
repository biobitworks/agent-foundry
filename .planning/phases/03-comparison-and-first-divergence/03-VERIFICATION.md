# Phase 3 verification

| Criterion | Evidence | State |
| --- | --- | --- |
| Outputs CONTROL_RUN, VARIANT_RUN, FIRST_DIVERGENCE, DOWNSTREAM_CHANGED_EVENTS, AFFECTED_CLAIMS | `compare_runs` result keys; evidence/model/failure scenarios | EXECUTED (fixture runs) |
| Identical runs => DIVERGENCE=NULL | `test_identical_runs_yield_null_divergence_not_manufactured` | EXECUTED |
| Downstream uses declared deps only | `test_downstream_uses_declared_deps_only_not_chronology` (later differing event without a dep path reported separately, no causal claim) | EXECUTED |
| Failure in variant visible, claim absence visible | `test_provider_failure_in_variant_is_...` | EXECUTED |

Limits: single run per side, nondeterminism NOT_COMPUTED; alignment is positional (no reordering/insert alignment);
comparison is native, NOT delegated to Glasswork (`adapters/glasswork/` still empty; GLASSWORK_BRIDGE = NOT_IMPLEMENTED).
Explanations are deterministic templates, no LLM. 24 tests pass.
