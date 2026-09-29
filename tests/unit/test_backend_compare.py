import copy
import hashlib
import importlib.util
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from agent_foundry import backend_compare as bc, compare_fco as cf, dataset_fco as dfco
from agent_foundry.compare import compare_runs
from agent_foundry.recorder import read_run

ROOT = dfco.ROOT
D = ROOT / "demo" / "recorded" / "context_compare" / "eca_v01"
MAN = json.loads((D / "context_manifest.json").read_text())
FC, FE = dfco.load_canonical_sub("context_compare")
sha = lambda b: hashlib.sha256(b).hexdigest()


def _studio_module():
    spec = importlib.util.spec_from_file_location("studio_liquid_arm", ROOT / "scripts" / "studio_liquid_arm.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- frozen context: exact bytes, identity, Vithia invariants
def test_frozen_contexts_match_manifest_fco_and_committed_bytes():
    for label, c in MAN["contexts"].items():
        b = (D / c["file"]).read_bytes()
        assert len(b) == c["byte_count"] and sha(b) == c["sha256"] and c["content_id"] == "sha256:" + sha(b)
        f = FC[c["fco_content_hash"]]
        assert f["object_type"] == "CanonicalContextFCO" and f["content_hash"] == "sha256:" + sha(b) and f["body"]["context_text_utf8"].encode() == b
        committed = subprocess.run(["git", "show", f"HEAD:demo/recorded/context_compare/eca_v01/{c['file']}"], capture_output=True, cwd=ROOT)
        if committed.returncode == 0:
            assert committed.stdout == b  # git stored exactly these bytes (the GitHub transfer path)


def test_model_visible_context_carries_no_ids_hashes_or_reference_labels():
    forbidden = {"recommended_action", "recommended_move", "golden_action", "best_action", "optimal_action_set", "safe_fraction", "regret", "state_id", "fco_id", "sha256", "decision_margin"}
    for c in MAN["contexts"].values():
        text = (D / c["file"]).read_text()
        keys = set()
        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    keys.add(k)
                    walk(v)
            elif isinstance(x, list):
                [walk(i) for i in x]
        walk(json.loads(text))
        assert not (forbidden & keys) and "sha256:" not in text
    assert set(json.loads((D / MAN["contexts"]["primary"]["file"]).read_text())["state"]) > set(json.loads((D / MAN["contexts"]["control"]["file"]).read_text())["state"])  # Vithia arm is a strict superset of the raw control


def test_vithia_executed_once_per_arm_and_before_any_model():
    prep = read_run(D / "eca-v01-prep.jsonl")
    pre = [e for e in prep if e["payload"].get("normalized_kind") == "VithiaPreprocessEvent"]
    assert len(pre) == 2 and {e["payload"]["arm"] for e in pre} == {"A5_VITA01_FULL", "A0_RAW"} and all(e["payload"]["executed_once"] for e in pre)
    assert not any(e["event_type"] == "model" for e in prep)
    assert all(json.loads(p.read_text())["start_utc"] > MAN["frozen_at"] for p in D.glob("arm_*.json"))


def test_context_is_reproducible_from_the_pinned_upstream_when_present():
    if not bc.UP.exists():
        pytest.skip("upstream checkout not present (NOT_TESTED)")
    mods, up = bc.upstream()
    rows, info = bc.load_corpus_rows()
    idx, row = bc.select_row(rows)
    assert info["bytes_match_manifest"] and idx == MAN["row_index"] and row["state_id"] == MAN["state_id"] and up["commit"] == MAN["upstream"]["commit"]
    for label, arm in (("primary", bc.PRIMARY_ARM), ("control", bc.CONTROL_ARM)):
        assert bc.compact(bc.build_context(mods, row, arm)) == (D / MAN["contexts"][label]["file"]).read_bytes()


# ---- backend renderings of the same bytes; Studio runner is fail-closed and byte-identical in its request
def test_studio_runner_builds_the_same_request_bytes_as_the_pro_module():
    m = _studio_module()
    for c in MAN["contexts"].values():
        b = (D / c["file"]).read_bytes()
        for model in ("liquid-vithia-1.2b:latest", "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M"):
            assert m.liquid_body(b, model) == bc.liquid_body(b, model)
    assert bc.openjev_body((D / MAN["contexts"]["primary"]["file"]).read_bytes()) == bc.openjev_body((D / MAN["contexts"]["primary"]["file"]).read_bytes())


def test_studio_runner_stops_before_any_model_call_on_a_hash_or_length_mismatch(tmp_path):
    f = D / MAN["contexts"]["primary"]["file"]
    good = MAN["contexts"]["primary"]
    for bad_sha, bad_n in (("0" * 64, good["byte_count"]), (good["sha256"], good["byte_count"] + 1)):
        out = tmp_path / "o.json"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "studio_liquid_arm.py"), "--context", str(f), "--sha256", bad_sha, "--bytes", str(bad_n), "--endpoint", "http://127.0.0.1:9", "--out", str(out)], capture_output=True, text=True)
        assert r.returncode != 0 and "CONTEXT_IDENTITY_MATCH" in r.stdout and "FAIL" in r.stdout and not out.exists()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "studio_liquid_arm.py"), "--context", str(f), "--sha256", good["sha256"], "--bytes", str(good["byte_count"]), "--endpoint", "http://127.0.0.1:9",
                        "--host", "testhost", "--out", str(tmp_path / "ok.json")], capture_output=True, text=True)
    res = json.loads((tmp_path / "ok.json").read_text())
    assert res["context_identity_match"] == "PASS" and res["executed"] is False and res["error_type"] and res["host"] == "testhost"  # unreachable endpoint: failure recorded, not hidden
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "studio_liquid_arm.py"), "--context", str(f), "--sha256", good["sha256"], "--bytes", str(good["byte_count"]), "--endpoint", "http://10.0.0.5:11437", "--out", str(tmp_path / "x.json")], capture_output=True, text=True)
    assert r2.returncode != 0 and not (tmp_path / "x.json").exists()  # non-loopback refused


