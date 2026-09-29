# Phase 1 verification

| Criterion | Evidence | State |
| --- | --- | --- |
| Schema validates every declared event type | `test_every_event_type_validates_and_roundtrips` (13 types; model/tool/evidence/failure/abstention covered in other tests) | EXECUTED (12/12 tests pass) |
| Ordered JSONL, distinct CONTENT_ID / OCCURRENCE_ID / RUN_ID | `test_content_id_is_stable_across_runs_but_occurrence_differs`, `test_meta_and_ts_do_not_change_content_id` | EXECUTED |
| Failure and abstention recorded and read back | `test_failure_and_abstention_are_first_class_and_kept`, wrong-state rejected | EXECUTED |
| Tamper / deletion detected | `test_tamper_is_detected`, `test_deleted_event_is_detected` | EXECUTED |

Limits (not claimed): integrity is internal consistency only. No signing, no Merkle/MMR, no authenticity claim.
Coverage of the `agent`/`run_started` variants with the real provider path: NOT_TESTED (Phase 2).
Plan authored inline; GSD planner/plan-checker/verifier agents were NOT run for this phase.
