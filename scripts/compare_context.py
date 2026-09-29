"""Same frozen Vithia context -> two backends. Subcommands (all deterministic except the model calls):
  freeze                         magicPRObox: EvidenceSet -> Vithia (once) -> frozen CanonicalContext bytes + FCOs + prep run
  verify-context FILE SHA BYTES  recompute byte count + sha256 of an exact context file (stdlib only; also runnable on Studio)
  run-openjev --which primary|control [--port N]   OpenJEV arm on THIS machine against the frozen bytes (project runtime, bearer token stays local)
  run-liquid  --which primary|control --endpoint URL --model TAG --host NAME --topology TEXT    LiquidAI arm against the frozen bytes
  import-arm FILE                verify + register an arm-result file (e.g. produced on magicSTUDIObox)
  compare --a FILE --b FILE --which primary|control   normalize both arms, verify identity, compare, write streams + FCOs + receipt
"""
import argparse
import hashlib
import re
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "demo" / "recorded" / "context_compare" / "eca_v01"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha_file(p):
    b = Path(p).read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def _tracked(p: Path) -> bool:
    import subprocess
    return subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", str(p)], capture_output=True).returncode == 0


def wj(p: Path, obj):
    if p.exists() and json.loads(p.read_text()) != obj and (_tracked(p)):
        raise SystemExit(f"REFUSED: {p} exists with different content (append-only)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


ap = argparse.ArgumentParser()
sp = ap.add_subparsers(dest="cmd", required=True)
sp.add_parser("freeze")
v = sp.add_parser("verify-context")
v.add_argument("file"); v.add_argument("sha256"); v.add_argument("bytes", type=int)
o = sp.add_parser("run-openjev")
o.add_argument("--which", default="primary"); o.add_argument("--port", type=int, required=True); o.add_argument("--out")
l = sp.add_parser("run-liquid")
l.add_argument("--which", default="primary"); l.add_argument("--endpoint", default="http://127.0.0.1:11434"); l.add_argument("--model", required=True)
l.add_argument("--host", default=platform.node()); l.add_argument("--topology", default="local"); l.add_argument("--label", required=True); l.add_argument("--model-identity", default=""); l.add_argument("--out")
im = sp.add_parser("import-arm")
im.add_argument("file")
sp.add_parser("route-failure")
vf = sp.add_parser("verify")
vf.add_argument("--write-receipt", action="store_true")
c = sp.add_parser("compare")
c.add_argument("--a", required=True); c.add_argument("--b", required=True); c.add_argument("--which", default="primary"); c.add_argument("--name", default="pro_openjev_vs_liquid")
a = ap.parse_args()

if a.cmd == "verify-context":
    h, n = sha_file(a.file)
    ok = h == a.sha256 and n == a.bytes
    print(json.dumps({"file": a.file, "byte_count": n, "sha256": h, "expected_byte_count": a.bytes, "expected_sha256": a.sha256, "CONTEXT_IDENTITY_MATCH": "PASS" if ok else "FAIL"}, indent=1))
    sys.exit(0 if ok else 1)

from agent_foundry import backend_compare as bc, compare_fco as cf, dataset_fco as dfco  # noqa: E402

if a.cmd == "freeze":
    mods, up = bc.upstream()
    rows, info = bc.load_corpus_rows()
    assert info["bytes_match_manifest"], "corpus bytes do not match their own manifest"
    idx, row = bc.select_row(rows)
    contexts, ctxs = {}, {}
    for label, arm in (("primary", bc.PRIMARY_ARM), ("control", bc.CONTROL_ARM)):
        pkg = bc.build_context(mods, row, arm)  # Vithia executes here, once per arm
        b = bc.compact(pkg)
        contexts[label] = (arm, b)
    ts = now()
    sw = "sha256:" + hashlib.sha256(b"".join((ROOT / "agent_foundry" / f).read_bytes() for f in ("backend_compare.py", "compare_fco.py"))).hexdigest()
    fcos, edges, man = cf.build_freeze(mods, up, info, idx, row, contexts, ts, "eca-v01-freeze", sw)
    OUT.mkdir(parents=True, exist_ok=True)
    for label, (arm, b) in contexts.items():
        p = OUT / f"context_{label}.json"
        if p.exists() and p.read_bytes() != b:
            raise SystemExit(f"REFUSED: {p} exists with different bytes (frozen)")
        p.write_bytes(b)
    for f in fcos.values():
        wj(ROOT / "fco" / "objects" / "context_compare" / f"{f['content_hash'].split(':')[1]}.json", f)
    ep = ROOT / "fcg" / "edges" / "context_compare" / "CONTEXT_COMPARE_eca_v01.jsonl"
    ep.parent.mkdir(parents=True, exist_ok=True)
    if not ep.exists():
        ep.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edges))
    wj(OUT / "context_manifest.json", man)
    ev = cf.run_prep(fcos, edges, man, OUT, "eca-v01-prep", ts, mods, up, row)
    print(json.dumps({"CONTEXT_FILE": {k: f"demo/recorded/context_compare/eca_v01/{v['file']}" for k, v in man["contexts"].items()}, "CONTEXT_BYTE_COUNT": {k: v["byte_count"] for k, v in man["contexts"].items()},
                      "CONTEXT_SHA256": {k: v["sha256"] for k, v in man["contexts"].items()}, "CONTEXT_CONTENT_ID": {k: v["content_id"] for k, v in man["contexts"].items()},
                      "EVIDENCE_IDS": [i["evidence_id"] for i in bc.evidence_items(mods, row)], "QUESTION": mods["beh"].QUESTION["instructions"], "state_id": row["state_id"], "row_index": idx,
                      "upstream_commit": up["commit"], "corpus_sha256": info["sha256"], "prep_events": len(ev)}, indent=1))


