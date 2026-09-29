"""PathDivergenceFCO objects, FCG edges, the Agent Foundry diagnosis run, and the Neo4j projection helpers.

Uses the existing FCO schema (fco_minimum_schema v1.3.0, pinned) and FCG ontology names (derived_from, compared_with). Nothing here asserts causality; the perturbation is
a RECORDED controlled intervention (declared by design), not a discovered cause. Neo4j is a rebuildable projection.
"""
import hashlib
import json
from datetime import datetime, timedelta

from . import dataset_fco as dfco
from . import dataset_graph as dg
from . import path_divergence as pd
from .recorder import RunRecorder, read_run

ACTOR = "agent-foundry-path-divergence"
CEILING = ("diagnostic localization on a deterministic SIMULATED replay pair; not a causal-mechanism claim; G*/DeltaG*/S*/Anticube explanation is NOT_COMPUTED; "
           "the simulator has no state dynamics (readings are scripted functions of tick), so endpoint agreement after a perturbation is a property of the script")
SYSTEM = {"kind": "system", "name": "agent-foundry-path-divergence"}
TOOL = {"kind": "tool", "name": "path-divergence-analysis", "provider_kind": "deterministic"}
UNSUPPORTED = ["EPISTEMIC_STATE (no definition in recovered artifacts)", "DISPOSITION (needs known SELFNESS and SAFETY)", "G_star (no probabilistic comparison frame)", "DeltaG_star (G* undefined)",
               "DELTA_GRAPH_STRUCTURE / DELTA_REPLAY / DELTA_CUSTODY / DELTA_PREDICTION / DELTA_INFORMATION / DELTA_COMPLEXITY (no frozen definitions)", "S_star (terms undefined, weights not preregistered)",
               "P(Gamma) (PROPOSED only)", "direction_error_aggregate and magnitude_error_aggregate across mixed units (no preregistered scaling)", "first_anticube_divergence (all Anticube states UNKNOWN)",
               "first_delta_g_star_divergence"]


def _status(h: dict) -> dict:
    a = h["classification"]["vector_metrics"]
    return {"endpoint_error": "COMPUTED (per component in native units; single-unit L2 over changed components where applicable)", "direction_error": "COMPUTED_PER_COMPONENT; aggregate NOT_COMPUTED",
            "magnitude_error": "COMPUTED_PER_COMPONENT; aggregate NOT_COMPUTED", "first_fcg_divergence": "COMPUTED (identity-based diff over declared dependencies; not DELTA_GRAPH_STRUCTURE)",
            "first_anticube_divergence": str(h["anticube"]["first_anticube_divergence"]), "first_delta_g_star_divergence": "NOT_COMPUTED", "S_star": "NOT_COMPUTED", "path_weighting": "PROPOSED",
            "first_divergence_event_id": "COMPUTED (reproduced 3 independent ways)"}


def _diagnosis(name: str, h: dict, diag: dict) -> dict:
    lab = h["classification"]["labels"]
    rep = diag["reproduction"]
    f = rep["first_divergent_leaf"]
    yes = [k for k, v in lab.items() if v["value"] is True and k != "FCG_STATE_ENDPOINT_DIFFERS"]
    if name.startswith("T1"):
        text = (f"{' + '.join(yes)} localized to component '{f['sensor']}' at first divergent evidence event index {rep['prefix_identical_events']} (tick {f['tick']}): nominal {f['nominal_value']} vs perturbed "
                f"{f['perturbed_value']}. The divergence matches the RECORDED controlled perturbation {rep['perturbation_from_recorded_config']} (intervention known by design, not discovered). "
                "No G*/DeltaG*/Anticube explanation is computable.")
    else:
        text = (f"PATH_WRONG with observation-endpoint agreement: start and end observation vectors coincide, the intermediate state at tick {f['tick']} differs in '{f['sensor']}' "
                f"({f['nominal_value']} vs {f['perturbed_value']}); the FCG-state endpoints still differ because downstream workflow events differ (action {diag['fcg']['action_divergence']['nominal']} vs "
                f"{diag['fcg']['action_divergence']['perturbed'].split(' (')[0]}). The simulator has no state dynamics, so endpoint agreement is a property of the script. No G*/DeltaG*/Anticube explanation is computable.")
    return {"primary": "+".join(yes) if yes else "NO_MISMATCH_IN_OBSERVATION_VECTOR", "labels": {k: v["value"] for k, v in lab.items()}, "text": text}


