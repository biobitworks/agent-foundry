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


def test_antigence_capture_endpoints_and_integrity():
    idx = c.get("/api/antigence").json()["cases"]
    assert {x["model"] for x in idx} >= {"lfm350m", "lfm1p2b", "lfm2p6b"} and len(idx) >= 12
    r = c.get("/api/antigence/adv-ignore/lfm350m").json()
    assert r["source"] == "RECORDED_REAL_EXECUTION" and r["control"][4]["actor"]["provider_kind"] == "deterministic"
    assert r["variant"][4]["actor"]["provider_kind"] == "real"
    assert c.get("/api/antigence/../x/y").status_code in (400, 404)
    assert c.get("/api/antigence/adv-ignore/nope").status_code == 404


def test_antigence_capture_files_match_manifest_hashes():
    import hashlib
    root = RECORDED / "antigence_lfm"
    files = {}
    for m in sorted(root.glob("manifest_*.json")):
        files.update(json.loads(m.read_text())["files_sha256"])
    assert files
    for rel, h in files.items():
        assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == h, f"{rel} changed since capture"
