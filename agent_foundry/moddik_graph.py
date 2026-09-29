"""Neo4j projection of a canonical Moddik run. Neo4j is a REBUILDABLE projection and query layer: it is not the canonical FCG and
not the canonical provenance store. Canonical = runs/<run_id>.jsonl (+ provenance/). Deleting the database loses no evidence.

Edges declare relationships only. Nothing here asserts causality (no CAUSED_BY).
Credentials are read from a gitignored local file or the environment; values are never logged or returned.
"""
import hashlib
import os
from pathlib import Path

from neo4j import GraphDatabase

from . import moddik_sim as sim

CRED = Path(__file__).resolve().parent.parent / ".local" / "moddik-neo4j.credentials"
PROJECTION_SCHEMA = "agent-foundry.moddik.neo4j_projection.v1"


ENV_KEYS = {"NEO4J_URI": "AGENT_FOUNDRY_NEO4J_URI", "NEO4J_USER": "AGENT_FOUNDRY_NEO4J_USER", "NEO4J_PASSWORD": "AGENT_FOUNDRY_NEO4J_PASSWORD"}
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")


def _creds() -> dict:
    """Project-local credentials file, optionally overridden ONLY by AGENT_FOUNDRY_NEO4J_* variables.
    The generic NEO4J_* variables are deliberately ignored: an operator's shell may hold credentials for an unrelated (e.g. cloud Aura) database,
    and this demo must never clear or write into it."""
    d = {}
    if CRED.exists():
        for line in CRED.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    for k, env in ENV_KEYS.items():
        if os.environ.get(env):
            d[k] = os.environ[env]
    return d


def _is_local(uri: str) -> bool:
    host = uri.split("://", 1)[-1].rsplit(":", 1)[0]
    return host in LOCAL_HOSTS


