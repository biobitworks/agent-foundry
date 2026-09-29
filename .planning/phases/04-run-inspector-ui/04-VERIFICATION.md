# Phase 4 verification

| Criterion | Evidence | State |
| --- | --- | --- |
| Side-by-side runs with first divergence marked | driven in the in-app browser: `local_evidence`, `local_models`, fixtures | OBSERVED (manual, browser-driven) |
| Event click shows model/tool/evidence details and field diff | inspector renders both events + changed-field table | OBSERVED (manual) |
| Failures, abstentions, affected outputs visible | `provider_failure`, `missing_evidence`, real qwen abstention; claims table shows `(no claim)` | OBSERVED (manual) |
| Plain-language explanation | deterministic template text in verdict card | OBSERVED |
| `DIVERGENCE=NULL` shown, nothing highlighted | `identical` replicate pair | OBSERVED (manual) |
| API contract, bad-input handling, recorded-capture hash integrity | `tests/unit/test_api.py` | EXECUTED (automated) |

Defects found and fixed during verification: (1) replicate pair rejected by `run_pair`; (2) UI left the previous scenario's
results on screen under an error line (now hidden on every new comparison).
Not covered: automated UI tests, mobile layout, accessibility audit, multi-user concurrency. UI is unauthenticated and binds to 127.0.0.1 only.