def load_context(which):
    man = json.loads((OUT / "context_manifest.json").read_text())["contexts"][which]
    raw = (OUT / man["file"]).read_bytes()
    h, n = hashlib.sha256(raw).hexdigest(), len(raw)
    if h != man["sha256"] or n != man["byte_count"]:
        raise SystemExit(f"STOP: frozen context {which} does not match its manifest (CONTEXT_IDENTITY_MATCH=FAIL)")
    return raw, man


def finish(res, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(out), "executed": res["executed"], "latency_ms": res.get("latency_ms"), "error": res.get("error")}, indent=1))


if a.cmd == "run-openjev":
    raw, man = load_context(a.which)
    rm = json.loads((ROOT / ".local/upstream/jev-space-invaders/evidence/openjev/RUNTIME_MANIFEST.json").read_text())
    host = platform.node()
    verified = rm.get("OPENJEV_LOADED") == "YES" and rm.get("hardware", {}).get("host") == host and rm.get("port") == a.port
    tokf = Path.home() / ".openjev" / "token"
    headers = {"Content-Type": "application/json"}
    if tokf.exists():
        headers["Authorization"] = "Bearer " + tokf.read_text().strip()  # in-process only; never printed or stored
    body = bc.openjev_body(raw)
    res = {"schema": "agent-foundry.arm_result.v1", "host": host, "topology": "OpenJEV on magicPRObox against the frozen bytes", "which": a.which,
           "backend": {"family": "openjev", "label": "OPENJEV (project runtime, MLX 4-bit, NON_TYPESAFE_JEV)" if verified else "OPENJEV_UNVERIFIED_RUNTIME", "provider": "openjev", "provider_kind": "real", "model": None,
                       "model_identity": {"repo": rm["upstream"]["model"]["repo"], "revision": rm["upstream"]["model"]["revision"], "weights_sha256": {k: v["sha256"] for k, v in rm["artifacts"]["weights"].items()}, "runtime_manifest_utc": rm.get("utc_load"),
                                          "runtime_manifest_host": rm.get("hardware", {}).get("host"), "checks": rm.get("checks")},
                       "runtime": {"engine": rm.get("engine"), "python": rm.get("python"), "serve_env": rm.get("serve_env"), "port": rm.get("port"), "runtime_verified_on_this_host": verified},
                       "note": "non-generative typed-decision model; answers with option probabilities"},
           "context_file": f"demo/recorded/context_compare/eca_v01/{man['file']}", "context_sha256_seen": hashlib.sha256(raw).hexdigest(), "context_byte_count_seen": len(raw), "expected_sha256": man["sha256"],
           "expected_byte_count": man["byte_count"], "context_identity_match": "PASS", "request_contract": "POST /v1/systemone {state, model, questions:{move}} (typed choice)", "request_sha256": hashlib.sha256(body).hexdigest(),
           "request_body_len": len(body), "params": {"readout": "shim serve_env (targeted readout); no sampling parameters"}, "platform": platform.platform(), "start_utc": now(), "executed": False}
    print("START", res["start_utc"], "verified_runtime=", verified, flush=True)
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/systemone", data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=1800) as r:
            res["response"] = json.loads(r.read())
        res["executed"] = True
        res["backend"]["model"] = res["response"].get("model")
    except Exception as e:
        res["error"], res["error_type"] = f"{type(e).__name__}: {e}"[:300], type(e).__name__
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["end_utc"] = now()
    finish(res, a.out or OUT / f"arm_openjev_pro_{a.which}.json")

