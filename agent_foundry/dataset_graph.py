"""Neo4j projection of the canonical FCO/FCG files + the Agent Foundry run for an external-dataset admission.

Neo4j is a REBUILDABLE projection: canonical = fco/objects/*.json, fcg/edges/*.jsonl and the recorded run log. Every node written here carries
admission_id, so clearing/rebuilding touches ONLY this admission (never the Moddik projection or any other database).
Edge types mirror the FCG relationships; nothing here asserts causality (no CAUSED_BY).
"""
from . import moddik_graph as base

REL_MAP = {"derived_from": "DERIVED_FROM", "part_of": "PART_OF", "licensed_under": "LICENSED_UNDER", "compared_with": "COMPARED_WITH"}
LABEL_MAP = {"SourcePageSnapshot": "SourcePageSnapshot", "DatasetSource": "DatasetSource", "DatasetFile": "DatasetFile", "LicenseDeclaration": "LicenseDeclaration",
             "EndpointState": "EndpointState", "PathDivergenceFCO": "PathDivergence", "RunLog": "RunLog"}
EVENT_LABEL = {"evidence": "EvidenceEvent", "tool": "ToolEvent", "evaluation": "VerifierEvent", "run_started": "RunEvent", "run_completed": "RunEvent", "failure": "FailureEvent"}


def clear_admission(drv, admission_id: str):
    with drv.session() as s:
        s.run("MATCH (n {admission_id:$a}) DETACH DELETE n", a=admission_id)


def project(drv, admission_id: str, fcos: dict, edges: list, events: list = None) -> dict:
    with drv.session() as s:
        for f in fcos.values():
            lab = LABEL_MAP[f["object_type"]]
            b = f["body"]
            props = {"content_hash": f["content_hash"], "object_id": f["object_id"], "object_type": f["object_type"], "status": f["status"], "claim_ceiling": f["claim_ceiling"],
                     "source_or_derivative": f["source_or_derivative"], "admission_id": admission_id, "run_id": admission_id}
            for k in ("source_url", "doi", "title", "declared_name", "custody_state", "raw_bytes_state", "declared_license_url", "byte_length", "tick", "sim_time_s", "horizon", "role", "run_id_of_log",
                      "start_state_id", "predicted_end_state_id", "observed_end_state_id", "predicted_path_id", "observed_path_id", "diagnosis_primary"):
                if k in b and isinstance(b[k], (str, int, float, bool)):
                    props[k] = b[k]
            for k in ("predicted_path", "observed_path"):
                if isinstance(b.get(k), list) and all(isinstance(x, str) for x in b[k]):
                    props[k] = b[k]
            s.run(f"MERGE (n:FCO:{lab} {{content_hash:$h, admission_id:$a}}) SET n += $p", h=f["content_hash"], a=admission_id, p=props)
        for e in edges:
            rel = REL_MAP[e["rel"]]
            s.run(f"MATCH (a:FCO {{content_hash:$s, admission_id:$ad}}), (b:FCO {{content_hash:$d, admission_id:$ad}}) MERGE (a)-[r:{rel} {{edge_id:$id}}]->(b) "
                  "SET r.relationship_status=$st, r.ontology_status=$os, r.basis=$bs, r.causal=false",
                  s=e["src_content_hash"], d=e["dst_content_hash"], ad=admission_id, id=e["edge_id"], st=e["relationship_status"], os=e["ontology_status"], bs=e["basis"])
        n_ev = 0
        if events:
            rid = events[0]["run_id"]
            s.run("MERGE (r:Run {run_id:$r, admission_id:$a}) SET r.run_type=$rt, r.event_count=$n", r=rid, a=admission_id, n=len(events), rt=events[0]["payload"].get("run_type", "UNKNOWN"))
            for ev in events:
                lab = EVENT_LABEL.get(ev["event_type"], "Event")
                p = {"event_id": ev["event_id"], "content_id": ev["content_id"], "run_id": rid, "seq": ev["seq"], "state": ev["state"], "event_type": ev["event_type"], "admission_id": admission_id}
                if ev["payload"].get("fco_content_hash"):
                    p["fco_content_hash"] = ev["payload"]["fco_content_hash"]
                s.run(f"MERGE (n:{lab} {{event_id:$id, admission_id:$a}}) SET n += $p WITH n MATCH (r:Run {{run_id:$r, admission_id:$a}}) MERGE (n)-[:OBSERVED_IN]->(r)", id=ev["event_id"], p=p, r=rid, a=admission_id)
                n_ev += 1
            for ev in events:
                for d in ev["deps"]:
                    s.run("MATCH (a {event_id:$a, admission_id:$ad}), (b {event_id:$b, admission_id:$ad}) MERGE (a)-[:DECLARED_DEPENDENCY]->(b)", a=ev["event_id"], b=d, ad=admission_id)
                h = ev["payload"].get("fco_content_hash")
                if ev["event_type"] == "evidence" and h:  # the event is a projection of the FCO (a relationship, not a claim of causality)
                    s.run("MATCH (e:EvidenceEvent {event_id:$e, admission_id:$a}), (f:FCO {content_hash:$h, admission_id:$a}) MERGE (e)-[:PROJECTED_FROM]->(f)", e=ev["event_id"], h=h, a=admission_id)
    return counts(drv, admission_id)


