"""Canonical task and demo scenarios (controlled pairs differing in one declared variable)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = json.loads((ROOT / "demo" / "tasks" / "refund_policy.json").read_text())
BASE = {"provider": "fixture", "model": "fixture-a", "evidence": "policy-v1"}
QWEN = {"provider": "ollama", "model": "qwen2.5:7b", "evidence": "policy-v1"}

SCENARIOS = {
    "local_evidence": {"title": "REAL: same local model, evidence changed (policy v1 -> v2)", "control": QWEN, "variant": {**QWEN, "evidence": "policy-v2"}, "real": True},
    "local_models": {"title": "REAL: same task, two local models (qwen2.5:7b vs llama3.2:3b)", "control": QWEN, "variant": {**QWEN, "model": "llama3.2:3b"}, "real": True},
    "evidence_changed": {"title": "FIXTURE: evidence changed (policy v1 -> v2)", "control": BASE, "variant": {**BASE, "evidence": "policy-v2"}},
    "model_changed": {"title": "FIXTURE: model changed (fixture-a -> fixture-b)", "control": BASE, "variant": {**BASE, "model": "fixture-b"}},
    "identical": {"title": "FIXTURE: nothing changed (expect DIVERGENCE=NULL)", "control": BASE, "variant": dict(BASE)},
    "provider_failure": {"title": "FIXTURE: provider failure in variant", "control": BASE, "variant": {**BASE, "model": "fixture-fail"}},
    "missing_evidence": {"title": "FIXTURE: evidence unavailable (abstention)", "control": BASE, "variant": {**BASE, "evidence": "policy-v9"}},
}
