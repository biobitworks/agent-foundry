"""Agent Foundry run for an external-dataset admission (RUN_TYPE=EXTERNAL_DATASET_REPLAY). No model inference: the acceptance criterion is provenance traversal.

Mapping (existing event schema): each FCO -> an `evidence` event (source_ref + content_digest are the FCO pointer and identity); declared FCG dependencies -> event deps;
canonical trace and Neo4j trace -> `tool` events; their comparison -> an `evaluation` event. Payloads reference FCO content hashes (stable), occurrence ids live in deps/meta.
"""
from datetime import datetime, timedelta, timezone

from . import dataset_fco as dfco
from . import dataset_graph as dg
from .recorder import RunRecorder, read_run

SYSTEM = {"kind": "system", "name": "agent-foundry-dataset-intake"}
TOOL = {"kind": "tool", "name": "fco-fcg-trace", "provider_kind": "deterministic"}
ORDER = ["SourcePageSnapshot", "LicenseDeclaration", "DatasetSource", "DatasetFile"]  # dependencies first
TASK_ID = "external-dataset-provenance-trace"
QUESTION = "Trace the declared dataset file back to the authoritative dataset source."


def _ts(ts0: str, k: int) -> str:
    return (datetime.fromisoformat(ts0.replace("Z", "+00:00")) + timedelta(seconds=k)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_admission(fcos: dict, edges: list, out_dir, run_id: str, ts0: str, drv=None, admission_id: str = None) -> dict:
    rec = RunRecorder(run_id, out_dir)
    start = rec.record("run_started", SYSTEM, {"task_id": TASK_ID, "run_type": "EXTERNAL_DATASET_REPLAY", "question": QUESTION, "level": "METADATA_LEVEL (raw dataset bytes ACCESS_BLOCKED)",
                                               "limits": ["FCG edges declare relationships; they do not prove causality", "hashes establish identity, not truth",
                                                          "hosting on IEEE DataPort does not prove any scientific claim about the dataset"]},
                       meta={"config": {"admission_id": admission_id, "graph": drv is not None}, "label": "CONTROL_RUN"}, ts=_ts(ts0, 0))
    by_type = {f["object_type"]: f for f in fcos.values()}
    ev_of = {}
    dep_src = {}
    for e in edges:  # declared dependency: an object's event depends on the events of the objects it is derived from / part of / licensed under
        dep_src.setdefault(e["src_content_hash"], []).append(e["dst_content_hash"])
    for k, t in enumerate(ORDER, start=1):
        f = by_type[t]
        need = dep_src.get(f["content_hash"], [])
        assert all(d in ev_of for d in need), "dependency order violated"
        deps = [ev_of[d]["event_id"] for d in need] or [start["event_id"]]
        b = f["body"]
        ev_of[f["content_hash"]] = rec.record("evidence", SYSTEM, {
            "source_ref": b.get("source_url") or f"fco:{f['content_hash']}", "content_digest": f["content_hash"], "fco_content_hash": f["content_hash"], "fco_object_id": f["object_id"],
            "fco_object_type": t, "custody_state": b.get("custody_state", "METADATA_ONLY"), "raw_bytes_state": b.get("raw_bytes_state", "NOT_COMPUTED"),
            "claim_ceiling": f["claim_ceiling"], "source": "EXTERNAL_DATASET_METADATA"}, state="OBSERVED", deps=deps, ts=_ts(ts0, k))
    start_hash = by_type["DatasetFile"]["content_hash"]
    canon = dfco.trace(fcos, edges, start_hash)
    t1 = rec.record("tool", TOOL, {"tool": "fco.trace", "arguments": {"start_content_hash": start_hash, "follow": ["part_of", "derived_from"], "source": "canonical fco/objects + fcg/edges"},
                                   "ok": True, "chain": canon["chain"], "chain_types": canon["chain_types"], "rels": [h["rel"] for h in canon["hops"]], "source_url": canon["source_url"]},
                    state="EXECUTED", deps=[ev_of[h]["event_id"] for h in canon["chain"]], ts=_ts(ts0, 5))
    graph_res, verdict, deps_eval = None, "NOT_COMPUTED (Neo4j unavailable; canonical trace only)", [t1["event_id"]]
    if drv is not None:
        counts = dg.project(drv, admission_id, fcos, edges, read_run(rec.path))
        g = dg.trace(drv, admission_id, start_hash)
        graph_res = g["paths"][0] if g["paths"] else None
        t2 = rec.record("tool", TOOL, {"tool": "neo4j.trace", "arguments": {"start_content_hash": start_hash, "admission_id": "$ADMISSION"}, "ok": bool(graph_res), "cypher": g["cypher"],
                                       "chain": graph_res and graph_res["chain"], "chain_types": graph_res and graph_res["types"], "rels": graph_res and graph_res["rels"], "source_url": graph_res and graph_res["source_url"]},
                        state="EXECUTED" if graph_res else "FAILED", deps=[t1["event_id"]], meta={"bound_params": {"$ADMISSION": admission_id}, "projection_counts": counts}, ts=_ts(ts0, 6))
        deps_eval.append(t2["event_id"])
        same = bool(graph_res) and graph_res["chain"] == canon["chain"] and graph_res["source_url"] == canon["source_url"] and [r.lower() for r in graph_res["rels"]] == [h["rel"] for h in canon["hops"]]
        verdict = "PASS" if same else "FAIL"
    rec.record("evaluation", TOOL, {"metric": "canonical_vs_neo4j_lineage_equal", "result": verdict, "expected": canon["chain"], "observed": graph_res and graph_res["chain"], "note": "equality of two descriptions of the same lineage; not evidence of causality"},
               state="EXECUTED" if verdict == "PASS" else ("NOT_COMPUTED" if verdict.startswith("NOT_COMPUTED") else "FAILED"), deps=deps_eval, ts=_ts(ts0, 7))
    rec.record("run_completed", SYSTEM, {"status": "completed", "authoritative_source_url": canon["source_url"], "chain_types": canon["chain_types"]}, state="EXECUTED", deps=[rec.last_id], ts=_ts(ts0, 8))
    events = read_run(rec.path)
    final_counts = dg.project(drv, admission_id, fcos, edges, events) if drv is not None else None
    return {"run_path": str(rec.path), "events": events, "canonical_trace": canon, "neo4j_trace_path": graph_res, "projection_counts": final_counts, "verdict": verdict}
