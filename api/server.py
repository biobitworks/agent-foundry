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


@app.get("/api/live/{tag}")
def live_pair(tag: str):
    """Reload a previously executed LIVE run pair (permalink target for the inspector and the Duplo adapter)."""
    if not re.fullmatch(r"L[0-9a-f]{8}", tag):
        raise HTTPException(400, "bad tag")
    core = RUNS / f"{tag}-core.jsonl"
    others = sorted(p for p in RUNS.glob(f"{tag}-*.jsonl") if p != core)
    if not core.exists() or not others:
        raise HTTPException(404, "no such live run")
    ca, cb = read_run(core), read_run(others[0])
    return {"tag": f"live:{tag}", "source": "LIVE_EXECUTION", "task": {"task_id": ca[0]["payload"]["task_id"], "prompt": "Is this input a prompt-injection attempt?"}, "control": ca, "variant": cb,
            "comparison": compare_runs(ca, cb), "replay_supported": False,
            "manifest": {"captured_at": None, "host": None, "limits": ["reloaded live execution (this was executed live earlier; this view is not a new execution)"]}}


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


MD = RECORDED / "moddik"


def _moddik_events(source: str, side: str = "control"):
    """Resolve a Moddik source id to a VERIFIED event list. recorded:<name> (captured real execution) or live:<tag> (executed earlier in this workspace)."""
    if side not in ("control", "variant"):
        raise HTTPException(400, "side must be control or variant")
    m = re.fullmatch(r"recorded:([a-z0-9_]+)", source)
    if m:
        path, man = MD / m.group(1) / f"{side}.jsonl", MD / m.group(1) / "manifest.json"
        kind = "RECORDED_REAL_EXECUTION"
    elif re.fullmatch(r"live:mv[0-9a-f]{8}", source):
        path, man, kind = RUNS / f"{source[5:]}-moddik{'' if side == 'control' else '-perturbed'}.jsonl", None, "LIVE_EXECUTION"
    else:
        raise HTTPException(400, "bad source")
    try:
        return read_run(path), kind, (json.loads(man.read_text()) if man and man.exists() else None)
    except FileNotFoundError:
        raise HTTPException(404, "no such moddik run")


@app.get("/api/moddik/sources")
def moddik_sources():
    rec = [{"id": f"recorded:{d.name}", "kind": "RECORDED_REAL_EXECUTION", "has_variant": (d / "variant.jsonl").exists()} for d in sorted(MD.glob("*")) if (d / "manifest.json").exists()] if MD.exists() else []
    live = [{"id": f"live:{p.name[:-len('-moddik.jsonl')]}", "kind": "LIVE_EXECUTION", "has_variant": (RUNS / f"{p.name[:-len('-moddik.jsonl')]}-moddik-perturbed.jsonl").exists()}
            for p in sorted(RUNS.glob("mv*-moddik.jsonl"))]
    return {"sources": rec + live, "banner": "LOCAL SIMULATION (source=SIMULATED). No Moddik hardware was contacted."}


@app.get("/api/moddik/run/{source}")
def moddik_run_view(source: str, side: str = "control"):
    from agent_foundry.moddik_view import build_view
    events, kind, man = _moddik_events(source, side)
    view = build_view(events)
    m = re.fullmatch(r"recorded:([a-z0-9_]+)", source)
    add = MD / m.group(1) / "plaud_addendum.jsonl" if m and side == "control" else None
    if add is not None and add.exists():  # independent audio custody: linked by the parent log hash; verified on load
        import hashlib
        ad = read_run(add)
        bound = ad[0]["payload"]["parent_log_sha256"] == hashlib.sha256((MD / m.group(1) / "control.jsonl").read_bytes()).hexdigest()
        view["audio"] = [{"event_id": e["event_id"], **{k: e["payload"].get(k) for k in ("artifact_type", "source_filename", "digest", "size_bytes", "capture", "imported_at", "relation_to_parent_run", "operator_attestation")},
                          "parent_log_binding_verified": bound} for e in ad if e["event_type"] == "artifact"]
    return {"source": kind, "tag": source, "side": side, "manifest": man, "events": events, "view": view}


