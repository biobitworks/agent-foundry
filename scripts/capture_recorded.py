"""Capture REAL runs as recorded evidence. Usage: python3 scripts/capture_recorded.py <scenario_id> [...]

Writes demo/recorded/<scenario>/{control,variant}.jsonl + manifest.json (hashes, models, host, time).
Recorded runs are real executions captured once; replaying the log is NOT a new execution.
"""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_foundry.scenarios import SCENARIOS, TASK  # noqa: E402
from agent_foundry.runner import run_pair  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402
from agent_foundry.compare import compare_runs  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "demo" / "recorded"


def ollama_models():
    try:
        rows = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30).stdout.splitlines()[1:]
        return {r.split()[0]: r.split()[1] for r in rows if r.strip()}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


for sid in sys.argv[1:]:
    sc = SCENARIOS[sid]
    d = OUT / sid
    if d.exists():
        sys.exit(f"{d} exists; recorded captures are immutable. Choose a new scenario id or remove deliberately.")
    d.mkdir(parents=True)
    a, b, var = run_pair(TASK, sc["control"], sc["variant"], d, sid)
    (d / "control.jsonl").write_text(a.path.read_text()); (d / "variant.jsonl").write_text(b.path.read_text())
    a.path.unlink(); b.path.unlink()
    ca, cb = read_run(d / "control.jsonl"), read_run(d / "variant.jsonl")
    cmp_ = compare_runs(ca, cb)
    models = ollama_models()
    manifest = {"schema": "agent-foundry.recorded_capture.v1", "scenario": sid, "title": sc["title"], "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "host": platform.node(), "kind": "REAL_EXECUTION_RECORDED", "declared_variable": var,
                "control_config": sc["control"], "variant_config": sc["variant"],
                "ollama_model_ids": {m: models.get(m) for m in {sc["control"].get("model"), sc["variant"].get("model")} if m},
                "files": {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in ("control.jsonl", "variant.jsonl")},
                "comparison_summary": {"DIVERGENCE": cmp_["DIVERGENCE"], "first_divergence_index": (cmp_["FIRST_DIVERGENCE"] or {}).get("index"), "kind": (cmp_["FIRST_DIVERGENCE"] or {}).get("kind")},
                "limits": ["single execution per side; nondeterminism not measured beyond n=2 spot repeats at temperature 0/seed 1",
                           "hashes establish identity of these files, not correctness of model answers", "captured via Ollama HTTP API directly, NOT via Ollarma routing"]}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(sid, cmp_["DIVERGENCE"], manifest["comparison_summary"])
