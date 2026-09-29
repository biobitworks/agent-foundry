import copy
import json
import subprocess

import pytest

from agent_foundry import dataset_fco as dfco, dataset_run as drun
from agent_foundry.recorder import read_run

ROOT = dfco.ROOT
FCOS, EDGES = dfco.load_canonical()
BY = {f["object_type"]: f for f in FCOS.values()}

# SYNTHETIC page (not IEEE bytes): exercises the extractor only
FIXTURE = b"""<html><h2 class="title">Datasets <h3>Standard Dataset</h3></h2><h1>Some Dataset</h1>
<script type="application/ld+json">{"@graph":[{"@type":"Dataset","name":"x","creator":{"name":"Sub Mitter"},"license":"https://creativecommons.org/licenses/by/4.0/"}]}</script>
<dl><dt>Citation Author(s):</dt><dd><div>A Author</div></dd><dt>Submitted by:</dt><dd><a>Sub Mitter</a></dd><dt>Date Created:</dt><dd><time datetime="2025-04-10T15:29:45+0000">x</time></dd>
<dt>Last updated:</dt><dd><time datetime="2025-04-11T00:00:00+0000">x</time></dd><dt>DOI:</dt><dd><a href="https://dx.doi.org/10.1234/abcd-ef12">10.1234/abcd-ef12</a></dd></dl>
<p>The dataset comprises 10 samples, each represented as a 4-frame array, resulting in a total of 40 data points.</p></html>"""


def test_extractor_reads_only_declared_fields_and_marks_the_rest_unknown():
    m = dfco.extract_page_metadata(FIXTURE)
    assert m["doi"] == "10.1234/abcd-ef12" and m["title"] == "Some Dataset" and m["dataset_label_on_page"] == "Standard Dataset"
    assert m["declared_structure"]["samples"] == 10 and m["declared_structure"]["data_points"] == 40
    assert m["declared_structure"]["split_test"] == "UNKNOWN" and m["camera_declared"] == "UNKNOWN" and m["declared_files"] == ["UNKNOWN"]
    assert m["json_ld"]["license"].endswith("by/4.0/") and m["files_require_login"] is False


def test_committed_fcos_conform_to_schema_and_recompute_their_content_ids():
    assert set(BY) == {"SourcePageSnapshot", "DatasetSource", "DatasetFile", "LicenseDeclaration"}
    for f in FCOS.values():
        dfco.validate_fco(f)
        assert dfco.verify_fco_hash(f)
    assert BY["SourcePageSnapshot"]["canonicalization_method"] == dfco.SNAPSHOT_METHOD


def test_content_identity_is_separate_from_context_and_tamper_is_detected():
    b = BY["DatasetSource"]
    same = dfco.build_fco(b["object_type"], b["body"], created_at="1999-01-01T00:00:00Z", run_id="another-run", source_or_derivative="derivative", claim_ceiling="x", actor_id="someone-else")
    assert same["content_hash"] == b["content_hash"]  # time/run/actor/status/parents are context, not identity
    t = copy.deepcopy(b)
    t["body"]["doi"] = "10.0000/forged"
    assert not dfco.verify_fco_hash(t)


def test_edges_use_declared_ontology_only_and_never_claim_causality():
    assert {e["rel"] for e in EDGES} == {"derived_from", "licensed_under", "part_of"}
    for e in EDGES:
        assert e["causal"] is False and e["src_content_hash"] in FCOS and e["dst_content_hash"] in FCOS
    assert next(e for e in EDGES if e["rel"] == "part_of")["ontology_status"].startswith("PROPOSED_EXTENSION")
    assert next(e for e in EDGES if e["rel"] == "licensed_under")["relationship_status"] == "DECLARED_BY_SOURCE_UNVERIFIED"
    with pytest.raises(ValueError):
        dfco.build_edge("caused_by", "a", "b", basis="x", relationship_status="x", created_at="t", run_id="r")


