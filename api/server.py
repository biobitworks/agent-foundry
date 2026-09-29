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


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "index.html")
