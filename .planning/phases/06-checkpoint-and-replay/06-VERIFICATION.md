# Phase 6 verification

| Criterion | Evidence | State |
| --- | --- | --- |
| Checkpoint descriptors recorded | `make_checkpoint` (prefix content ids + digest, config, next step) | IMPLEMENTED; per-phase git-head descriptors in `.planning/checkpoints/` |
| Replay executes and is compared with the original | `tests/unit/test_replay.py` (fixture): verify, branch, divergence, provider error | EXECUTED (automated, fixtures) |
| `replayable` only after a real replay succeeds | REAL replay of recorded qwen2.5:7b run via the UI: identical, 7 events | EXECUTED (real, n=1; `demo/recorded/replay_local_evidence_control`) |
| Divergent replay reported, not hidden | `test_replay_that_diverges_is_reported_not_hidden` | EXECUTED (simulated) |
| Provider error is not a divergence | `test_provider_error_during_verify_is_replay_failed_not_diverged` -> REPLAY_FAILED / replayable UNKNOWN | EXECUTED |
| Branch under another provider | `test_branch_...`; UI button | EXECUTED on fixtures; real branch NOT_TESTED |

Design flaw found during the real replay: a provider timeout would have been classified REPLAY_DIVERGED / replayable=false. Fixed (REPLAY_FAILED, UNKNOWN).
Limits: only resume point is right after `evidence`; n=1; nondeterminism NOT_COMPUTED; HydraDG-compatibility of the descriptor is UNKNOWN
(HydraDG's format was not inspected, so HYDRADG_BRIDGE = NOT_IMPLEMENTED).
