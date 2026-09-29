"""Builds one Moddik demonstration run through the existing Agent Foundry RunRecorder (no new event format).

Mapping: sensor reading -> evidence; hardware breakpoint -> checkpoint; transcript -> evidence; audio -> artifact;
graph query / policy check -> tool; local model -> model; verifier -> evaluation; simulated recommendation -> decision (PROPOSED, never actuated).
The simulator timestamps are SIMULATION TIME (epoch 2000-01-01T00:00:00Z + sim_time_s), not wall-clock, so a replay is byte-identical.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import moddik_agent as agent
from . import moddik_graph as graph
from . import moddik_sim as sim
from .ids import canonical_json
from .merkle import build_commitment, fco_reference_cross_check
from .recorder import RunRecorder, read_run

SIM_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)
SIMULATOR = {"kind": "system", "name": "moddik-simulator", "provider_kind": "deterministic"}
SYSTEM = {"kind": "system", "name": "agent-foundry-moddik-runner"}
OPERATOR = {"kind": "human", "name": "operator"}
ORCH_TOOL = {"kind": "tool", "name": "moddik-orchestrator", "provider_kind": "deterministic"}
VERIFIER = {"kind": "tool", "name": "moddik-output-verifier", "provider_kind": "deterministic"}
TASK_ID = "moddik-sim-intervention-review"
NOMINAL_BREAKPOINT_TICK = 4
DEFAULT_TRANSCRIPT = "What changed, and does this culture need intervention?"


def sim_ts(sim_time_s: int) -> str:
    return (SIM_EPOCH + timedelta(seconds=sim_time_s)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


ENVELOPE = ("source_ref", "content_digest")  # existing evidence-schema required fields; NOT part of the Merkle leaf


def leaf_of(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in ENVELOPE}


def sensor_payload(leaf: dict) -> dict:
    return {**leaf, "source_ref": f"moddik-sim:{leaf['hardware_id']}/{leaf['sensor']}@tick{leaf['tick']}",
            "content_digest": "sha256:" + hashlib.sha256(canonical_json(leaf).encode("utf-8")).hexdigest()}


def _breakpoint(rec: RunRecorder, tick: int, leaf_events: list, parent: dict, label: str, records_event: dict = None) -> dict:
    records_content_id = records_event["content_id"] if records_event else None
    """Commit to the ORDERED current-state leaves and record the checkpoint with the full verification receipt."""
    leaves = [leaf_of(e["payload"]) for e in leaf_events]
    receipt = build_commitment(leaves, fco_reference_cross_check())
    ok = receipt["verification"]["PASS"]
    # every leaf must be byte-identical to the canonical payload of the event it claims to commit to
    binding = all(canonical_json(leaf_of(e["payload"])) == r["canonical_bytes_utf8"] for e, r in zip(leaf_events, receipt["leaves"])) if receipt.get("leaves") else False
    ok = ok and binding
    bid = f"HB:{label}:tick{tick}"  # run-independent so identical replays have identical content
    payload = {"checkpoint_id": bid, "breakpoint_id": bid, "label": label, "tick": tick, "sim_time_s": tick * sim.TICK_SECONDS, "hardware_id": sim.HARDWARE_ID, "source": "SIMULATED",
               "leaf_content_ids": [e["content_id"] for e in leaf_events], "parent_breakpoint_root": parent.get("root") if parent else None,
               "leaf_event_binding_verified": binding, "records_content_id": records_content_id, "commitment": {k: receipt[k] for k in ("schema", "construction", "leaf_count", "leaves") if k in receipt},
               "MERKLE_ROOT": receipt["MERKLE_ROOT"] if ok else "NOT_COMPUTED", "verification": receipt["verification"],
               "claim": "integrity/identity over the declared ordered leaves only; not a statement about physical truth"}
    ev = rec.record("checkpoint", SYSTEM, payload, state="EXECUTED" if ok else "NOT_COMPUTED", deps=[e["event_id"] for e in leaf_events] + ([records_event["event_id"]] if records_event else []), ts=sim_ts(tick * sim.TICK_SECONDS))
    return {"event": ev, "root": payload["MERKLE_ROOT"], "tick": tick}


def _emit_tick(rec, tick, start_id, seed, perturb):
    evs = []
    for leaf in sim.tick_readings(tick, seed, perturb):
        evs.append(rec.record("evidence", SIMULATOR, sensor_payload(leaf), state="OBSERVED", deps=[start_id], ts=sim_ts(leaf["sim_time_s"])))
    return evs


def _alias_items(rows: list, alias_map: dict, counter: list, canon_by_id: dict) -> list:
    items = []
    for r in rows:
        alias = f"S{counter[0]}"
        counter[0] += 1
        item = {"alias": alias, "sensor": r["sensor"], "value": r["value"], "unit": r["unit"], "sim_time_s": r["sim_time_s"]}
        alias_map[alias] = {**item, "content_id": canon_by_id[r["event_id"]]["content_id"]}
        items.append(item)
    return items


def _canonical_lookup(events: list) -> dict:
    return {e["event_id"]: e for e in events}


def run_moddik(run_id: str, out_dir, *, transcript: str = DEFAULT_TRANSCRIPT, transcript_source: str = "OPERATOR_TEXT_INPUT", transcript_meta: dict = None,
               model_key: str = "lfm2p6b", num_predict: int = 3500, perturb: dict = None, seed: str = sim.SEED, use_graph: bool = True,
               ollama_host: str = "http://127.0.0.1:11434", audio_events: list = None, label: str = None) -> dict:
    """Execute the scenario. Returns {run_path, events, summary}. Nothing here actuates anything."""
    rec = RunRecorder(run_id, out_dir)
    cfg = {"seed": seed, "perturb": {f"{k[0]}@{k[1]}": v for k, v in (perturb or {}).items()}, "model_key": model_key, "num_predict": num_predict, "use_graph": use_graph,
           "transcript_source": transcript_source}
    start = rec.record("run_started", SYSTEM, {"task_id": TASK_ID, "scenario": "moddik-local-simulation", "source": "SIMULATED", "hardware_id": sim.HARDWARE_ID,
                                               "ticks": sim.TICKS, "tick_seconds": sim.TICK_SECONDS, "policy": sim.POLICY,
                                               "limits": ["LOCAL SIMULATION; no Moddik hardware contacted; no sensor physically tested", "thresholds and trajectories are ILLUSTRATIVE scenario parameters",
                                                          "a Merkle root proves integrity over declared leaves, not physical truth", "a graph edge does not prove causality"]},
                       meta={"config": cfg, **({"label": label} if label else {}), **({"variable": "sensor_value"} if perturb else {})}, ts=sim_ts(0))
    sid = start["event_id"]
    last_state, breakpoints, last_bp = {}, [], None
    # 1. nominal + rising-stress stream up to the decision tick, with a nominal breakpoint
    for tick in range(sim.DECISION_TICK + 1):
        evs = _emit_tick(rec, tick, sid, seed, perturb)
        last_state = evs
        if tick == NOMINAL_BREAKPOINT_TICK:
            last_bp = _breakpoint(rec, tick, evs, None, "nominal")
            breakpoints.append(last_bp)
    hb_decision = _breakpoint(rec, sim.DECISION_TICK, last_state, last_bp, "decision-state")
    breakpoints.append(hb_decision)
    # 2. operator question (transcript evidence); audio artifact events are attached if supplied
    t_ts = sim_ts(sim.DECISION_TICK * sim.TICK_SECONDS + 5)
    audio_ids = []
    for a in (audio_events or []):
        audio_ids.append(rec.record("artifact", a["actor"], a["payload"], state="OBSERVED", deps=[sid], ts=t_ts)["event_id"])
    tr = rec.record("evidence", OPERATOR, {"source_ref": f"operator-transcript:{transcript_source}", "content_digest": "sha256:" + hashlib.sha256(transcript.encode("utf-8")).hexdigest(), "excerpt": transcript, "text": transcript, "transcript_source": transcript_source, "language": "en", **(transcript_meta or {}), "source": "OPERATOR_INPUT"},
                    state="OBSERVED", deps=[sid, *audio_ids], ts=t_ts)
    # 3. graph projection of what has happened so far, then bounded queries
    drv, graph_status = None, {"backend": "canonical_jsonl_fallback", "reason": "graph disabled"}
    if use_graph:
        try:
            drv = graph.connect()
            graph.clear_run(drv, run_id)
            counts = graph.project_run(drv, read_run(rec.path), rec.path)
            graph_status = {"backend": "neo4j", "projection": counts}
        except Exception as e:  # recorded, never hidden
            drv, graph_status = None, {"backend": "canonical_jsonl_fallback", "reason": f"neo4j unavailable: {type(e).__name__}"}
    proj = rec.record("tool", ORCH_TOOL, {"tool": "neo4j.project_run", "arguments": {"run_id": "$RUN"}, "ok": drv is not None, "backend": graph_status["backend"],
                                          "note": "projection is rebuildable; canonical evidence is this run log; counts and log hash are in meta"},
                      state="EXECUTED" if drv is not None else "FAILED", deps=[hb_decision["event"]["event_id"], tr["event_id"]], meta={"bound_params": {"$RUN": run_id}, "projection": graph_status.get("projection"), "reason": graph_status.get("reason")}, ts=sim_ts(sim.DECISION_TICK * sim.TICK_SECONDS + 6))
    canon = _canonical_lookup(read_run(rec.path))
    canon_leaf = {eid: e for eid, e in canon.items() if e["payload"].get("schema") == sim.LEAF_SCHEMA}

    def q(name, cypher, params, fallback_rows):
        if drv is not None:
            rows = graph.query(drv, cypher, **params)
        else:
            rows = fallback_rows()
        ok_canon = all(r["event_id"] in canon_leaf and canon_leaf[r["event_id"]]["payload"]["value"] == r["value"] for r in rows)  # projection is never trusted blindly
        ev = rec.record("tool", ORCH_TOOL, {"tool": name, "backend": "neo4j" if drv is not None else "canonical_jsonl_fallback", "cypher": cypher if drv is not None else None, "arguments": {**params, "run": "$RUN"},
                                            "ok": ok_canon, "row_count": len(rows), "result_content_ids": [canon[r["event_id"]]["content_id"] for r in rows if r["event_id"] in canon], "rows_match_canonical_run_log": ok_canon},
                        state="EXECUTED" if ok_canon else "FAILED", deps=[proj["event_id"]] + [r["event_id"] for r in rows if r["event_id"] in canon], meta={"bound_params": {"$RUN": run_id}, "result_event_ids": [r["event_id"] for r in rows]},
                        ts=sim_ts(sim.DECISION_TICK * sim.TICK_SECONDS + 7))
        return rows, ev

    def latest_fb():
        out = {}
        for e in canon_leaf.values():
            p = e["payload"]
            if p["tick"] <= sim.DECISION_TICK and p["sensor"] != "actuator_state" and (p["sensor"] not in out or p["tick"] > out[p["sensor"]]["tick"]):
                out[p["sensor"]] = {"event_id": e["event_id"], **{k: p[k] for k in ("sensor", "value", "unit", "tick", "sim_time_s", "source")}}
        return sorted(out.values(), key=lambda r: sim.ORDER.index(r["sensor"]))

    def hist_fb():
        return sorted([{"event_id": e["event_id"], **{k: e["payload"][k] for k in ("sensor", "value", "unit", "tick", "sim_time_s", "source")}} for e in canon_leaf.values()
                       if e["payload"]["sensor"] in ("nutrient", "waste") and sim.DECISION_TICK - 3 <= e["payload"]["tick"] < sim.DECISION_TICK],
                      key=lambda r: (r["tick"], sim.ORDER.index(r["sensor"])))

    latest_rows, ev_latest = q("neo4j.latest_sensor_state", graph.CYPHER_LATEST, {"run": run_id, "tick": sim.DECISION_TICK}, latest_fb)
    hist_rows, ev_hist = q("neo4j.nutrient_waste_history", graph.CYPHER_HISTORY, {"run": run_id, "sensors": ["nutrient", "waste"], "t0": sim.DECISION_TICK - 3, "t1": sim.DECISION_TICK - 1}, hist_fb)
    alias_map, counter = {}, [1]
    items = _alias_items(latest_rows, alias_map, counter, canon) + _alias_items(hist_rows, alias_map, counter, canon)
    latest = {r["sensor"]: r["value"] for r in latest_rows}
    pc = agent.policy_check(latest)
    ev_pol = rec.record("tool", ORCH_TOOL, {"tool": "policy_check", "arguments": {"latest_values": pc["latest_values"]}, "ok": True, "policy": sim.POLICY, "result": pc, "note": "deterministic rule evaluation over the retrieved latest values; ILLUSTRATIVE policy"},
                        state="EXECUTED", deps=[ev_latest["event_id"]], ts=sim_ts(sim.DECISION_TICK * sim.TICK_SECONDS + 8))
    alias_map["P1"] = {"alias": "P1", "sensor": "policy_check", "content_id": ev_pol["content_id"]}
    # 4. local Liquid model over ONLY the bounded context
    prompt = agent.build_prompt(transcript, items, pc)
    tag = agent.MODELS[model_key]
    actor = {"kind": "model", "name": tag, "provider": "ollama", "model": tag, "provider_kind": "real"}
    model_deps = [tr["event_id"], ev_latest["event_id"], ev_hist["event_id"], ev_pol["event_id"]]
    out = agent.call_model(tag, prompt, num_predict, ollama_host)
    mts = sim_ts(sim.DECISION_TICK * sim.TICK_SECONDS + 9)
    summary = {"run_id": run_id, "graph": graph_status, "breakpoints": [{"tick": b["tick"], "root": b["root"]} for b in breakpoints], "model": tag}
    if not out["ok"]:
        f = rec.record("failure", actor, {"where": "model_call", "error_type": out["error_type"], "message": out["message"], "recoverable": True}, deps=model_deps, ts=mts)
        rec.record("abstention", SYSTEM, {"reason": "no model output; no simulated action derived", "about": "medium exchange recommendation"}, deps=[f["event_id"]], ts=mts)
        rec.record("run_completed", SYSTEM, {"status": "failed"}, state="EXECUTED", deps=[f["event_id"]], ts=mts)
        summary["status"] = "MODEL_FAILED"
        return {"run_path": str(rec.path), "events": read_run(rec.path), "summary": summary}
    obj, err = agent.extract(out["text"])
    ver = agent.verify(obj, alias_map, pc) if obj is not None else {"PASS": False, "checks": {}, "findings": [err], "evidence_content_ids": []}
    by_cid = {e["content_id"]: e["event_id"] for e in read_run(rec.path)}
    ev_ids = [by_cid[c] for c in ver["evidence_content_ids"]]
    model_ev = rec.record("model", actor, {"request": {"prompt": prompt, "alias_map": alias_map, "policy_check_alias": "P1", "contract": agent.CONTRACT}, "response": {"text": out["text"]},
                                           "params": {**agent.OPTIONS, "num_predict": num_predict}, "done_reason": out["done_reason"],
                                           "verified_evidence_content_ids": ver["evidence_content_ids"] if ver["PASS"] else []},
                          deps=model_deps, meta={"latency_ms": out["latency_ms"], "eval_count": out["eval_count"], "verified_evidence_event_ids": ev_ids if ver["PASS"] else []}, ts=mts)
    v_ev = rec.record("evaluation", VERIFIER, {"metric": "moddik-output-verifier-v1", "result": "PASS" if ver["PASS"] else "FAIL", "PASS": ver["PASS"], "extraction_error": err, "checks": ver["checks"], "findings": ver["findings"],
                                               "evidence_content_ids": ver["evidence_content_ids"], "contract": agent.CONTRACT},
                      state="EXECUTED" if ver["PASS"] else "FAILED", deps=[model_ev["event_id"]], meta={"evidence_event_ids": ev_ids}, ts=mts)
    rec_out = (obj or {}).get("recommendation")
    if ver["PASS"] and rec_out == "MEDIUM_EXCHANGE_RECOMMENDED" and pc["criteria_met"]:
        act = rec.record("decision", agent_actor(), {"decision": "MEDIUM_EXCHANGE_RECOMMENDED", "SIMULATED_ACTION": "MEDIUM_EXCHANGE_RECOMMENDED", "actuation": "NONE (simulation only; no physical actuation)", "model_content_id": model_ev["content_id"],
                                                     "verifier_content_id": v_ev["content_id"], "policy_check_content_id": ev_pol["content_id"], "evidence_content_ids": ver["evidence_content_ids"],
                                                     "hardware_breakpoint_content_id": hb_decision["event"]["content_id"], "hardware_breakpoint_root": hb_decision["root"],
                                                     "model_confidence": obj["confidence"], "relevant_values": obj["values"], "rationale": obj["rationale"]},
                         state="PROPOSED", deps=[model_ev["event_id"], v_ev["event_id"], hb_decision["event"]["event_id"], ev_pol["event_id"]],
                         meta={"evidence_event_ids": ev_ids, "model_event_id": model_ev["event_id"], "verifier_event_id": v_ev["event_id"], "policy_check_event_id": ev_pol["event_id"], "hardware_breakpoint_event_id": hb_decision["event"]["event_id"]}, ts=mts)
        summary["simulated_action"] = "MEDIUM_EXCHANGE_RECOMMENDED"
        summary["status"] = "ACTION_PROPOSED"
        prev_dep = act
    else:
        ab = rec.record("abstention", SYSTEM, {"reason": "no simulated action derived: " + ("; ".join(ver["findings"]) or f"recommendation={rec_out}, criteria_met={pc['criteria_met']}"),
                                               "about": "medium exchange recommendation"}, deps=[v_ev["event_id"]], ts=mts)
        summary["simulated_action"] = "NOT_COMPUTED"
        summary["status"] = "NO_ACTION" if ver["PASS"] else "VERIFIER_FAILED"
        prev_dep = ab
    # 5. sim continues (no actuation); next breakpoint after the decision, chained to the decision-state breakpoint
    post = []
    for leaf in sim.tick_readings(sim.DECISION_TICK + 1, seed, perturb):
        post.append(rec.record("evidence", SIMULATOR, sensor_payload(leaf), state="OBSERVED", deps=[sid], ts=sim_ts(leaf["sim_time_s"])))
    hb_next = _breakpoint(rec, sim.DECISION_TICK + 1, post, hb_decision, "post-decision", records_event=prev_dep)
    breakpoints.append(hb_next)
    rec.record("run_completed", SYSTEM, {"status": "completed", "simulated_action": summary["simulated_action"], "breakpoint_roots": [b["root"] for b in breakpoints]},
               state="EXECUTED", deps=[hb_next["event"]["event_id"]], ts=sim_ts((sim.DECISION_TICK + 1) * sim.TICK_SECONDS + 1))
    events = read_run(rec.path)
    if drv is not None:
        summary["graph"] = {"backend": "neo4j", "projection": graph.project_run(drv, events, rec.path)}
        drv.close()
    summary["breakpoints"] = [{"tick": b["tick"], "root": b["root"]} for b in breakpoints]
    return {"run_path": str(rec.path), "events": events, "summary": summary}


def agent_actor():
    return {"kind": "agent", "name": "moddik-monitor-agent"}
