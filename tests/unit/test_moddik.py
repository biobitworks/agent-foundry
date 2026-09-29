import copy
import hashlib
import json

import pytest

from agent_foundry import merkle, moddik_agent as agent, moddik_run as mr, moddik_sim as sim
from agent_foundry.compare import compare_runs
from agent_foundry.ids import canonical_json
from agent_foundry.recorder import read_run


# ---- simulator -------------------------------------------------------------------------------------------------------
def test_stream_is_deterministic_and_simulated():
    a, b = list(sim.stream()), list(sim.stream())
    assert a == b and len(a) == sim.TICKS * len(sim.ORDER)
    assert {x["source"] for x in a} == {"SIMULATED"}
    assert [x["sequence"] for x in a] == list(range(len(a)))
    assert list(sim.stream(seed="other")) != a


def test_scripted_trajectory_crosses_the_rule_only_at_the_decision_tick():
    met = []
    for t in range(sim.TICKS):
        v = {x["sensor"]: x["value"] for x in sim.tick_readings(t)}
        met.append(sim.policy_met(v["nutrient"], v["waste"]))
    assert not any(met[: sim.DECISION_TICK]) and all(met[sim.DECISION_TICK:])


# ---- merkle ----------------------------------------------------------------------------------------------------------
def _lh(b):
    return hashlib.sha256(b"\x00" + hashlib.sha256(b).digest()).hexdigest()


def _nh(l, r):
    return hashlib.sha256(b"\x01" + bytes.fromhex(l) + bytes.fromhex(r)).hexdigest()


def test_known_answer_roots_computed_independently():
    leaves = [{"n": i} for i in range(3)]
    hs = [_lh(canonical_json(x).encode()) for x in leaves]
    expected = _nh(_nh(hs[0], hs[1]), hs[2])  # odd node promoted
    r = merkle.build_commitment(leaves)
    assert r["MERKLE_ROOT"] == expected and r["verification"]["PASS"]
    assert merkle.build_commitment(leaves[:1])["MERKLE_ROOT"] == hs[0]
    assert merkle.merkle_root([]) == hashlib.sha256(b"\x02").hexdigest()


def test_order_is_committed():
    a = merkle.build_commitment([{"n": 1}, {"n": 2}])["MERKLE_ROOT"]
    b = merkle.build_commitment([{"n": 2}, {"n": 1}])["MERKLE_ROOT"]
    assert a != b


def test_inclusion_proofs_for_every_leaf_and_size():
    for n in range(1, 12):
        hs = [_lh(str(i).encode()) for i in range(n)]
        root = merkle.merkle_root(hs)
        assert all(merkle.verify_inclusion(hs[i], merkle.inclusion_proof(hs, i), root) for i in range(n))
        assert not merkle.verify_inclusion(_lh(b"x"), merkle.inclusion_proof(hs, 0), root)


def test_tampered_receipt_fails_verification_and_never_passes_silently():
    r = merkle.build_commitment(sim.tick_readings(9))
    assert r["verification"]["PASS"]
    t = copy.deepcopy(r)
    t["leaves"][3]["canonical_bytes_utf8"] = t["leaves"][3]["canonical_bytes_utf8"].replace("nutrient", "nutrienT")
    assert not merkle.verify_commitment(t)["PASS"]
    t2 = copy.deepcopy(r)
    t2["MERKLE_ROOT"] = "NOT_COMPUTED"
    assert not merkle.verify_commitment(t2)["PASS"]  # a NOT_COMPUTED root is never upgraded to a pass
    t3 = copy.deepcopy(r)
    t3["leaves"][0], t3["leaves"][1] = t3["leaves"][1], t3["leaves"][0]
    assert not merkle.verify_commitment(t3)["PASS"]


def test_agrees_with_fco_reference_when_present():
    ref = merkle.fco_reference_cross_check()
    if ref is None:
        pytest.skip("fractal-custody-objects checkout not present (cross-check NOT_TESTED)")
    r = merkle.build_commitment(sim.tick_readings(9), ref)
    assert r["verification"]["checks"]["independent_implementation_agrees"] is True


