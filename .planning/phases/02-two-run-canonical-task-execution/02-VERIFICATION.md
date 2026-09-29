# Phase 2 verification (PARTIAL)

| Criterion | Evidence | State |
| --- | --- | --- |
| Canonical task yields two recorded runs differing in exactly one declared variable | `test_pair_differs_in_exactly_one_variable_and_is_labeled`, `test_pair_with_two_differences_is_refused` | EXECUTED (fixture providers only) |
| Each run labeled real provider or `fixture` | `test_fixture_is_always_labeled_fixture` | EXECUTED |
| Provider failure recorded, not hidden | `test_provider_failure_is_recorded_not_hidden`; missing evidence -> abstention | EXECUTED (simulated failure) |
| Real model provider run | none | NOT_TESTED |
| Ollama adapter (`providers/ollama.py`) | none; 11434 not listening on magicPRObox | IMPLEMENTED, NOT_TESTED (`OLLARMA_COMPARATOR=NOT_TESTED`) |

Design correction found by tests: `run_started` originally hashed config/label, which would have made every pair
"diverge" at event 0. Config/label/variable now live in non-hashed `meta`; tool arguments contain only what the
agent sends. Schema amended (Phase 1 artifact); 19 tests pass. First behavioral difference in the demo pair is the
retrieved `evidence` event (seq 3), by declared variable `evidence` (policy-v1 vs policy-v2).

Blocked on operator: which real providers to run and which credentials may be used. This session's
`ANTHROPIC_*` environment is the Claude Code harness and is NOT reused for product runs without approval.
