"""Deterministic stand-in providers. Always provider_kind='fixture'."""
import re

from .base import Provider, ProviderError


class FixtureProvider(Provider):
    name = "fixture"
    provider_kind = "fixture"

    def __init__(self, model="fixture-a"):
        self.model = model

    def complete(self, request: dict) -> dict:
        if self.model == "fixture-fail":
            raise ProviderError("Timeout", "fixture provider simulated timeout", recoverable=True)
        docs = request.get("evidence", [])
        text = " ".join(d.get("text", "") for d in docs)
        m = re.search(r"within (\d+) days", text)
        days = int(m.group(1)) if m else None
        purchased = 20  # canonical task fixes the purchase age; a fixture, not extracted from language
        if days is None:
            return {"text": "ABSTAIN: no policy evidence available.", "meta": {"abstained": True}}
        eligible = purchased <= days
        if self.model == "fixture-a":
            ans = f"Yes, you are eligible for a refund (window is {days} days)." if eligible else f"No, the refund window is {days} days and you are past it."
        elif self.model == "fixture-b":
            # deliberately different phrasing style, same decision logic
            ans = f"Eligible: refund allowed, {days}-day window." if eligible else f"Not eligible: {days}-day window has passed."
        else:
            raise ProviderError("UnknownModel", f"unknown fixture model {self.model}")
        return {"text": ans, "meta": {"latency_ms": 0}}
