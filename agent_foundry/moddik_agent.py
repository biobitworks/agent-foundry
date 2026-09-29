"""Bounded local-model step for the Moddik demo: prompt construction, model call, output contract, deterministic verifier.

The model sees ONLY: the operator transcript, aliased evidence lines (latest sensor state + retrieved history) and a deterministic
policy-check result. Full prompt text is recorded in the model event, so "evidence consumed" is auditable: present in the prompt,
cited in the output, and resolved by the verifier. The verifier is deterministic code, not a model.
"""
import json
import re
import time
import urllib.error
import urllib.request

from . import moddik_sim as sim

MODELS = {
    "lfm2p6b": "hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M",
    "lfm1p2b": "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M",
}
# Liquid model card recommended generation parameters for LFM2.5 (temperature 0.1, top_k 50, repetition_penalty 1.1); seed pinned.
OPTIONS = {"temperature": 0.1, "top_k": 50, "repeat_penalty": 1.1, "seed": 1}
RECOMMENDATIONS = ("MEDIUM_EXCHANGE_RECOMMENDED", "NO_INTERVENTION", "ABSTAIN")
CAUSAL = re.compile(r"\b(because|caused?|causing|due to|leads? to|led to|results? in|resulting|therefore|as a result|driven by|owing to)\b", re.I)
CONTRACT = ("contract=json-after-think-v1: take the text after the last </think> if present, else the whole reply; strip whitespace; "
            "it must parse as ONE JSON object exactly (no markdown fence, no repair, no lenient extraction)")


def evidence_lines(items: list) -> list:
    """items: [{alias, sensor, value, unit, sim_time_s}] -> prompt lines."""
    return [f"{i['alias']} {i['sensor']} = {i['value']} {i['unit']} (t={i['sim_time_s']}s)" for i in items]


def build_prompt(transcript: str, items: list, policy_check: dict) -> str:
    pc = policy_check
    return (
        "You monitor a SIMULATED cell-culture plate. Use ONLY the numbered evidence below; do not use outside knowledge.\n"
        f'Operator question: "{transcript}"\n'
        "Evidence:\n" + "\n".join(evidence_lines(items)) + "\n"
        f"P1 policy_check (deterministic tool) = nutrient_below_{pc['nutrient_below']}:{pc['nutrient_is_below']} "
        f"waste_above_{pc['waste_above']}:{pc['waste_is_above']} criteria_met:{pc['criteria_met']}\n"
        "Policy (illustrative, not calibrated): the recommendation is MEDIUM_EXCHANGE_RECOMMENDED only when criteria_met is True, otherwise NO_INTERVENTION.\n"
        "Answer with ONE JSON object and nothing else, with exactly these keys: "
        "recommendation (MEDIUM_EXCHANGE_RECOMMENDED, NO_INTERVENTION or ABSTAIN), confidence (high, medium or low), "
        "evidence (array of the evidence ids you relied on, chosen from the list above, including P1), "
        "values (object with the latest nutrient and waste numbers), "
        "rationale (one short sentence stating only what the numbers show, no causes)."
    )


def call_model(tag: str, prompt: str, num_predict: int, host: str = "http://127.0.0.1:11434", timeout: int = 900) -> dict:
    body = json.dumps({"model": tag, "prompt": prompt, "stream": False, "options": {**OPTIONS, "num_predict": num_predict}}).encode()
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(host.rstrip("/") + "/api/generate", body, {"Content-Type": "application/json"}), timeout=timeout) as r:
            out = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return {"ok": False, "error_type": type(e).__name__, "message": str(e), "latency_ms": int((time.time() - t0) * 1000)}
    return {"ok": True, "text": out.get("response", ""), "done_reason": out.get("done_reason"), "eval_count": out.get("eval_count"), "latency_ms": int((time.time() - t0) * 1000)}


def extract(raw: str):
    """Returns (obj|None, error|None) under CONTRACT. Reasoning before the last </think> is kept in the recorded raw text, not parsed."""
    text = raw.rsplit("</think>", 1)[-1].strip()
    if text.startswith("```"):
        return None, "output wrapped in a markdown fence (not accepted; no repair)"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"not valid JSON after the think block: {e.msg}"
    return (obj, None) if isinstance(obj, dict) else (None, "JSON is not an object")


def verify(obj: dict, alias_map: dict, policy_check: dict) -> dict:
    """Deterministic checks of the model output against what it was actually given. Returns {PASS, checks, findings, evidence_event_ids}."""
    findings, checks = [], {}
    checks["keys_exact"] = set(obj) == {"recommendation", "confidence", "evidence", "values", "rationale"}
    if not checks["keys_exact"]:
        findings.append(f"unexpected key set: {sorted(obj)}")
    rec = obj.get("recommendation")
    checks["recommendation_valid"] = rec in RECOMMENDATIONS
    checks["confidence_valid"] = obj.get("confidence") in ("high", "medium", "low")
    cited = obj.get("evidence") if isinstance(obj.get("evidence"), list) else []
    checks["evidence_is_nonempty_list"] = bool(cited) and all(isinstance(x, str) for x in cited)
    unknown = [c for c in cited if c not in alias_map]
    checks["all_cited_ids_were_in_prompt"] = not unknown
    if unknown:
        findings.append(f"cited ids not present in the prompt: {unknown}")
    checks["cites_policy_check"] = "P1" in cited
    sensors_cited = {alias_map[c]["sensor"] for c in cited if c in alias_map}
    checks["cites_nutrient_and_waste_evidence"] = {"nutrient", "waste"} <= sensors_cited
    vals = obj.get("values") if isinstance(obj.get("values"), dict) else {}
    latest = {k: v for k, v in policy_check["latest_values"].items()}
    checks["values_match_latest_evidence"] = all(isinstance(vals.get(k), (int, float)) and abs(vals[k] - latest[k]) < 1e-9 for k in ("nutrient", "waste"))
    if not checks["values_match_latest_evidence"]:
        findings.append(f"values {vals} do not match latest evidence {latest}")
    expected = "MEDIUM_EXCHANGE_RECOMMENDED" if policy_check["criteria_met"] else "NO_INTERVENTION"
    checks["recommendation_consistent_with_policy_check"] = rec in (expected, "ABSTAIN")
    if not checks["recommendation_consistent_with_policy_check"]:
        findings.append(f"recommendation {rec} contradicts the deterministic policy check (expected {expected})")
    rat = obj.get("rationale") if isinstance(obj.get("rationale"), str) else ""
    checks["rationale_present"] = bool(rat.strip())
    checks["no_causal_language"] = not CAUSAL.search(rat)
    if not checks["no_causal_language"]:
        findings.append("rationale contains causal wording")
    return {"PASS": all(checks.values()), "checks": checks, "findings": findings,
            "evidence_content_ids": [alias_map[c]["content_id"] for c in cited if c in alias_map]}


def policy_check(latest: dict) -> dict:
    n, w = latest["nutrient"], latest["waste"]
    return {"policy_id": sim.POLICY["id"], "status": sim.POLICY["status"], "nutrient_below": sim.POLICY["nutrient_below"], "waste_above": sim.POLICY["waste_above"],
            "nutrient_is_below": n < sim.POLICY["nutrient_below"], "waste_is_above": w > sim.POLICY["waste_above"], "criteria_met": sim.policy_met(n, w),
            "latest_values": {"nutrient": n, "waste": w}}
