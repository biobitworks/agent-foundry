"""Read-model for the inspector: derives the sensor series, breakpoints (with re-verification) and the decision evidence route from a
VERIFIED canonical event list. Nothing here is stored; everything is recomputed from the run log (never from Neo4j)."""
from . import moddik_sim as sim
from .merkle import verify_commitment


def is_leaf(e):
    return e["event_type"] == "evidence" and e["payload"].get("schema") == sim.LEAF_SCHEMA


def build_view(events: list) -> dict:
    by_id = {e["event_id"]: e for e in events}
    by_cid = {e["content_id"]: e for e in events}
    ticks = {}
    for i, e in enumerate(events):
        if is_leaf(e):
            p = e["payload"]
            t = ticks.setdefault(p["tick"], {"tick": p["tick"], "sim_time_s": p["sim_time_s"], "values": {}, "units": {}, "event_index": {}, "event_ids": {}})
            t["values"][p["sensor"]] = p["value"]
            t["units"][p["sensor"]] = p["unit"]
            t["event_index"][p["sensor"]] = i
            t["event_ids"][p["sensor"]] = e["event_id"]
    bps = []
    for i, e in enumerate(events):
        if e["event_type"] != "checkpoint":
            continue
        p = e["payload"]
        rep = verify_commitment({"leaves": p["commitment"]["leaves"], "MERKLE_ROOT": p["MERKLE_ROOT"], "construction": p["commitment"]["construction"]}) if p["MERKLE_ROOT"] != "NOT_COMPUTED" else {"PASS": False, "checks": {}}
        leaf_events = [by_cid.get(c) for c in p["leaf_content_ids"]]
        bps.append({"event_index": i, "event_id": e["event_id"], "label": p["label"], "tick": p["tick"], "root": p["MERKLE_ROOT"], "parent_root": p["parent_breakpoint_root"],
                    "recorded_verification_pass": p["verification"]["PASS"], "reverified_now": rep["PASS"], "reverify_checks": rep["checks"], "binding_verified": p["leaf_event_binding_verified"],
                    "construction": p["commitment"]["construction"],
                    "leaves": [{"index": r["index"], "sensor": (le or {}).get("payload", {}).get("sensor"), "value": (le or {}).get("payload", {}).get("value"), "unit": (le or {}).get("payload", {}).get("unit"),
                                "event_index": next((k for k, x in enumerate(events) if x is le), None), "event_id": (le or {}).get("event_id"), "leaf_hash": r["leaf_hash"], "canonical_bytes_utf8": r["canonical_bytes_utf8"]}
                               for r in p["commitment"]["leaves"] for le in [leaf_events[r["index"]]]]})
    route = None
    dec = next((e for e in events if e["event_type"] == "decision"), None)
    model = next((e for e in events if e["event_type"] == "model"), None)
    ver = next((e for e in events if e["event_type"] == "evaluation"), None)
    tr = next((e for e in events if e["event_type"] == "evidence" and "transcript_source" in e["payload"]), None)
    if model:
        cited = [by_cid[c] for c in model["payload"].get("verified_evidence_content_ids", []) if c in by_cid]
        hb = by_id.get(dec["meta"]["hardware_breakpoint_event_id"]) if dec else next((b for b in events if b["event_type"] == "checkpoint" and b["payload"]["label"] == "decision-state"), None)
        nxt = next((e for e in events if e["event_type"] == "checkpoint" and e["payload"]["label"] == "post-decision"), None)
        idx = {e["event_id"]: i for i, e in enumerate(events)}
        route = {"sensor_leaves": [{"event_index": idx[e["event_id"]], "event_id": e["event_id"], "label": (e["payload"].get("sensor") or e["payload"].get("tool")), "value": e["payload"].get("value"),
                                     "unit": e["payload"].get("unit")} for e in cited],
                 "breakpoint": hb and {"event_index": idx[hb["event_id"]], "event_id": hb["event_id"], "root": hb["payload"]["MERKLE_ROOT"], "tick": hb["payload"]["tick"]},
                 "transcript": tr and {"event_index": idx[tr["event_id"]], "event_id": tr["event_id"], "text": tr["payload"]["text"], "source": tr["payload"]["transcript_source"]},
                 "model": {"event_index": idx[model["event_id"]], "event_id": model["event_id"], "model": model["actor"]["model"], "response_tail": model["payload"]["response"]["text"].rsplit("</think>", 1)[-1].strip()},
                 "verifier": ver and {"event_index": idx[ver["event_id"]], "event_id": ver["event_id"], "pass": ver["payload"]["PASS"], "findings": ver["payload"]["findings"]},
                 "action": dec and {"event_index": idx[dec["event_id"]], "event_id": dec["event_id"], "simulated_action": dec["payload"]["SIMULATED_ACTION"], "actuation": dec["payload"]["actuation"]},
                 "next_breakpoint": nxt and {"event_index": idx[nxt["event_id"]], "event_id": nxt["event_id"], "root": nxt["payload"]["MERKLE_ROOT"], "tick": nxt["payload"]["tick"]}}
    return {"run_id": events[0]["run_id"], "policy": events[0]["payload"].get("policy"), "limits": events[0]["payload"].get("limits"), "config": (events[0].get("meta") or {}).get("config"),
            "ticks": [ticks[k] for k in sorted(ticks)], "breakpoints": bps, "route": route, "event_count": len(events),
            "audio": [{"event_id": e["event_id"], **{k: e["payload"].get(k) for k in ("artifact_type", "ref", "digest", "capture", "relation")}} for e in events if e["event_type"] == "artifact"]}