# ---- model output contract / verifier --------------------------------------------------------------------------------
LATEST = {"nutrient": 10.197, "waste": 16.927}
PC = agent.policy_check(LATEST)
AMAP = {"S4": {"sensor": "nutrient", "content_id": "cid:a"}, "S5": {"sensor": "waste", "content_id": "cid:b"}, "P1": {"sensor": "policy_check", "content_id": "cid:c"}}
GOOD = {"recommendation": "MEDIUM_EXCHANGE_RECOMMENDED", "confidence": "high", "evidence": ["S4", "S5", "P1"], "values": dict(LATEST), "rationale": "Nutrient is below 12.0 mM and waste exceeds 15.0 mM."}


def test_extract_takes_text_after_think_and_refuses_fences_and_repair():
    assert agent.extract("reasoning...</think>" + json.dumps(GOOD))[0] == GOOD
    assert agent.extract("```json\n" + json.dumps(GOOD) + "\n```")[0] is None
    assert agent.extract("Sure! " + json.dumps(GOOD))[0] is None
    assert agent.extract("[1]")[0] is None


def test_verifier_passes_good_and_names_each_failure():
    assert agent.verify(GOOD, AMAP, PC)["PASS"]
    ids = agent.verify(GOOD, AMAP, PC)["evidence_content_ids"]
    assert ids == ["cid:a", "cid:b", "cid:c"]
    bad = [
        ({**GOOD, "evidence": ["S4", "S99", "P1"]}, "all_cited_ids_were_in_prompt"),
        ({**GOOD, "values": {"nutrient": 14.379, "waste": 12.561}}, "values_match_latest_evidence"),
        ({**GOOD, "recommendation": "NO_INTERVENTION"}, "recommendation_consistent_with_policy_check"),
        ({**GOOD, "rationale": "Waste is high because cells consumed glucose."}, "no_causal_language"),
        ({**GOOD, "evidence": ["S4", "P1"]}, "cites_nutrient_and_waste_evidence"),
        ({**GOOD, "extra": 1}, "keys_exact"),
    ]
    for obj, check in bad:
        r = agent.verify(obj, AMAP, PC)
        assert not r["PASS"] and r["checks"][check] is False, check


# ---- full run with a stubbed model (no Ollama, no Neo4j) ------------------------------------------------------------
def _stub(monkeypatch, mutate=None):
    def fake(tag, prompt, num_predict, host="", timeout=0):
        # the stub reads what was ACTUALLY put in the prompt, so it cannot cite evidence the prompt did not contain
        import re
        vals = {m.group(1): float(m.group(2)) for m in re.finditer(r"S\d+ (nutrient|waste) = ([\d.]+) mM \(t=5400s\)", prompt)}
        obj = {"recommendation": "MEDIUM_EXCHANGE_RECOMMENDED" if "criteria_met:True" in prompt else "NO_INTERVENTION", "confidence": "high", "evidence": ["S4", "S5", "P1"],
               "values": {"nutrient": vals["nutrient"], "waste": vals["waste"]}, "rationale": "Numbers read as reported."}
        obj = mutate(obj) if mutate else obj
        return {"ok": True, "text": "<think>x</think>" + json.dumps(obj), "done_reason": "stop", "eval_count": 1, "latency_ms": 1}
    monkeypatch.setattr(agent, "call_model", fake)


