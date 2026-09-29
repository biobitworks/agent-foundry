"""Metadata-level admission of the IEEE DataPort 'Digital Microfluidics Datasets' page as FCO/FCG objects + an Agent Foundry run + a Neo4j projection.
  python3 scripts/ieee_dmf_admit.py admit  --capture .local/sources/ieee_dmf/capture_<ts>.json
  python3 scripts/ieee_dmf_admit.py verify [--write-receipt]
Raw dataset bytes are ACCESS_BLOCKED (login required; no credentials used). The saved page bytes stay OUTSIDE git (.local/); git gets hashes and pointers only."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_foundry import dataset_fco as dfco, dataset_graph as dg, dataset_run as drun, moddik_graph as mg  # noqa: E402
from agent_foundry.ids import canonical_json  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402

ADMISSION = "ieee_dmf_fco_v01"
RUN_ID = "ieee-dmf-v01"
INTAKE_RUN = "ieee-dmf-v01-intake"
OUT = ROOT / "demo" / "recorded" / "external_datasets" / "ieee_dmf_v01"
ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
a1 = sub.add_parser("admit")
a1.add_argument("--capture", required=True)
a2 = sub.add_parser("verify")
a2.add_argument("--write-receipt", action="store_true")
a = ap.parse_args()
CLAIM = "source-declared metadata only; does not establish the dataset payload, its scientific validity, or the validity/applicability of the declared license"


def write_json(p: Path, obj):
    if p.exists() and json.loads(p.read_text()) != obj:
        raise SystemExit(f"REFUSED: {p} exists with different content (append-only)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


if a.cmd == "admit":
    cap = json.loads(Path(a.capture).read_text())
    page = (ROOT / cap["saved_path"]).read_bytes()
    sha, n = hashlib.sha256(page).hexdigest(), len(page)
    assert str(n) == cap["response_headers"]["Content-Length"], "saved bytes differ from the recorded Content-Length"
    ts = cap["retrieval_timestamp_utc"]
    sw = "sha256:" + hashlib.sha256((ROOT / "agent_foundry" / "dataset_fco.py").read_bytes()).hexdigest()
    md = dfco.extract_page_metadata(page)
    mk = lambda t, body, **kw: dfco.build_fco(t, body, created_at=ts, run_id=INTAKE_RUN, actor_id="agent-foundry-dataset-intake", software_hash=sw, **kw)
    A = mk("SourcePageSnapshot", {"source_url": cap["source_url"], "retrieval_method": cap["retrieval_method"], "user_agent": cap["user_agent"], "retrieval_timestamp_utc": ts,
                                  "http_status": cap["http_status"], "response_headers": cap["response_headers"], "byte_length": n, "saved_filename": Path(cap["saved_path"]).name,
                                  "local_pointer": cap["saved_path"], "bytes_in_git": False, "hash_scope": "the exact saved HTML response bytes of the source PAGE; NOT the dataset payload hash",
                                  "custody_state": "PAGE_BYTES_RETAINED_OUTSIDE_GIT", "raw_bytes_state": "NOT_APPLICABLE (page snapshot)"},
           content_hash="sha256:" + sha, canonicalization_method=dfco.SNAPSHOT_METHOD, source_or_derivative="source",
           claim_ceiling="identity of the captured page bytes only; not the dataset payload; not the truth of the page's claims")
    D = mk("LicenseDeclaration", {"declared_license_url": md["json_ld"]["license"], "declared_in": "page JSON-LD (schema.org Dataset.license)", "visible_in_page_text": False, "verification": "NOT_VERIFIED",
                                  "applicability_to_data_bytes": "UNKNOWN", "site_terms_url": "https://www.ieee.org/about/help/site-terms-conditions.html", "custody_state": "METADATA_ONLY",
                                  "raw_bytes_state": "NOT_APPLICABLE"}, parent_hashes=[A["content_hash"]], source_or_derivative="derivative", claim_ceiling=CLAIM,
           notes="a machine-readable page declaration, not a verified grant; redistribution/derivative/commercial status remain UNKNOWN")
    B = mk("DatasetSource", {"semantic_name": "IEEE_DATAPORT_DIGITAL_MICROFLUIDICS_DATASET", "domain": "digital_microfluidics", "source_url": cap["source_url"], "publisher_repository": "IEEE DataPort",
                             "title": md["title"], "dataset_label_on_page": md["dataset_label_on_page"], "doi": md["doi"], "doi_resolver": f"https://dx.doi.org/{md['doi']}",
                             "citation_authors": md["citation_authors"], "submitted_by": md["submitted_by"], "json_ld_creator": md["json_ld"]["creator"], "date_created_utc": md["date_created_utc"],
                             "last_updated_utc": md["last_updated_utc"], "version": "UNKNOWN (no version field on the page)", "data_format_declared": md["data_format_declared"],
                             "abstract": md["abstract"], "instructions_excerpt": md["instructions_excerpt"], "declared_structure": md["declared_structure"], "camera_declared": md["camera_declared"],
                             "operations_declared": md["operations_declared"], "declared_files": md["declared_files"],
                             "declared_license_url": md["json_ld"]["license"], "license_status": "DECLARED_IN_PAGE_JSON_LD_UNVERIFIED",
                             "access": {"source_page": "PUBLIC (HTTP 200 anonymous)", "data_bytes": "ACCESS_BLOCKED (login required; no credentials used)", "files_require_login": md["files_require_login"],
                                        "file_folder_marked_restricted": md["file_folder_marked_restricted"]},
                             "license_flags": {"REDISTRIBUTION_ALLOWED": "UNKNOWN", "DERIVATIVE_USE_ALLOWED": "UNKNOWN", "COMMERCIAL_USE_STATUS": "UNKNOWN"},
                             "associated_publication": "UNKNOWN (page cites 'our previous research' without a reference)",
                             "source_discrepancies": ["JSON-LD creator (Zhen Gu) differs from the visible Citation Author (Boyi Feng); Zhen Gu is the submitter", "JSON-LD citation URL is empty ('https://dx.doi.org/')",
                                                      "page 'Data Format' is *.npz but the only listed file is DMFDataset.zip (relation unverified)"],
                             "raw_bytes_identity": "NOT_COMPUTED", "custody_state": "METADATA_ONLY", "raw_bytes_state": "ACCESS_BLOCKED"},
           parent_hashes=[A["content_hash"], D["content_hash"]], source_or_derivative="derivative", claim_ceiling=CLAIM,
           notes="views/downloads counters appear only in the rendered DOM and are volatile; deliberately excluded from identity")
    f0 = md["declared_files"][0]
    C = mk("DatasetFile", {"declared_name": f0["name"], "declared_size_text": f0["size_text"], "declared_size_bytes": "UNKNOWN", "sha256": "NOT_COMPUTED", "byte_range": "UNKNOWN", "path_in_dataset": f0["name"],
                           "declared_container": "zip", "declared_inner_format": md["data_format_declared"] + " (page 'Data Format'; relation to zip contents unverified)",
                           "semantics": "declared file of the dataset (metadata-level atom; no bytes obtained)", "custody_state": "METADATA_ONLY", "raw_bytes_state": "ACCESS_BLOCKED"},
           parent_hashes=[B["content_hash"]], source_or_derivative="derivative", claim_ceiling=CLAIM)
    E = lambda rel, s, d, basis, st: dfco.build_edge(rel, s["content_hash"], d["content_hash"], basis=basis, relationship_status=st, created_at=ts, run_id=INTAKE_RUN)
    edges = [E("derived_from", B, A, "DatasetSource fields were extracted deterministically from the snapshot bytes (dataset_fco.extract_page_metadata)", "OBSERVED_DETERMINISTIC_EXTRACTION"),
             E("derived_from", D, A, "license declaration read from the snapshot's JSON-LD", "OBSERVED_DETERMINISTIC_EXTRACTION"),
             E("licensed_under", B, D, "page JSON-LD declares this license URL for the dataset; applicability to the data bytes not verified", "DECLARED_BY_SOURCE_UNVERIFIED"),
             E("part_of", C, B, "the page lists DMFDataset.zip under DATASET FILES of this dataset", "DECLARED_BY_SOURCE")]
    for f in (A, B, C, D):
        write_json(ROOT / "fco" / "objects" / f"{f['content_hash'].split(':')[1]}.json", f)
    ep = ROOT / "fcg" / "edges" / "IEEE_DMF_v01.jsonl"
    if not ep.exists():
        ep.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edges))
    write_json(ROOT / "fco" / "manifests" / "ieee_dmf_v01_source_capture.json", {
        "schema": "agent-foundry.external_source_capture.v1", "source_id": "IEEE_DATAPORT_DIGITAL_MICROFLUIDICS_DATASET", "source_url": cap["source_url"], "doi": md["doi"], "retrieval_timestamp_utc": ts,
        "retrieval_method": cap["retrieval_method"], "http_status": cap["http_status"], "response_headers": cap["response_headers"], "source_type": "source_page_html",
        "SOURCE_BYTES_HASH": "sha256:" + sha, "SOURCE_BYTES_HASH_SCOPE": "exact saved PAGE bytes only; NOT the dataset payload", "source_byte_length": n, "saved_filename": Path(cap["saved_path"]).name,
        "bytes_location": "outside git (.local/sources/ieee_dmf/); redistribution of the page bytes not assessed", "DATASET_PAYLOAD_HASH": "NOT_COMPUTED",
        "gates": {"SOURCE_PAGE_ACCESS": "PUBLIC (HTTP 200 anonymous)", "DATA_BYTES_ACCESS": "ACCESS_BLOCKED (login required; no credentials used; no account created)",
                  "LICENSE": "DECLARED_CC_BY_4.0_IN_PAGE_JSON_LD_UNVERIFIED (not shown in visible page text)", "REDISTRIBUTION_ALLOWED": "UNKNOWN", "DERIVATIVE_USE_ALLOWED": "UNKNOWN", "COMMERCIAL_USE_STATUS": "UNKNOWN",
                  "RAW_PAYLOAD_COMMITTED_TO_GIT": False},
        "dataset_merkle_root": "NOT_COMPUTED (no raw bytes; no governed dataset-admission breakpoint pattern for metadata-only intake)"})
    fcos, edges = dfco.load_canonical()
    try:
        drv = mg.connect()
    except Exception as e:
        drv = None
        print("NEO4J unavailable:", type(e).__name__)
    OUT.mkdir(parents=True, exist_ok=True)
    if drv is not None:
        dg.clear_admission(drv, ADMISSION)
    res = drun.run_admission(fcos, edges, OUT, RUN_ID, ts, drv, ADMISSION)
    print(json.dumps({"fcos": {f["object_type"]: f["content_hash"] for f in fcos.values()}, "edges": [(e["rel"], e["edge_id"][:28]) for e in edges], "run": res["run_path"], "verdict": res["verdict"],
                      "canonical_trace": res["canonical_trace"]["chain_types"], "projection_counts": res["projection_counts"]}, indent=1))
    (OUT / "manifest.json").write_text(json.dumps({"schema": "agent-foundry.external_dataset_recording.v1", "kind": "REAL_EXECUTION_RECORDED", "admission_id": ADMISSION, "level": "METADATA_LEVEL",
                                                   "run_file": f"{RUN_ID}.jsonl", "run_sha256": hashlib.sha256((OUT / f"{RUN_ID}.jsonl").read_bytes()).hexdigest(),
                                                   "limits": ["no raw dataset bytes obtained (ACCESS_BLOCKED)", "no samples/frames atomized", "no Merkle root computed (NOT_COMPUTED)"]}, indent=2) + "\n")
else:
    from agent_foundry.dataset_fco import verify_fco_hash
    res = {"schema": "agent-foundry.dataset_admission_verification.v1", "admission_id": ADMISSION, "checks": {}}
    fcos, edges = dfco.load_canonical()
    C = res["checks"]
    for f in fcos.values():
        dfco.validate_fco(f)
    C["fco_schema_valid"] = True
    C["fco_content_hashes_recomputed"] = all(verify_fco_hash(f) for f in fcos.values())
    man = json.loads((ROOT / "fco" / "manifests" / "ieee_dmf_v01_source_capture.json").read_text())
    snap = next(f for f in fcos.values() if f["object_type"] == "SourcePageSnapshot")
    C["snapshot_hash_equals_capture_manifest"] = snap["content_hash"] == man["SOURCE_BYTES_HASH"] and snap["body"]["byte_length"] == man["source_byte_length"]
    pp = ROOT / snap["body"]["local_pointer"]
    C["snapshot_bytes_present_locally_and_rehash"] = (hashlib.sha256(pp.read_bytes()).hexdigest() == man["SOURCE_BYTES_HASH"].split(":")[1] and pp.stat().st_size == man["source_byte_length"]) if pp.exists() else "NOT_TESTED (bytes not present on this machine)"
    C["edges_resolve_and_not_causal"] = all(e["src_content_hash"] in fcos and e["dst_content_hash"] in fcos and e["causal"] is False for e in edges)
    C["edge_types_declared"] = {e["rel"]: e["ontology_status"] for e in edges}
    C["no_raw_payload_atoms_created"] = {f["object_type"] for f in fcos.values()} == {"SourcePageSnapshot", "DatasetSource", "DatasetFile", "LicenseDeclaration"} and all(f["body"].get("raw_bytes_state") != "PRESENT" for f in fcos.values())
    canon = dfco.trace(fcos, edges, next(f["content_hash"] for f in fcos.values() if f["object_type"] == "DatasetFile"))
    C["canonical_trace"] = {"chain_types": canon["chain_types"], "chain": canon["chain"], "source_url": canon["source_url"], "reaches_authoritative_url": canon["source_url"].startswith("https://ieee-dataport.org/")}
    events = read_run(OUT / f"{RUN_ID}.jsonl")
    C["run_log_integrity"] = True
    C["run_manifest_hash"] = hashlib.sha256((OUT / f"{RUN_ID}.jsonl").read_bytes()).hexdigest() == json.loads((OUT / "manifest.json").read_text())["run_sha256"]
    C["events_reference_fco_content_hashes"] = {e["payload"]["fco_content_hash"] for e in events if e["payload"].get("fco_content_hash")} == set(fcos)
    drv = mg.connect()
    before = dg.fingerprint(drv, ADMISSION)
    cnt_before = dg.counts(drv, ADMISSION)
    moddik_before = mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL RETURN count(n) AS n")[0]["n"]
    dg.clear_admission(drv, ADMISSION)
    gone = dg.counts(drv, ADMISSION)["nodes"]
    moddik_after_delete = mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL RETURN count(n) AS n")[0]["n"]
    cnt_after = dg.project(drv, ADMISSION, fcos, edges, events)
    after = dg.fingerprint(drv, ADMISSION)
    tr = dg.trace(drv, ADMISSION, canon["chain"][0])["paths"]
    C["neo4j"] = {"nodes_before_delete": cnt_before["nodes"], "nodes_after_delete": gone, "nodes_after_rebuild": cnt_after["nodes"], "relationships_after_rebuild": cnt_after["relationships"], "by_label": cnt_after["by_label"], "by_rel": cnt_after["by_rel"],
                  "rebuilt_fco_fcg_subgraph_identical_to_before": before == after, "counts_identical": cnt_before == cnt_after, "unrelated_nodes_untouched": moddik_before == moddik_after_delete,
                  "causal_like_edges": cnt_after["causal_like_edges"], "neo4j_trace_chain_equals_canonical": bool(tr) and tr[0]["chain"] == canon["chain"], "neo4j_trace_types": tr and tr[0]["types"], "neo4j_trace_rels": tr and tr[0]["rels"],
                  "neo4j_terminal_source_url": tr and tr[0]["source_url"]}
    C["dataset_merkle_root"] = "NOT_COMPUTED"
    flat = []
    def walk(x, skip=("by_label", "by_rel", "chain", "chain_types", "source_url", "edge_types_declared", "nodes_before_delete", "nodes_after_delete", "nodes_after_rebuild", "relationships_after_rebuild", "causal_like_edges", "neo4j_trace_types", "neo4j_trace_rels", "neo4j_terminal_source_url", "dataset_merkle_root")):
        if isinstance(x, dict):
            [walk(v) for k, v in x.items() if k not in skip]
        elif isinstance(x, bool):
            flat.append(x)
    walk(C)
    res["PASS"] = all(flat) and C["neo4j"]["nodes_after_delete"] == 0 and C["neo4j"]["causal_like_edges"] == 0
    print(json.dumps(res, indent=1))
    if a.write_receipt:
        res["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        p = ROOT / "provenance" / "dataset" / f"ieee_dmf_admission_verification_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=2) + "\n")
        print("wrote", p)
    sys.exit(0 if res["PASS"] else 1)
