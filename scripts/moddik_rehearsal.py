"""Deterministic end-to-end Moddik rehearsal (LOCAL SIMULATION). Usage:
  python3 scripts/moddik_rehearsal.py [--model lfm2p6b|lfm1p2b] [--tag NAME] [--no-graph] [--bonus] [--transcript TEXT]
Writes runs/<tag>-moddik.jsonl (canonical, append-only). Prints START / RUNNING / PASS|FAIL per stage and a status table.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_foundry import moddik_run as mr  # noqa: E402
from agent_foundry.compare import compare_runs  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="lfm2p6b")
ap.add_argument("--tag", default=time.strftime("m%m%d%H%M%S"))
ap.add_argument("--no-graph", action="store_true")
ap.add_argument("--bonus", action="store_true", help="also run the one-sensor-difference replay and report the first divergent event")
ap.add_argument("--transcript", default=mr.DEFAULT_TRANSCRIPT)
ap.add_argument("--num-predict", type=int, default=3500)
ap.add_argument("--record", help="copy the (control + variant) canonical run logs to demo/recorded/moddik/<NAME>/ with a hash manifest; implies --bonus")
a = ap.parse_args()
if a.record:
    a.bonus = True
out = ROOT / "runs"
print(f"START moddik rehearsal tag={a.tag} model={a.model} graph={'off' if a.no_graph else 'on'}", flush=True)
t0 = time.time()
print("RUNNING simulator -> events -> breakpoints -> graph -> model (model call can take 1-3 min)", flush=True)
res = mr.run_moddik(f"{a.tag}-moddik", out, transcript=a.transcript, model_key=a.model, num_predict=a.num_predict, use_graph=not a.no_graph, label="CONTROL_RUN")
print(json.dumps(res["summary"], indent=1))
if a.bonus:
    print("RUNNING bonus replay with ONE controlled sensor difference (nutrient@tick9 +2.5 mM)", flush=True)
    res2 = mr.run_moddik(f"{a.tag}-moddik-perturbed", out, transcript=a.transcript, model_key=a.model, num_predict=a.num_predict, use_graph=not a.no_graph,
                         perturb={("nutrient", 9): 2.5}, label="VARIANT_RUN")
    cmp_ = compare_runs(res["events"], res2["events"])
    print(json.dumps({"summary": res2["summary"], "DIVERGENCE": cmp_["DIVERGENCE"], "first_divergence": cmp_["FIRST_DIVERGENCE"] and {"index": cmp_["FIRST_DIVERGENCE"]["index"], "kind": cmp_["FIRST_DIVERGENCE"]["kind"],
                      "changed_fields": cmp_["FIRST_DIVERGENCE"]["changed_fields"]}}, indent=1))
if a.record:
    import hashlib, platform, shutil, subprocess, urllib.request
    from datetime import datetime, timezone
    from agent_foundry import moddik_agent as ag, moddik_sim as sim
    d = ROOT / "demo" / "recorded" / "moddik" / a.record
    d.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(out / f"{a.tag}-moddik.jsonl", d / "control.jsonl")
    shutil.copyfile(out / f"{a.tag}-moddik-perturbed.jsonl", d / "variant.jsonl")
    tags = {m["name"]: m["digest"][:12] for m in json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10).read())["models"]}
    roots = lambda ev: [{"label": e["payload"]["label"], "tick": e["payload"]["tick"], "MERKLE_ROOT": e["payload"]["MERKLE_ROOT"]} for e in ev if e["event_type"] == "checkpoint"]
    man = {"schema": "agent-foundry.moddik_recording.v1", "kind": "REAL_EXECUTION_RECORDED", "scenario": "moddik-local-simulation", "source": "SIMULATED",
           "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "host": platform.node(),
           "head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(), "working_tree_dirty_at_capture": True,
           "model": {"key": a.model, "ollama_tag": ag.MODELS[a.model], "ollama_model_id": tags.get(ag.MODELS[a.model]), "options": {**ag.OPTIONS, "num_predict": a.num_predict}, "contract": ag.CONTRACT},
           "simulator": {"seed": sim.SEED, "hardware_id": sim.HARDWARE_ID, "ticks": sim.TICKS, "policy": sim.POLICY},
           "transcript_source": "OPERATOR_TEXT_INPUT", "graph_backend": res["summary"]["graph"]["backend"],
           "control_breakpoints": roots(res["events"]), "variant_breakpoints": roots(res2["events"]), "variant_difference": {"sensor": "nutrient", "tick": 9, "delta_mM": 2.5},
           "files": {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in ("control.jsonl", "variant.jsonl")},
           "limits": ["LOCAL SIMULATION; no Moddik hardware contacted; no sensor physically tested", "single execution per side; model nondeterminism NOT_COMPUTED",
                      "thresholds/trajectories are ILLUSTRATIVE scenario parameters", "transcript was typed operator text; live ASR NOT_TESTED", "PLAUD custody lane NOT_TESTED with a real recording"]}
    (d / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
    print("recorded ->", d)
print(f"DONE in {time.time()-t0:.0f}s")