def build_objects(diag: dict, recorded_rel: str, created_at: str, run_id: str, sw_hash: str = None):
    mk = lambda t, body, **kw: dfco.build_fco(t, body, created_at=created_at, run_id=run_id, actor_id=ACTOR, software_hash=sw_hash, claim_ceiling=CEILING, **kw)
    runlogs = {}
    for role, key in (("nominal", "control"), ("perturbed", "variant")):
        path = f"{recorded_rel}/{key}.jsonl"
        ev = diag["control_events"] if key == "control" else diag["variant_events"]
        runlogs[role] = mk("RunLog", {"path": path, "role": role, "run_id_of_log": ev[0]["run_id"], "byte_length": len((dfco.ROOT / path).read_bytes()), "source": "SIMULATED (local Moddik simulation)",
                                      "custody_state": "COMMITTED_IN_GIT", "raw_bytes_state": "PRESENT"},
                           content_hash="sha256:" + diag["run_sha256"][key], canonicalization_method="sha256 over the exact committed run-log bytes", source_or_derivative="source")
    states = {}
    ctx = {}
    for role, chain in diag["chains"].items():
        for st in chain:
            ctx.setdefault(st["state_id"], []).append({"run_role": st["context"]["run_role"], "run_id": st["context"]["run_id"], "source_run_sha256": st["context"]["source_run_sha256"],
                                                       "last_event_id": st["context"]["last_event_id"], "evidence_event_ids": st["context"]["evidence_event_ids"]})
            states.setdefault(st["state_id"], st)
    state_fcos = {}
    for sid, st in states.items():
        f = mk("EndpointState", st["identity"], source_or_derivative="derivative", parent_hashes=sorted({runlogs["nominal" if c["run_role"].startswith("predicted") else "perturbed"]["content_hash"] for c in ctx[sid]}))
        assert "state:" + f["content_hash"] == sid
        f["context"] = {"occurrences": ctx[sid], "note": "context (run occurrences) is outside the content identity; a state shared by both runs has one identity and two occurrences"}
        state_fcos[sid] = f
    edges = []
    E = lambda rel, s, d, basis, st: edges.append(dfco.build_edge(rel, s, d, basis=basis, relationship_status=st, created_at=created_at, run_id=run_id))
    for sid, f in state_fcos.items():
        for c in ctx[sid]:
            E("derived_from", f["content_hash"], runlogs["nominal" if c["run_role"].startswith("predicted") else "perturbed"]["content_hash"], "state computed from the committed run log at the stated tick", "OBSERVED_DETERMINISTIC_COMPUTATION")
    pdfs = {}
    ev_ids = lambda: [diag["reproduction"]["control_event_id"], diag["reproduction"]["variant_event_id"]]
    dec = next((e["event_id"] for e in diag["control_events"] if e["event_type"] == "decision"), None)
    abst = next((e["event_id"] for e in diag["variant_events"] if e["event_type"] == "abstention"), None)
    for name, h in diag["horizons"].items():
        cv = h["classification"]["vector_metrics"]
        body = {"diagnostic_name": "PathDivergenceFCO", "program": pd.PROGRAM, "not_hydra_delta_g_star": True, "is_thermodynamic_gibbs_free_energy": False, "horizon": name,
                "role_assignment": diag["role_assignment"], "start_state_id": diag["x0_state_id"], "predicted_end_state_id": h["predicted_chain"][-1], "observed_end_state_id": h["observed_chain"][-1],
                "predicted_path": h["predicted_chain"], "observed_path": h["observed_chain"], "predicted_path_id": h["predicted_path_id"], "observed_path_id": h["observed_path_id"],
                "first_divergence_event_id": {"index": diag["reproduction"]["prefix_identical_events"], "nominal_occurrence": diag["reproduction"]["control_event_id"], "perturbed_occurrence": diag["reproduction"]["variant_event_id"],
                                              "reproduced_by": ["compare_runs", "raw_content_id_scan", "resimulation_from_seed"], "all_agree": diag["reproduction"]["all_agree"]},
                "net_vector_predicted": cv["net_vector_predicted"], "net_vector_observed": cv["net_vector_observed"],
                "endpoint_error": {"per_component": cv["endpoint_error_per_component"], "aggregate": cv["endpoint_error_aggregate"]},
                "direction_error": {"per_component": cv["direction_error_per_component"], "aggregate": cv["direction_error_aggregate"]},
                "magnitude_error": {"per_component": cv["magnitude_error_per_component"], "aggregate": cv["magnitude_error_aggregate"]},
                "classification": {k: v for k, v in h["classification"]["labels"].items()}, "path_step_deviation": h["path_step_deviation"],
                "first_anticube_divergence": h["anticube"]["first_anticube_divergence"], "anticube_comparison_executed": h["anticube"]["executed"], "first_delta_g_star_divergence": h["first_delta_g_star_divergence"],
                "g_star_tracking": {"predicted": h["g_star_predicted"], "observed": h["g_star_observed"]}, "S_star": {"predicted": h["S_star_predicted"], "observed": h["S_star_observed"]},
                "path_weighting": diag["path_weighting"], "first_fcg_divergence": diag["fcg"]["first_fcg_divergence"], "fcg": {k: v for k, v in diag["fcg"].items() if k != "first_fcg_divergence"},
                "diagnosis": _diagnosis(name, h, diag), "diagnosis_primary": _diagnosis(name, h, diag)["primary"],
                "evidence_ids": [*ev_ids(), *([dec] if dec else []), *([abst] if abst else [])], "computation_status": _status(h), "unsupported_fields": UNSUPPORTED,
                "custody_state": "COMPUTED_FROM_COMMITTED_RUN_LOGS", "raw_bytes_state": "NOT_APPLICABLE"}
        f = mk("PathDivergenceFCO", body, source_or_derivative="derivative", parent_hashes=[state_fcos[s]["content_hash"] for s in dict.fromkeys(h["predicted_chain"] + h["observed_chain"])])
        pdfs[name] = f
        for s in dict.fromkeys(h["predicted_chain"] + h["observed_chain"]):
            E("derived_from", f["content_hash"], state_fcos[s]["content_hash"], "diagnostic computed over this state", "OBSERVED_DETERMINISTIC_COMPUTATION")
    # comparison of the divergent intermediate states (T1 endpoint pair) is always recorded
    t1 = diag["horizons"]["T1_one_step"]
    E("compared_with", state_fcos[t1["predicted_chain"][-1]]["content_hash"], state_fcos[t1["observed_chain"][-1]]["content_hash"], "predicted (nominal) vs observed (perturbed) end state; roles declared by this analysis", "DECLARED_ROLE_ASSIGNMENT")
    t2 = diag["horizons"]["T2_two_endpoint_path"]
    E("compared_with", state_fcos[t2["predicted_chain"][-1]]["content_hash"], state_fcos[t2["observed_chain"][-1]]["content_hash"], "predicted (nominal) vs observed (perturbed) end state; roles declared by this analysis", "DECLARED_ROLE_ASSIGNMENT")
    uniq, seen = [], set()
    for e in edges:
        if e["edge_id"] not in seen:
            seen.add(e["edge_id"])
            uniq.append(e)
    fcos = {f["content_hash"]: f for f in [*runlogs.values(), *state_fcos.values(), *pdfs.values()]}
    return fcos, uniq