# ---- normalization and comparison (synthetic FIXTURE arms: never labelled as a real backend)
def _arm(family, response=None, err=None, host="fixture-host", label=None):
    return {"backend": {"family": family, "label": label or f"FIXTURE_{family.upper()}", "provider": "fixture", "provider_kind": "fixture", "model": "fixture"}, "executed": err is None, "error": err, "response": response, "host": host,
            "start_utc": "2026-09-29T23:00:00Z", "end_utc": "2026-09-29T23:00:01Z", "latency_ms": 1.0, "context_sha256_seen": MAN["contexts"]["primary"]["sha256"], "context_byte_count_seen": MAN["contexts"]["primary"]["byte_count"],
            "request_contract": "fixture", "request_sha256": "0" * 64, "params": {}, "_file_sha256": "1" * 64, "context_identity_match": "PASS", "which": "primary"}


def test_normalize_openjev_and_liquid_preserve_ties_probabilities_and_failures():
    oj = bc.normalize(_arm("openjev", {"answers": {"move": {"choice": "LEFT", "confidence": 0.13, "probabilities": {"LEFT": 0.4, "STAY": 0.4, "RIGHT": 0.2}}}, "usage": {"input_tokens": 3, "output_tokens": 0}}))
    assert oj["choice"] == "LEFT" and oj["top_probability_tie"] == ["LEFT", "STAY"] and oj["probabilities"]["RIGHT"] == 0.2
    lq = bc.normalize(_arm("liquid", {"response": '{"choice":"STAY"}', "eval_count": 9}))
    assert lq["choice"] == "STAY" and lq["probabilities"] == bc.NA and lq["confidence"] == bc.NA  # never filled in
    bad = bc.normalize(_arm("liquid", {"response": "not json"}))
    assert bad["format_valid"] is False and bad["choice"] == bc.NC and bad["fallback"] is True
    off = bc.normalize(_arm("openjev", {"answers": {"move": {"choice": "JUMP"}}}))
    assert off["format_valid"] is False and off["format_error"] == "choice_not_in_action_set"
    fail = bc.normalize(_arm("liquid", None, err="URLError: refused"))
    assert fail["format_valid"] is False and "refused" in fail["format_error"]


