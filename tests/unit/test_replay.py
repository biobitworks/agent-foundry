import json
from pathlib import Path

import pytest

from agent_foundry.recorder import read_run
from agent_foundry.replay import default_checkpoint_seq, make_checkpoint, replay
from agent_foundry.runner import run_task

TASK = json.loads((Path(__file__).resolve().parents[2] / "demo/tasks/refund_policy.json").read_text())
A = {"provider": "fixture", "model": "fixture-a", "evidence": "policy-v1"}


def orig(tmp_path, cfg=A, rid="orig"):
    return read_run(run_task(TASK, cfg, rid, tmp_path, "CONTROL_RUN", "none").path)


def test_verify_replay_succeeds_and_only_then_sets_replayable(tmp_path):
    ev = orig(tmp_path)
    r = replay(TASK, ev, tmp_path, "rp1")
    assert r["mode"] == "verify" and r["replay_state"] == "EXECUTED" and r["replayable"] is True
    assert r["comparison_vs_original"]["DIVERGENCE"] == "NULL" and r["prefix_identical"]
    assert r["replay_run"][0]["meta"]["label"] == "REPLAY_RUN" and r["replay_run"][0]["run_id"] != ev[0]["run_id"]


def test_checkpoint_default_is_after_evidence_and_descriptor_is_honest(tmp_path):
    ev = orig(tmp_path)
    cp = make_checkpoint(ev, default_checkpoint_seq(ev))
    assert cp["at_seq"] == 3 and cp["next_event_type_in_source"] == "model"
    assert cp["replayable"] == "NOT_TESTED" and cp["hydradg_compatible"].startswith("UNKNOWN")


def test_replay_uses_recorded_evidence_not_the_corpus(tmp_path):
    ev = orig(tmp_path)
    poisoned = json.loads(json.dumps(TASK))
    poisoned["corpus"]["policy-v1"]["text"] = "Refunds are available within 1 days of purchase."
    r = replay(poisoned, ev, tmp_path, "rp2")
    assert r["replay_state"] == "EXECUTED"  # recorded evidence (30 days) drove the resume, not the mutated corpus


def test_branch_under_another_model_reports_divergence_and_never_sets_replayable(tmp_path):
    ev = orig(tmp_path)
    r = replay(TASK, ev, tmp_path, "rp3", override={"model": "fixture-b"})
    assert r["mode"] == "branch" and r["replayable"] == "NOT_APPLICABLE" and r["replay_state"] == "BRANCH_EXECUTED"
    assert r["prefix_identical"] and r["comparison_vs_original"]["FIRST_DIVERGENCE"]["index"] == 4


def test_replay_that_diverges_is_reported_not_hidden(tmp_path, monkeypatch):
    ev = orig(tmp_path)
    from providers import fixture
    real = fixture.FixtureProvider.complete
    monkeypatch.setattr(fixture.FixtureProvider, "complete", lambda self, req: {**real(self, req), "text": "Something else entirely."})
    r = replay(TASK, ev, tmp_path, "rp4")
    assert r["replay_state"] == "REPLAY_DIVERGED" and r["replayable"] is False


def test_replay_failure_of_provider_is_recorded(tmp_path):
    ev = orig(tmp_path)
    r = replay(TASK, ev, tmp_path, "rp5", override={"model": "fixture-fail"})
    assert r["replay_run"][-2]["event_type"] == "failure"


def test_unsupported_resume_point_is_refused(tmp_path):
    ev = orig(tmp_path)
    with pytest.raises(ValueError, match="unsupported resume point"):
        make_checkpoint(ev, 2)
    with pytest.raises(ValueError):
        make_checkpoint(ev, 99)


def test_provider_error_during_verify_is_replay_failed_not_diverged(tmp_path, monkeypatch):
    from providers import fixture
    from providers.base import ProviderError
    ev = orig(tmp_path)

    def boom(self, req):
        raise ProviderError("Timeout", "provider timed out", recoverable=True)

    monkeypatch.setattr(fixture.FixtureProvider, "complete", boom)
    r = replay(TASK, ev, tmp_path, "rp6")
    assert r["replay_state"] == "REPLAY_FAILED" and r["replayable"] == "UNKNOWN"
    assert r["checkpoint"]["replayable"] == "UNKNOWN"
    assert r["replay_run"][-2]["event_type"] == "failure"  # still visible


def test_recorded_real_replay_evidence_is_intact_and_matches_original():
    import hashlib
    from agent_foundry.compare import compare_runs
    root = Path(__file__).resolve().parents[2] / "demo" / "recorded"
    d = root / "replay_local_evidence_control"
    m = json.loads((d / "manifest.json").read_text())
    assert hashlib.sha256((d / "replay.jsonl").read_bytes()).hexdigest() == m["replay_sha256"]
    assert hashlib.sha256((root / "local_evidence" / "control.jsonl").read_bytes()).hexdigest() == m["original_sha256"]
    assert compare_runs(read_run(root / "local_evidence" / "control.jsonl"), read_run(d / "replay.jsonl"))["DIVERGENCE"] == "NULL"
