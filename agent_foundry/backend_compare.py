"""Same frozen Vithia context -> two backends (OpenJEV on magicPRObox, LiquidAI on magicSTUDIObox) -> provider-neutral event streams -> field-level comparison.

Real components used (read-only, pinned): biobitworks/jev-space-invaders @ dbca313
  * evidence: data/daisy/VITHIA_DAISY_ECA_ACTION_CORPUS_V1/rows.jsonl (public, CC-BY-4.0, deterministic and model-free), verified against its own MANIFEST sha256
  * Vithia preprocessing: src/daisy/eca_corpus.arm_context(row, arm)  (arms: A0_RAW is the raw control, A5_VITA01_FULL the full Vithia context)
  * question: src/daisy/openjev_behavior.QUESTION (typed choice LEFT / STAY / RIGHT); leakage guard: src/s01/protocol.FORBIDDEN_KEYS
  * OpenJEV request/response contract: POST /v1/systemone {state, model, questions:{move}} -> answers.move.{choice, probabilities, confidence}
Honesty rules:
  * Both backends answer the SAME typed-choice contract, but neither has a citation channel: "evidence used" is NOT_AVAILABLE for both; only "evidence supplied" is recorded.
  * OpenJEV returns probabilities; the Liquid adapter returns a structured choice only (probabilities NOT_AVAILABLE). That asymmetry is recorded, never filled in.
  * Machine, runtime, quantization and latency are context, not evidence. A model choice is behavior, not ground truth; no quality claim is made without a preregistered evaluation.
  * A backend is labelled OPENJEV only when its result carries the verified runtime record; anything else keeps its own label.
Hashes establish identity, not truth.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .ids import canonical_json

ROOT = Path(__file__).resolve().parent.parent
UP = ROOT / ".local" / "upstream" / "jev-space-invaders"
ACTIONS = ("LEFT", "STAY", "RIGHT")
NC = "NOT_COMPUTED"
NA = "NOT_AVAILABLE"
SCHEMA = "agent-foundry.canonical_context.v1"
PRIMARY_ARM, CONTROL_ARM = "A5_VITA01_FULL", "A0_RAW"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compact(obj) -> bytes:
    """The single serializer for frozen context bytes (sorted keys, compact separators, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def upstream():
    """Import the pinned upstream modules read-only. Returns (modules dict, identity dict)."""
    if not UP.exists():
        raise RuntimeError("upstream checkout missing: git clone https://github.com/biobitworks/jev-space-invaders .local/upstream/jev-space-invaders")
    sys.path.insert(0, str(UP))
    try:
        import importlib
        mods = {"eca": importlib.import_module("src.daisy.eca_corpus"), "beh": importlib.import_module("src.daisy.openjev_behavior"), "proto": importlib.import_module("src.s01.protocol")}
    finally:
        sys.path.remove(str(UP))
    head = subprocess.run(["git", "-C", str(UP), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(UP), "status", "--porcelain", "--", "src", "data/daisy/VITHIA_DAISY_ECA_ACTION_CORPUS_V1"], capture_output=True, text=True).stdout.strip()
    files = {p: sha((UP / p).read_bytes()) for p in ("src/daisy/eca_corpus.py", "src/daisy/openjev_behavior.py", "src/s01/protocol.py")}
    return mods, {"repo": "https://github.com/biobitworks/jev-space-invaders", "commit": head, "worktree_modified": bool(dirty), "files_sha256": files}


def load_corpus_rows():
    p = UP / "data" / "daisy" / "VITHIA_DAISY_ECA_ACTION_CORPUS_V1" / "rows.jsonl"
    man = json.loads((p.parent / "MANIFEST.json").read_text())
    b = p.read_bytes()
    ok = sha(b) == man["files"][0]["sha256"] and len(b) == man["files"][0]["bytes"]
    return [json.loads(l) for l in b.decode().splitlines() if l.strip()], {"file": "data/daisy/VITHIA_DAISY_ECA_ACTION_CORPUS_V1/rows.jsonl", "sha256": sha(b), "bytes": len(b), "manifest_sha256": man["files"][0]["sha256"],
                                                                         "manifest_bytes": man["files"][0]["bytes"], "bytes_match_manifest": ok, "license": man["license"], "dataset_id": man["dataset_id"],
                                                                         "source": man["source"], "code_commit_at_generation": man["code_commit_at_generation"], "claim_ceiling": man["claim_ceiling"]}


def select_row(rows: list):
    """Frozen rule: the first validation-split STATE (file order) whose optimal action set has exactly one member and a positive decision margin."""
    for i, r in enumerate(rows):
        if r["split"] == "validation" and r["action"] == "LEFT" and len(r["optimal_action_set"]) == 1 and r["decision_margin"] > 0:
            return i, r
    raise RuntimeError("no row satisfies the selection rule")


def evidence_items(mods, row: dict) -> list:
    e = mods["eca"]
    return [{"role": "state", "evidence_id": row["state_id"], "content": "ship position x and hazard row on a ring of width W", "field": "state"},
            {"role": "rule_truth_table", "evidence_id": e.rule_atom(row["rule_id"])["rule_hash"], "content": "ECA rule truth table (history)", "field": "history"},
            {"role": "public_anticube", "evidence_id": e.cid(row["public_anticube"]), "content": "public Anticube flags already present in the corpus row", "field": "anticube"},
            {"role": "path_distribution", "evidence_id": e.cid(row["path_distribution"]), "content": "limited-lookahead path distribution (H=2), not DeltaG*", "field": "path_distribution"}]


def build_context(mods, row: dict, arm: str) -> dict:
    """Vithia preprocessing (executed by the upstream function). The package is exactly what the backends see: schema + question + state. No ids, no hashes, no reference labels."""
    state = mods["eca"].arm_context(row, arm, other=None, seed=0)
    leaked = mods["proto"].FORBIDDEN_KEYS & set(json.dumps(state).split('"'))
    if leaked:
        raise ValueError(f"decision leakage: {sorted(leaked)}")
    return {"schema": SCHEMA, "question": mods["beh"].QUESTION, "state": state}


# ------------------------------------------------------------------ backend request renderings of the SAME frozen bytes
def parse_context(ctx_bytes: bytes) -> dict:
    return json.loads(ctx_bytes.decode("utf-8"))


def openjev_body(ctx_bytes: bytes, model: str = "openjev") -> bytes:
    c = parse_context(ctx_bytes)
    return json.dumps({"state": c["state"], "model": model, "questions": {"move": c["question"]}}).encode()


LIQUID_SCHEMA = {"type": "object", "properties": {"choice": {"type": "string", "enum": list(ACTIONS)}}, "required": ["choice"], "additionalProperties": False}


def liquid_body(ctx_bytes: bytes, model: str) -> bytes:
    """Mirrors the upstream LiquidOllamaDecider request format (temperature 0, seed 0, num_predict 32, JSON-schema constrained choice) for the ECA question."""
    c = parse_context(ctx_bytes)
    prompt = ("You are the System-1 decider for a cellular-automaton dodge game. Choose exactly one legal action. Return only the required JSON object.\nQUESTION=" +
              json.dumps(c["question"], sort_keys=True, separators=(",", ":")) + "\nSTATE=" + json.dumps(c["state"], sort_keys=True, separators=(",", ":")))
    return json.dumps({"model": model, "prompt": prompt, "stream": False, "format": LIQUID_SCHEMA, "options": {"temperature": 0, "seed": 0, "num_predict": 32}}, sort_keys=True, separators=(",", ":")).encode()


# ------------------------------------------------------------------ arm result normalization (behavior fields only)
def normalize(arm: dict) -> dict:
    """arm: an arm-result JSON (from the OpenJEV runner, the Liquid runner, or a fixture). Preserves failures and malformed outputs."""
    r = arm.get("response") or {}
    err = arm.get("error")
    if err or not arm.get("executed", False):
        return {"format_valid": False, "format_error": err or "not executed", "choice": NC, "probabilities": NC, "confidence": NC, "fallback": True, "fallback_reason": err or "not executed"}
    if arm["backend"]["family"] == "openjev":
        ans = (r.get("answers") or {}).get("move") or {}
        choice = ans.get("choice")
        ok = choice in ACTIONS
        return {"format_valid": ok, "format_error": None if ok else "choice_not_in_action_set", "choice": choice if ok else NC, "probabilities": ans.get("probabilities", NA), "confidence": ans.get("confidence", NA),
                "fallback": not ok, "fallback_reason": None if ok else "choice_not_in_action_set", "tokens": {"input": (r.get("usage") or {}).get("input_tokens"), "output": (r.get("usage") or {}).get("output_tokens")}}
    try:
        ans = json.loads(r.get("response") or "{}")
    except (ValueError, TypeError):
        ans = {}
    choice = ans.get("choice") if isinstance(ans, dict) else None
    ok = choice in ACTIONS
    return {"format_valid": ok, "format_error": None if ok else "choice_not_in_action_set", "choice": choice if ok else NC, "probabilities": NA, "confidence": NA, "fallback": not ok,
            "fallback_reason": None if ok else "choice_not_in_action_set", "tokens": {"input": r.get("prompt_eval_count"), "output": r.get("eval_count")}}


FIELD_ORDER = [("format_valid", "VerifierEvent"), ("choice", "DecisionEvent"), ("probabilities", "ModelEvent"), ("confidence", "ModelEvent"), ("fallback", "VerifierEvent")]
EXPECTED_BACKEND_DIFFERENCES = ["backend/provider/model identity", "machine and runtime (context, not evidence)", "quantization / weight file", "request encoding (typed /v1/systemone vs Ollama JSON-schema generate)", "latency and token counts"]


def compare_behavior(a: dict, b: dict) -> dict:
    rows, first = [], None
    for f, ev in FIELD_ORDER:
        va, vb = a.get(f), b.get(f)
        if isinstance(va, str) and va.startswith(("NOT_", "NOT_COMPUTED")) or isinstance(vb, str) and vb.startswith(("NOT_", "NOT_COMPUTED")):
            status = "NOT_AVAILABLE_ON_AT_LEAST_ONE_ARM"
        else:
            status = "SAME" if va == vb else "DIFFERENT"
            if status == "DIFFERENT" and first is None:
                first = {"event": ev, "field": f, "arm_a": va, "arm_b": vb}
        rows.append({"field": f, "event": ev, "arm_a": va, "arm_b": vb, "status": status})
    return {"rows": rows, "first_behavioral_divergence": first or "NONE_IN_COMPARABLE_FIELDS", "expected_backend_differences": EXPECTED_BACKEND_DIFFERENCES,
            "evidence_used_arm_a": NA + " (typed choice; no citation channel)", "evidence_used_arm_b": NA + " (typed choice; no citation channel)"}