def test_compare_behavior_finds_the_first_divergent_field_not_a_string_diff():
    same = bc.compare_behavior({"format_valid": True, "choice": "LEFT", "probabilities": bc.NA, "confidence": bc.NA, "fallback": False}, {"format_valid": True, "choice": "LEFT", "probabilities": bc.NA, "confidence": bc.NA, "fallback": False})
    assert same["first_behavioral_divergence"] == "NONE_IN_COMPARABLE_FIELDS"
    diff = bc.compare_behavior({"format_valid": True, "choice": "LEFT", "probabilities": {"LEFT": 0.5}, "confidence": 0.5, "fallback": False, "top_probability_tie": []},
                               {"format_valid": True, "choice": "STAY", "probabilities": bc.NA, "confidence": bc.NA, "fallback": False})
    assert diff["first_behavioral_divergence"] == {"event": "DecisionEvent", "field": "choice", "arm_a": "LEFT", "arm_b": "STAY"}
    assert {r["field"]: r["status"] for r in diff["rows"]}["probabilities"] == "NOT_AVAILABLE_ON_AT_LEAST_ONE_ARM"
    assert diff["evidence_used_arm_a"].startswith("NOT_AVAILABLE")


def test_arm_streams_are_provider_neutral_with_machine_identity_only_in_meta_and_failures_preserved(tmp_path):
    fco = FC[MAN["contexts"]["primary"]["fco_content_hash"]]
    raw = (D / MAN["contexts"]["primary"]["file"]).read_bytes()
    q = bc.parse_context(raw)["question"]
    a = cf.arm_stream(_arm("openjev", {"answers": {"move": {"choice": "LEFT", "probabilities": {"LEFT": 0.5, "STAY": 0.3, "RIGHT": 0.2}}}}, host="hostA"), raw, fco, tmp_path, "t-a", "2026-09-29T23:00:00Z", q)
    b = cf.arm_stream(_arm("liquid", {"response": '{"choice":"STAY"}'}, host="hostB"), raw, fco, tmp_path, "t-b", "2026-09-29T23:00:00Z", q)
    kinds = [e["payload"].get("normalized_kind") for e in a]
    assert kinds[1:8] == ["QuestionEvent", "ContextEvent", "ModelStartEvent", "ModelEvent", "EvidenceUseEvent", "VerifierEvent", "DecisionEvent"]
    for i in (1, 2, 3):  # question, context, model-start: identical content across arms (machine identity is meta, not payload)
        assert a[i]["content_id"] == b[i]["content_id"]
    assert a[2]["meta"]["machine"]["host"] == "hostA" and b[2]["meta"]["machine"]["host"] == "hostB"
    fd = compare_runs(a, b)["FIRST_DIVERGENCE"]
    assert a[fd["index"]]["event_type"] == "model"  # the backend is the intentional independent variable
    f = cf.arm_stream(_arm("liquid", None, err="URLError: refused"), raw, fco, tmp_path, "t-f", "2026-09-29T23:00:00Z", q)
    assert [e["event_type"] for e in f[-3:]] == ["failure", "abstention", "run_completed"] and f[-3]["payload"]["normalized_kind"] == "FailureEvent"


# ---- the recorded comparison
def test_recorded_comparisons_identity_first_divergence_and_labels():
    for name in ("primary", "control"):
        r = json.loads((D / name / "comparison.json").read_text())
        assert r["CONTEXT_IDENTITY_MATCH"] == "PASS" and all(r["identity_checks"].values())
        assert r["FIRST_DIVERGENT_EVENT"] == "DecisionEvent" and r["FIRST_DIVERGENT_FIELD"] == "choice"
        assert r["arm_a"]["label"].startswith("OPENJEV") and "NON_TYPESAFE_JEV" in r["arm_a"]["label"] and r["arm_a"]["host"].startswith("magicPRObox")
        assert "PROVISIONAL" in r["arm_b"]["label"]  # not presented as the Studio arm
        assert r["behavior_comparison"]["evidence_used_arm_a"].startswith("NOT_AVAILABLE") and r["arm_b"]["normalized"]["probabilities"] == bc.NA
        assert len(read_run(D / name / f"eca-v01-{name}-a.jsonl")) == len(read_run(D / name / f"eca-v01-{name}-b.jsonl"))
    p = json.loads((D / "primary" / "comparison.json").read_text())
    assert p["arm_a"]["normalized"]["top_probability_tie"] == ["LEFT", "STAY"] and p["behavior_comparison"]["notes"]  # OpenJEV's own tie is disclosed


