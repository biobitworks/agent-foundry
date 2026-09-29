import json
from pathlib import Path

from agent_foundry.compare import compare_runs
from agent_foundry.recorder import RunRecorder, read_run
from agent_foundry.runner import run_pair, run_task

TASK = json.loads((Path(__file__).resolve().parents[2] / "demo/tasks/refund_policy.json").read_text())
A = {"provider": "fixture", "model": "fixture-a", "evidence": "policy-v1"}


def cmp_pair(tmp_path, variant, tag="p"):
    a, b, _ = run_pair(TASK, A, variant, tmp_path, tag)
    return compare_runs(read_run(a.path), read_run(b.path))


def test_identical_runs_yield_null_divergence_not_manufactured(tmp_path):
    a = run_task(TASK, A, "x1", tmp_path)
    b = run_task(TASK, A, "x2", tmp_path)
    r = compare_runs(read_run(a.path), read_run(b.path))
    assert r["DIVERGENCE"] == "NULL" and r["FIRST_DIVERGENCE"] is None
    assert r["DOWNSTREAM_CHANGED_EVENTS"] == [] and r["AFFECTED_CLAIMS"] == []


def test_evidence_variable_diverges_at_the_evidence_event(tmp_path):
    r = cmp_pair(tmp_path, {**A, "evidence": "policy-v2"})
    fd = r["FIRST_DIVERGENCE"]
    assert r["DIVERGENCE"] == "OBSERVED" and fd["index"] == 3 and fd["control_event"]["event_type"] == "evidence"
    assert {"payload.source_ref", "payload.excerpt"} <= {f["path"] for f in fd["changed_fields"]}
    assert {e["event_type"] for e in r["DOWNSTREAM_CHANGED_EVENTS"]} == {"model", "claim", "run_completed"}
    claim = r["AFFECTED_CLAIMS"][0]
    assert claim["claim_id"] == "refund-eligibility" and claim["changed"] and "eligible" in claim["control"] and "past it" in claim["variant"]
    assert "Affected claim" in r["explanation"] and "'evidence'" in r["explanation"]


def test_model_variable_diverges_at_the_model_event_with_actor_change(tmp_path):
    r = cmp_pair(tmp_path, {**A, "model": "fixture-b"})
    fd = r["FIRST_DIVERGENCE"]
    assert fd["index"] == 4 and fd["control_event"]["event_type"] == "model"
    assert "actor.model" in {f["path"] for f in fd["changed_fields"]}


def test_provider_failure_in_variant_is_a_structural_divergence_and_listed(tmp_path):
    r = cmp_pair(tmp_path, {**A, "model": "fixture-fail"})
    fd = r["FIRST_DIVERGENCE"]
    assert fd["kind"] == "event_type" and fd["variant_event"]["event_type"] == "failure"
    assert any(e["event_type"] == "failure" and e["run"] == "VARIANT_RUN" for e in r["failures_and_abstentions"])
    assert r["AFFECTED_CLAIMS"][0]["variant"] is None  # claim absent in variant, visible not dropped


def test_downstream_uses_declared_deps_only_not_chronology(tmp_path):
    def build(rid, text_x, text_y):
        rec = RunRecorder(rid, tmp_path)
        S = {"kind": "system", "name": "s"}
        s = rec.record("run_started", S, {"task_id": "t"}, meta={"config": {}, "variable": "v"})
        x = rec.record("decision", S, {"decision": text_x}, deps=[s["event_id"]])
        rec.record("decision", S, {"decision": text_y}, deps=[s["event_id"]])  # later event, NO dep on x
        rec.record("decision", S, {"decision": "dep-on-x"}, deps=[x["event_id"]])
        return read_run(rec.path)

    r = compare_runs(build("c", "X1", "Y1"), build("v", "X2", "Y2"))
    assert r["FIRST_DIVERGENCE"]["index"] == 1
    assert [e["event_type"] for e in r["DOWNSTREAM_CHANGED_EVENTS"]] == ["decision", "decision"]  # one per run: the dep-on-x event
    assert len(r["changed_without_declared_dependency"]) == 1  # Y differs but has no declared path from X
    assert "no causal link is asserted" in r["explanation"]