def _ts(ts0, k):
    return (datetime.fromisoformat(ts0.replace("Z", "+00:00")) + timedelta(seconds=k)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_diagnosis(fcos: dict, edges: list, diag: dict, out_dir, run_id: str, ts0: str, drv=None, admission_id: str = None) -> dict:
    rec = RunRecorder(run_id, out_dir)
    start = rec.record("run_started", SYSTEM, {"task_id": "two-endpoint-path-divergence", "run_type": "PATH_DIVERGENCE_DIAGNOSIS", "question": "Why was this state-transition vector wrong?", "program": pd.PROGRAM,
                                               "limits": ["G*/DeltaG* are not thermodynamic Gibbs free energy; this is not Hydra DeltaG*", "FCG edges declare relationships; they do not prove causality",
                                                          "nominal=predicted / perturbed=observed is a declared role assignment", "G*, DeltaG*, S*, P(Gamma) and Anticube explanation are NOT_COMPUTED"]},
                       meta={"config": {"admission_id": admission_id, "graph": drv is not None}, "label": "CONTROL_RUN"}, ts=_ts(ts0, 0))
    order = [h for h, f in fcos.items() if f["object_type"] == "RunLog"] + [h for h, f in fcos.items() if f["object_type"] == "EndpointState"] + [h for h, f in fcos.items() if f["object_type"] == "PathDivergenceFCO"]
    need = {}
    for e in edges:
        if e["rel"] == "derived_from":
            need.setdefault(e["src_content_hash"], []).append(e["dst_content_hash"])
    ev_of = {}
    for k, h in enumerate(order, start=1):
        f = fcos[h]
        deps = [ev_of[d]["event_id"] for d in need.get(h, [])] or [start["event_id"]]
        ev_of[h] = rec.record("evidence", SYSTEM, {"source_ref": f["body"].get("path") or f"fco:{h}", "content_digest": h, "fco_content_hash": h, "fco_object_id": f["object_id"], "fco_object_type": f["object_type"],
                                                   "custody_state": f["body"].get("custody_state", "COMPUTED_FROM_COMMITTED_RUN_LOGS"), "raw_bytes_state": f["body"].get("raw_bytes_state", "NOT_APPLICABLE"),
                                                   "claim_ceiling": f["claim_ceiling"], "source": "SIMULATED_RUN_PAIR_DIAGNOSTIC"}, state="OBSERVED", deps=deps, ts=_ts(ts0, k))
    rep = diag["reproduction"]
    t1 = rec.record("tool", TOOL, {"tool": "reproduce_first_divergence", "arguments": {"pair": "control/variant recorded run logs"}, "ok": rep["all_agree"], "compare_runs_index": rep["compare_runs_index"],
                                   "raw_scan_index": rep["raw_scan_index"], "resimulation_index": rep["resimulation_index"], "first_divergent_leaf": rep["first_divergent_leaf"],
                                   "recorded_leaves_equal_regenerated_simulation": rep["recorded_leaves_equal_regenerated_simulation"]},
                    state="EXECUTED" if rep["all_agree"] else "FAILED", deps=[ev_of[h]["event_id"] for h in order if fcos[h]["object_type"] == "RunLog"], ts=_ts(ts0, 20))
    pdf_hashes = [h for h in order if fcos[h]["object_type"] == "PathDivergenceFCO"]
    canon = {h: sorted(dfco.closure(edges, h)) for h in pdf_hashes}
    t2 = rec.record("tool", TOOL, {"tool": "fco.lineage_closure", "arguments": {"starts": pdf_hashes, "follow": ["derived_from"], "source": "canonical fco/objects/path_divergence + fcg/edges/path_divergence"}, "ok": True,
                                   "closure_sizes": {h: len(c) for h, c in canon.items()}, "reaches_run_log_bytes": all(any(fcos[x]["object_type"] == "RunLog" for x in c) for c in canon.values())},
                    state="EXECUTED", deps=[ev_of[h]["event_id"] for h in pdf_hashes], ts=_ts(ts0, 21))
    verdict, deps_eval = "NOT_COMPUTED (Neo4j unavailable)", [t2["event_id"]]
    if drv is not None:
        dg.project(drv, admission_id, fcos, edges, read_run(rec.path))
        got = {h: sorted(r["h"] for r in dg.base.query(drv, "MATCH (s:FCO {content_hash:$h, admission_id:$a})-[:DERIVED_FROM*1..4]->(t:FCO {admission_id:$a}) RETURN DISTINCT t.content_hash AS h", h=h, a=admission_id)) for h in pdf_hashes}
        t3 = rec.record("tool", TOOL, {"tool": "neo4j.lineage_closure", "arguments": {"starts": pdf_hashes, "admission_id": "$ADMISSION"}, "ok": got == canon, "closure_sizes": {h: len(c) for h, c in got.items()}},
                        state="EXECUTED" if got == canon else "FAILED", deps=[t2["event_id"]], meta={"bound_params": {"$ADMISSION": admission_id}}, ts=_ts(ts0, 22))
        deps_eval.append(t3["event_id"])
        verdict = "PASS" if got == canon else "FAIL"
    rec.record("evaluation", TOOL, {"metric": "canonical_vs_neo4j_lineage_closure_equal", "result": verdict, "note": "equality of two descriptions of the same lineage; not evidence of causality"},
               state="EXECUTED" if verdict == "PASS" else ("NOT_COMPUTED" if verdict.startswith("NOT_COMPUTED") else "FAILED"), deps=deps_eval, ts=_ts(ts0, 23))
    rec.record("run_completed", SYSTEM, {"status": "completed", "diagnosis_T1": fcos[pdf_hashes[0]]["body"]["diagnosis_primary"], "diagnosis_T2": fcos[pdf_hashes[-1]]["body"]["diagnosis_primary"]}, state="EXECUTED", deps=[rec.last_id], ts=_ts(ts0, 24))
    events = read_run(rec.path)
    counts = dg.project(drv, admission_id, fcos, edges, events) if drv is not None else None
    return {"run_path": str(rec.path), "events": events, "verdict": verdict, "projection_counts": counts}