def credential_status() -> dict:
    d = _creds()
    return {k: ("PRESENT" if d.get(k) else "ABSENT") for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")} | {"VALUE": "NOT_CAPTURED"}


def connect():
    d = _creds()
    if not all(d.get(k) for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")):
        raise RuntimeError("Neo4j credentials not present (run scripts/moddik_neo4j.sh up)")
    if not _is_local(d["NEO4J_URI"]) and os.environ.get("AGENT_FOUNDRY_NEO4J_ALLOW_REMOTE") != "1":
        raise RuntimeError("refusing non-loopback Neo4j URI: this projection only writes to the project-local instance (set AGENT_FOUNDRY_NEO4J_ALLOW_REMOTE=1 to override deliberately)")
    drv = GraphDatabase.driver(d["NEO4J_URI"], auth=(d["NEO4J_USER"], d["NEO4J_PASSWORD"]))
    drv.verify_connectivity()
    return drv


def _label(ev: dict) -> str:
    t, p = ev["event_type"], ev["payload"]
    if t == "evidence" and p.get("schema") == sim.LEAF_SCHEMA:
        return "SensorEvent"
    return {"evidence": "TranscriptEvent" if "transcript_source" in p else "EvidenceEvent", "checkpoint": "HardwareBreakpoint", "artifact": "AudioArtifact",
            "tool": "ToolEvent", "model": "ModelEvent", "decision": "ActionEvent", "evaluation": "VerifierEvent", "failure": "FailureEvent",
            "abstention": "AbstentionEvent", "run_started": "RunEvent", "run_completed": "RunEvent"}.get(t, "Event")


def _props(ev: dict) -> dict:
    p = ev["payload"]
    base = {"event_id": ev["event_id"], "content_id": ev["content_id"], "run_id": ev["run_id"], "seq": ev["seq"], "state": ev["state"], "event_type": ev["event_type"]}
    if p.get("schema") == sim.LEAF_SCHEMA:
        base |= {k: p[k] for k in ("sensor", "unit", "tick", "sim_time_s", "source", "sequence")} | {"value": str(p["value"]) if p["sensor"] == "actuator_state" else p["value"]}
    if ev["event_type"] == "checkpoint":
        base |= {"tick": p["tick"], "root": p["MERKLE_ROOT"], "breakpoint_id": p["breakpoint_id"], "verification_pass": p["verification"]["PASS"]}
    if ev["event_type"] == "model":
        base |= {"model": ev["actor"].get("model", ""), "provider_kind": ev["actor"].get("provider_kind", "")}
    if ev["event_type"] == "decision":
        base |= {"simulated_action": p.get("SIMULATED_ACTION"), "actuation": p.get("actuation")}
    if ev["event_type"] == "tool":
        base |= {"tool": p.get("tool")}
    if ev["event_type"] == "evaluation":
        base |= {"verifier_pass": p.get("PASS")}
    if "transcript_source" in p:
        base |= {"text": p["text"], "transcript_source": p["transcript_source"]}
    if ev["event_type"] == "artifact":
        base |= {"sha256": p.get("sha256"), "capture": p.get("capture")}
    return base


def project_run(drv, events: list, run_log_path=None) -> dict:
    """Idempotent MERGE projection of a verified event list. Returns counts."""
    run_id = events[0]["run_id"]
    log_sha = hashlib.sha256(Path(run_log_path).read_bytes()).hexdigest() if run_log_path else None
    with drv.session() as s:
        s.run("MERGE (r:Run {run_id:$r}) SET r.projection_schema=$ps, r.canonical_log_sha256=$h, r.event_count=$n", r=run_id, ps=PROJECTION_SCHEMA, h=log_sha, n=len(events))
        s.run("MERGE (h:Hardware {hardware_id:$h}) SET h.source='SIMULATED' MERGE (p:Plate {plate_id:$p}) SET p.source='SIMULATED' MERGE (p)-[:PART_OF]->(h) "
              "WITH h MATCH (r:Run {run_id:$r}) MERGE (h)-[:OBSERVED_IN]->(r)", h=sim.HARDWARE_ID, p=sim.PLATE_ID, r=run_id)
        for name in sim.ORDER:
            s.run("MERGE (x:Sensor {sensor_id:$id}) SET x.name=$n MERGE (p:Plate {plate_id:$p}) MERGE (x)-[:PART_OF]->(p)", id=f"{sim.HARDWARE_ID}/{name}", n=name, p=sim.PLATE_ID)
        s.run("MERGE (a:EvidenceArtifact {artifact_id:$id}) SET a.kind='canonical_run_log', a.sha256=$h, a.path=$p "
              "WITH a MATCH (r:Run {run_id:$r}) MERGE (r)-[:PROJECTED_FROM]->(a)", id=f"runlog:{run_id}", h=log_sha, p=f"runs/{run_id}.jsonl", r=run_id)
        by_id = {}
        for ev in events:
            lab = _label(ev)
            by_id[ev["event_id"]] = (lab, ev)
            s.run(f"MERGE (n:{lab} {{event_id:$id}}) SET n += $props WITH n MATCH (r:Run {{run_id:$r}}) MERGE (n)-[:OBSERVED_IN]->(r)", id=ev["event_id"], props=_props(ev), r=run_id)
            if lab == "SensorEvent":
                s.run("MATCH (n:SensorEvent {event_id:$id}), (x:Sensor {sensor_id:$sid}) MERGE (n)-[:OBSERVATION_OF]->(x)", id=ev["event_id"], sid=f"{sim.HARDWARE_ID}/{ev['payload']['sensor']}")
        n_dep = 0
        for ev in events:
            for d in ev["deps"]:
                rel = "DERIVED_FROM" if ev["event_type"] == "checkpoint" else "DECLARED_DEPENDENCY"
                s.run(f"MATCH (a {{event_id:$a}}), (b {{event_id:$b}}) MERGE (a)-[e:{rel}]->(b)", a=ev["event_id"], b=d)
                n_dep += 1
            p = ev["payload"]
            if ev["event_type"] == "model":
                for cid in p.get("verified_evidence_content_ids", []):
                    s.run("MATCH (m:ModelEvent {event_id:$m}), (e {run_id:$r, content_id:$c}) MERGE (m)-[:USED_EVIDENCE]->(e)", m=ev["event_id"], r=run_id, c=cid)
            if ev["event_type"] == "decision" and p.get("model_content_id"):
                s.run("MATCH (m:ModelEvent {run_id:$r, content_id:$c}), (a:ActionEvent {event_id:$a}) MERGE (m)-[:RECOMMENDED]->(a)", r=run_id, c=p["model_content_id"], a=ev["event_id"])
            if ev["event_type"] == "artifact" and p.get("parallel_capture_of"):
                s.run("MATCH (a:AudioArtifact {event_id:$a}), (b:AudioArtifact {run_id:$r, content_id:$b}) MERGE (a)-[c:PARALLEL_CAPTURE]->(b) SET c.relation='SAME_SESSION', c.same_bytes=false",
                      a=ev["event_id"], r=run_id, b=p["parallel_capture_of"])
        c = s.run("MATCH (n {run_id:$r}) RETURN count(n) AS nodes", r=run_id).single()["nodes"]
        rc = s.run("MATCH ({run_id:$r})-[e]->() RETURN count(e) AS rels", r=run_id).single()["rels"]
    return {"run_id": run_id, "event_nodes": c, "event_edges": rc, "declared_dependency_edges_written": n_dep, "canonical_log_sha256": log_sha}


def clear_run(drv, run_id: str):
    """Rebuild support: removes ONLY this run's projected nodes (projection layer; canonical log untouched)."""
    with drv.session() as s:
        s.run("MATCH (n {run_id:$r}) DETACH DELETE n", r=run_id)
        s.run("MATCH (r:Run {run_id:$r}) DETACH DELETE r", r=run_id)


CYPHER_LATEST = ("MATCH (e:SensorEvent {run_id:$run}) WHERE e.tick <= $tick AND e.sensor <> 'actuator_state' "
                 "WITH e.sensor AS s, max(e.tick) AS mt "
                 "MATCH (x:SensorEvent {run_id:$run, sensor:s, tick:mt}) RETURN x.event_id AS event_id, x.sensor AS sensor, x.value AS value, x.unit AS unit, x.tick AS tick, x.sim_time_s AS sim_time_s, x.source AS source ORDER BY x.sequence")
CYPHER_HISTORY = ("MATCH (x:SensorEvent {run_id:$run}) WHERE x.sensor IN $sensors AND x.tick >= $t0 AND x.tick <= $t1 "
                  "RETURN x.event_id AS event_id, x.sensor AS sensor, x.value AS value, x.unit AS unit, x.tick AS tick, x.sim_time_s AS sim_time_s, x.source AS source ORDER BY x.tick, x.sequence")
CYPHER_BREAKPOINT = ("MATCH (b:HardwareBreakpoint {run_id:$run}) WHERE b.tick <= $tick RETURN b.event_id AS event_id, b.tick AS tick, b.root AS root, b.verification_pass AS verification_pass ORDER BY b.tick DESC LIMIT 1")


def query(drv, cypher: str, **params) -> list:
    with drv.session() as s:
        return [dict(r) for r in s.run(cypher, **params)]


def evidence_path(drv, run_id: str) -> dict:
    """Small subgraph for the inspector's right column: the decision route only (bounded)."""
    rows = query(drv, "MATCH (a:ActionEvent {run_id:$r}) OPTIONAL MATCH (m:ModelEvent)-[:RECOMMENDED]->(a) OPTIONAL MATCH (m)-[u:USED_EVIDENCE]->(e) "
                 "RETURN a.event_id AS action, a.simulated_action AS simulated_action, m.event_id AS model, m.model AS model_name, collect(DISTINCT {id:e.event_id, label:labels(e)[0], sensor:e.sensor, value:e.value, tick:e.tick, root:e.root}) AS used", r=run_id)
    return {"run_id": run_id, "routes": rows, "note": "projection query; edges declare relationships and do not prove causality"}