def test_trace_reaches_the_authoritative_source_url():
    t = dfco.trace(FCOS, EDGES, BY["DatasetFile"]["content_hash"])
    assert t["chain_types"] == ["DatasetFile", "DatasetSource", "SourcePageSnapshot"] and t["source_url"] == "https://ieee-dataport.org/documents/digital-microfluidics-datasets"


def test_metadata_level_only_no_fabricated_payload_hashes_or_atoms():
    f = BY["DatasetFile"]["body"]
    assert f["sha256"] == "NOT_COMPUTED" and f["raw_bytes_state"] == "ACCESS_BLOCKED" and f["declared_size_bytes"] == "UNKNOWN"
    s = BY["DatasetSource"]["body"]
    assert s["raw_bytes_identity"] == "NOT_COMPUTED" and s["access"]["data_bytes"].startswith("ACCESS_BLOCKED") and s["version"].startswith("UNKNOWN")
    assert s["license_flags"] == {"REDISTRIBUTION_ALLOWED": "UNKNOWN", "DERIVATIVE_USE_ALLOWED": "UNKNOWN", "COMMERCIAL_USE_STATUS": "UNKNOWN"}
    man = json.loads((ROOT / "fco" / "manifests" / "ieee_dmf_v01_source_capture.json").read_text())
    assert man["DATASET_PAYLOAD_HASH"] == "NOT_COMPUTED" and man["gates"]["RAW_PAYLOAD_COMMITTED_TO_GIT"] is False and man["dataset_merkle_root"].startswith("NOT_COMPUTED")
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT).stdout.splitlines()
    assert not [t for t in tracked if t.lower().endswith((".zip", ".npz")) or "ieee_dmf/page_" in t]  # no payload archives and no saved third-party page bytes in git


def test_recorded_run_verifies_and_references_every_fco_by_content_hash():
    ev = read_run(ROOT / "demo" / "recorded" / "external_datasets" / "ieee_dmf_v01" / "ieee-dmf-v01.jsonl")
    assert {e["payload"]["fco_content_hash"] for e in ev if e["payload"].get("fco_content_hash")} == set(FCOS)
    assert next(e for e in ev if e["event_type"] == "run_started")["meta"]["label"] == "CONTROL_RUN"
    assert next(e for e in ev if e["event_type"] == "evaluation")["payload"]["result"] == "PASS"
    assert not any(e["event_type"] == "model" for e in ev)  # provenance traversal only; no model inference


def test_without_neo4j_the_run_reports_not_computed_instead_of_faking_a_pass(tmp_path):
    r = drun.run_admission(FCOS, EDGES, tmp_path, "t-ds", "2026-09-29T20:45:47Z", drv=None)
    assert r["verdict"].startswith("NOT_COMPUTED") and r["canonical_trace"]["chain_types"][-1] == "SourcePageSnapshot"


def test_neo4j_projection_is_rebuildable_and_scoped_to_its_admission():
    from agent_foundry import dataset_graph as dg, moddik_graph as mg
    try:
        drv = mg.connect()
    except Exception:
        pytest.skip("project-local Neo4j not reachable (NOT_TESTED)")
    aid = "ieee_dmf_fco_v01_unit_test"
    ev = read_run(ROOT / "demo" / "recorded" / "external_datasets" / "ieee_dmf_v01" / "ieee-dmf-v01.jsonl")
    dg.clear_admission(drv, aid)
    other_before = mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=aid)[0]["n"]
    dg.project(drv, aid, FCOS, EDGES, ev)
    before, tr = dg.fingerprint(drv, aid), dg.trace(drv, aid, BY["DatasetFile"]["content_hash"])["paths"]
    assert tr and tr[0]["chain"] == dfco.trace(FCOS, EDGES, BY["DatasetFile"]["content_hash"])["chain"]
    dg.clear_admission(drv, aid)
    assert dg.counts(drv, aid)["nodes"] == 0
    dg.project(drv, aid, FCOS, EDGES, ev)
    assert dg.fingerprint(drv, aid) == before and dg.counts(drv, aid)["causal_like_edges"] == 0
    dg.clear_admission(drv, aid)
    assert mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=aid)[0]["n"] == other_before
    drv.close()
