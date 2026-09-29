"""Two-endpoint path divergence diagnosis (bounded prototype) over a recorded nominal/perturbed pair.

Program naming: GSTAR_PROGRAM_UNNAMED. This is NOT Hydra DeltaG*. G*/DeltaG* here are dimensionless graph/state surrogates and are NEVER thermodynamic Gibbs free energy.

What is DEFINED in the recovered project artifacts, and therefore implemented:
  * Anticube: SELFNESS x SAFETY (UNKNOWN preserved), successor points via SUPERSEDES, no inference from statistical/verifier results
    (cloudmer/src/cloudmer/fop/anticube.py; CORE_MSM_FCG_ANTICUBE_DELTA_G_MODEL_v1.md; PROJECT_INTENT_QUADRANT_CONTRACT_v1.md).
  * DeltaG* is a VECTOR of components (DELTA_PREDICTION, DELTA_INFORMATION, DELTA_GRAPH_STRUCTURE, DELTA_REPLAY, DELTA_CUSTODY, DELTA_COMPLEXITY) that default to
    NOT_EXECUTED; scalarization is forbidden without preregistration; hash distance is forbidden (cloudmer/.../delta_graph_star.py).
    G_info requires a valid probabilistic comparison frame (KL(q||p) + comparator constant); otherwise NOT_COMPARABLE.
NOT defined there (so NOT_COMPUTED here): EPISTEMIC_STATE and DISPOSITION as Anticube dimensions; delta_g_star_cost / anticube_cost / fcg_edge_cost / uncertainty_cost /
hysteresis_cost as executed terms with frozen weights; tau; q(Gamma); M_A(Gamma). The only executed S*/exp(-S*/tau) code found (fco-r18 path_sum.py) labels itself an
EDITORIAL heuristic with unfrozen weights over a different graph, so it is not reused.

The observation vector (sensor readings) is a DOMAIN extension of X_t used for displacement arithmetic; categorical parts (actions, Anticube) are never subtracted.
The nominal run is assigned the PREDICTED role and the perturbed run the OBSERVED role by declaration of this analysis: no independent model prediction exists in the artifacts.
"""
import hashlib
import json
from pathlib import Path

from . import moddik_sim as sim
from .compare import compare_runs
from .dataset_fco import content_hash_of
from .ids import canonical_json, sha256_hex
from .recorder import read_run

PROGRAM = "GSTAR_PROGRAM_UNNAMED"
NUMERIC = [s for s in sim.SENSORS]  # pH, O2, CO2, nutrient, waste, mechanical_stress
UNITS = {s: sim.SENSORS[s][0] for s in sim.SENSORS}
DELTA_COMPONENTS = ("DELTA_PREDICTION", "DELTA_INFORMATION", "DELTA_GRAPH_STRUCTURE", "DELTA_REPLAY", "DELTA_CUSTODY", "DELTA_COMPLEXITY")
ANTICUBE_DIMS = ("SELFNESS", "SAFETY", "EPISTEMIC_STATE", "DISPOSITION")
NC = "NOT_COMPUTED"
LEAF_ENVELOPE = ("source_ref", "content_digest")


# ------------------------------------------------------------------ Anticube (successor points, never mutated)
def anticube_point(*, tick: int, supersedes: str = None) -> dict:
    p = {"schema": "agent-foundry.anticube_point.v1", "SELFNESS": "UNKNOWN", "SAFETY": "UNKNOWN",
         "EPISTEMIC_STATE": "NOT_DEFINED_IN_RECOVERED_ARTIFACTS", "DISPOSITION": NC + " (requires known SELFNESS and SAFETY; default disposition table has no UNKNOWN row)",
         "PREDICATE_IDS": [], "EVIDENCE_FCOS": [], "TIME": tick, "SUPERSEDES": supersedes, "statistical_result_implies_class": False,
         "note": "no Anticube predicates were assessed for this simulation; verifier PASS and workflow abstention are NOT mapped to Anticube classes"}
    p["POINT_SHA256"] = sha256_hex(canonical_json(p))
    return p


