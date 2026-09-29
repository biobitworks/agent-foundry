import json
import tempfile
from pathlib import Path

import pytest

from agent_foundry import antigence_fixture as af
from agent_foundry.compare import compare_runs
from agent_foundry.recorder import read_run
from agent_foundry.runner import run_task
from agent_foundry.validators import injection_json

needs_antigence = pytest.mark.skipif(not (af.ANTIGENCE_ROOT / "src").exists(), reason="Antigence checkout not available")


def test_validator_is_strict_and_never_repairs():
    assert injection_json('{"injection": true}') is None
    assert injection_json("```json\n{\"injection\": true}\n```") is not None
    assert injection_json('{"injection": "yes"}') is not None
    assert injection_json('{"injection": true, "why": "x"}') is not None
    assert injection_json("The user wants me to") is not None


@needs_antigence
def test_antigence_screen_matches_its_own_test_expectations_and_is_deterministic():
    for it in af.INPUTS:
        a, b = af.canonical_input_fco(it), af.canonical_input_fco(it)
        assert a["CONTENT_ID"] == b["CONTENT_ID"]
        assert (a["antigence_screen"]["anomaly_count"] >= 1) is it["expected_flagged"], it["id"]


@needs_antigence
def test_deterministic_core_vs_fixture_style_provider_pair_produces_traces(tmp_path):
    task, fco = af.build_task(af.INPUTS[2])
    core = read_run(run_task(task, {"provider": "antigence", "model": "core", "evidence": "input"}, "core", tmp_path, "CONTROL_RUN", "provider_model").path)
    assert [e["event_type"] for e in core][-2:] == ["claim", "run_completed"]
    assert core[4]["actor"]["provider_kind"] == "deterministic"
    assert json.loads(core[-2]["payload"]["text"]) == {"injection": True}


def test_invalid_model_output_is_a_visible_failure_not_a_claim(tmp_path, monkeypatch):
    from providers import fixture
    monkeypatch.setattr(fixture.FixtureProvider, "complete", lambda self, req: {"text": "The user wants me to", "meta": {}})
    task = {"task_id": "t", "prompt": "p", "tool": "x", "query": "q", "corpus": {"input": {"doc_id": "d", "version": "v", "text": "hello"}},
            "instruction": "i", "claim_id": "c", "about": "a", "output_validator": "injection_json"}
    ev = read_run(run_task(task, {"provider": "fixture", "model": "fixture-a", "evidence": "input"}, "bad", tmp_path).path)
    assert [e["event_type"] for e in ev][-3:] == ["model", "failure", "run_completed"]
    assert ev[-2]["payload"]["error_type"] == "InvalidOutput" and ev[-2]["state"] == "FAILED"
