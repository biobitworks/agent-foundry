import json

import pytest
from fastapi.testclient import TestClient

from agent_foundry import dataset_fco as dfco, path_divergence as pd
from agent_foundry.recorder import read_run

ROOT = dfco.ROOT
REC = ROOT / "demo" / "recorded" / "moddik" / "rehearsal_1"
D = pd.analyze(REC)
H1, H2 = D["horizons"]["T1_one_step"], D["horizons"]["T2_two_endpoint_path"]
FCOS, EDGES = dfco.load_canonical_sub("path_divergence")
PDF = {f["body"]["horizon"]: f for f in FCOS.values() if f["object_type"] == "PathDivergenceFCO"}


def _st(vals, ids=("a",)):
    obs = {s: {"value": vals.get(s, 0.0), "unit": pd.UNITS[s]} for s in pd.NUMERIC}
    return {"state_id": "s" + str(sorted(vals.items())) + str(ids), "identity": {"observation": obs, "fcg_state": {"node_content_ids": list(ids)}}}


# ---- recovery of the pair and the first divergence
def test_pair_recovered_and_first_divergence_reproduced_three_independent_ways():
    r = D["reproduction"]
    assert r["compare_runs_index"] == r["raw_scan_index"] == r["resimulation_index"] == 68 and r["all_agree"] and r["prefix_identical_events"] == 68
    assert r["first_divergent_leaf"] == {"sensor": "nutrient", "tick": 9, "nominal_value": 10.197, "perturbed_value": 12.697}
    assert r["recorded_leaves_equal_regenerated_simulation"] and r["perturbation_from_recorded_config"] == {"nutrient@9": 2.5}


def test_common_predecessor_is_one_state_identity_with_two_run_occurrences():
    assert D["common_predecessor_identified"]
    x0 = FCOS[D["x0_state_id"].split("state:")[1]]
    assert {o["run_role"] for o in x0["context"]["occurrences"]} == {"predicted_nominal", "observed_perturbed"}  # context is outside identity
    assert x0["body"]["tick"] == 8


# ---- vector algebra and classification (T1 one step, T2 two-endpoint path)
def test_one_step_transition_is_endpoint_direction_and_magnitude_wrong_only_in_nutrient():
    cv = H1["classification"]["vector_metrics"]
    assert cv["net_vector_predicted"]["nutrient"] == -1.958 and cv["net_vector_observed"]["nutrient"] == 0.542
    assert cv["changed_components"] == ["nutrient"] and cv["endpoint_error_per_component"]["nutrient"] == 2.5
    assert cv["endpoint_error_aggregate"] == {"unit": "mM", "l2_over_changed_components": 2.5, "changed_components": ["nutrient"]}
    lab = H1["classification"]["labels"]
    assert lab["ENDPOINT_WRONG"]["value"] and lab["DIRECTION_WRONG"]["value"] and lab["MAGNITUDE_WRONG"]["value"]
    assert lab["PATH_WRONG"]["value"] == "NOT_EVALUABLE" and lab["TIMING_WRONG"]["value"] is False
    assert cv["direction_error_aggregate"].startswith("NOT_COMPUTED") and cv["magnitude_error_aggregate"].startswith("NOT_COMPUTED")


def test_two_endpoint_path_has_equal_observation_endpoints_but_a_wrong_path_and_different_fcg_state():
    lab = H2["classification"]["labels"]
    assert lab["ENDPOINT_WRONG"]["value"] is False and lab["PATH_WRONG"]["value"] is True and lab["FCG_STATE_ENDPOINT_DIFFERS"]["value"] is True
    assert H2["classification"]["vector_metrics"]["net_vector_predicted"] == H2["classification"]["vector_metrics"]["net_vector_observed"]
    assert H2["classification"]["vector_metrics"]["endpoint_error_aggregate"].startswith("NOT_COMPUTED")  # nothing differs: no fabricated zero aggregate
    assert [d["tick"] for d in H2["path_step_deviation"] if d["observation_deviation_observed_minus_predicted"]] == [9]


def test_action_divergence_and_fcg_localization_use_declared_dependencies_only():
    f = D["fcg"]
    assert f["first_fcg_divergence"]["index"] == 68 and f["first_action_divergence_index"] == 80 and f["changed_without_declared_dependency"] == 0
    assert f["action_divergence"]["nominal"] == "MEDIUM_EXCHANGE_RECOMMENDED" and f["action_divergence"]["perturbed"].startswith("NONE")
    assert f["DELTA_GRAPH_STRUCTURE"].startswith("NOT_EXECUTED")  # the identity diff is not silently relabelled as that component


