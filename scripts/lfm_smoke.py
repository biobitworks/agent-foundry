"""Minimal deterministic smoke test per local model. Usage: python3 scripts/lfm_smoke.py [--host URL] <ollama-tag> ...

A model is READY only if inference executed AND the output parses AND equals the expected JSON exactly.
Downloaded != ready. Results are appended (immutable file per invocation) under provenance/local_models/.
"""
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROMPT = 'Return only JSON:\n{"model_ready":true,"marker":"AGENT_FOUNDRY_LOCAL_TEST"}'
EXPECTED = {"model_ready": True, "marker": "AGENT_FOUNDRY_LOCAL_TEST"}
args = sys.argv[1:]
host = "http://127.0.0.1:11434"
if args and args[0] == "--host":
    host, args = args[1], args[2:]


def call(path, body=None, timeout=300):
    req = urllib.request.Request(host + path, json.dumps(body).encode() if body else None, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


present = {m["name"]: m for m in call("/api/tags", timeout=30)["models"]}
out = {"schema": "agent-foundry.local_model_smoke.v1", "host": platform.node(), "ollama_host": host, "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "prompt": PROMPT, "expected": EXPECTED, "options": {"temperature": 0, "seed": 1, "num_predict": 64}, "results": {}}
for tag in args:
    r = {"MODEL_PRESENT": tag in present, "MODEL_ID": (present.get(tag) or {}).get("digest", "")[:12], "INFERENCE_EXECUTED": False, "OUTPUT_VALID": False, "LATENCY_S": None, "FAILURE": None, "raw_output": None}
    if r["MODEL_PRESENT"]:
        t0 = time.time()
        try:
            resp = call("/api/generate", {"model": tag, "prompt": PROMPT, "stream": False, "options": out["options"]})
            r["INFERENCE_EXECUTED"], r["LATENCY_S"], r["raw_output"] = True, round(time.time() - t0, 1), resp.get("response", "")
            text = r["raw_output"].strip()
            if text.startswith("```"):  # record, do not repair: fenced output is NOT valid under 'return only JSON'
                r["FAILURE"] = "output wrapped in markdown fence (not 'only JSON')"
            else:
                try:
                    r["OUTPUT_VALID"] = json.loads(text) == EXPECTED
                    if not r["OUTPUT_VALID"]:
                        r["FAILURE"] = "valid JSON but not the expected object"
                except json.JSONDecodeError as e:
                    r["FAILURE"] = f"not valid JSON: {e.msg}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            r["FAILURE"], r["LATENCY_S"] = f"{type(e).__name__}: {e}", round(time.time() - t0, 1)
    r["READY"] = bool(r["INFERENCE_EXECUTED"] and r["OUTPUT_VALID"])
    out["results"][tag] = r
    print(tag, {k: r[k] for k in ("MODEL_PRESENT", "INFERENCE_EXECUTED", "OUTPUT_VALID", "LATENCY_S", "READY", "FAILURE")}, flush=True)
name = f"lfm_smoke_{platform.node().split('.')[0]}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
p = Path(__file__).resolve().parent.parent / "provenance" / "local_models" / name
p.write_text(json.dumps(out, indent=2) + "\n")
print("wrote", p)
