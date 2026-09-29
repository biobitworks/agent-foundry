"""Native lineage export (FCO-style nodes and declared edges) for a run or a compared pair.

Nodes: one CONTENT node per distinct CONTENT_ID, one OCCURRENCE node per event (RUN_ID/PHASE separate).
Edges are DECLARED relationships only: `declared_dependency` (event deps), `occurrence_of`, and for claims
`declared_support` (claim deps on evidence). Edges never assert causality. This is NOT the canonical FCO/FCG repo format:
FCO_FCG_BRIDGE to biobitworks/fractal-custody-objects remains NOT_IMPLEMENTED. No signing, no Merkle/MMR claims.
"""
from .ids import canonical_json, sha256_hex


def export_lineage(*runs: list) -> dict:
    content, occ, edges = {}, [], []
    for events in runs:
        for e in events:
            content.setdefault(e["content_id"], {"node": e["content_id"], "kind": "CONTENT", "event_type": e["event_type"], "actor": e["actor"]})
            occ.append({"node": e["event_id"], "kind": "OCCURRENCE", "run_id": e["run_id"], "seq": e["seq"], "state": e["state"], "event_type": e["event_type"]})
            edges.append({"src": e["event_id"], "dst": e["content_id"], "rel": "occurrence_of", "declared": True})
            by_id = {x["event_id"]: x for x in events}
            for d in e["deps"]:
                rel = "declared_support" if e["event_type"] == "claim" and by_id[d]["event_type"] == "evidence" else "declared_dependency"
                edges.append({"src": e["event_id"], "dst": d, "rel": rel, "declared": True})
    doc = {"schema": "agent-foundry.lineage_export.v1", "content_nodes": list(content.values()), "occurrence_nodes": occ, "edges": edges,
           "notes": ["edges declare relationships; they do not prove causality", "not the canonical FCO/FCG repo format (bridge NOT_IMPLEMENTED)", "unsigned; no Merkle/MMR"]}
    doc["export_digest"] = "sha256:" + sha256_hex(canonical_json({k: doc[k] for k in ("content_nodes", "occurrence_nodes", "edges")}))
    return doc
