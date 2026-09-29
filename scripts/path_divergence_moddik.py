"""Two-endpoint path divergence over the recorded Moddik nominal/perturbed pair -> PathDivergenceFCO objects + FCG edges + Agent Foundry run + Neo4j projection.
  python3 scripts/path_divergence_moddik.py build
  python3 scripts/path_divergence_moddik.py verify [--write-receipt]
GSTAR_PROGRAM_UNNAMED; not Hydra DeltaG*; G*/DeltaG* are not thermodynamic Gibbs free energy. Missing/undefined quantities stay NOT_COMPUTED."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_foundry import dataset_fco as dfco, dataset_graph as dg, moddik_graph as mg, path_divergence as pd, path_divergence_fco as pf  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402

REC = "demo/recorded/moddik/rehearsal_1"
SUB = "path_divergence"
OUT = ROOT / "demo" / "recorded" / "path_divergence" / "moddik_v01"
ADM = "path_divergence_moddik_v01"
RUN_ID = "pd-moddik-v01"
ap = argparse.ArgumentParser()
sp = ap.add_subparsers(dest="cmd", required=True)
sp.add_parser("build")
v = sp.add_parser("verify")
v.add_argument("--write-receipt", action="store_true")
a = ap.parse_args()


def wj(p: Path, obj):
    if p.exists() and json.loads(p.read_text()) != obj:
        raise SystemExit(f"REFUSED: {p} exists with different content (append-only)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


if a.cmd == "build":
    diag = pd.analyze(ROOT / REC)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    sw = "sha256:" + hashlib.sha256(b"".join((ROOT / "agent_foundry" / f).read_bytes() for f in ("path_divergence.py", "path_divergence_fco.py"))).hexdigest()
    fcos, edges = pf.build_objects(diag, REC, ts, "pd-moddik-v01-intake", sw)
    for f in fcos.values():
        wj(ROOT / "fco" / "objects" / SUB / f"{f['content_hash'].split(':')[1]}.json", f)
    ep = ROOT / "fcg" / "edges" / SUB / "PATH_DIVERGENCE_moddik_v01.jsonl"
    if not ep.exists():
        ep.parent.mkdir(parents=True, exist_ok=True)
        ep.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edges))
    fcos, edges = dfco.load_canonical_sub(SUB)
    try:
        drv = mg.connect()
        dg.clear_admission(drv, ADM)
    except Exception as e:
        drv = None
        print("NEO4J unavailable:", type(e).__name__)
    OUT.mkdir(parents=True, exist_ok=True)
    res = pf.run_diagnosis(fcos, edges, diag, OUT, RUN_ID, ts, drv, ADM)
    (OUT / "manifest.json").write_text(json.dumps({"schema": "agent-foundry.path_divergence_recording.v1", "kind": "REAL_EXECUTION_RECORDED", "admission_id": ADM, "run_file": f"{RUN_ID}.jsonl",
                                                   "run_sha256": hashlib.sha256((OUT / f"{RUN_ID}.jsonl").read_bytes()).hexdigest(), "source_pair": REC, "program": pd.PROGRAM,
                                                   "limits": ["G*/DeltaG*/S*/P(Gamma)/Anticube explanation NOT_COMPUTED", "nominal=predicted role is declared", "simulator has no state dynamics"]}, indent=2) + "\n")
    print(json.dumps({"fcos": {f["body"].get("diagnostic_name", f["object_type"]) + ":" + f["object_type"]: h for h, f in fcos.items() if f["object_type"] == "PathDivergenceFCO"}, "n_fcos": len(fcos), "n_edges": len(edges),
                      "verdict": res["verdict"], "projection_counts": res["projection_counts"]}, indent=1))
else:
    res = {"schema": "agent-foundry.path_divergence_verification.v1", "admission_id": ADM, "checks": {}}
    C = res["checks"]
    fcos, edges = dfco.load_canonical_sub(SUB)
    for f in fcos.values():
        dfco.validate_fco(f)
    C["fco_schema_valid"] = True
    C["fco_content_ids_recomputed"] = all(dfco.verify_fco_hash(f) for f in fcos.values())
    C["edges_resolve_ontology_declared_and_not_causal"] = all(e["src_content_hash"] in fcos and e["dst_content_hash"] in fcos and e["causal"] is False and e["ontology_status"] == "FCG_ONTOLOGY_V1.3.0" for e in edges)
    diag = pd.analyze(ROOT / REC)
    C["first_divergence_reproduced_three_ways"] = diag["reproduction"]["all_agree"]
    C["common_predecessor_identified"] = diag["common_predecessor_identified"]
    pdf = {f["body"]["horizon"]: f for f in fcos.values() if f["object_type"] == "PathDivergenceFCO"}
    rebuilt = {}
    tmp_fcos, tmp_edges = pf.build_objects(diag, REC, "1970-01-01T00:00:00Z", "verify", None)
    C["recomputed_diagnostics_equal_stored"] = all(tmp_fcos[h]["body"] == fcos[h]["body"] for h in tmp_fcos if tmp_fcos[h]["object_type"] in ("PathDivergenceFCO", "EndpointState")) and set(tmp_fcos) == set(fcos)
    C["not_computed_fields_preserved"] = all(pdf[k]["body"]["S_star"]["predicted"]["S_star"] == "NOT_COMPUTED" and pdf[k]["body"]["first_delta_g_star_divergence"].startswith("NOT_COMPUTED") and pdf[k]["body"]["path_weighting"]["status"] == "PROPOSED"
                                             and pdf[k]["body"]["first_anticube_divergence"] == "NOT_COMPUTED_ALL_UNKNOWN" and "DeltaG_star (G* undefined)" in pdf[k]["body"]["unsupported_fields"] for k in pdf)
    C["no_zero_substituted_for_delta_g_star"] = all(x != 0 and not isinstance(x, (int, float)) for k in pdf for x in pdf[k]["body"]["g_star_tracking"]["predicted"]["delta_g_star_per_step"])
    C["endpoint_vs_path_distinction"] = {"T1_ENDPOINT_WRONG": pdf["T1_one_step"]["body"]["classification"]["ENDPOINT_WRONG"]["value"], "T1_DIRECTION_WRONG": pdf["T1_one_step"]["body"]["classification"]["DIRECTION_WRONG"]["value"],
                                        "T2_ENDPOINT_WRONG": pdf["T2_two_endpoint_path"]["body"]["classification"]["ENDPOINT_WRONG"]["value"], "T2_PATH_WRONG": pdf["T2_two_endpoint_path"]["body"]["classification"]["PATH_WRONG"]["value"]}
    ok_split = (pdf["T1_one_step"]["body"]["classification"]["ENDPOINT_WRONG"]["value"] is True and pdf["T2_two_endpoint_path"]["body"]["classification"]["ENDPOINT_WRONG"]["value"] is False
                and pdf["T2_two_endpoint_path"]["body"]["classification"]["PATH_WRONG"]["value"] is True)
    man = json.loads((OUT / "manifest.json").read_text())
    events = read_run(OUT / man["run_file"])
    C["run_log_integrity_and_manifest"] = hashlib.sha256((OUT / man["run_file"]).read_bytes()).hexdigest() == man["run_sha256"]
    drv = mg.connect()
    q = lambda c, **k: mg.query(drv, c, **k)
    before, cb = dg.fingerprint(drv, ADM), dg.counts(drv, ADM)
    other_before = q("MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=ADM)[0]["n"]
    dg.clear_admission(drv, ADM)
    gone = dg.counts(drv, ADM)["nodes"]
    other_mid = q("MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=ADM)[0]["n"]
    ca = dg.project(drv, ADM, fcos, edges, events)
    after = dg.fingerprint(drv, ADM)
    pdf_h = [h for h, f in fcos.items() if f["object_type"] == "PathDivergenceFCO"]
    got = {h: sorted(r["h"] for r in q("MATCH (s:FCO {content_hash:$h, admission_id:$a})-[:DERIVED_FROM*1..4]->(t:FCO {admission_id:$a}) RETURN DISTINCT t.content_hash AS h", h=h, a=ADM)) for h in pdf_h}
    want = {h: sorted(dfco.closure(edges, h)) for h in pdf_h}
    cmp_pairs = sorted((r["s"], r["d"]) for r in q("MATCH (a:FCO {admission_id:$ad})-[:COMPARED_WITH]->(b:FCO {admission_id:$ad}) RETURN a.content_hash AS s, b.content_hash AS d", ad=ADM))
    C["neo4j"] = {"nodes_before_delete": cb["nodes"], "nodes_after_delete": gone, "nodes_after_rebuild": ca["nodes"], "relationships_after_rebuild": ca["relationships"], "by_label": ca["by_label"], "by_rel": ca["by_rel"],
                  "rebuilt_subgraph_identical_to_before": before == after, "counts_identical": cb == ca, "unrelated_nodes_untouched": other_before == other_mid, "causal_like_edges": ca["causal_like_edges"],
                  "lineage_closure_equals_canonical": got == want, "compared_with_pairs_equal_canonical": cmp_pairs == sorted((e["src_content_hash"], e["dst_content_hash"]) for e in edges if e["rel"] == "compared_with"),
                  "closures_reach_run_log_bytes": all(any(fcos[x]["object_type"] == "RunLog" for x in c) for c in want.values())}
    res["distinction_holds"] = ok_split
    skip = {"by_label", "by_rel", "nodes_before_delete", "nodes_after_delete", "nodes_after_rebuild", "relationships_after_rebuild", "causal_like_edges", "endpoint_vs_path_distinction"}
    flat = []
    def walk(x):
        if isinstance(x, dict):
            [walk(v) for k, v in x.items() if k not in skip]
        elif isinstance(x, bool):
            flat.append(x)
    walk(C)
    res["PASS"] = all(flat) and ok_split and C["neo4j"]["nodes_after_delete"] == 0 and C["neo4j"]["causal_like_edges"] == 0
    print(json.dumps(res, indent=1))
    if a.write_receipt:
        res["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        p = ROOT / "provenance" / "path_divergence" / f"path_divergence_verification_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=2) + "\n")
        print("wrote", p)
    sys.exit(0 if res["PASS"] else 1)
