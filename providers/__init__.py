from .base import Provider, ProviderError  # noqa: F401
from .fixture import FixtureProvider  # noqa: F401


def get_provider(cfg: dict):
    kind = cfg.get("provider", "fixture")
    if kind == "fixture":
        return FixtureProvider(cfg.get("model", "fixture-a"))
    if kind == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(cfg["model"], cfg.get("host", "http://127.0.0.1:11434"))
    raise ValueError(f"unknown provider: {kind}")