def test_classification_rules_do_not_force_a_label_on_synthetic_cases():
    x0 = _st({"nutrient": 10.0})
    # magnitude only: same direction, different size
    m = pd.classify(x0, [x0, _st({"nutrient": 8.0})], [x0, _st({"nutrient": 6.0})])["labels"]
    assert m["MAGNITUDE_WRONG"]["value"] and not m["DIRECTION_WRONG"]["value"] and m["ENDPOINT_WRONG"]["value"]
    # timing: the observed end value equals an EARLIER predicted state
    t = pd.classify(x0, [x0, _st({"nutrient": 8.0}), _st({"nutrient": 6.0})], [x0, _st({"nutrient": 8.0}), _st({"nutrient": 8.0})])["labels"]
    assert t["TIMING_WRONG"]["value"] == "NOT_EVALUABLE" and "time-shifted" in t["TIMING_WRONG"]["basis"]
    # identical
    i = pd.classify(x0, [x0, _st({"nutrient": 8.0})], [x0, _st({"nutrient": 8.0})])["labels"]
    assert not i["ENDPOINT_WRONG"]["value"] and not i["DIRECTION_WRONG"]["value"] and not i["MAGNITUDE_WRONG"]["value"]
    # mixed units: no aggregate is invented
    mixed = pd.compare_vectors(x0, _st({"nutrient": 1.0, "pH": 7.0}), _st({"nutrient": 2.0, "pH": 7.5}))
    assert mixed["endpoint_error_aggregate"].startswith("NOT_COMPUTED") and "mixed units" in mixed["endpoint_error_aggregate"]


# ---- Anticube: successor points; UNKNOWN is never equality
def test_anticube_points_are_successors_and_unknown_is_not_comparable():
    a = pd.anticube_point(tick=8)
    b = pd.anticube_point(tick=9, supersedes=a["POINT_SHA256"])
    assert b["SUPERSEDES"] == a["POINT_SHA256"] and a["POINT_SHA256"] != b["POINT_SHA256"] and a["statistical_result_implies_class"] is False
    assert a["EPISTEMIC_STATE"].startswith("NOT_DEFINED") and a["DISPOSITION"].startswith("NOT_COMPUTED")
    for h in (H1, H2):
        assert h["anticube"]["first_anticube_divergence"] == "NOT_COMPUTED_ALL_UNKNOWN" and h["anticube"]["executed"]
        assert all(v.startswith("NOT_EVALUABLE") for row in h["anticube"]["steps"] for v in row.values())


def test_anticube_comparison_finds_the_first_divergence_when_states_are_known():
    mk = lambda t, s, sf: {**pd.anticube_point(tick=t), "SELFNESS": s, "SAFETY": sf}
    r = pd.anticube_compare([mk(0, "SELF", "SAFE"), mk(1, "SELF", "SAFE"), mk(2, "SELF", "SAFE")], [mk(0, "SELF", "SAFE"), mk(1, "SELF", "NON_SAFE"), mk(2, "NON_SELF", "NON_SAFE")])
    assert r["first_anticube_divergence"] == {"step": 1, "dimension": "SAFETY", "predicted": "SAFE", "observed": "NON_SAFE"}


# ---- G* / DeltaG*: never substitute 0
def test_delta_g_star_never_substitutes_zero():
    g = pd.g_star_state()
    assert g["G_star"] == "NOT_COMPUTED" and g["is_thermodynamic_gibbs_free_energy"] is False and g["program"] == "GSTAR_PROGRAM_UNNAMED" and set(g["components"].values()) == {"NOT_EXECUTED"}
    assert pd.delta_g_star(None, g) == "NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR" and pd.delta_g_star(g, g) == "NOT_COMPUTED_G_STAR_UNDEFINED"
    assert pd.delta_g_star({"G_star": 1.5}, {"G_star": 2.0}) == 0.5  # only when both are defined under a frozen frame
    tr = H2["g_star_predicted"]
    assert tr["delta_g_star_per_step"][0] == "NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR" and all(isinstance(x, str) for x in tr["delta_g_star_per_step"])
    assert all(v.startswith("NOT_COMPUTED") for k, v in tr.items() if k in ("mean", "variance", "quantiles", "drift", "persistence", "value_or_distribution"))


def test_s_star_and_path_weighting_stay_not_computed_and_proposed():
    for h in (H1, H2):
        s = h["S_star_predicted"]
        assert s["S_star"] == "NOT_COMPUTED" and s["weights"] == "NOT_PREREGISTERED" and s["tau"] == "NOT_DEFINED" and all(v.startswith("NOT_COMPUTED") for v in s["terms"].values())
    assert D["path_weighting"]["status"] == "PROPOSED" and all(v == "NOT_COMPUTED" for v in D["path_weighting"]["value_per_path"].values())


