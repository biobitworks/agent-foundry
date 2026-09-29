"""Ollama adapter (local execution lane). STATE: IMPLEMENTED, NOT_TESTED until an actual run succeeds."""
import json
import time
import urllib.error
import urllib.request

from .base import Provider, ProviderError


class OllamaProvider(Provider):
    name = "ollama"
    provider_kind = "real"

    def __init__(self, model, host="http://127.0.0.1:11434", timeout=240, num_predict=None):
        self.model, self.host, self.timeout, self.num_predict = model, host.rstrip("/"), timeout, num_predict

    def complete(self, request: dict) -> dict:
        ev = "\n".join(d.get("text", "") for d in request.get("evidence", []))
        if request.get("instruction"):
            prompt = f"{request['instruction']}\nInput:\n{ev}"
        else:
            prompt = (f"You are a support agent. Answer the customer's question in one sentence using ONLY the policy text below and the facts in the question. "
                  f"Reply exactly 'ABSTAIN' only if the policy text does not contain a rule that applies.\nPolicy: {ev}\nQuestion: {request['prompt']}")
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0, "seed": 1, **({"num_predict": self.num_predict or 64} if request.get("instruction") else ({"num_predict": self.num_predict} if self.num_predict else {}))}}).encode()
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.host + "/api/generate", body, {"Content-Type": "application/json"}), timeout=self.timeout) as r:
                out = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ProviderError(type(e).__name__, str(e), recoverable=True)
        return {"text": out.get("response", "").strip(), "meta": {"latency_ms": int((time.time() - t0) * 1000)}}
