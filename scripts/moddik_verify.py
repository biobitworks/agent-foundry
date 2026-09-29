"""Independent verification of a recorded Moddik run. Recomputes; trusts nothing stored except the raw bytes.
  python3 scripts/moddik_verify.py [demo/recorded/moddik/rehearsal_1] [--neo4j] [--write-receipt]
Checks: manifest file hashes; run-log integrity (schema, order, id recomputation); every HardwareBreakpoint root recomputed from its stored canonical leaf bytes
(+ FCO reference cross-check when available); every leaf bound to its sensor event; decision -> evidence chain resolves; SOURCE=SIMULATED everywhere;
optional: Neo4j projection is complete vs the canonical log and REBUILDABLE after deleting the projection (canonical log hash unchanged)."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_foundry import merkle, moddik_sim as sim  # noqa: E402
from agent_foundry.ids import canonical_json  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402

args = [x for x in sys.argv[1:] if not x.startswith("--")]
d = Path(args[0]) if args else ROOT / "demo" / "recorded" / "moddik" / "rehearsal_1"
res = {"schema": "agent-foundry.moddik_verification.v1", "target": str(d.relative_to(ROOT)) if d.is_absolute() and ROOT in d.parents else str(d), "checks": {}}
man = json.loads((d / "manifest.json").read_text())
res["checks"]["manifest_file_hashes"] = all(hashlib.sha256((d / f).read_bytes()).hexdigest() == h for f, h in man["files"].items())
ref = merkle.fco_reference_cross_check()
res["checks"]["fco_reference_implementation_present"] = ref is not None
for side in ("control", "variant"):
    ev = read_run(d / f"{side}.jsonl")  # raises on any inconsistency
    c = res["checks"][side] = {"run_log_integrity": True, "events": len(ev)}
    by_id, by_cid = {e["event_id"]: e for e in ev}, {e["content_id"]: e for e in ev}
    c["all_sensor_events_source_simulated"] = all(e["payload"]["source"] == "SIMULATED" for e in ev if e["payload"].get("schema") == sim.LEAF_SCHEMA)
    bps = []
    for e in ev:
        if e["event_type"] != "checkpoint":
            continue
        p = e["payload"]
        rep = merkle.verify_commitment({"leaves": p["commitment"]["leaves"], "MERKLE_ROOT": p["MERKLE_ROOT"], "construction": p["commitment"]["construction"]}, ref)
        bound = all(canonical_json({k: v for k, v in by_cid[cid]["payload"].items() if k not in ("source_ref", "content_digest")}) == r["canonical_bytes_utf8"] for cid, r in zip(p["leaf_content_ids"], p["commitment"]["leaves"]))
        bps.append({"label": p["label"], "tick": p["tick"], "MERKLE_ROOT": p["MERKLE_ROOT"], "recomputed_pass": rep["PASS"], "leaves_bound_to_events": bound, "leaf_count": p["commitment"]["leaf_count"],
                    "checks": rep["checks"]})
    c["breakpoints"] = bps
    c["all_breakpoints_verified"] = bool(bps) and all(b["recomputed_pass"] and b["leaves_bound_to_events"] and b["MERKLE_ROOT"] != "NOT_COMPUTED" for b in bps)
    dec = next((e for e in ev if e["event_type"] == "decision"), None)
    if dec:
        c["decision_evidence_chain_resolves"] = all(i in by_id for i in dec["meta"]["evidence_event_ids"]) and all(x in by_cid for x in dec["payload"]["evidence_content_ids"]) and dec["state"] == "PROPOSED"
        c["decision_actuation"] = dec["payload"]["actuation"]
    else:
        c["decision"] = "NO_DECISION_EVENT (NOT_COMPUTED path)"
    # prefix determinism: breakpoint roots over identical leaves must match between control and variant
ctrl_roots = [b["MERKLE_ROOT"] for b in res["checks"]["control"]["breakpoints"]]
var_roots = [b["MERKLE_ROOT"] for b in res["checks"]["variant"]["breakpoints"]]
res["checks"]["replay_prefix_breakpoint_identical"] = ctrl_roots[0] == var_roots[0]
res["checks"]["divergent_breakpoint_differs"] = ctrl_roots[1] != var_roots[1]
add = d / "plaud_addendum.jsonl"
if add.exists():  # independent audio custody, if present
    ad = read_run(add)
    art = next(e for e in ad if e["event_type"] == "artifact")["payload"]
    pc = res["checks"]["plaud_custody"] = {"addendum_log_integrity": True, "parent_log_binding": ad[0]["payload"]["parent_log_sha256"] == hashlib.sha256((d / "control.jsonl").read_bytes()).hexdigest(),
                                          "relation_is_parallel_capture_not_same_bytes": art["relation_to_parent_run"].startswith("PARALLEL_CAPTURE") and art["same_bytes_as_local_capture"] in (False, art["same_bytes_as_local_capture"]) and art["same_bytes_as_local_capture"] is not True,
                                          "operator_attested": art["operator_attestation"] != "NOT_ATTESTED", "decodable_media_at_import": art.get("media_probe", {}).get("is_media") is True, "recorded": {k: art[k] for k in ("source_filename", "size_bytes", "digest", "imported_at")}}
    if "--plaud-audio" in sys.argv:
        f = Path(sys.argv[sys.argv.index("--plaud-audio") + 1])
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        pc["exported_file_bytes_match_recorded_digest_and_size"] = art["digest"] == f"sha256:{h}" and art["size_bytes"] == f.stat().st_size
if "--neo4j" in sys.argv:
    from agent_foundry import moddik_graph as g
    drv = g.connect()
    ev = read_run(d / "control.jsonl")
    rid = ev[0]["run_id"]
    g.clear_run(drv, rid)
    gone = g.query(drv, "MATCH (n {run_id:$r}) RETURN count(n) AS n", r=rid)[0]["n"]
    before = hashlib.sha256((d / "control.jsonl").read_bytes()).hexdigest()
    proj = g.project_run(drv, ev, d / "control.jsonl")
    n_nodes = g.query(drv, "MATCH (n {run_id:$r}) WHERE NOT n:Run RETURN count(n) AS n", r=rid)[0]["n"]
    dep_edges = g.query(drv, "MATCH (a {run_id:$r})-[e:DECLARED_DEPENDENCY|DERIVED_FROM]->(b) RETURN count(e) AS n", r=rid)[0]["n"]
    want_deps = sum(len(e["deps"]) for e in ev)
    causal = g.query(drv, "MATCH ()-[e]->() WHERE type(e) CONTAINS 'CAUS' RETURN count(e) AS n")[0]["n"]
    res["checks"]["neo4j"] = {"projection_deleted_then_rebuilt": gone == 0 and proj["event_nodes"] > 0, "event_nodes_equal_canonical_events": n_nodes == len(ev),
                              "dependency_edges_equal_canonical_deps": dep_edges == want_deps, "canonical_log_unchanged_by_deletion": hashlib.sha256((d / "control.jsonl").read_bytes()).hexdigest() == before,
                              "no_causal_edges_present": causal == 0, "counts": {"events": len(ev), "nodes": n_nodes, "dep_edges": dep_edges, "canonical_deps": want_deps}}
    drv.close()
flat = []
def walk(x):
    if isinstance(x, dict):
        [walk(v) for k, v in x.items() if k not in ("counts", "checks", "events", "leaf_count", "tick", "label", "MERKLE_ROOT", "decision_actuation", "decision", "recorded")]
    elif isinstance(x, bool):
        flat.append(x)
walk(res["checks"])
res["PASS"] = all(flat)
res["note"] = "integrity/consistency over declared leaves and logs; not physical truth; single recorded execution"
print(json.dumps(res, indent=1))
if "--write-receipt" in sys.argv:
    out = ROOT / "provenance" / "moddik" / f"verification_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    res["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out.write_text(json.dumps(res, indent=2) + "\n")
    print("wrote", out)
sys.exit(0 if res["PASS"] else 1)
