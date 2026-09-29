"""Two-run comparison: first divergence, declared-downstream impact, affected claims.

Only DECLARED dependencies imply downstream impact. Chronology alone never does.
"""


def _diff(a, b, path=""):
    """Field-level diff; returns [{path, control, variant}]."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _diff(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    return [] if a == b else [{"path": path, "control": a, "variant": b}]


def _brief(ev):
    return None if ev is None else {"event_id": ev["event_id"], "seq": ev["seq"], "event_type": ev["event_type"], "content_id": ev["content_id"], "state": ev["state"]}


def _downstream(events, root_id):
    """Event ids reachable from root via declared deps (root excluded)."""
    reached, changed = {root_id}, True
    while changed:
        changed = False
        for ev in events:
            if ev["event_id"] not in reached and any(d in reached for d in ev["deps"]):
                reached.add(ev["event_id"])
                changed = True
    reached.discard(root_id)
    return [e for e in events if e["event_id"] in reached]


def _claims(events):
    return {e["payload"]["claim_id"]: e for e in events if e["event_type"] == "claim"}


def compare_runs(control: list, variant: list) -> dict:
    c0, v0 = control[0], variant[0]
    result = {
        "CONTROL_RUN": c0["run_id"],
        "VARIANT_RUN": v0["run_id"],
        "declared_variable": v0.get("meta", {}).get("variable"),
        "attribution_note": "single run per side; provider nondeterminism NOT_COMPUTED; attribution to the declared variable rests on the controlled design, not on repeated trials",
        "events_compared": [len(control), len(variant)],
    }
    n = min(len(control), len(variant))
    idx = next((i for i in range(n) if control[i]["content_id"] != variant[i]["content_id"]), None)
    kind = None
    if idx is not None:
        c, v = control[idx], variant[idx]
        kind = "event_type" if c["event_type"] != v["event_type"] else ("actor" if c["actor"] != v["actor"] else "payload")
    elif len(control) != len(variant):
        idx, c, v = n, (control[n] if n < len(control) else None), (variant[n] if n < len(variant) else None)
        kind = "length"

    attention = [{"run": r, **_brief(e), "payload": e["payload"]} for r, evs in (("CONTROL_RUN", control), ("VARIANT_RUN", variant)) for e in evs if e["event_type"] in ("failure", "abstention")]
    result["failures_and_abstentions"] = attention

    if idx is None:
        result.update({"DIVERGENCE": "NULL", "divergence_state": "NULL", "FIRST_DIVERGENCE": None, "DOWNSTREAM_CHANGED_EVENTS": [], "AFFECTED_CLAIMS": [], "changed_without_declared_dependency": []})
        result["explanation"] = f"The two runs are identical across all {len(control)} events (same content identities). No divergence was found; none was manufactured."
        return result

    fd = {"index": idx, "kind": kind, "control_event": _brief(c), "variant_event": _brief(v),
          "changed_fields": _diff({"actor": c["actor"], "payload": c["payload"]}, {"actor": v["actor"], "payload": v["payload"]}) if c and v and c["event_type"] == v["event_type"] else []}
    result.update({"DIVERGENCE": "OBSERVED", "divergence_state": "OBSERVED", "FIRST_DIVERGENCE": fd})

    down_c = _downstream(control, c["event_id"]) if c else []
    down_v = _downstream(variant, v["event_id"]) if v else []
    result["DOWNSTREAM_CHANGED_EVENTS"] = [{"run": "CONTROL_RUN", **_brief(e)} for e in down_c] + [{"run": "VARIANT_RUN", **_brief(e)} for e in down_v]
    declared = {e["event_id"] for e in down_c} | {e["event_id"] for e in down_v}
    result["changed_without_declared_dependency"] = [
        {"index": i, "control_event": _brief(control[i]), "variant_event": _brief(variant[i])}
        for i in range(idx + 1, n)
        if control[i]["content_id"] != variant[i]["content_id"] and control[i]["event_id"] not in declared and variant[i]["event_id"] not in declared
    ]

    cc, vc = _claims(control), _claims(variant)
    affected = []
    for cid in sorted(set(cc) | set(vc)):
        ce, ve = cc.get(cid), vc.get(cid)
        in_downstream = (ce is not None and ce["event_id"] in declared) or (ve is not None and ve["event_id"] in declared)
        text_c = ce["payload"]["text"] if ce else None
        text_v = ve["payload"]["text"] if ve else None
        if in_downstream or (ce is None) != (ve is None):
            affected.append({"claim_id": cid, "control": text_c, "variant": text_v, "changed": text_c != text_v,
                             "basis": "declared dependency on divergent event" if in_downstream else "claim present in only one run"})
    result["AFFECTED_CLAIMS"] = affected
    result["explanation"] = explain(result, control, variant)
    return result


def explain(res: dict, control: list, variant: list) -> str:
    fd = res["FIRST_DIVERGENCE"]
    i = fd["index"]
    ce, ve = fd["control_event"], fd["variant_event"]
    parts = [f"The runs were identical for the first {i} event(s)."]
    if fd["kind"] == "length":
        parts.append(f"At position {i} one run ended and the other continued.")
    elif fd["kind"] == "event_type":
        parts.append(f"At event {i} the control run recorded a '{ce['event_type']}' while the variant recorded a '{ve['event_type']}'.")
    else:
        parts.append(f"At event {i} ('{ce['event_type']}') the {fd['kind']} differs.")
        for f in fd["changed_fields"][:3]:
            if f["path"].endswith(("content_digest",)):
                continue
            parts.append(f"{f['path']}: {f['control']!r} -> {f['variant']!r}.")
    if res.get("declared_variable") == "none":
        parts.append("No controlled difference was declared (replicate pair), so this divergence is unexplained nondeterminism or an environment difference.")
    elif res.get("declared_variable"):
        parts.append(f"The declared controlled difference between the runs was '{res['declared_variable']}' (single run per side; nondeterminism not measured).")
    if res["DOWNSTREAM_CHANGED_EVENTS"]:
        types = sorted({e["event_type"] for e in res["DOWNSTREAM_CHANGED_EVENTS"]})
        parts.append(f"Events downstream through declared dependencies: {', '.join(types)}.")
    for a in res["AFFECTED_CLAIMS"]:
        parts.append(f"Affected claim '{a['claim_id']}': {a['control']!r} -> {a['variant']!r}.")
    if res["failures_and_abstentions"]:
        parts.append("Failures/abstentions present: " + "; ".join(f"{e['run']} {e['event_type']}" for e in res["failures_and_abstentions"]) + ".")
    if res["changed_without_declared_dependency"]:
        parts.append(f"{len(res['changed_without_declared_dependency'])} later event(s) also differ with no declared dependency on the divergence; no causal link is asserted.")
    return " ".join(parts)
