#!/usr/bin/env python3
"""LiquidAI arm for the same-frozen-context comparison. STDLIB ONLY: runnable on magicSTUDIObox with no repo dependencies.

  python3 scripts/studio_liquid_arm.py --context demo/recorded/context_compare/eca_v01/context_primary.json \
      --sha256 <PRO_CONTEXT_SHA256> --bytes <PRO_CONTEXT_BYTE_COUNT> --host magicSTUDIObox \
      --endpoint http://127.0.0.1:11437 --model liquid-vithia-1.2b:latest --label LIQUIDAI_STUDIO --out liquid_studio_arm.json

Order of operations (fail-closed): 1) recompute byte count and sha256 of the EXACT file and compare with the values from magicPRObox; on mismatch STOP (nothing is sent to a model);
2) build the request from the parsed frozen bytes; 3) call the local Ollama endpoint; 4) write the arm result. It never runs Vithia, never regenerates or reorders the context,
never reads credentials, and refuses non-loopback endpoints.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

ACTIONS = ("LEFT", "STAY", "RIGHT")
LIQUID_SCHEMA = {"type": "object", "properties": {"choice": {"type": "string", "enum": list(ACTIONS)}}, "required": ["choice"], "additionalProperties": False}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def liquid_body(ctx_bytes: bytes, model: str) -> bytes:  # must stay byte-identical to agent_foundry.backend_compare.liquid_body (a test enforces this)
    c = json.loads(ctx_bytes.decode("utf-8"))
    prompt = ("You are the System-1 decider for a cellular-automaton dodge game. Choose exactly one legal action. Return only the required JSON object.\nQUESTION=" +
              json.dumps(c["question"], sort_keys=True, separators=(",", ":")) + "\nSTATE=" + json.dumps(c["state"], sort_keys=True, separators=(",", ":")))
    return json.dumps({"model": model, "prompt": prompt, "stream": False, "format": LIQUID_SCHEMA, "options": {"temperature": 0, "seed": 0, "num_predict": 32}}, sort_keys=True, separators=(",", ":")).encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--bytes", type=int, required=True)
    ap.add_argument("--host", default=platform.node())
    ap.add_argument("--endpoint", default="http://127.0.0.1:11437")
    ap.add_argument("--model", default="liquid-vithia-1.2b:latest")
    ap.add_argument("--label", default="LIQUIDAI")
    ap.add_argument("--model-identity", default="")
    ap.add_argument("--topology", default="LiquidAI on magicSTUDIObox against the exact frozen bytes transferred via GitHub")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.context, "rb").read()
    seen_sha, seen_n = hashlib.sha256(raw).hexdigest(), len(raw)
    match = seen_sha == a.sha256 and seen_n == a.bytes
    print(json.dumps({"STUDIO_CONTEXT_BYTE_COUNT": seen_n, "STUDIO_CONTEXT_SHA256": seen_sha, "PRO_CONTEXT_BYTE_COUNT": a.bytes, "PRO_CONTEXT_SHA256": a.sha256, "CONTEXT_IDENTITY_MATCH": "PASS" if match else "FAIL"}, indent=1))
    if not match:
        sys.exit("STOP: CONTEXT_IDENTITY_MATCH=FAIL; the comparison must not proceed as if the inputs were equivalent")
    if urlparse(a.endpoint).hostname not in ("127.0.0.1", "localhost", "::1"):
        sys.exit("STOP: non-loopback endpoint refused")
    body = liquid_body(raw, a.model)
    res = {"schema": "agent-foundry.arm_result.v1", "host": a.host, "topology": a.topology, "which": "primary" if "primary" in a.context else ("control" if "control" in a.context else "unknown"),
           "backend": {"family": "liquid", "label": a.label, "provider": "ollama", "provider_kind": "real", "model": a.model, "model_identity": a.model_identity or "NOT_RECORDED", "runtime": "Ollama (loopback)",
                       "note": "LiquidAI; Vithia was NOT re-run on this machine"},
           "context_file": a.context, "context_sha256_seen": seen_sha, "context_byte_count_seen": seen_n, "expected_sha256": a.sha256, "expected_byte_count": a.bytes, "context_identity_match": "PASS",
           "request_contract": "Ollama /api/generate, JSON-schema constrained {choice}", "request_sha256": hashlib.sha256(body).hexdigest(), "request_body_len": len(body),
           "params": {"temperature": 0, "seed": 0, "num_predict": 32}, "platform": platform.platform(), "python": sys.version.split()[0], "start_utc": now(), "executed": False}
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(a.endpoint.rstrip("/") + "/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=600) as r:
            res["response"] = json.loads(r.read())
        res["executed"] = True
    except Exception as e:  # recorded, never hidden
        res["error"], res["error_type"] = f"{type(e).__name__}: {e}", type(e).__name__
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["end_utc"] = now()
    open(a.out, "w").write(json.dumps(res, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"executed": res["executed"], "latency_ms": res["latency_ms"], "out": a.out, "choice": (json.loads(res["response"].get("response") or "{}").get("choice") if res["executed"] else None)}, indent=1))


if __name__ == "__main__":
    main()
