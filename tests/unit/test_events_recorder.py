import json

import pytest

from agent_foundry.events import validate_event
from agent_foundry.recorder import RunRecorder, read_run

MODEL = {"kind": "model", "name": "m", "provider": "fixture", "model": "fx-1", "provider_kind": "fixture"}
SYS = {"kind": "system", "name": "recorder"}
TOOL = {"kind": "tool", "name": "search"}


def make_run(tmp_path, run_id="run-a", meta=None, answer="42"):
    r = RunRecorder(run_id, tmp_path)
    s = r.record("run_started", SYS, {"task_id": "t1"}, meta={"config": {"model": "fx-1"}, "label": "CONTROL_RUN"})
    t = r.record("tool", TOOL, {"tool": "search", "arguments": {"q": "x"}, "ok": True}, deps=[s["event_id"]], meta=meta)
    ev = r.record("evidence", TOOL, {"source_ref": "doc://1", "content_digest": "abc"}, deps=[t["event_id"]])
    m = r.record("model", MODEL, {"request": {"p": "q"}, "response": {"text": answer}}, deps=[ev["event_id"]])
    r.record("run_completed", SYS, {"status": "completed"}, state="EXECUTED", deps=[m["event_id"]])
    return r


def test_every_event_type_validates_and_roundtrips(tmp_path):
    r = RunRecorder("run-all", tmp_path)
    samples = [
        ("run_started", SYS, {"task_id": "t"}),
        ("agent", {"kind": "agent", "name": "a"}, {"agent_id": "a1", "action": "plan"}),
        ("decision", SYS, {"decision": "use tool"}),
        ("checkpoint", SYS, {"checkpoint_id": "cp1"}),
        ("artifact", SYS, {"artifact_type": "report", "ref": "out.md"}),
        ("claim", SYS, {"claim_id": "c1", "text": "x"}),
        ("evaluation", SYS, {"metric": "match", "result": True}),
        ("run_completed", SYS, {"status": "completed"}),
    ]
    for et, actor, payload in samples:
        r.record(et, actor, payload, state="OBSERVED", meta={"config": {}} if et == "run_started" else None)
    assert len(read_run(r.path)) == len(samples)


def test_content_id_is_stable_across_runs_but_occurrence_differs(tmp_path):
    a = make_run(tmp_path, "run-a")
    b = make_run(tmp_path, "run-b")
    ea, eb = read_run(a.path), read_run(b.path)
    assert [e["content_id"] for e in ea] == [e["content_id"] for e in eb]
    assert all(x["event_id"] != y["event_id"] for x, y in zip(ea, eb))


def test_meta_and_ts_do_not_change_content_id(tmp_path):
    a = make_run(tmp_path, "run-a", meta={"latency_ms": 5})
    b = make_run(tmp_path, "run-b", meta={"latency_ms": 900})
    assert [e["content_id"] for e in read_run(a.path)] == [e["content_id"] for e in read_run(b.path)]


def test_payload_change_changes_content_id(tmp_path):
    a = make_run(tmp_path, "run-a", answer="42")
    b = make_run(tmp_path, "run-b", answer="43")
    ca = [e["content_id"] for e in read_run(a.path)]
    cb = [e["content_id"] for e in read_run(b.path)]
    assert ca[:3] == cb[:3] and ca[3] != cb[3]


def test_failure_and_abstention_are_first_class_and_kept(tmp_path):
    r = RunRecorder("run-f", tmp_path)
    r.record("run_started", SYS, {"task_id": "t"}, meta={"config": {}})
    f = r.record("failure", MODEL, {"where": "model_call", "error_type": "Timeout", "message": "provider timed out", "recoverable": True})
    ab = r.record("abstention", SYS, {"reason": "insufficient evidence", "about": "claim c1"}, deps=[f["event_id"]])
    r.record("run_completed", SYS, {"status": "abstained"}, state="EXECUTED")
    evs = read_run(r.path)
    assert [e["event_type"] for e in evs][1:3] == ["failure", "abstention"]
    assert evs[1]["state"] == "FAILED" and evs[2]["state"] == "NOT_COMPUTED"
    assert ab["deps"] == [f["event_id"]]


def test_failure_with_wrong_state_is_rejected(tmp_path):
    r = RunRecorder("run-x", tmp_path)
    with pytest.raises(ValueError):
        r.record("failure", SYS, {"where": "w", "error_type": "e", "message": "m"}, state="EXECUTED")


def test_model_event_requires_provider_kind(tmp_path):
    r = RunRecorder("run-x", tmp_path)
    with pytest.raises(ValueError):
        r.record("model", {"kind": "model", "name": "m"}, {"request": {}, "response": {}})


def test_unknown_event_type_and_forward_dep_rejected(tmp_path):
    r = RunRecorder("run-x", tmp_path)
    with pytest.raises(ValueError):
        r.record("magic", SYS, {})
    with pytest.raises(ValueError):
        r.record("decision", SYS, {"decision": "d"}, deps=["occ:sha256:" + "0" * 64])
    assert not r.path.exists() or r.path.read_text() == ""  # invalid events never persisted


def test_tamper_is_detected(tmp_path):
    r = make_run(tmp_path)
    lines = r.path.read_text().splitlines()
    ev = json.loads(lines[3])
    ev["payload"]["response"]["text"] = "forged"
    lines[3] = json.dumps(ev)
    r.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="content_id"):
        read_run(r.path)


def test_deleted_event_is_detected(tmp_path):
    r = make_run(tmp_path)
    lines = r.path.read_text().splitlines()
    del lines[2]
    r.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        read_run(r.path)


def test_recorder_refuses_to_overwrite_existing_log(tmp_path):
    make_run(tmp_path, "run-a")
    with pytest.raises(FileExistsError):
        RunRecorder("run-a", tmp_path)


def test_schema_rejects_extra_top_level_field():
    with pytest.raises(ValueError):
        validate_event({"nope": 1})