def anticube_compare(pred_chain: list, obs_chain: list) -> dict:
    """First step at which a KNOWN Anticube dimension differs. UNKNOWN / NOT_* on either side is not evaluable, never 'equal'."""
    steps = []
    first = None
    for i, (a, b) in enumerate(zip(pred_chain, obs_chain)):
        row = {}
        for d in ANTICUBE_DIMS:
            va, vb = a[d], b[d]
            known = lambda v: v not in ("UNKNOWN", "ABSTAIN") and not str(v).startswith(("NOT_", "NOT_DEFINED"))
            if known(va) and known(vb):
                row[d] = "DIFFERENT" if va != vb else "SAME"
                if va != vb and first is None:
                    first = {"step": i, "dimension": d, "predicted": va, "observed": vb}
            else:
                row[d] = "NOT_EVALUABLE (UNKNOWN/NOT_DEFINED on at least one side)"
        steps.append(row)
    return {"first_anticube_divergence": first or "NOT_COMPUTED_ALL_UNKNOWN", "steps": steps, "executed": True}


# ------------------------------------------------------------------ G* / DeltaG*
def g_star_state() -> dict:
    return {"program": PROGRAM, "G_star": NC, "is_thermodynamic_gibbs_free_energy": False,
            "reason": ["no probabilistic comparison frame: sensor readings are point observations and the model output is not a distribution (G_info needs KL(q||p))",
                       "no frozen target/comparison frame", "DeltaG* component definitions have no executed, frozen implementation in the recovered artifacts"],
            "components": {c: "NOT_EXECUTED" for c in DELTA_COMPONENTS}, "uses_hash_distance": False}


def delta_g_star(prev: dict, cur: dict):
    """DeltaG*(t) = G*(t) - G*(t-1) for comparable states only. Never substitutes 0."""
    if prev is None:
        return "NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR"
    if prev.get("G_star") == NC or cur.get("G_star") == NC:
        return "NOT_COMPUTED_G_STAR_UNDEFINED"
    return cur["G_star"] - prev["G_star"]  # only reachable when both are numbers under a frozen frame


def g_star_tracking(states: list) -> dict:
    return {"value_or_distribution": NC + " (no G* values, no distributions)", "mean": NC + " (no distribution)", "variance": NC + " (no distribution)", "quantiles": NC + " (no distribution)",
            "drift": NC + " (needs a G* time series)", "persistence": NC + " (needs a G* time series)", "n_states": len(states),
            "delta_g_star_per_step": [delta_g_star(None if i == 0 else states[i - 1]["identity"]["g_star_state"], s["identity"]["g_star_state"]) for i, s in enumerate(states)]}


# ------------------------------------------------------------------ states
def _leaf(e):
    return {k: v for k, v in e["payload"].items() if k not in LEAF_ENVELOPE}


def is_leaf(e):
    return e["event_type"] == "evidence" and e["payload"].get("schema") == sim.LEAF_SCHEMA


def build_state(events: list, tick: int, role: str, run_sha: str, prev_point: dict = None) -> dict:
    idx = {e["event_id"]: i for i, e in enumerate(events)}
    leaves = {e["payload"]["sensor"]: (i, e) for i, e in enumerate(events) if is_leaf(e) and e["payload"]["tick"] == tick}
    last = max(i for i, _ in leaves.values())
    inc = events[: last + 1]
    cid = {e["event_id"]: e["content_id"] for e in inc}
    pairs = sorted((cid[e["event_id"]], cid[d]) for e in inc for d in e["deps"])
    ap = anticube_point(tick=tick, supersedes=prev_point["POINT_SHA256"] if prev_point else None)
    identity = {"schema": "agent-foundry.endpoint_state.v1", "domain": "moddik-local-simulation (SOURCE=SIMULATED)", "tick": tick, "sim_time_s": tick * sim.TICK_SECONDS,
                "observation": {s: {"value": leaves[s][1]["payload"]["value"], "unit": UNITS.get(s, "state")} for s in NUMERIC + ["actuator_state"]},
                "fcg_state": {"last_event_index": last, "node_count": len(inc), "node_content_ids": [e["content_id"] for e in inc], "edge_count": len(pairs),
                              "edges_sha256_identity_only": sha256_hex(canonical_json(pairs))},
                "anticube_state": ap, "g_star_state": g_star_state(), "timestamp_or_sequence": {"tick": tick, "sim_time_s": tick * sim.TICK_SECONDS, "last_event_index": last}}
    sid = "state:" + content_hash_of("EndpointState", identity)
    return {"state_id": sid, "identity": identity, "context": {"run_role": role, "run_id": events[0]["run_id"], "source_run_sha256": run_sha, "last_event_id": events[last]["event_id"],
                                                             "evidence_event_ids": {s: leaves[s][1]["event_id"] for s in NUMERIC + ["actuator_state"]}}, "_events_upto": last}