def counts(drv, admission_id: str) -> dict:
    q = lambda c, **k: base.query(drv, c, **k)
    return {"nodes": q("MATCH (n {admission_id:$a}) RETURN count(n) AS n", a=admission_id)[0]["n"],
            "relationships": q("MATCH ({admission_id:$a})-[r]->({admission_id:$a}) RETURN count(r) AS n", a=admission_id)[0]["n"],
            "by_label": {r["l"]: r["c"] for r in q("MATCH (n {admission_id:$a}) RETURN labels(n)[0] AS l, count(*) AS c ORDER BY l", a=admission_id)},
            "by_rel": {r["t"]: r["c"] for r in q("MATCH ({admission_id:$a})-[r]->({admission_id:$a}) RETURN type(r) AS t, count(*) AS c ORDER BY t", a=admission_id)},
            "causal_like_edges": q("MATCH ({admission_id:$a})-[r]->() WHERE type(r) CONTAINS 'CAUS' RETURN count(r) AS n", a=admission_id)[0]["n"]}


CYPHER_TRACE = ("MATCH p=(s:FCO {content_hash:$start, admission_id:$a})-[:PART_OF|DERIVED_FROM*1..6]->(t:FCO {admission_id:$a}) WHERE NOT (t)-[:PART_OF|DERIVED_FROM]->() "
                "RETURN [n IN nodes(p) | n.content_hash] AS chain, [n IN nodes(p) | n.object_type] AS types, [r IN relationships(p) | type(r)] AS rels, t.source_url AS source_url")


def trace(drv, admission_id: str, start: str) -> dict:
    rows = base.query(drv, CYPHER_TRACE, start=start, a=admission_id)
    return {"paths": rows, "cypher": CYPHER_TRACE}


def fingerprint(drv, admission_id: str) -> dict:
    """Order-independent description of the projected FCO/FCG subgraph, comparable across rebuilds."""
    q = lambda c, **k: base.query(drv, c, **k)
    nodes = sorted((r["l"], r["h"]) for r in q("MATCH (n:FCO {admission_id:$a}) RETURN labels(n)[1] AS l, n.content_hash AS h", a=admission_id))
    edges = sorted((r["t"], r["s"], r["d"], r["e"]) for r in q("MATCH (a:FCO {admission_id:$a})-[r]->(b:FCO {admission_id:$a}) RETURN type(r) AS t, a.content_hash AS s, b.content_hash AS d, r.edge_id AS e", a=admission_id))
    return {"nodes": nodes, "edges": edges}