# ---- the stored diagnostic object
def test_stored_fcos_edges_and_diagnostic_fields():
    assert len(FCOS) == 9 and set(PDF) == {"T1_one_step", "T2_two_endpoint_path"}
    for f in FCOS.values():
        dfco.validate_fco(f)
        assert dfco.verify_fco_hash(f)  # RunLog bytes are re-hashed from the committed files
    assert {e["rel"] for e in EDGES} == {"derived_from", "compared_with"} and all(e["ontology_status"] == "FCG_ONTOLOGY_V1.3.0" and e["causal"] is False for e in EDGES)
    required = ["start_state_id", "predicted_end_state_id", "observed_end_state_id", "first_divergence_event_id", "endpoint_error", "direction_error", "magnitude_error", "first_anticube_divergence",
                "first_delta_g_star_divergence", "first_fcg_divergence", "predicted_path_id", "observed_path_id", "diagnosis", "evidence_ids", "computation_status", "unsupported_fields"]
    for f in PDF.values():
        assert all(k in f["body"] for k in required)
        assert f["body"]["not_hydra_delta_g_star"] is True and f["body"]["is_thermodynamic_gibbs_free_energy"] is False and f["body"]["program"] == "GSTAR_PROGRAM_UNNAMED"
        assert any("EPISTEMIC_STATE" in u for u in f["body"]["unsupported_fields"]) and f["body"]["path_weighting"]["status"] == "PROPOSED"
        assert isinstance(f["body"]["diagnosis"], dict) and f["body"]["evidence_ids"]  # component metrics stay visible: no single unexplained scalar
    assert PDF["T1_one_step"]["body"]["start_state_id"] == D["x0_state_id"] == PDF["T2_two_endpoint_path"]["body"]["start_state_id"]


def test_stored_diagnostics_equal_a_fresh_recomputation():
    fresh, _ = __import__("agent_foundry.path_divergence_fco", fromlist=["x"]).build_objects(D, "demo/recorded/moddik/rehearsal_1", "1970-01-01T00:00:00Z", "t", None)
    assert set(fresh) == set(FCOS)
    for h in fresh:
        if fresh[h]["object_type"] in ("PathDivergenceFCO", "EndpointState"):
            assert fresh[h]["body"] == FCOS[h]["body"]


def test_recorded_run_verifies_and_moddik_pair_is_untouched():
    ev = read_run(ROOT / "demo" / "recorded" / "path_divergence" / "moddik_v01" / "pd-moddik-v01.jsonl")
    assert next(e for e in ev if e["event_type"] == "run_started")["payload"]["run_type"] == "PATH_DIVERGENCE_DIAGNOSIS" and not any(e["event_type"] == "model" for e in ev)
    man = json.loads((REC / "manifest.json").read_text())
    import hashlib
    assert all(hashlib.sha256((REC / f).read_bytes()).hexdigest() == h for f, h in man["files"].items())  # the analysed Moddik pair still matches its own manifest


def test_api_serves_the_diagnostic_reverified():
    from api.server import app
    r = TestClient(app).get("/api/path_divergence/moddik_v01").json()
    assert r["run_sha256_matches_manifest"] and r["fco_hashes_recomputed"] and len(r["diagnostics"]) == 2 and len(r["states"]) == 5 and len(r["run_logs"]) == 2
    assert TestClient(app).get("/api/path_divergence/nope").status_code == 404


def test_neo4j_projection_rebuildable_and_scoped_to_its_admission():
    from agent_foundry import dataset_graph as dg, moddik_graph as mg
    try:
        drv = mg.connect()
    except Exception:
        pytest.skip("project-local Neo4j not reachable (NOT_TESTED)")
    aid = "path_divergence_unit_test"
    ev = read_run(ROOT / "demo" / "recorded" / "path_divergence" / "moddik_v01" / "pd-moddik-v01.jsonl")
    dg.clear_admission(drv, aid)
    other = lambda: mg.query(drv, "MATCH (n) WHERE n.admission_id IS NULL OR n.admission_id <> $a RETURN count(n) AS n", a=aid)[0]["n"]
    ob = other()
    dg.project(drv, aid, FCOS, EDGES, ev)
    before = dg.fingerprint(drv, aid)
    dg.clear_admission(drv, aid)
    assert dg.counts(drv, aid)["nodes"] == 0
    dg.project(drv, aid, FCOS, EDGES, ev)
    assert dg.fingerprint(drv, aid) == before and dg.counts(drv, aid)["causal_like_edges"] == 0
    dg.clear_admission(drv, aid)
    assert other() == ob
    drv.close()
