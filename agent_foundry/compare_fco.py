"""FCO/FCG objects and provider-neutral event streams for the same-context / two-backend comparison.

FCO objects use the pinned fco_minimum_schema (v1.3.0) and FCG ontology names (derived_from, compared_with). Edges declare relationships; they never assert causality.
"""
import hashlib
import json
from datetime import datetime, timedelta

from . import backend_compare as bc
from . import dataset_fco as dfco
from .recorder import RunRecorder, read_run

SYSTEM = {"kind": "system", "name": "agent-foundry-context-compare"}
CEILING = ("behavioral comparison of two backends on one frozen context; a model choice is behavior, not ground truth; no quality claim without a preregistered evaluation; "
           "G*/DeltaG* are NOT_COMPUTED and are not used")
NOT_COMPUTED_FIELDS = ["G_star", "delta_G_star", "H_norm", "S_star", "P(Gamma)", "Anticube EPISTEMIC_STATE (not defined in recovered artifacts)", "Anticube DISPOSITION (needs known SELFNESS and SAFETY)",
                       "Merkle root over the context (not computed for this object)", "any quality/accuracy score (no preregistered evaluation)"]


def _ts(ts0: str, k: int) -> str:
    return (datetime.fromisoformat(ts0.replace("Z", "+00:00")) + timedelta(seconds=k)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_freeze(mods, up_id: dict, rows_info: dict, row_index: int, row: dict, contexts: dict, created_at: str, run_id: str, sw_hash: str):
    """contexts: {'primary': (arm, bytes), 'control': (arm, bytes)}. Returns (fcos, edges, manifest)."""
    mk = lambda t, body, **kw: dfco.build_fco(t, body, created_at=created_at, run_id=run_id, actor_id="agent-foundry-context-freeze", software_hash=sw_hash, claim_ceiling=CEILING, **kw)
    ds = mk("SourceDatasetFile", {"dataset_id": rows_info["dataset_id"], "file": rows_info["file"], "sha256": rows_info["sha256"], "byte_length": rows_info["bytes"], "license": rows_info["license"],
                                  "manifest_sha256_matches": rows_info["bytes_match_manifest"], "source": rows_info["source"], "claim_ceiling_of_source": rows_info["claim_ceiling"],
                                  "upstream_commit": up_id["commit"], "bytes_in_git": False, "custody_state": "LOCAL_BYTES_VERIFIED_AGAINST_SOURCE_MANIFEST", "raw_bytes_state": "PRESENT_LOCALLY_OUTSIDE_GIT"},
            content_hash="sha256:" + rows_info["sha256"], canonicalization_method="sha256 over the exact rows.jsonl bytes", source_or_derivative="source")
    items = bc.evidence_items(mods, row)
    es = mk("EvidenceSetFCO", {"run_id": run_id, "task": "choose LEFT / STAY / RIGHT for one ECA dodge state", "question": mods["beh"].QUESTION, "ordered_evidence": items,
                               "source_datasets": [{"dataset_id": rows_info["dataset_id"], "sha256": rows_info["sha256"], "row_index": row_index, "state_id": row["state_id"], "split": row["split"], "rule_id": row["rule_id"]}],
                               "selection_rule": "first validation-split STATE (file order) whose optimal action set has exactly one member and a positive decision margin; reference labels are NOT given to any model",
                               "retrieval": "FROZEN ONCE before any model ran; no backend retrieves independently", "custody_state": "FROZEN_BEFORE_MODEL_EXECUTION", "raw_bytes_state": "PRESENT_LOCALLY_OUTSIDE_GIT"},
            source_or_derivative="derivative", parent_hashes=[ds["content_hash"]])
    fcos = {ds["content_hash"]: ds, es["content_hash"]: es}
    edges = [dfco.build_edge("derived_from", es["content_hash"], ds["content_hash"], basis="evidence items are fields of this corpus row", relationship_status="OBSERVED_DETERMINISTIC_EXTRACTION", created_at=created_at, run_id=run_id)]
    man = {"schema": "agent-foundry.context_freeze_manifest.v1", "frozen_at": created_at, "upstream": up_id, "dataset": rows_info, "row_index": row_index, "state_id": row["state_id"], "contexts": {}}
    for label, (arm, b) in contexts.items():
        ck = mk("CanonicalContextFCO", {"context_file": f"demo/recorded/context_compare/eca_v01/context_{label}.json", "byte_count": len(b), "sha256": bc.sha(b), "context_text_utf8": b.decode("utf-8"),
                                        "arm": arm, "arm_role": "PRIMARY (full Vithia context)" if label == "primary" else "RAW CONTROL (not Vithia-processed)", "ordered_evidence_ids": [i["evidence_id"] for i in items] if arm != bc.CONTROL_ARM else [items[0]["evidence_id"]],
                                        "question": mods["beh"].QUESTION,
                                        "vithia": {"function": "src.daisy.eca_corpus.arm_context(row, arm, other=None, seed=0)", "arm": arm, "upstream": up_id, "executed": "ONCE (frozen before any model call)",
                                                   "leakage_guard": "src.s01.protocol.FORBIDDEN_KEYS ∩ context keys = ∅ (executed)"},
                                        "preprocessing_parameters": {"arm": arm, "seed": 0, "W": 16, "H_oracle": 8, "H_a4": 2, "serializer": "sorted keys, compact separators, UTF-8, ensure_ascii=False"},
                                        "bounded_history_included": "rule truth table only (step 0; corpus history_atoms = NOT_APPLICABLE (t=0))" if arm != bc.CONTROL_ARM else "none",
                                        "anticube_fields_available": row["public_anticube"] if arm not in (bc.CONTROL_ARM, "A1_VITACONTEXT") else "not included in this arm",
                                        "not_computed": NOT_COMPUTED_FIELDS + [f"corpus fields G_star={row['G_star']}, delta_G_star={row['delta_G_star']}, H_norm={row['H_norm']}"],
                                        "custody_state": "FROZEN_BEFORE_MODEL_EXECUTION", "raw_bytes_state": "PRESENT"},
                source_or_derivative="derivative", parent_hashes=[es["content_hash"]], content_hash="sha256:" + bc.sha(b), canonicalization_method="sha256 over the exact frozen context bytes")
        fcos[ck["content_hash"]] = ck
        edges.append(dfco.build_edge("derived_from", ck["content_hash"], es["content_hash"], basis="Vithia preprocessing of this evidence set", relationship_status="OBSERVED_DETERMINISTIC_COMPUTATION", created_at=created_at, run_id=run_id))
        man["contexts"][label] = {"arm": arm, "file": f"context_{label}.json", "byte_count": len(b), "sha256": bc.sha(b), "content_id": "sha256:" + bc.sha(b), "fco_content_hash": ck["content_hash"]}
    return fcos, edges, man


def run_prep(fcos: dict, edges: list, man: dict, out_dir, run_id: str, ts0: str, mods, up_id: dict, row: dict):
    rec = RunRecorder(run_id, out_dir)
    start = rec.record("run_started", SYSTEM, {"task_id": "eca-context-freeze", "run_type": "CANONICAL_CONTEXT_FREEZE", "question": "Freeze one canonical Vithia context before any backend runs",
                                               "limits": ["hashes establish identity, not truth", "no model has executed at this point"]}, meta={"config": {"topology": "magicPRObox: EvidenceSet -> Vithia -> CanonicalContextFCO"}, "label": "CONTROL_RUN"}, ts=_ts(ts0, 0))
    by_type = {}
    for h, f in fcos.items():
        by_type.setdefault(f["object_type"], []).append(f)
    ev = {}
    for k, f in enumerate([*by_type["SourceDatasetFile"], *by_type["EvidenceSetFCO"]], start=1):
        deps = [ev[p]["event_id"] for p in f["parent_hashes"] if p in ev] or [start["event_id"]]
        ev[f["content_hash"]] = rec.record("evidence", SYSTEM, {"source_ref": f["body"].get("file") or f"fco:{f['content_hash']}", "content_digest": f["content_hash"], "fco_content_hash": f["content_hash"],
                                                              "fco_object_type": f["object_type"], "custody_state": f["body"]["custody_state"], "raw_bytes_state": f["body"].get("raw_bytes_state"), "source": "EXTERNAL_DATASET_EVIDENCE"},
                                          state="OBSERVED", deps=deps, ts=_ts(ts0, k))
    es_ev = ev[by_type["EvidenceSetFCO"][0]["content_hash"]]
    pre = []
    for label, c in man["contexts"].items():
        pre.append(rec.record("tool", SYSTEM, {"tool": "vithia.arm_context", "arguments": {"arm": c["arm"], "seed": 0, "state_id": man["state_id"]}, "ok": True, "arm": c["arm"], "output_sha256": c["sha256"],
                                               "output_byte_count": c["byte_count"], "upstream_commit": up_id["commit"], "normalized_kind": "VithiaPreprocessEvent", "executed_once": True},
                              state="EXECUTED", deps=[es_ev["event_id"]], ts=_ts(ts0, 10 + len(pre))))
    for label, c in man["contexts"].items():
        ck = fcos[c["fco_content_hash"]]
        rec.record("artifact", SYSTEM, {"artifact_type": "canonical_context", "ref": ck["body"]["context_file"], "digest": c["content_id"], "byte_count": c["byte_count"], "fco_content_hash": ck["content_hash"],
                                        "normalized_kind": "CanonicalContextFrozen", "label": label, "arm": c["arm"]}, state="OBSERVED", deps=[p["event_id"] for p in pre], ts=_ts(ts0, 20 + list(man["contexts"]).index(label)))
    rec.record("run_completed", SYSTEM, {"status": "completed", "contexts_frozen": {k: v["sha256"] for k, v in man["contexts"].items()}}, state="EXECUTED", deps=[rec.last_id], ts=_ts(ts0, 30))
    return read_run(rec.path)


# ------------------------------------------------------------------ arm stream (provider-neutral normalized events)
def arm_stream(arm: dict, ctx_bytes: bytes, ctx_fco: dict, out_dir, run_id: str, ts0: str, question_obj: dict) -> list:
    """arm: arm-result JSON. Events are backend-neutral in payload; backend/machine identity lives in actor/meta."""
    beh = bc.normalize(arm)
    cid = "sha256:" + bc.sha(ctx_bytes)
    b = arm["backend"]
    rec = RunRecorder(run_id, out_dir)
    meta_machine = {"host": arm["host"], "runtime": b.get("runtime"), "backend_label": b["label"], "model": b.get("model"), "model_identity": b.get("model_identity"), "started_utc": arm.get("start_utc"), "ended_utc": arm.get("end_utc"),
                    "latency_ms": arm.get("latency_ms"), "arm_result_sha256": arm.get("_file_sha256"), "topology": arm.get("topology")}
    start = rec.record("run_started", SYSTEM, {"task_id": "eca-context-arm", "run_type": "BACKEND_ARM", "question": "Choose LEFT / STAY / RIGHT for the frozen context"},
                       meta={"config": {"backend": b["label"], "host": arm["host"]}, "label": "CONTROL_RUN" if b["family"] == "openjev" else "VARIANT_RUN"}, ts=_ts(ts0, 0))
    q = rec.record("evidence", SYSTEM, {"source_ref": "question:move", "content_digest": "sha256:" + bc.sha(bc.compact(question_obj)), "excerpt": question_obj["instructions"], "normalized_kind": "QuestionEvent",
                                        "criteria": list(question_obj["criteria"])}, state="OBSERVED", deps=[start["event_id"]], ts=_ts(ts0, 1))
    c = rec.record("artifact", SYSTEM, {"artifact_type": "canonical_context", "ref": ctx_fco["body"]["context_file"], "digest": cid, "byte_count": len(ctx_bytes), "context_content_id": cid,
                                        "context_sha256_seen_by_arm": arm["context_sha256_seen"], "context_bytes_seen_by_arm": arm["context_byte_count_seen"], "ordered_evidence_ids": ctx_fco["body"]["ordered_evidence_ids"],
                                        "normalized_kind": "ContextEvent"}, state="OBSERVED", deps=[q["event_id"]], meta={"machine": meta_machine}, ts=_ts(ts0, 2))
    s = rec.record("agent", SYSTEM, {"agent_id": "backend-arm", "role": "model_start", "action": "model_start", "normalized_kind": "ModelStartEvent", "context_content_id": cid,
                                     "generation_bounds": "temperature 0; deterministic decoding where the backend supports it", "tools_available": "none", "run_policy": "single call, no retries beyond the backend adapter's own"},
                   state="EXECUTED", deps=[c["event_id"]], ts=_ts(ts0, 3))
    actor = {"kind": "model", "name": b["label"], "provider": b["provider"], "model": b.get("model") or b["label"], "provider_kind": b.get("provider_kind", "real")}
    if arm.get("error") or not arm.get("executed"):
        f = rec.record("failure", actor, {"where": "model_call", "error_type": (arm.get("error_type") or "ArmNotExecuted"), "message": arm.get("error") or "arm not executed", "recoverable": True, "normalized_kind": "FailureEvent"},
                       deps=[s["event_id"]], meta={"machine": meta_machine}, ts=_ts(ts0, 4))
        rec.record("abstention", SYSTEM, {"reason": "no decision: " + (arm.get("error") or "not executed"), "about": "move choice", "normalized_kind": "AbstentionEvent"}, deps=[f["event_id"]], ts=_ts(ts0, 8))
        rec.record("run_completed", SYSTEM, {"status": "failed"}, state="EXECUTED", deps=[rec.last_id], ts=_ts(ts0, 9))
        return read_run(rec.path)
    m = rec.record("model", actor, {"request": {"contract": arm["request_contract"], "request_sha256": arm["request_sha256"]}, "response": {"raw": arm["response"]}, "params": arm.get("params", {}), "normalized_kind": "ModelEvent"},
                   deps=[s["event_id"]], meta={"machine": meta_machine, "tokens": beh.get("tokens")}, ts=_ts(ts0, 4))
    eu = rec.record("evaluation", SYSTEM, {"metric": "evidence_use", "result": "NOT_AVAILABLE", "supplied_evidence_ids": ctx_fco["body"]["ordered_evidence_ids"], "used_evidence_ids": bc.NA,
                                           "note": "typed choice has no citation channel; only supplied ids are recorded", "normalized_kind": "EvidenceUseEvent"}, state="NOT_COMPUTED", deps=[m["event_id"]], ts=_ts(ts0, 5))
    v = rec.record("evaluation", SYSTEM, {"metric": "format_validity", "result": "PASS" if beh["format_valid"] else "FAIL", "checks": {"choice_in_action_set": beh["format_valid"], "fallback": beh["fallback"]}, "findings": [beh["format_error"]] if beh["format_error"] else [],
                                          "normalized_kind": "VerifierEvent"}, state="EXECUTED" if beh["format_valid"] else "FAILED", deps=[m["event_id"]], ts=_ts(ts0, 6))
    if beh["format_valid"]:
        rec.record("decision", SYSTEM, {"decision": beh["choice"], "choice": beh["choice"], "probabilities": beh["probabilities"], "confidence": beh["confidence"], "normalized_kind": "DecisionEvent"}, state="PROPOSED",
                   deps=[m["event_id"], v["event_id"], eu["event_id"]], ts=_ts(ts0, 7))
    else:
        rec.record("abstention", actor, {"reason": beh["format_error"] or "invalid output", "about": "move choice", "normalized_kind": "AbstentionEvent"}, deps=[v["event_id"]], ts=_ts(ts0, 7))
    rec.record("run_completed", SYSTEM, {"status": "completed"}, state="EXECUTED", deps=[rec.last_id], ts=_ts(ts0, 9))
    return read_run(rec.path)
