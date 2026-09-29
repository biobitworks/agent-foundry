"""Demo preflight. Prints PASS/FAIL per check and writes a receipt to provenance/preflight/. Read-mostly:
the only side effect is one tiny generation to warm the live model (keep_alive 30m). No service is stopped or restarted.
"""
import json
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M"
checks = {}


def rec(name, ok, detail=""):
    checks[name] = {"status": "PASS" if ok else "FAIL", "detail": detail}
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, cwd=ROOT).stdout.strip()


head, origin = sh("git", "rev-parse", "HEAD"), sh("git", "rev-parse", "origin/main")
rec("git_parity_with_origin_main", head == origin, f"HEAD={head[:8]} origin={origin[:8]} (run `git fetch` first)")
rec("worktree_clean", sh("git", "status", "--short") == "", "")
t = subprocess.run(["make", "test"], capture_output=True, text=True, cwd=ROOT)
rec("tests", t.returncode == 0, t.stdout.strip().splitlines()[-1] if t.stdout.strip() else "no output")
s = socket.socket(); s.settimeout(1)
rec("port_8765_free_for_inspector", s.connect_ex(("127.0.0.1", 8765)) != 0, "")
s.close()
rec("disk_free_gb>=5", shutil.disk_usage(str(Path.home())).free / 1e9 >= 5, f"{shutil.disk_usage(str(Path.home())).free/1e9:.1f} GB free")
try:
    tags = {m["name"] for m in json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())["models"]}
    rec("ollama_reachable", True, f"{len(tags)} models")
    rec("live_model_present", LIVE in tags, LIVE)
    if LIVE in tags:
        t0 = time.time()
        body = json.dumps({"model": LIVE, "prompt": 'Return only JSON: {"injection": false}', "stream": False, "keep_alive": "30m", "options": {"temperature": 0, "seed": 1, "num_predict": 16}}).encode()
        r = json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", body, {"Content-Type": "application/json"}), timeout=300).read())
        rec("live_model_warm_inference_executed", bool(r.get("response")), f"{time.time()-t0:.1f}s (cold load included on first run)")
except Exception as e:  # noqa: BLE001
    rec("ollama_reachable", False, f"{type(e).__name__}: {e}")
try:
    sys.path.insert(0, str(ROOT))
    from agent_foundry import antigence_fixture as af
    ok = all((af.screen(i["text"])["anomaly_count"] >= 1) is i["expected_flagged"] for i in af.INPUTS)
    rec("antigence_fixture_matches_its_own_test_expectations", ok, "4 inputs")
except Exception as e:  # noqa: BLE001
    rec("antigence_fixture_matches_its_own_test_expectations", False, f"{type(e).__name__}: {e}")
dc = sh("docker", "compose", "-f", "/Users/byron/projects/toolchains/agent-foundry-duplo/docker-compose.yml", "ps", "--format", "{{.Service}} {{.State}}")
rec("duplocloud_containers_up", bool(dc) and all(l.endswith("running") for l in dc.splitlines()), (dc.replace("\n", "; ") or "none running"))
out = {"schema": "agent-foundry.preflight.v1", "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "host": platform.node(), "head": head, "checks": checks,
       "all_pass": all(c["status"] == "PASS" for c in checks.values()), "note": "duplocloud check is informational for the local demo path; it gates the sponsor path"}
d = ROOT / "provenance" / "preflight"; d.mkdir(exist_ok=True)
(d / f"preflight_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json").write_text(json.dumps(out, indent=2) + "\n")
print("ALL_PASS" if out["all_pass"] else "SOME_FAIL")