# ------------------------------------------------------------------ vector algebra (per component, native units; no invented weights)
def displacement(x0: dict, x1: dict) -> dict:
    return {s: round(x1["identity"]["observation"][s]["value"] - x0["identity"]["observation"][s]["value"], 6) for s in NUMERIC}


def sign(v):
    return (v > 0) - (v < 0)


def compare_vectors(x0, pred, obs) -> dict:
    """endpoint / direction / magnitude errors per component. Aggregates only where all involved components share one unit."""
    dp, do = displacement(x0, pred), displacement(x0, obs)
    end = {s: round(obs["identity"]["observation"][s]["value"] - pred["identity"]["observation"][s]["value"], 6) for s in NUMERIC}
    direction = {s: {"predicted_sign": sign(dp[s]), "observed_sign": sign(do[s]), "flipped": sign(dp[s]) != sign(do[s])} for s in NUMERIC}
    magnitude = {s: {"predicted_abs": abs(dp[s]), "observed_abs": abs(do[s]), "abs_difference": round(abs(do[s]) - abs(dp[s]), 6)} for s in NUMERIC}
    changed = [s for s in NUMERIC if end[s] != 0]
    units = {UNITS[s] for s in changed}
    agg = ({"unit": next(iter(units)), "l2_over_changed_components": round(sum(end[s] ** 2 for s in changed) ** 0.5, 6), "changed_components": changed}
           if len(units) == 1 else (NC + " (no differing components)" if not units else NC + " (mixed units; no preregistered weighting)"))
    return {"net_vector_predicted": dp, "net_vector_observed": do, "endpoint_error_per_component": end, "endpoint_error_aggregate": agg,
            "direction_error_per_component": direction, "direction_error_aggregate": NC + " (cosine/angle across mixed units is not defined without preregistered scaling)",
            "magnitude_error_per_component": magnitude, "magnitude_error_aggregate": NC + " (mixed units; no preregistered weighting)",
            "changed_components": changed, "units": UNITS}


def classify(x0, chain_pred: list, chain_obs: list) -> dict:
    """Deterministic rules over recorded evidence. Each label is TRUE / FALSE / NOT_EVALUABLE with its basis; nothing is forced."""
    cv = compare_vectors(x0, chain_pred[-1], chain_obs[-1])
    endpoint_diff = bool(cv["changed_components"])
    flips = [s for s, d in cv["direction_error_per_component"].items() if d["flipped"] and (d["predicted_sign"] or d["observed_sign"])]
    mag = [s for s, d in cv["magnitude_error_per_component"].items() if d["abs_difference"] != 0 and s in cv["changed_components"]]
    inter = list(zip(chain_pred[1:-1], chain_obs[1:-1]))
    path_dev = [i + 1 for i, (p, o) in enumerate(inter) if any(p["identity"]["observation"][s]["value"] != o["identity"]["observation"][s]["value"] for s in NUMERIC)]
    # timing: does any observed end value appear at a different tick of the predicted path?
    shifted = []
    if endpoint_diff:
        for s in cv["changed_components"]:
            v = chain_obs[-1]["identity"]["observation"][s]["value"]
            for i, p in enumerate(chain_pred):
                if i != len(chain_pred) - 1 and p["identity"]["observation"][s]["value"] == v:
                    shifted.append({"component": s, "matches_predicted_step": i})
    out = {
        "ENDPOINT_WRONG": {"value": endpoint_diff, "basis": f"observation endpoint differs in {cv['changed_components']}" if endpoint_diff else "observation endpoint identical in every component (exact equality; deterministic simulation)"},
        "DIRECTION_WRONG": {"value": bool(flips), "basis": f"displacement sign flipped in {flips}" if flips else "no displacement sign flips"},
        "MAGNITUDE_WRONG": {"value": bool(mag), "basis": f"|displacement| differs in {mag} (native units)" if mag else "net displacement magnitudes identical"},
        "PATH_WRONG": ({"value": bool(path_dev), "basis": f"intermediate state(s) at step {path_dev} differ" if path_dev else "intermediate states identical"} if inter else
                       {"value": "NOT_EVALUABLE", "basis": "single-step horizon: no intermediate states"}),
        "TIMING_WRONG": {"value": False if not shifted else "NOT_EVALUABLE", "basis": "no observed end value matches an earlier predicted state (no time-shifted match)" if not shifted else f"time-shifted matches {shifted} (not asserted)"},
    }
    # endpoint identity of non-numeric parts, reported separately
    fp, fo = chain_pred[-1]["identity"]["fcg_state"], chain_obs[-1]["identity"]["fcg_state"]
    out["FCG_STATE_ENDPOINT_DIFFERS"] = {"value": fp["node_content_ids"] != fo["node_content_ids"], "basis": "node content-id sets of the FCG state (identity comparison, not hash distance)"}
    return {"labels": out, "vector_metrics": cv}


