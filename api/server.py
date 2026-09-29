"""Agent Foundry API + run inspector. Binds to loopback by default."""
import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent_foundry.compare import compare_runs
from agent_foundry.recorder import read_run
from agent_foundry.replay import replay as do_replay
from agent_foundry.fcg_export import export_lineage
from agent_foundry.recorder import verify_run
from agent_foundry.runner import run_pair
from agent_foundry.scenarios import SCENARIOS, TASK

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RECORDED = ROOT / "demo" / "recorded"

app = FastAPI(title="Agent Foundry", version="0.0.1")


class PairRequest(BaseModel):
    scenario: str | None = None
    control: dict | None = None
    variant: dict | None = None


def _execute(control_cfg, variant_cfg):
    tag = "p" + uuid.uuid4().hex[:8]
    try:
        a, b, _ = run_pair(TASK, control_cfg, variant_cfg, RUNS, tag)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ca, cb = read_run(a.path), read_run(b.path)
    return {"tag": tag, "source": "LIVE_EXECUTION", "task": {"task_id": TASK["task_id"], "prompt": TASK["prompt"]}, "control": ca, "variant": cb, "comparison": compare_runs(ca, cb)}


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": [{"id": k, "title": v["title"], "control": v["control"], "variant": v["variant"], "real": bool(v.get("real")),
                           "recorded": (RECORDED / k / "manifest.json").exists()} for k, v in SCENARIOS.items()]}


@app.get("/api/recorded/{scenario}")
def recorded(scenario: str):
    """Replays a captured REAL run from disk. This is NOT a new execution."""
    if scenario not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    d = RECORDED / scenario
    if not (d / "manifest.json").exists():
        raise HTTPException(404, "no recorded capture for this scenario")
    ca, cb = read_run(d / "control.jsonl"), read_run(d / "variant.jsonl")  # re-verifies internal consistency
    return {"tag": f"recorded:{scenario}", "source": "RECORDED_REAL_EXECUTION", "manifest": json.loads((d / "manifest.json").read_text()),
            "task": {"task_id": TASK["task_id"], "prompt": TASK["prompt"]}, "control": ca, "variant": cb, "comparison": compare_runs(ca, cb)}


@app.post("/api/pair")
def pair(req: PairRequest):
    if req.scenario:
        if req.scenario not in SCENARIOS:
            raise HTTPException(404, "unknown scenario")
        sc = SCENARIOS[req.scenario]
        return _execute(sc["control"], sc["variant"])
    if req.control and req.variant:
        return _execute(req.control, req.variant)
    raise HTTPException(400, "provide scenario or control+variant")


@app.get("/api/pair/{tag}")
def get_pair(tag: str):
    if not re.fullmatch(r"p[0-9a-f]{8}", tag):
        raise HTTPException(400, "bad tag")
    try:
        ca, cb = read_run(RUNS / f"{tag}-control.jsonl"), read_run(RUNS / f"{tag}-variant.jsonl")
    except FileNotFoundError:
        raise HTTPException(404, "no such pair")
    return {"tag": tag, "control": ca, "variant": cb, "comparison": compare_runs(ca, cb)}


class ReplayRequest(BaseModel):
    source: str  # "recorded:<scenario>" or a live pair tag
    side: str = "control"
    override: dict | None = None  # e.g. {"provider": "fixture", "model": "fixture-b"} => branch under another provider


@app.post("/api/replay")
def replay_endpoint(req: ReplayRequest):
    """Resume from a checkpoint taken after the evidence event. Executes the remaining steps again (a real execution)."""
    if req.side not in ("control", "variant"):
        raise HTTPException(400, "side must be control or variant")
    m = re.fullmatch(r"recorded:([a-z_]+)", req.source)
    if m and m.group(1) in SCENARIOS:
        path = RECORDED / m.group(1) / f"{req.side}.jsonl"
    elif re.fullmatch(r"p[0-9a-f]{8}", req.source):
        path = RUNS / f"{req.source}-{req.side}.jsonl"
    else:
        raise HTTPException(400, "bad source")
    try:
        events = read_run(path)
    except FileNotFoundError:
        raise HTTPException(404, "no such run")
    try:
        return {"source": req.source, "side": req.side, "original": events, **do_replay(TASK, events, RUNS, "rp" + uuid.uuid4().hex[:8], override=req.override)}
    except ValueError as e:
        raise HTTPException(400, str(e))


AG = RECORDED / "antigence_lfm"


def _ag_manifests():
    """All captures, newest last; the row set per (input, label) comes from the manifest that recorded it."""
    return [json.loads(p.read_text()) for p in sorted(AG.glob("manifest_*.json"))] if AG.exists() else []


