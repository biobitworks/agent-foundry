"""Ollama adapter (local execution lane). STATE: IMPLEMENTED, NOT_TESTED until an actual run succeeds."""
import json
import time
import urllib.error
import urllib.request

from .base import Provider, ProviderError


class OllamaProvider(Provider):
    name = "ollama"
    provider_kind = "real"

    def __init__(self, model, host="http://127.0.0.1:11434", timeout=120):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def complete(self, request: dict) -> dict:
        ev = "\n".join(d.get("text", "") for d in request.get("evidence", []))
        prompt = f"Use ONLY this policy text. If it does not answer, reply ABSTAIN.\nPolicy: {ev}\nQuestion: {request['prompt']}"
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0, "seed": 1}}).encode()
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.host + "/api/generate", body, {"Content-Type": "application/json"}), timeout=self.timeout) as r:
                out = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ProviderError(type(e).__name__, str(e), recoverable=True)
        return {"text": out.get("response", "").strip(), "meta": {"latency_ms": int((time.time() - t0) * 1000)}}