def test_openjev_arm_records_a_verified_runtime_and_no_other_model_wears_the_label():
    for p in D.glob("arm_*.json"):
        r = json.loads(p.read_text())
        is_oj = "openjev" in p.name
        assert (r["backend"]["family"] == "openjev") == is_oj and (r["backend"]["label"].startswith("OPENJEV")) == is_oj
        if is_oj:
            assert r["backend"]["runtime"]["runtime_verified_on_this_host"] is True and r["backend"]["model_identity"]["repo"] == "openjev/openjev-MLX-4bit" and len(r["backend"]["model_identity"]["weights_sha256"]) == 4  # 3 shards + tokenizer.json
        assert r["context_sha256_seen"] == MAN["contexts"][r["which"]]["sha256"] and r["context_byte_count_seen"] == MAN["contexts"][r["which"]]["byte_count"]


def test_route_failure_is_preserved_with_separated_evidence_and_an_alternate_topology():
    rc = json.loads((D / "route_failure_receipt.json").read_text())
    assert rc["OPENJEV_STUDIO_CONNECTIVITY"] == "FAILED" and any(o["observed_by"] == "operator" and o["verified_by_agent"] is False for o in rc["observations"])
    ev = read_run(D / "eca-v01-route-attempts.jsonl")
    assert [e["event_type"] for e in ev] == ["run_started", "failure", "decision", "run_completed"] and ev[1]["payload"]["message"] == "OPENJEV_STUDIO_CONNECTIVITY=FAILED"
    assert "magicPRObox" in ev[2]["payload"]["chosen"] and "magicSTUDIObox" in ev[2]["payload"]["chosen"]


def test_arm_result_fcos_and_edges():
    arms = [f for f in FC.values() if f["object_type"] == "ArmResultFCO"]
    assert len(arms) == 4
    for f in FC.values():
        dfco.validate_fco(f)
    for f in arms:
        assert sha((ROOT / f["body"]["file"]).read_bytes()) == f["content_hash"].split(":")[1] and f["body"]["context_content_id"].startswith("sha256:")
    assert {e["rel"] for e in FE} == {"derived_from", "compared_with"} and all(e["causal"] is False and e["ontology_status"] == "FCG_ONTOLOGY_V1.3.0" for e in FE)


def test_api_reports_studio_arm_status_honestly():
    from api.server import app
    r = TestClient(app).get("/api/compare/eca_v01").json()
    assert set(r["comparisons"]) >= {"primary", "control"} and all(v["bytes_verified"] for v in r["contexts"].values())
    assert r["studio_liquid_arm"]["status"] in ("PENDING_OPERATOR_EXECUTION_ON_MAGICSTUDIOBOX", "IMPORTED") and r["route_failure"]["OPENJEV_STUDIO_CONNECTIVITY"] == "FAILED"
    assert TestClient(app).get("/api/compare/nope").status_code == 404


def test_neo4j_projection_rebuildable_and_scoped():
    from agent_foundry import dataset_graph as dg, moddik_graph as mg
    try:
        drv = mg.connect()
    except Exception:
        pytest.skip("project-local Neo4j not reachable (NOT_TESTED)")
    aid = "context_compare_unit_test"
    runs = [D / "eca-v01-prep.jsonl", D / "primary" / "eca-v01-primary-a.jsonl", D / "primary" / "eca-v01-primary-b.jsonl"]
    other = lambda: mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=aid)[0]["n"]
    dg.clear_admission(drv, aid)
    ob = other()
    for r in runs:
        dg.project(drv, aid, FC, FE, read_run(r))
    before = dg.fingerprint(drv, aid)
    dg.clear_admission(drv, aid)
    assert dg.counts(drv, aid)["nodes"] == 0
    for r in runs:
        dg.project(drv, aid, FC, FE, read_run(r))
    assert dg.fingerprint(drv, aid) == before and dg.counts(drv, aid)["causal_like_edges"] == 0
    dg.clear_admission(drv, aid)
    assert other() == ob
    drv.close()
