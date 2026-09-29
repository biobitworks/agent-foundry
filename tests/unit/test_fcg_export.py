import json
from pathlib import Path

from agent_foundry.fcg_export import export_lineage
from agent_foundry.recorder import read_run
from agent_foundry.runner import run_task

TASK = json.loads((Path(__file__).resolve().parents[2] / "demo/tasks/refund_policy.json").read_text())
A = {"provider": "fixture", "model": "fixture-a", "evidence": "policy-v1"}


def test_shared_content_is_one_node_with_two_occurrences_and_only_declared_edges(tmp_path):
    a = read_run(run_task(TASK, A, "a", tmp_path).path)
    b = read_run(run_task(TASK, {**A, "evidence": "policy-v2"}, "b", tmp_path).path)
    g = export_lineage(a, b)
    shared = a[0]["content_id"]
    assert sum(1 for e in g["edges"] if e["dst"] == shared and e["rel"] == "occurrence_of") == 2
    assert len(g["occurrence_nodes"]) == len(a) + len(b) and len(g["content_nodes"]) < len(g["occurrence_nodes"])
    assert all(e["declared"] for e in g["edges"]) and {e["rel"] for e in g["edges"]} == {"occurrence_of", "declared_dependency", "declared_support"}
    assert not any("cause" in e["rel"] for e in g["edges"])


def test_export_digest_is_deterministic(tmp_path):
    a = read_run(run_task(TASK, A, "a", tmp_path).path)
    assert export_lineage(a)["export_digest"] == export_lineage(a)["export_digest"]