@app.get("/api/antigence")
def antigence_index():
    rows = {}
    for m in _ag_manifests():
        for r in m["rows"]:
            rows[(r["input_id"], r["model"])] = {**r, "captured_at": m["captured_at"], "num_predict": m["models"][r["model"]].get("num_predict", 64)}
    return {"cases": [{"id": f"{i}|{l}", **v} for (i, l), v in sorted(rows.items())]}


@app.get("/api/antigence/{input_id}/{label}")
def antigence_pair(input_id: str, label: str):
    """Replays a captured REAL comparison: Antigence deterministic core (control) vs a local Liquid model (variant)."""
    if not (re.fullmatch(r"[a-z0-9-]+", input_id) and re.fullmatch(r"[a-z0-9_]+", label)):
        raise HTTPException(400, "bad id")
    d = AG / input_id
    if not (d / f"{label}.jsonl").exists():
        raise HTTPException(404, "no such capture")
    ca, cb = read_run(d / "core.jsonl"), read_run(d / f"{label}.jsonl")
    man = next((m for m in reversed(_ag_manifests()) if label in m["models"]), None)
    return {"tag": f"antigence:{input_id}:{label}", "source": "RECORDED_REAL_EXECUTION", "manifest": man and {k: man[k] for k in ("captured_at", "host", "antigence", "options", "models", "limits")},
            "task": {"task_id": f"antigence-screen-{input_id}", "prompt": "Is this input a prompt-injection attempt?"}, "control": ca, "variant": cb, "comparison": compare_runs(ca, cb), "replay_supported": False}


LIVE_MODELS = {"lfm350m": "hf.co/LiquidAI/LFM2.5-350M-GGUF:Q4_K_M", "lfm1p2b": "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M"}


class LiveRequest(BaseModel):
    text: str
    model: str = "lfm1p2b"


@app.post("/api/antigence/live")
def antigence_live(req: LiveRequest):
    """LIVE execution: deterministic Antigence core (control) vs a local Liquid model (variant) on the SAME canonical input.
    2.6B is excluded: it failed the strict-JSON test in every setting (see provenance/local_models)."""
    import hashlib
    from agent_foundry import antigence_fixture as af
    from agent_foundry.runner import run_task
    if req.model not in LIVE_MODELS:
        raise HTTPException(400, f"model must be one of {sorted(LIVE_MODELS)}")
    text = req.text.strip()
    if not (1 <= len(text) <= 600):
        raise HTTPException(400, "text must be 1-600 characters")
    iid = "live-" + hashlib.sha256(text.encode()).hexdigest()[:10]
    task, fco = af.build_task({"id": iid, "text": text, "expected_flagged": None})
    tag = "L" + uuid.uuid4().hex[:8]
    a = run_task(task, {"provider": "antigence", "model": "antigence-prompt-injection-antibodies", "evidence": "input"}, f"{tag}-core", RUNS, "CONTROL_RUN", "provider_model")
    b = run_task(task, {"provider": "ollama", "model": LIVE_MODELS[req.model], "evidence": "input"}, f"{tag}-{req.model}", RUNS, "VARIANT_RUN", "provider_model")
    ca, cb = read_run(a.path), read_run(b.path)
    return {"tag": f"live:{tag}", "source": "LIVE_EXECUTION", "task": {"task_id": task["task_id"], "prompt": task["prompt"]}, "canonical_input_content_id": fco["CONTENT_ID"],
            "control": ca, "variant": cb, "comparison": compare_runs(ca, cb), "replay_supported": False,
            "manifest": {"captured_at": None, "host": None, "antigence": af.antigence_identity(), "options": {"temperature": 0, "seed": 1, "num_predict": 64}, "models": {req.model: {"tag": LIVE_MODELS[req.model]}}, "limits": ["live single execution; nondeterminism not measured"]}}


class LineageRequest(BaseModel):
    control: list
    variant: list


@app.post("/api/lineage")
def lineage(req: LineageRequest):
    """Verifies both runs (schema, ordering, id recomputation) then exports declared-edge lineage. Unsigned; no Merkle/MMR."""
    try:
        verify_run(req.control)
        verify_run(req.variant)
    except (ValueError, KeyError, IndexError) as e:
        raise HTTPException(400, f"run failed verification: {e}")
    return export_lineage(req.control, req.variant)


@app.get("/api/lineage/recorded/{scenario}")
def lineage_recorded(scenario: str):
    if scenario not in SCENARIOS or not (RECORDED / scenario / "manifest.json").exists():
        raise HTTPException(404, "no recorded capture for this scenario")
    d = RECORDED / scenario
    return export_lineage(read_run(d / "control.jsonl"), read_run(d / "variant.jsonl"))


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "index.html")