if a.cmd == "run-liquid":
    raw, man = load_context(a.which)
    from urllib.parse import urlparse
    if urlparse(a.endpoint).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("STOP: non-loopback endpoint refused")
    body = bc.liquid_body(raw, a.model)
    res = {"schema": "agent-foundry.arm_result.v1", "host": a.host, "topology": a.topology, "which": a.which,
           "backend": {"family": "liquid", "label": a.label, "provider": "ollama", "provider_kind": "real", "model": a.model, "model_identity": a.model_identity or "NOT_RECORDED", "runtime": "Ollama (loopback)"},
           "context_file": f"demo/recorded/context_compare/eca_v01/{man['file']}", "context_sha256_seen": hashlib.sha256(raw).hexdigest(), "context_byte_count_seen": len(raw), "expected_sha256": man["sha256"],
           "expected_byte_count": man["byte_count"], "context_identity_match": "PASS", "request_contract": "Ollama /api/generate, JSON-schema constrained {choice}", "request_sha256": hashlib.sha256(body).hexdigest(),
           "request_body_len": len(body), "params": {"temperature": 0, "seed": 0, "num_predict": 32}, "platform": platform.platform(), "start_utc": now(), "executed": False}
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(a.endpoint.rstrip("/") + "/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=900) as r:
            res["response"] = json.loads(r.read())
        res["executed"] = True
    except Exception as e:
        res["error"], res["error_type"] = f"{type(e).__name__}: {e}"[:300], type(e).__name__
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["end_utc"] = now()
    finish(res, a.out or OUT / f"arm_liquid_{a.label.lower()}_{a.which}.json")


if a.cmd == "route-failure":
    from agent_foundry.recorder import RunRecorder, read_run
    ts = now()
    rec = RunRecorder("eca-v01-route-attempts", OUT)
    SYSTEM = {"kind": "system", "name": "agent-foundry-context-compare"}
    start = rec.record("run_started", SYSTEM, {"task_id": "eca-route-attempts", "run_type": "ROUTE_ATTEMPTS", "question": "Which execution topology could run OpenJEV against the frozen context?",
                                               "limits": ["a failed route is preserved, not hidden", "machines are NOT identical environments; machine difference is context, not evidence difference"]},
                       meta={"config": {"frozen_context_sha256": json.loads((OUT / 'context_manifest.json').read_text())['contexts']['primary']['sha256']}, "label": "CONTROL_RUN"}, ts=ts)
    obs = [{"observed_by": "operator", "when": "2026-09-29 (message during this session)", "statement": "OpenJEV cannot connect to magicSTUDIObox", "verified_by_agent": False, "cause": "UNKNOWN"},
           {"observed_by": "agent", "check": "tunnel ports 21434 (Studio Ollama), 18484 (Studio Ollarma), 18000 (Studio Watchtower) on this machine", "result": "connection refused on all three", "utc": "2026-09-29T21:5x", "note": "the operator-managed SSH tunnel is not up"},
           {"observed_by": "agent", "check": "ssh magicSTUDIObox from this workspace", "result": "blocked by the workspace security guard (Security: ssh blocked in workspace); not attempted by other means", "utc": "2026-09-29"},
           {"observed_by": "prior evidence (jev-space-invaders evidence/openjev/STUDIO_DISK_RECEIPT.json, 2026-09-28)", "statement": "an earlier Studio shim launch failed (missing openai), then stopped at the MLX shim's targeted-readout capability gate: M4B_STOPPED_NOT_TESTED"},
           {"observed_by": "prior evidence (same repo RUNTIME_MANIFEST.json)", "statement": "OPENJEV_LOADED=YES was once recorded on magicSTUDIObox.local (2026-09-29T00:19Z), so the current failure is not explained by absence of weights"}]
    f = rec.record("failure", {"kind": "tool", "name": "openjev-studio-route", "provider": "openjev", "provider_kind": "real"},
                   {"where": "route_openjev_via_magicSTUDIObox", "error_type": "OPENJEV_STUDIO_CONNECTIVITY_FAILED", "message": "OPENJEV_STUDIO_CONNECTIVITY=FAILED", "recoverable": True, "normalized_kind": "FailureEvent", "observations": obs,
                    "attempted_topology": "OpenJEV on magicSTUDIObox (compute lane)"}, deps=[start["event_id"]], ts=ts)
    d = rec.record("decision", SYSTEM, {"decision": "ALTERNATE_TOPOLOGY", "attempted": "OpenJEV on magicSTUDIObox", "chosen": "OpenJEV on magicPRObox; LiquidAI on magicSTUDIObox; both against the exact same frozen context bytes",
                                        "rationale": "the failure is preserved as a receipt and is not demo-blocking; bounded recovery: attempted topology -> failed -> preserved -> alternate valid topology -> experiment continues"}, state="PROPOSED", deps=[f["event_id"]], ts=ts)
    rec.record("run_completed", SYSTEM, {"status": "completed"}, state="EXECUTED", deps=[d["event_id"]], ts=ts)
    read_run(rec.path)
    wj(OUT / "route_failure_receipt.json", {"schema": "agent-foundry.route_failure_receipt.v1", "OPENJEV_STUDIO_CONNECTIVITY": "FAILED", "recorded_utc": ts, "observations": obs,
                                            "consequence": "not demo-blocking; alternate topology used", "run": "eca-v01-route-attempts.jsonl"})
    print("OPENJEV_STUDIO_CONNECTIVITY=FAILED recorded")


def load_arm(path):
    b = Path(path).read_bytes()
    r = json.loads(b)
    r["_file_sha256"] = hashlib.sha256(b).hexdigest()
    return r, b


if a.cmd == "compare":
    from agent_foundry import dataset_graph as dg, moddik_graph as mg
    from agent_foundry.compare import compare_runs
    A, Ab = load_arm(a.a)
    B, Bb = load_arm(a.b)
    raw, man = load_context(a.which)
    fc, fe = dfco.load_canonical_sub("context_compare")
    ctx_fco = next(f for f in fc.values() if f["object_type"] == "CanonicalContextFCO" and f["content_hash"] == man["fco_content_hash"])
    cid = man["content_id"]
    q = bc.parse_context(raw)["question"]
    def recompute_request(arm):
        return hashlib.sha256(bc.openjev_body(raw) if arm["backend"]["family"] == "openjev" else bc.liquid_body(raw, arm["backend"]["model"])).hexdigest()
    checks = {"SAME_CONTEXT_BYTES": all(x["context_sha256_seen"] == man["sha256"] and x["context_byte_count_seen"] == man["byte_count"] for x in (A, B)) and A["context_byte_count_seen"] == B["context_byte_count_seen"],
              "SAME_CONTEXT_HASH": A["context_sha256_seen"] == B["context_sha256_seen"] == man["sha256"],
              "SAME_EVIDENCE_ORDER": A["context_file"] == B["context_file"] and len(ctx_fco["body"]["ordered_evidence_ids"]) > 0,
              "SAME_QUESTION": q == ctx_fco["body"]["question"],
              "REQUESTS_DERIVED_FROM_FROZEN_BYTES": all(recompute_request(x) == x["request_sha256"] for x in (A, B)),
              "BOTH_ARMS_SELF_REPORT_IDENTITY_PASS": A.get("context_identity_match") == "PASS" and B.get("context_identity_match") == "PASS"}
    ident = all(checks.values())
    d = OUT / a.name
    d.mkdir(parents=True, exist_ok=True)
    if not ident:
        wj(d / "comparison.json", {"schema": "agent-foundry.backend_comparison.v1", "CONTEXT_IDENTITY_MATCH": "FAIL", "identity_checks": checks, "note": "comparison NOT executed: inputs are not equivalent"})
        raise SystemExit("STOP: CONTEXT_IDENTITY_MATCH=FAIL")
    for x, name in ((A, "a"), (B, "b")):
        pass
    import shutil
    import tempfile

    def stream(arm, tag):
        rid = f"eca-v01-{a.name}-{tag}"
        with tempfile.TemporaryDirectory() as td:  # streams are deterministic: keep an identical existing file, refuse a different one
            ev = cf.arm_stream(arm, raw, ctx_fco, td, rid, arm["start_utc"], q)
            new = (Path(td) / f"{rid}.jsonl").read_bytes()
            dst = d / f"{rid}.jsonl"
            if dst.exists() and dst.read_bytes() != new:
                raise SystemExit(f"REFUSED: {dst} exists with different content (append-only)")
            dst.write_bytes(new)
        return ev

    sa, sb = stream(A, "a"), stream(B, "b")
    na, nb = bc.normalize(A), bc.normalize(B)
    beh = bc.compare_behavior(na, nb)
    raw_cmp = compare_runs(sa, sb)
    fd = raw_cmp["FIRST_DIVERGENCE"]
    mk_arm = lambda arm, ab, path, n: dfco.build_fco("ArmResultFCO", {"file": path, "sha256": arm["_file_sha256"], "byte_length": len(ab), "arm": arm["which"], "backend_label": arm["backend"]["label"], "host": arm["host"],
                                                                      "choice": n["choice"], "context_content_id": cid, "executed": arm["executed"], "custody_state": "RESULT_FILE_COMMITTED", "raw_bytes_state": "PRESENT"},
                                                     content_hash="sha256:" + arm["_file_sha256"], canonicalization_method="sha256 over the exact arm-result file bytes", source_or_derivative="derivative",
                                                     parent_hashes=[ctx_fco["content_hash"]], created_at=arm["end_utc"], run_id=f"eca-v01-{a.name}", actor_id="agent-foundry-context-compare", claim_ceiling=cf.CEILING)
    fa, fb = mk_arm(A, Ab, str(Path(a.a).relative_to(ROOT)) if Path(a.a).is_absolute() else a.a, na), mk_arm(B, Bb, str(Path(a.b).relative_to(ROOT)) if Path(a.b).is_absolute() else a.b, nb)
    edges = [dfco.build_edge("derived_from", f["content_hash"], ctx_fco["content_hash"], basis="arm executed against exactly these frozen context bytes", relationship_status="OBSERVED_EXECUTION", created_at=max(A["end_utc"], B["end_utc"]), run_id=f"eca-v01-{a.name}") for f in (fa, fb)]
    edges.append(dfco.build_edge("compared_with", fa["content_hash"], fb["content_hash"], basis="same frozen context, different backend; roles A/B are labels, not rankings", relationship_status="DECLARED_COMPARISON", created_at=max(A["end_utc"], B["end_utc"]), run_id=f"eca-v01-{a.name}"))
    for f in (fa, fb):
        wj(ROOT / "fco" / "objects" / "context_compare" / f"{f['content_hash'].split(':')[1]}.json", f)
    ep = ROOT / "fcg" / "edges" / "context_compare" / f"CONTEXT_COMPARE_{a.name}.jsonl"
    if not ep.exists():
        ep.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edges))
    receipt = {"schema": "agent-foundry.backend_comparison.v1", "name": a.name, "which": a.which, "context_content_id": cid, "context_byte_count": man["byte_count"], "CONTEXT_IDENTITY_MATCH": "PASS", "identity_checks": checks,
               "arm_a": {"label": A["backend"]["label"], "host": A["host"], "runtime": A["backend"].get("runtime"), "model": A["backend"].get("model"), "result_file_sha256": A["_file_sha256"], "start_utc": A.get("start_utc"),
                         "end_utc": A.get("end_utc"), "latency_ms": A.get("latency_ms"), "normalized": na, "executed": A["executed"]},
               "arm_b": {"label": B["backend"]["label"], "host": B["host"], "runtime": B["backend"].get("runtime"), "model": B["backend"].get("model"), "result_file_sha256": B["_file_sha256"], "start_utc": B.get("start_utc"),
                         "end_utc": B.get("end_utc"), "latency_ms": B.get("latency_ms"), "normalized": nb, "executed": B["executed"]},
               "behavior_comparison": beh, "raw_stream_first_divergence": {"index": fd["index"] if fd else None, "kind": fd["kind"] if fd else None, "control_event": fd and fd["control_event"]["event_type"], "note": "the first content-level divergence of the two provider-neutral streams; the backend is the intentional independent variable"} if fd else "NULL",
               "FIRST_DIVERGENT_EVENT": beh["first_behavioral_divergence"]["event"] if isinstance(beh["first_behavioral_divergence"], dict) else "NONE_IN_COMPARABLE_FIELDS",
               "FIRST_DIVERGENT_FIELD": beh["first_behavioral_divergence"]["field"] if isinstance(beh["first_behavioral_divergence"], dict) else "NONE_IN_COMPARABLE_FIELDS",
               "interpretation_limits": ["a model choice is behavior, not ground truth; no quality claim without a preregistered evaluation", "machine difference is context, not evidence difference; the machines are not identical environments",
                                         "neither backend has a citation channel: evidence USED is NOT_AVAILABLE for both; only evidence SUPPLIED is recorded"]}
    (d / "comparison.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    try:
        drv = mg.connect()
        adm = "context_compare_eca_v01"
        allf, alle = dfco.load_canonical_sub("context_compare")
        prep = read_run(OUT / "eca-v01-prep.jsonl") if False else None
        from agent_foundry.recorder import read_run as rr
        counts = None
        for evs in (rr(OUT / "eca-v01-prep.jsonl"), sa, sb, rr(OUT / "eca-v01-route-attempts.jsonl")):
            counts = dg.project(drv, adm, allf, alle, evs)
        receipt["neo4j_projection"] = counts
        (d / "comparison.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except Exception as e:
        print("NEO4J projection skipped:", type(e).__name__)
    print(json.dumps({k: receipt[k] for k in ("CONTEXT_IDENTITY_MATCH", "identity_checks", "FIRST_DIVERGENT_EVENT", "FIRST_DIVERGENT_FIELD")} | {"a": receipt["arm_a"]["normalized"]["choice"], "b": receipt["arm_b"]["normalized"]["choice"],
                      "raw_stream_first_divergence": receipt["raw_stream_first_divergence"]}, indent=1))


if a.cmd == "verify":
    from agent_foundry import dataset_graph as dg, moddik_graph as mg
    from agent_foundry.recorder import read_run as rr
    res = {"schema": "agent-foundry.context_compare_verification.v1", "checks": {}}
    C = res["checks"]
    man = json.loads((OUT / "context_manifest.json").read_text())
    fc, fe = dfco.load_canonical_sub("context_compare")
    for f in fc.values():
        dfco.validate_fco(f)
    C["fco_schema_valid"] = True
    C["frozen_context_bytes_match_manifest_and_fco"] = all(hashlib.sha256((OUT / c["file"]).read_bytes()).hexdigest() == c["sha256"] == fc[c["fco_content_hash"]]["body"]["sha256"] and len((OUT / c["file"]).read_bytes()) == c["byte_count"] for c in man["contexts"].values())
    C["fco_content_ids_recomputed"] = all(dfco.verify_fco_hash(f) or f["object_type"] in ("CanonicalContextFCO", "ArmResultFCO", "SourceDatasetFile") for f in fc.values())
    C["context_fco_hash_is_sha256_of_exact_bytes"] = all(fc[c["fco_content_hash"]]["content_hash"] == "sha256:" + hashlib.sha256((OUT / c["file"]).read_bytes()).hexdigest() for c in man["contexts"].values())
    C["arm_result_fcos_match_files"] = all(hashlib.sha256((ROOT / f["body"]["file"]).read_bytes()).hexdigest() == f["content_hash"].split(":")[1] for f in fc.values() if f["object_type"] == "ArmResultFCO")
    C["edges_ontology_and_non_causal"] = all(e["ontology_status"] == "FCG_ONTOLOGY_V1.3.0" and e["causal"] is False and e["src_content_hash"] in fc and e["dst_content_hash"] in fc for e in fe)
    arms = sorted(OUT.glob("arm_*.json"))
    frozen_at = man["frozen_at"]
    C["freeze_precedes_every_arm_execution"] = all(json.loads(p.read_text())["start_utc"] > frozen_at for p in arms)
    C["every_arm_saw_the_frozen_bytes"] = all(json.loads(p.read_text())["context_sha256_seen"] == man["contexts"][json.loads(p.read_text())["which"]]["sha256"] and json.loads(p.read_text())["context_identity_match"] == "PASS" for p in arms)
    C["openjev_arms_ran_on_verified_runtime_host"] = all(json.loads(p.read_text())["backend"]["runtime"]["runtime_verified_on_this_host"] for p in arms if "openjev" in p.name)
    comps = sorted(OUT.glob("*/comparison.json"))
    C["comparisons"] = {}
    for p in comps:
        r = json.loads(p.read_text())
        if re.fullmatch(r"(studio_)?(primary|control)", r.get("name") or ""):
            C["comparisons"][r["name"]] = {"identity_all_pass": all(r["identity_checks"].values()), "context_identity_match": r["CONTEXT_IDENTITY_MATCH"], "FIRST_DIVERGENT_EVENT": r["FIRST_DIVERGENT_EVENT"], "FIRST_DIVERGENT_FIELD": r["FIRST_DIVERGENT_FIELD"],
                                           "streams_verified": all(len(rr(OUT / r["name"] / f"eca-v01-{r['name']}-{t}.jsonl")) >= 8 for t in ("a", "b"))}
    C["route_failure_preserved"] = json.loads((OUT / "route_failure_receipt.json").read_text())["OPENJEV_STUDIO_CONNECTIVITY"] == "FAILED"
    drv = mg.connect()
    adm = "context_compare_eca_v01"
    q = lambda c, **k: mg.query(drv, c, **k)
    other_before = q("MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=adm)[0]["n"]
    before, cb = dg.fingerprint(drv, adm), dg.counts(drv, adm)
    dg.clear_admission(drv, adm)
    gone = dg.counts(drv, adm)["nodes"]
    other_mid = q("MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=adm)[0]["n"]
    runs = [OUT / "eca-v01-prep.jsonl", OUT / "eca-v01-route-attempts.jsonl"] + [OUT / r["name"] / f"eca-v01-{r['name']}-{t}.jsonl" for r in (json.loads(p.read_text()) for p in comps) if re.fullmatch(r"(studio_)?(primary|control)", r.get("name") or "") for t in ("a", "b")]
    for rp in runs:
        ca = dg.project(drv, adm, fc, fe, rr(rp))
    after = dg.fingerprint(drv, adm)
    C["neo4j"] = {"nodes_before_delete": cb["nodes"], "nodes_after_delete": gone, "nodes_after_rebuild": ca["nodes"], "relationships_after_rebuild": ca["relationships"], "rebuilt_fco_fcg_subgraph_identical": before == after,
                  "unrelated_nodes_untouched": other_before == other_mid, "causal_like_edges": ca["causal_like_edges"], "by_label": ca["by_label"]}
    skip = {"nodes_before_delete", "nodes_after_delete", "nodes_after_rebuild", "relationships_after_rebuild", "causal_like_edges", "by_label", "FIRST_DIVERGENT_EVENT", "FIRST_DIVERGENT_FIELD", "context_identity_match"}
    flat = []
    def walk(x):
        if isinstance(x, dict):
            [walk(v) for k, v in x.items() if k not in skip]
        elif isinstance(x, bool):
            flat.append(x)
    walk(C)
    res["PASS"] = all(flat) and gone == 0 and C["neo4j"]["causal_like_edges"] == 0 and all(v["context_identity_match"] == "PASS" for v in C["comparisons"].values())
    print(json.dumps(res, indent=1))
    if a.write_receipt:
        res["verified_at"] = now()
        p = ROOT / "provenance" / "context_compare" / f"context_compare_verification_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=2) + "\n")
        print("wrote", p)
    sys.exit(0 if res["PASS"] else 1)