# ------------------------------------------------------------------ candidate paths and S*
def path_id(chain: list) -> str:
    return "path:sha256:" + sha256_hex(canonical_json([s["state_id"] for s in chain]))


def s_star(chain: list) -> dict:
    """S*[Gamma] = sum over transitions of delta_g_star_cost + anticube_cost + fcg_edge_cost + uncertainty_cost + hysteresis_cost. Only defined terms with frozen weights may be computed."""
    reason = "no executed definition with preregistered/frozen weight in the recovered artifacts"
    return {"S_star": NC, "terms": {"delta_g_star_cost": NC + " (DeltaG* NOT_COMPUTED)", "anticube_cost": NC + " (Anticube supplies admissibility separately; no cost defined)",
                                    "fcg_edge_cost": NC + " (" + reason + ")", "uncertainty_cost": NC + " (" + reason + ")", "hysteresis_cost": NC + " (" + reason + ")"},
            "n_transitions": len(chain) - 1, "weights": "NOT_PREREGISTERED", "tau": "NOT_DEFINED"}


def candidate_weighting(paths: dict) -> dict:
    return {"status": "PROPOSED", "formula": "P(Gamma) ~ q(Gamma) * M_A(Gamma) * exp(-S_star[Gamma] / tau)", "value_per_path": {k: NC for k in paths},
            "reason": "no executed implementation and no frozen parameters (q, M_A, tau, weights) exist in the project; the fco-r18 path_sum.py heuristic is editorial and not GSTAR"}


# ------------------------------------------------------------------ independent reproduction of the first divergent event
def reproduce_first_divergence(control: list, variant: list) -> dict:
    m1 = compare_runs(control, variant)["FIRST_DIVERGENCE"]["index"]
    m2 = next(i for i in range(min(len(control), len(variant))) if control[i]["content_id"] != variant[i]["content_id"])
    perturb = {tuple(k.split("@")[0:1]) + (int(k.split("@")[1]),): v for k, v in (variant[0]["meta"]["config"].get("perturb") or {}).items()}
    a, b = list(sim.stream()), list(sim.stream(perturb=perturb))
    k = next(i for i in range(len(a)) if a[i] != b[i])
    leaf_idx = [i for i, e in enumerate(control) if is_leaf(e)]
    m3 = leaf_idx[k]
    regen_ok = all(_leaf(control[leaf_idx[i]]) == a[i] for i in range(len(a))) and all(_leaf(variant[leaf_idx[i]]) == b[i] for i in range(len(b)))
    return {"compare_runs_index": m1, "raw_scan_index": m2, "resimulation_index": m3, "all_agree": m1 == m2 == m3, "recorded_leaves_equal_regenerated_simulation": regen_ok,
            "first_divergent_leaf": {"sensor": a[k]["sensor"], "tick": a[k]["tick"], "nominal_value": a[k]["value"], "perturbed_value": b[k]["value"]}, "perturbation_from_recorded_config": {f"{s}@{t}": v for (s, t), v in perturb.items()},
            "control_event_id": control[m2]["event_id"], "variant_event_id": variant[m2]["event_id"], "prefix_identical_events": m2}


