# Phase 2 verification (PARTIAL)

| Criterion | Evidence | State |
| --- | --- | --- |
| Canonical task yields two recorded runs differing in exactly one declared variable | `test_pair_differs_in_exactly_one_variable_and_is_labeled`, `test_pair_with_two_differences_is_refused` | EXECUTED (fixture providers only) |
| Each run labeled real provider or `fixture` | `test_fixture_is_always_labeled_fixture` | EXECUTED |
| Provider failure recorded, not hidden | `test_provider_failure_is_recorded_not_hidden`; missing evidence -> abstention | EXECUTED (simulated failure) |
| Real model provider run (local Ollama, direct HTTP) | `demo/recorded/local_evidence`, `local_models`: real qwen2.5:7b and llama3.2:3b executions captured, hashes in manifests | EXECUTED (local models only; cloud providers NOT_TESTED) |
| Ollama adapter (`providers/ollama.py`) | ran against 127.0.0.1:11434 on magicPRObox | EXECUTED. Ollarma routing (:8484) was NOT exercised: `OLLARMA_COMPARATOR=NOT_TESTED` |

Design correction found by tests: `run_started` originally hashed config/label, which would have made every pair
"diverge" at event 0. Config/label/variable now live in non-hashed `meta`; tool arguments contain only what the
agent sends. Schema amended (Phase 1 artifact); 19 tests pass. First behavioral difference in the demo pair is the
retrieved `evidence` event (seq 3), by declared variable `evidence` (policy-v1 vs policy-v2).

Blocked on operator: which real providers to run and which credentials may be used. This session's
`ANTHROPIC_*` environment is the Claude Code harness and is NOT reused for product runs without approval.

## Correction (2026-09-29)
An earlier note said port 11434 was not listening on magicPRObox. That was a WRONG observation (a `nc` flag quirk).
`lsof` shows `ollama` listening on 127.0.0.1:11434 and a python process on 127.0.0.1:8484 (not inspected, not claimed to be Ollarma).

Real-run findings (n=2 repeats at temperature 0, seed 1, identical outputs; not a determinism proof):
qwen2.5:7b answers "yes" for policy v1, ABSTAINs for policy v2 (arguably wrong); llama3.2:3b answers "no" for v1 (wrong: 20 <= 30) and "no" for v2.
Cold model swaps on this 16 GB machine take 70-150 s, so live two-model comparison here is unreliable; recorded captures are used for the demo.