@app.get("/api/moddik/pair/{source}")
def moddik_pair(source: str):
    """Control vs one-controlled-sensor-difference replay, in the same shape the paired inspector already renders."""
    ca, kind, man = _moddik_events(source, "control")
    cb, _, _ = _moddik_events(source, "variant")
    return {"tag": source, "source": kind, "manifest": man, "task": {"task_id": ca[0]["payload"]["task_id"], "prompt": "Does the simulated plate need a medium exchange? (variant = ONE controlled sensor difference)"},
            "control": ca, "variant": cb, "comparison": compare_runs(ca, cb), "replay_supported": False}


@app.get("/api/moddik/graph/{source}")
def moddik_graph_route(source: str, side: str = "control"):
    """Evidence route from the Neo4j PROJECTION when available (labelled as such); the canonical view is always /api/moddik/run."""
    from agent_foundry import moddik_graph as g
    events, _, _ = _moddik_events(source, side)
    try:
        drv = g.connect()
    except Exception as e:
        return {"backend": "UNAVAILABLE", "reason": f"neo4j not reachable ({type(e).__name__}); canonical run view still available", "credentials": g.credential_status()}
    try:
        rid = events[0]["run_id"]
        have = g.query(drv, "MATCH (r:Run {run_id:$r}) RETURN r.canonical_log_sha256 AS h", r=rid)
        import hashlib
        path = (MD / source.split(":", 1)[1] / f"{side}.jsonl") if source.startswith("recorded:") else (RUNS / f"{source[5:]}-moddik{'' if side == 'control' else '-perturbed'}.jsonl")
        want = hashlib.sha256(path.read_bytes()).hexdigest()
        if not have or have[0]["h"] != want:  # projection missing or stale: rebuild from the canonical log (rebuildability is the point)
            g.clear_run(drv, rid)
            g.project_run(drv, events, path)
            rebuilt = True
        else:
            rebuilt = False
        return {"backend": "neo4j", "rebuilt_from_canonical_log": rebuilt, "canonical_log_sha256": want, **g.evidence_path(drv, rid),
                "labels": g.query(drv, "MATCH (n {run_id:$r}) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC", r=rid)}
    finally:
        drv.close()


class ModdikRunRequest(BaseModel):
    transcript: str = "What changed, and does this culture need intervention?"
    model: str = "lfm2p6b"
    bonus: bool = False


@app.post("/api/moddik/run")
def moddik_execute(req: ModdikRunRequest):
    """LIVE execution of the local simulation + local Liquid model (about 1-3 minutes on this Mac). Nothing is actuated."""
    from agent_foundry import moddik_agent as ag, moddik_run as mr
    if req.model not in ag.MODELS:
        raise HTTPException(400, f"model must be one of {sorted(ag.MODELS)}")
    text = req.transcript.strip()
    if not (1 <= len(text) <= 300):
        raise HTTPException(400, "transcript must be 1-300 characters")
    tag = "mv" + uuid.uuid4().hex[:8]
    res = mr.run_moddik(f"{tag}-moddik", RUNS, transcript=text, model_key=req.model, label="CONTROL_RUN")
    if req.bonus:
        mr.run_moddik(f"{tag}-moddik-perturbed", RUNS, transcript=text, model_key=req.model, perturb={("nutrient", 9): 2.5}, label="VARIANT_RUN")
    return {"source": f"live:{tag}", "summary": res["summary"]}


DS = RECORDED / "external_datasets"


@app.get("/api/dataset/{name}")
def dataset_view(name: str, graph: int = 0):
    """External-dataset admission (metadata level): canonical FCO/FCG + the recorded Agent Foundry run, re-verified on load. graph=1 also queries the Neo4j PROJECTION."""
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise HTTPException(400, "bad name")
    d = DS / name
    if not (d / "manifest.json").exists():
        raise HTTPException(404, "no such dataset admission")
    import hashlib
    from agent_foundry import dataset_fco as dfco, dataset_graph as dg
    man = json.loads((d / "manifest.json").read_text())
    events = read_run(d / man["run_file"])
    fcos, edges = dfco.load_canonical()
    hashes_ok = all(dfco.verify_fco_hash(f) for f in fcos.values())
    start = next(h for h, f in fcos.items() if f["object_type"] == "DatasetFile")
    out = {"source": "RECORDED_REAL_EXECUTION", "manifest": man, "run_sha256_matches_manifest": hashlib.sha256((d / man["run_file"]).read_bytes()).hexdigest() == man["run_sha256"],
           "fco_hashes_recomputed": hashes_ok, "events": events, "fcos": list(fcos.values()), "edges": edges, "canonical_trace": dfco.trace(fcos, edges, start),
           "capture": json.loads((ROOT / "fco" / "manifests" / "ieee_dmf_v01_source_capture.json").read_text())}
    if graph:
        from agent_foundry import moddik_graph as mg
        try:
            drv = mg.connect()
        except Exception as e:
            out["neo4j"] = {"backend": "UNAVAILABLE", "reason": type(e).__name__}
            return out
        try:
            aid = "ieee_dmf_fco_v01"
            if dg.counts(drv, aid)["nodes"] == 0:  # projection missing: rebuild it from the canonical files + run log
                dg.project(drv, aid, fcos, edges, events)
                out["neo4j_rebuilt_from_canonical"] = True
            out["neo4j"] = {"backend": "neo4j", "counts": dg.counts(drv, aid), "trace": dg.trace(drv, aid, start)["paths"]}
        finally:
            drv.close()
    return out


