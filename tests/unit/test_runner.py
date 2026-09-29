import json
from pathlib import Path

import pytest

from agent_foundry.recorder import read_run
from agent_foundry.runner import run_pair, run_task

TASK = json.loads((Path(__file__).resolve().parents[2] / "demo/tasks/refund_policy.json").read_text())
A = {"provider": "fixture", "model": "fixture-a", "evidence": "policy-v1"}


def types(rec):
    return [e["event_type"] for e in read_run(rec.path)]


def test_pair_differs_in_exactly_one_variable_and_is_labeled(tmp_path):
    a, b, var = run_pair(TASK, A, {**A, "evidence": "policy-v2"}, tmp_path)
    assert var == "evidence"
    ea, eb = read_run(a.path), read_run(b.path)
    assert ea[0]["meta"]["label"] == "CONTROL_RUN" and eb[0]["meta"]["label"] == "VARIANT_RUN"
    assert ea[0]["meta"]["variable"] == "evidence" and ea[0]["meta"]["config"]["evidence"] == "policy-v1"
    # identical through run_started, agent plan, tool call; first behavioral difference is the retrieved evidence
    assert [e["content_id"] for e in ea][:3] == [e["content_id"] for e in eb][:3]
    assert ea[3]["event_type"] == "evidence" and ea[3]["content_id"] != eb[3]["content_id"]


def test_pair_with_two_differences_is_refused(tmp_path):
    with pytest.raises(ValueError):
        run_pair(TASK, A, {**A, "evidence": "policy-v2", "model": "fixture-b"}, tmp_path)


def test_fixture_is_always_labeled_fixture(tmp_path):
    ev = read_run(run_task(TASK, A, "r", tmp_path).path)
    assert {e["actor"]["provider_kind"] for e in ev if e["event_type"] == "model"} == {"fixture"}


def test_answers_follow_the_evidence(tmp_path):
    a, b, _ = run_pair(TASK, A, {**A, "evidence": "policy-v2"}, tmp_path)
    ca = [e for e in read_run(a.path) if e["event_type"] == "claim"][0]["payload"]["text"]
    cb = [e for e in read_run(b.path) if e["event_type"] == "claim"][0]["payload"]["text"]
    assert "eligible for a refund" in ca and "past it" in cb


def test_provider_failure_is_recorded_not_hidden(tmp_path):
    rec = run_task(TASK, {**A, "model": "fixture-fail"}, "rf", tmp_path)
    ev = read_run(rec.path)
    assert [e["event_type"] for e in ev][-2:] == ["failure", "run_completed"]
    assert ev[-2]["state"] == "FAILED" and ev[-1]["payload"]["status"] == "failed"


def test_missing_evidence_is_an_abstention(tmp_path):
    rec = run_task(TASK, {**A, "evidence": "policy-v9"}, "ra", tmp_path)
    assert types(rec)[-2:] == ["abstention", "run_completed"]
    assert read_run(rec.path)[-1]["payload"]["status"] == "abstained"


def test_claim_declares_dependency_on_model_and_evidence(tmp_path):
    ev = read_run(run_task(TASK, A, "rc", tmp_path).path)
    by_id = {e["event_id"]: e for e in ev}
    claim = [e for e in ev if e["event_type"] == "claim"][0]
    assert {by_id[d]["event_type"] for d in claim["deps"]} == {"model", "evidence"}


def test_provider_switch_counts_as_one_composite_variable(tmp_path):
    dead = "http://127.0.0.1:9"  # nothing listens: deterministic connection failure, no real model call
    a, b, var = run_pair(TASK, {**A, "host": dead}, {**A, "provider": "ollama", "model": "qwen2.5:7b", "host": dead}, tmp_path)
    assert var == "provider_model"
    assert [e["event_type"] for e in read_run(b.path)][-2:] == ["failure", "run_completed"]  # unreachable provider is recorded


def test_replicate_pair_is_allowed_as_a_null_control(tmp_path):
    from agent_foundry.compare import compare_runs
    a, b, var = run_pair(TASK, A, dict(A), tmp_path)
    assert var == "none"
    assert compare_runs(read_run(a.path), read_run(b.path))["DIVERGENCE"] == "NULL"
