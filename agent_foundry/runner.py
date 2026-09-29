"""Canonical task runner. Emits provider-neutral events; never hides failures or abstentions."""
import hashlib

from providers import ProviderError, get_provider

from .recorder import RunRecorder

SYS = {"kind": "system", "name": "agent-foundry-runner"}
AGENT = {"kind": "agent", "name": "support-agent"}
TOOL = {"kind": "tool", "name": "lookup_policy"}


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def run_task(task: dict, config: dict, run_id: str, out_dir, label=None, variable=None) -> RunRecorder:
    rec = RunRecorder(run_id, out_dir)
    # config/label/variable are the controlled INPUT: recorded in non-hashed meta so they never register as a behavioral divergence
    start = rec.record("run_started", SYS, {"task_id": task["task_id"]}, meta={"config": config, **({"label": label} if label else {}), **({"variable": variable} if variable else {})})
    plan = rec.record("agent", AGENT, {"agent_id": "support-agent", "role": "answerer", "action": "plan: retrieve policy then answer"}, deps=[start["event_id"]])
    doc = task["corpus"].get(config.get("evidence"))
    if doc is None:
        tool = rec.record("tool", TOOL, {"tool": task["tool"], "arguments": {"query": task["query"]}, "ok": False}, deps=[plan["event_id"]])
        ab = rec.record("abstention", AGENT, {"reason": "policy lookup returned no document", "about": "refund eligibility"}, deps=[tool["event_id"]])
        rec.record("run_completed", SYS, {"status": "abstained"}, state="EXECUTED", deps=[ab["event_id"]])
        return rec
    tool = rec.record("tool", TOOL, {"tool": task["tool"], "arguments": {"query": task["query"]}, "ok": True}, deps=[plan["event_id"]])
    ev = rec.record("evidence", TOOL, {"source_ref": f"{doc['doc_id']}@{doc['version']}", "content_digest": _digest(doc["text"]), "excerpt": doc["text"]}, deps=[tool["event_id"]])

    return answer(rec, task, config, ev, doc["text"])


def answer(rec: RunRecorder, task: dict, config: dict, ev: dict, evidence_text: str) -> RunRecorder:
    """Everything after evidence retrieval. Used by run_task and by checkpoint resume (replay)."""
    provider = get_provider(config)
    actor = {"kind": "model", "name": provider.model, "provider": provider.name, "model": provider.model, "provider_kind": provider.provider_kind}
    request = {"prompt": task["prompt"], "evidence": [{"text": evidence_text}]}
    if task.get("instruction"):  # tasks with a constrained output format; absent for the refund task so its hashes are unchanged
        request["instruction"] = task["instruction"]
    claim_id, about = task.get("claim_id", "refund-eligibility"), task.get("about", "refund eligibility")
    try:
        out = provider.complete(request)
    except ProviderError as e:
        fail = rec.record("failure", actor, {"where": "model_call", "error_type": e.error_type, "message": str(e), "recoverable": e.recoverable}, deps=[ev["event_id"]])
        rec.record("run_completed", SYS, {"status": "failed"}, state="EXECUTED", deps=[fail["event_id"]])
        return rec
    model = rec.record("model", actor, {"request": request, "response": {"text": out["text"]}, "params": {"temperature": 0}}, deps=[ev["event_id"]], meta=out.get("meta"))
    if out.get("meta", {}).get("abstained") or out["text"].strip().upper().startswith("ABSTAIN"):
        ab = rec.record("abstention", actor, {"reason": out["text"], "about": about}, deps=[model["event_id"]])
        rec.record("run_completed", SYS, {"status": "abstained"}, state="EXECUTED", deps=[ab["event_id"]])
        return rec
    if task.get("output_validator"):
        from .validators import VALIDATORS
        err = VALIDATORS[task["output_validator"]](out["text"])
        if err:
            fail = rec.record("failure", actor, {"where": "output_validation", "error_type": "InvalidOutput", "message": err, "recoverable": False}, deps=[model["event_id"]])
            rec.record("run_completed", SYS, {"status": "failed"}, state="EXECUTED", deps=[fail["event_id"]])
            return rec
    claim = rec.record("claim", AGENT, {"claim_id": claim_id, "text": out["text"]}, state="OBSERVED", deps=[model["event_id"], ev["event_id"]])
    rec.record("run_completed", SYS, {"status": "completed"}, state="EXECUTED", deps=[claim["event_id"]])
    return rec


def run_pair(task: dict, control_cfg: dict, variant_cfg: dict, out_dir, tag="pair"):
    """EXE-02: the two configs must differ in EXACTLY ONE declared variable."""
    keys = set(control_cfg) | set(variant_cfg)
    diff = sorted(k for k in keys if control_cfg.get(k) != variant_cfg.get(k))
    # provider and model are one variable: changing the provider necessarily changes the model name
    if not diff:
        variable = "none"  # replicate pair: the null control that demonstrates DIVERGENCE=NULL when behavior is stable
    else:
        variable = "provider_model" if diff and set(diff) <= {"provider", "model"} and "provider" in diff else (diff[0] if len(diff) == 1 else None)
    if variable is None:
        raise ValueError(f"run pair must differ in exactly one variable, differs in {diff}")
    a = run_task(task, control_cfg, f"{tag}-control", out_dir, "CONTROL_RUN", variable)
    b = run_task(task, variant_cfg, f"{tag}-variant", out_dir, "VARIANT_RUN", variable)
    return a, b, variable
