import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.server import RECORDED, app

c = TestClient(app)


def test_scenarios_list_marks_real_and_recorded():
    sc = {s["id"]: s for s in c.get("/api/scenarios").json()["scenarios"]}
    assert sc["local_evidence"]["real"] and sc["local_evidence"]["recorded"]
    assert not sc["evidence_changed"]["real"]


def test_fixture_pair_endpoint_returns_comparison():
    r = c.post("/api/pair", json={"scenario": "evidence_changed"}).json()
    assert r["source"] == "LIVE_EXECUTION" and r["comparison"]["FIRST_DIVERGENCE"]["index"] == 3


def test_replicate_scenario_is_null_divergence():
    assert c.post("/api/pair", json={"scenario": "identical"}).json()["comparison"]["DIVERGENCE"] == "NULL"


def test_bad_inputs_are_rejected():
    assert c.post("/api/pair", json={"scenario": "nope"}).status_code == 404
    assert c.post("/api/pair", json={}).status_code == 400
    assert c.get("/api/pair/../../etc/passwd").status_code in (400, 404)
    assert c.get("/api/pair/bad").status_code == 400


def test_recorded_captures_match_their_manifest_hashes_and_are_real():
    for sid in ("local_evidence", "local_models"):
        d = RECORDED / sid
        m = json.loads((d / "manifest.json").read_text())
        assert m["kind"] == "REAL_EXECUTION_RECORDED"
        for f, h in m["files"].items():
            assert hashlib.sha256((d / f).read_bytes()).hexdigest() == h, f"{sid}/{f} changed since capture"
        r = c.get(f"/api/recorded/{sid}").json()
        assert r["source"] == "RECORDED_REAL_EXECUTION"
        assert {e["actor"]["provider_kind"] for e in r["control"] if e["event_type"] == "model"} == {"real"}
        assert r["comparison"]["DIVERGENCE"] == m["comparison_summary"]["DIVERGENCE"]


def test_index_serves_ui():
    assert "Agent Foundry" in c.get("/").text
