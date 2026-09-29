import hashlib
import json

from fastapi.testclient import TestClient

from api.server import RECORDED, app

c = TestClient(app)
REC = RECORDED / "moddik" / "rehearsal_1"


def test_recorded_moddik_files_match_manifest_and_are_real_and_simulated():
    m = json.loads((REC / "manifest.json").read_text())
    assert m["kind"] == "REAL_EXECUTION_RECORDED" and m["source"] == "SIMULATED"
    for f, h in m["files"].items():
        assert hashlib.sha256((REC / f).read_bytes()).hexdigest() == h, f"{f} changed since capture"
    assert any("ASR NOT_TESTED" in x or "live ASR NOT_TESTED" in x for x in m["limits"])  # limits are carried, not dropped


def test_run_view_reverifies_and_exposes_route_and_breakpoint_leaves():
    r = c.get("/api/moddik/run/recorded:rehearsal_1").json()
    v = r["view"]
    assert r["source"] == "RECORDED_REAL_EXECUTION" and len(v["breakpoints"]) == 3
    assert all(b["reverified_now"] and b["binding_verified"] and len(b["leaves"]) == 7 for b in v["breakpoints"])
    assert v["route"]["action"]["simulated_action"] == "MEDIUM_EXCHANGE_RECOMMENDED" and "NONE" in v["route"]["action"]["actuation"]
    assert v["route"]["verifier"]["pass"] is True and v["route"]["breakpoint"]["root"] == v["breakpoints"][1]["root"]


def test_pair_first_divergence_is_the_perturbed_sensor():
    r = c.get("/api/moddik/pair/recorded:rehearsal_1").json()
    fd = r["comparison"]["FIRST_DIVERGENCE"]
    assert fd["control_event"]["event_type"] == "evidence" and {f["path"] for f in fd["changed_fields"]} >= {"payload.value"}
    assert r["control"][fd["index"]]["payload"]["sensor"] == "nutrient" and r["control"][fd["index"]]["payload"]["tick"] == 9


def test_bad_sources_are_rejected():
    assert c.get("/api/moddik/run/recorded:../../etc").status_code in (400, 404)
    assert c.get("/api/moddik/run/nope").status_code == 400
    assert c.get("/api/moddik/run/recorded:rehearsal_1?side=zzz").status_code == 400
    assert c.post("/api/moddik/run", json={"model": "gpt-9"}).status_code == 400
    assert c.post("/api/moddik/run", json={"transcript": ""}).status_code == 400


def test_graph_endpoint_degrades_honestly_without_neo4j(monkeypatch):
    from agent_foundry import moddik_graph as g
    monkeypatch.setattr(g, "connect", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    r = c.get("/api/moddik/graph/recorded:rehearsal_1").json()
    assert r["backend"] == "UNAVAILABLE" and "canonical" in r["reason"] and r["credentials"]["VALUE"] == "NOT_CAPTURED"


def test_generic_neo4j_env_vars_never_override_the_project_local_instance(monkeypatch):
    """Regression: a shell holding NEO4J_* for an unrelated cloud database must not redirect the projection there."""
    from agent_foundry import moddik_graph as g
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://someone-elses.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_USER", "x")
    monkeypatch.setenv("NEO4J_PASSWORD", "x")
    assert "databases.neo4j.io" not in g._creds().get("NEO4J_URI", "")


def test_non_loopback_neo4j_uri_is_refused(monkeypatch):
    import pytest
    from agent_foundry import moddik_graph as g
    monkeypatch.setenv("AGENT_FOUNDRY_NEO4J_URI", "neo4j+s://x.databases.neo4j.io:7687")
    monkeypatch.setenv("AGENT_FOUNDRY_NEO4J_USER", "u")
    monkeypatch.setenv("AGENT_FOUNDRY_NEO4J_PASSWORD", "p")
    monkeypatch.delenv("AGENT_FOUNDRY_NEO4J_ALLOW_REMOTE", raising=False)
    with pytest.raises(RuntimeError, match="non-loopback"):
        g.connect()
    assert g._is_local("bolt://127.0.0.1:7691") and g._is_local("bolt://localhost:7687") and not g._is_local("neo4j+s://x.databases.neo4j.io:7687")
