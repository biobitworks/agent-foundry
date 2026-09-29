"""Capture REAL runs: Antigence deterministic core (control) vs local Liquid models (variants) on Antigence's own test inputs.

Usage: python3 scripts/capture_antigence_lfm.py <label>=<ollama-tag> ...
Output (immutable): demo/recorded/antigence_lfm/<input_id>/{core.jsonl,<label>.jsonl}, and demo/recorded/antigence_lfm/manifest_<stamp>.json
Same canonical input FCO, same instruction, same options (temperature 0, seed 1, num_predict 64) for every model.
"""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from agent_foundry import antigence_fixture as af  # noqa: E402
from agent_foundry.compare import compare_runs  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402
from agent_foundry.runner import run_task  # noqa: E402

OUT = ROOT / "demo" / "recorded" / "antigence_lfm"
models = {}
tokcap = {}
for a in sys.argv[1:]:  # label=tag or label=tag#num_predict (a separate, labeled successor observation)
    label, rest = a.split("=", 1)
    tag, _, cap = rest.partition("#")
    models[label] = tag
    tokcap[label] = int(cap) if cap else 64
ids = {}
for line in subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout.splitlines()[1:]:
    parts = line.split()
    if len(parts) > 1:
        ids[parts[0]] = parts[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
rows, files = [], {}
for label, tag in models.items():           # model-outer loop: one cold load per model
    for item in af.INPUTS:
        d = OUT / item["id"]
        d.mkdir(parents=True, exist_ok=True)
        task, fco = af.build_task(item)
        core_path = d / "core.jsonl"
        if not core_path.exists():
            run_task(task, {"provider": "antigence", "model": "antigence-prompt-injection-antibodies", "evidence": "input"}, f"{item['id']}-core", d, "CONTROL_RUN", "provider_model")
            (d / f"{item['id']}-core.jsonl").rename(core_path)
        if (d / f"{label}.jsonl").exists():
            sys.exit(f"{d / (label + '.jsonl')} exists; captures are immutable")
        run_task(task, {"provider": "ollama", "model": tag, "evidence": "input", **({"num_predict": tokcap[label]} if tokcap[label] != 64 else {})}, f"{item['id']}-{label}", d, "VARIANT_RUN", "provider_model")
        (d / f"{item['id']}-{label}.jsonl").rename(d / f"{label}.jsonl")
        core, var = read_run(core_path), read_run(d / f"{label}.jsonl")
        cmp_ = compare_runs(core, var)
        claim = next((e for e in var if e["event_type"] == "claim"), None)
        fail = next((e for e in var if e["event_type"] == "failure"), None)
        core_claim = next(e for e in core if e["event_type"] == "claim")
        verdict = json.loads(claim["payload"]["text"])["injection"] if claim else None
        model_ev = next((e for e in var if e["event_type"] == "model"), None)
        rows.append({"input_id": item["id"], "model": label, "canonical_input_content_id": fco["CONTENT_ID"], "expected_flagged_per_antigence_tests": item["expected_flagged"],
                     "core_verdict": json.loads(core_claim["payload"]["text"])["injection"], "model_verdict": verdict,
                     "output_valid": claim is not None, "failure": (fail or {}).get("payload"), "latency_ms": (model_ev or {}).get("meta", {}).get("latency_ms"),
                     "agrees_with_core": (verdict == json.loads(core_claim["payload"]["text"])["injection"]) if claim else None,
                     "agrees_with_expected": (verdict == item["expected_flagged"]) if claim else None,
                     "first_divergence": {"index": (cmp_["FIRST_DIVERGENCE"] or {}).get("index"), "kind": (cmp_["FIRST_DIVERGENCE"] or {}).get("kind")},
                     "downstream_claim_changed": (cmp_["AFFECTED_CLAIMS"][0]["changed"] if cmp_["AFFECTED_CLAIMS"] else None)})
        print(item["id"], label, {k: rows[-1][k] for k in ("model_verdict", "output_valid", "agrees_with_core", "latency_ms")}, flush=True)
for p in sorted(OUT.glob("*/*.jsonl")):
    files[str(p.relative_to(OUT))] = hashlib.sha256(p.read_bytes()).hexdigest()
manifest = {"schema": "agent-foundry.recorded_capture.v2", "kind": "REAL_EXECUTION_RECORDED", "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "host": platform.node(),
            "experiment": "antigence deterministic core vs local Liquid models", "antigence": {**af.antigence_identity(), "antibody_module_sha256": af.module_sha256(), "ground_truth_source": af.SOURCE_TEST},
            "options": {"temperature": 0, "seed": 1, "num_predict_per_model": tokcap}, "instruction": af.INSTRUCTION, "models": {l: {"tag": t, "ollama_model_id": ids.get(t), "num_predict": tokcap[l]} for l, t in models.items()},
            "rows": rows, "files_sha256": files,
            "limits": ["n=1 execution per cell; nondeterminism not measured", "only 4 inputs copied from Antigence's own tests; not a benchmark", "num_predict=64 may truncate reasoning-style models before JSON (confound; failures kept as recorded)",
                       "Antigence checkout is dirty; identity = HEAD + dirty count + antibody module hash", "hashes establish file identity, not correctness"]}
(OUT / f"manifest_{stamp}.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("wrote manifest", stamp)