def test_run_maps_to_existing_events_and_breakpoints_verify(tmp_path, monkeypatch):
    _stub(monkeypatch)
    res = mr.run_moddik("t-a", tmp_path, use_graph=False)
    ev = res["events"]
    read_run(res["run_path"])  # re-verifies schema, ordering, id recomputation
    types = [e["event_type"] for e in ev]
    assert types.count("checkpoint") == 3 and types.count("model") == 1 and types.count("decision") == 1 and types[-1] == "run_completed"
    for e in ev:
        if e["event_type"] == "checkpoint":
            p = e["payload"]
            assert p["verification"]["PASS"] and p["leaf_event_binding_verified"] and p["MERKLE_ROOT"] != "NOT_COMPUTED"
            assert merkle.verify_commitment({"leaves": p["commitment"]["leaves"], "MERKLE_ROOT": p["MERKLE_ROOT"], "construction": p["commitment"]["construction"]})["PASS"]
    d = next(e for e in ev if e["event_type"] == "decision")
    assert d["state"] == "PROPOSED" and d["payload"]["SIMULATED_ACTION"] == "MEDIUM_EXCHANGE_RECOMMENDED" and "NONE" in d["payload"]["actuation"]
    ids = {e["event_id"]: e for e in ev}
    for eid in d["meta"]["evidence_event_ids"]:  # every named evidence event exists in this run and is the event whose content the model was given
        assert eid in ids and ids[eid]["content_id"] in d["payload"]["evidence_content_ids"]
    assert len(d["payload"]["evidence_content_ids"]) == 3
    m = next(e for e in ev if e["event_type"] == "model")
    assert set(m["deps"]) >= {e["event_id"] for e in ev if e["event_type"] == "tool" and e["payload"]["tool"] != "neo4j.project_run"}
    assert res["summary"]["graph"]["backend"] == "canonical_jsonl_fallback"


def test_replay_is_deterministic_up_to_the_model_step_and_a_perturbation_diverges_at_the_sensor(tmp_path, monkeypatch):
    _stub(monkeypatch)
    a = mr.run_moddik("t-b1", tmp_path, use_graph=False)["events"]
    b = mr.run_moddik("t-b2", tmp_path, use_graph=False)["events"]
    assert compare_runs(a, b)["DIVERGENCE"] == "NULL"  # identical content across the whole run under a deterministic stub
    assert [e["payload"]["MERKLE_ROOT"] for e in a if e["event_type"] == "checkpoint"] == [e["payload"]["MERKLE_ROOT"] for e in b if e["event_type"] == "checkpoint"]
    c = mr.run_moddik("t-b3", tmp_path, use_graph=False, perturb={("nutrient", 9): 2.5})["events"]
    cmp_ = compare_runs(a, c)
    fd = cmp_["FIRST_DIVERGENCE"]
    assert cmp_["DIVERGENCE"] == "OBSERVED"
    assert a[fd["index"]]["payload"]["sensor"] == "nutrient" and a[fd["index"]]["payload"]["tick"] == 9
    roots = lambda ev: [e["payload"]["MERKLE_ROOT"] for e in ev if e["event_type"] == "checkpoint"]
    assert roots(a)[0] == roots(c)[0]  # the prior (nominal) hardware breakpoint is identical: replay prefix verified
    assert roots(a)[1] != roots(c)[1]
    assert not any(e["event_type"] == "decision" for e in c)  # criteria no longer met: no simulated action, nothing manufactured


def test_no_action_when_verifier_fails(tmp_path, monkeypatch):
    _stub(monkeypatch, mutate=lambda o: {**o, "values": {"nutrient": 14.379, "waste": 12.561}})
    ev = mr.run_moddik("t-c", tmp_path, use_graph=False)["events"]
    assert not any(e["event_type"] == "decision" for e in ev)
    assert any(e["event_type"] == "abstention" for e in ev)
    assert next(e for e in ev if e["event_type"] == "evaluation")["state"] == "FAILED"


