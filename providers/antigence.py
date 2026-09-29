"""Deterministic Antigence antibody screen as a provider ('deterministic core only'). Not a model."""
import json

from .base import Provider


class AntigenceProvider(Provider):
    name = "antigence"
    provider_kind = "deterministic"
    model = "antigence-prompt-injection-antibodies"

    def complete(self, request: dict) -> dict:
        from agent_foundry.antigence_fixture import screen
        text = "\n".join(d.get("text", "") for d in request.get("evidence", []))
        sc = screen(text)
        return {"text": json.dumps({"injection": sc["anomaly_count"] >= 1}), "meta": {"latency_ms": 0}}