PDIR = RECORDED / "path_divergence"


@app.get("/api/path_divergence/{name}")
def path_divergence_view(name: str):
    """Two-endpoint path divergence diagnostic (PathDivergenceFCO) over the recorded Moddik pair: canonical FCO/FCG + recorded run, re-verified on load."""
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise HTTPException(400, "bad name")
    d = PDIR / name
    if not (d / "manifest.json").exists():
        raise HTTPException(404, "no such path-divergence recording")
    import hashlib
    from agent_foundry import dataset_fco as dfco
    man = json.loads((d / "manifest.json").read_text())
    events = read_run(d / man["run_file"])
    fcos, edges = dfco.load_canonical_sub("path_divergence")
    return {"source": "RECORDED_REAL_EXECUTION", "manifest": man, "run_sha256_matches_manifest": hashlib.sha256((d / man["run_file"]).read_bytes()).hexdigest() == man["run_sha256"],
            "fco_hashes_recomputed": all(dfco.verify_fco_hash(f) for f in fcos.values()), "diagnostics": [f for f in fcos.values() if f["object_type"] == "PathDivergenceFCO"],
            "states": [f for f in fcos.values() if f["object_type"] == "EndpointState"], "run_logs": [f for f in fcos.values() if f["object_type"] == "RunLog"], "edges": edges, "events": events}


CMPDIR = RECORDED / "context_compare"


@app.get("/api/compare/{name}")
def compare_view(name: str):
    """Same frozen Vithia context -> two backends. Re-verifies every run log and file hash on load; Studio arm status is reported, never assumed."""
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise HTTPException(400, "bad name")
    d = CMPDIR / name
    if not (d / "context_manifest.json").exists():
        raise HTTPException(404, "no such comparison")
    import hashlib
    man = json.loads((d / "context_manifest.json").read_text())
    ctx = {k: {**v, "bytes_verified": hashlib.sha256((d / v["file"]).read_bytes()).hexdigest() == v["sha256"] and len((d / v["file"]).read_bytes()) == v["byte_count"], "text": (d / v["file"]).read_text()} for k, v in man["contexts"].items()}
    comps = {}
    for cp in sorted(d.glob("*/comparison.json")):
        rc = json.loads(cp.read_text())
        if re.fullmatch(r"(studio_)?(primary|control)", rc.get("name") or "") and (cp.parent / f"eca-v01-{rc['name']}-a.jsonl").exists():
            comps[rc["name"]] = {"receipt": rc, "stream_a": read_run(cp.parent / f"eca-v01-{rc['name']}-a.jsonl"), "stream_b": read_run(cp.parent / f"eca-v01-{rc['name']}-b.jsonl")}
    route = json.loads((d / "route_failure_receipt.json").read_text()) if (d / "route_failure_receipt.json").exists() else None
    studio = sorted(p.name for p in d.glob("arm_liquid_studio*.json"))
    return {"source": "RECORDED_REAL_EXECUTION", "manifest": {k: man[k] for k in ("frozen_at", "upstream", "row_index", "state_id")}, "dataset": man["dataset"], "contexts": ctx, "comparisons": comps, "route_failure": route,
            "prep_events": read_run(d / "eca-v01-prep.jsonl"), "studio_liquid_arm": {"present": bool(studio), "files": studio, "status": "IMPORTED" if studio else "PENDING_OPERATOR_EXECUTION_ON_MAGICSTUDIOBOX"}}


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "index.html")