# ------------------------------------------------------------------ orchestration
def analyze(recorded_dir, x0_tick: int = 8, t_end: int = 10) -> dict:
    d = Path(recorded_dir)
    control, variant = read_run(d / "control.jsonl"), read_run(d / "variant.jsonl")
    sha = {r: hashlib.sha256((d / f"{r}.jsonl").read_bytes()).hexdigest() for r in ("control", "variant")}
    rep = reproduce_first_divergence(control, variant)
    assert rep["all_agree"], "first divergence could not be independently reproduced"
    mid = rep["first_divergent_leaf"]["tick"]
    assert x0_tick < mid <= t_end
    ticks = list(range(x0_tick, t_end + 1))
    chains = {}
    for role, ev, key in (("predicted_nominal", control, "control"), ("observed_perturbed", variant, "variant")):
        ch, prev = [], None
        for t in ticks:
            s = build_state(ev, t, role, sha[key], prev)
            ch.append(s)
            prev = s["identity"]["anticube_state"]
        chains[role] = ch
    x0_n, x0_p = chains["predicted_nominal"][0], chains["observed_perturbed"][0]
    common_predecessor = x0_n["state_id"] == x0_p["state_id"]
    horizons = {}
    for name, end in (("T1_one_step", mid - x0_tick), ("T2_two_endpoint_path", t_end - x0_tick)):
        cp, co = chains["predicted_nominal"][: end + 1], chains["observed_perturbed"][: end + 1]
        cl = classify(x0_n, cp, co)
        ac = anticube_compare([s["identity"]["anticube_state"] for s in cp], [s["identity"]["anticube_state"] for s in co])
        gs_p, gs_o = g_star_tracking(cp), g_star_tracking(co)
        step_dev = [{"tick": ticks[i], "observation_deviation_observed_minus_predicted": {s: round(co[i]["identity"]["observation"][s]["value"] - cp[i]["identity"]["observation"][s]["value"], 6) for s in NUMERIC if co[i]["identity"]["observation"][s]["value"] != cp[i]["identity"]["observation"][s]["value"]},
                     "fcg_state_differs": cp[i]["identity"]["fcg_state"]["node_content_ids"] != co[i]["identity"]["fcg_state"]["node_content_ids"]} for i in range(len(cp))]
        horizons[name] = {"horizon_steps": end, "predicted_chain": [s["state_id"] for s in cp], "observed_chain": [s["state_id"] for s in co], "predicted_path_id": path_id(cp), "observed_path_id": path_id(co),
                          "classification": cl, "anticube": ac, "g_star_predicted": gs_p, "g_star_observed": gs_o, "S_star_predicted": s_star(cp), "S_star_observed": s_star(co),
                          "path_step_deviation": step_dev, "first_delta_g_star_divergence": NC + " (DeltaG* NOT_COMPUTED on both paths)"}
    # structural FCG divergence (identity-based, declared dependencies only)
    cmp_ = compare_runs(control, variant)
    action = {"nominal": next((e["payload"]["SIMULATED_ACTION"] for e in control if e["event_type"] == "decision"), "NONE"),
              "perturbed": next((e["payload"]["SIMULATED_ACTION"] for e in variant if e["event_type"] == "decision"), "NONE (abstention event: " + next((e["payload"]["reason"] for e in variant if e["event_type"] == "abstention"), "?") + ")")}
    first_action_idx = next(i for i in range(len(control)) if control[i]["event_type"] in ("decision", "abstention") or variant[i]["event_type"] in ("decision", "abstention"))
    fcg = {"first_fcg_divergence": {"index": rep["prefix_identical_events"], "control_event_id": rep["control_event_id"], "variant_event_id": rep["variant_event_id"], "kind": cmp_["FIRST_DIVERGENCE"]["kind"]},
           "downstream_changed_event_types": sorted({x["event_type"] for x in cmp_["DOWNSTREAM_CHANGED_EVENTS"]}),
           "changed_without_declared_dependency": len(cmp_["changed_without_declared_dependency"]), "first_action_divergence_index": first_action_idx, "action_divergence": action,
           "DELTA_GRAPH_STRUCTURE": "NOT_EXECUTED (no frozen definition; this identity diff is descriptive and is NOT that component)"}
    return {"program": PROGRAM, "reproduction": rep, "common_predecessor_identified": common_predecessor, "x0_state_id": x0_n["state_id"], "chains": chains, "horizons": horizons, "fcg": fcg,
            "path_weighting": candidate_weighting({"predicted": 0, "observed": 0}), "run_sha256": sha, "ticks": ticks,
            "role_assignment": "nominal = PREDICTED (reference), perturbed = OBSERVED, declared by this analysis; no independent model prediction exists in the artifacts",
            "anticube_dimensions_defined_in_artifacts": {"SELFNESS": True, "SAFETY": True, "EPISTEMIC_STATE": False, "DISPOSITION": "only as a default disposition table over known SELFNESS x SAFETY"},
            "control_events": control, "variant_events": variant}