def test_tampering_with_a_sensor_leaf_is_detected(tmp_path, monkeypatch):
    _stub(monkeypatch)
    res = mr.run_moddik("t-d", tmp_path, use_graph=False)
    lines = open(res["run_path"]).read().splitlines()
    i = next(i for i, l in enumerate(lines) if json.loads(l)["payload"].get("sensor") == "nutrient" and json.loads(l)["payload"].get("tick") == 3)
    ev = json.loads(lines[i])
    ev["payload"]["value"] = ev["payload"]["value"] + 1  # edit the value, leave the recorded content_id/event_id untouched
    lines[i] = json.dumps(ev, sort_keys=True)
    open(res["run_path"], "w").write("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        read_run(res["run_path"])


# ---- PLAUD custody lane (SYNTHETIC test bytes; this proves the importer, NOT a real PLAUD recording) ---------------------
def test_plaud_import_hashes_exact_bytes_in_a_linked_addendum_and_never_touches_the_parent(tmp_path, monkeypatch):
    from agent_foundry import plaud_import as pi
    _stub(monkeypatch)
    parent = mr.run_moddik("t-p", tmp_path, use_graph=False)
    before = open(parent["run_path"], "rb").read()
    audio = tmp_path / "rec_abc123.wav"
    audio.write_bytes(b"RIFF-synthetic-test-bytes" * 50)
    tj = tmp_path / "abc123.json"
    tj.write_text(json.dumps({"id": "abc123", "source_list": [{"t": 0, "text": "x"}]}))
    r = pi.import_into_addendum(parent["run_path"], audio, tmp_path, recording_id="abc123", transcript_json=tj)
    assert open(parent["run_path"], "rb").read() == before  # append-only: the parent log is untouched
    ev = read_run(r["run_path"])
    art = next(e for e in ev if e["event_type"] == "artifact")
    assert art["payload"]["digest"] == "sha256:" + hashlib.sha256(audio.read_bytes()).hexdigest()
    assert art["payload"]["capture"] == "PLAUD_DEVICE" and r["transcript_relationship"] == "SUPPORTED_BY_RECORDED_EVIDENCE"
    assert ev[0]["payload"]["parent_log_sha256"] == hashlib.sha256(before).hexdigest()


def test_plaud_transcript_relationship_is_unknown_without_evidence(tmp_path):
    from agent_foundry import plaud_import as pi
    tj = tmp_path / "t.json"
    tj.write_text(json.dumps({"id": "zzz", "source_list": []}))
    assert pi.load_transcript_json(tj, "abc123", "recording.wav")["relationship_to_recording"] == "UNKNOWN"


def test_parallel_capture_is_never_claimed_as_same_bytes(tmp_path):
    from agent_foundry import plaud_import as pi
    a = tmp_path / "a.wav"
    a.write_bytes(b"aaaa")
    p = pi.audio_artifact_payload(a, capture="PLAUD_DEVICE", parallel_capture_of="cid:sha256:" + "0" * 64)
    assert p["same_bytes"] is False and p["relation"] == "PARALLEL_CAPTURE/SAME_SESSION"


def test_asr_engine_unavailable_is_explicit_not_faked():
    from agent_foundry import asr
    with pytest.raises(asr.EngineUnavailable):
        asr.transcribe("nope.wav")


def test_plaud_import_records_filename_size_hash_time_relation_and_attestation(tmp_path, monkeypatch):
    """SYNTHETIC audio (ffmpeg sine): proves the importer's records, NOT a real PLAUD recording."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not present")
    from agent_foundry import plaud_import as pi
    _stub(monkeypatch)
    parent = mr.run_moddik("t-q", tmp_path, use_graph=False)
    wav = tmp_path / "PLAUD_test_export.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(wav)], capture_output=True, check=True)
    r = pi.import_into_addendum(parent["run_path"], wav, tmp_path, recording_id="rid1", attest_plaud_export=True, session_note="synthetic")
    art = next(e for e in read_run(r["run_path"]) if e["event_type"] == "artifact")["payload"]
    assert art["source_filename"] == "PLAUD_test_export.wav" and art["size_bytes"] == wav.stat().st_size
    assert art["digest"] == "sha256:" + hashlib.sha256(wav.read_bytes()).hexdigest() and art["imported_at"].endswith("Z")
    assert art["media_probe"]["is_media"] is True and art["relation_to_parent_run"].startswith("PARALLEL_CAPTURE/SAME_SESSION")
    assert art["same_bytes_as_local_capture"].startswith("NOT_APPLICABLE") and "PASS_CANDIDATE" in r["status"] and "no MCP/SDK/API" in r["status"]
    un = pi.import_into_addendum(parent["run_path"], wav, tmp_path, attest_plaud_export=False, addendum_id="t-q-plaud-2")
    assert "NOT_ADMITTABLE" in un["status"]  # without operator attestation the lane is never presented as admitted custody
    junk = tmp_path / "notaudio.wav"
    junk.write_bytes(b"not media")
    assert "NOT_ADMITTABLE" in pi.import_into_addendum(parent["run_path"], junk, tmp_path, attest_plaud_export=True, addendum_id="t-q-plaud-3")["status"]
