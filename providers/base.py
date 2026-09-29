class ProviderError(Exception):
    """Raised by a provider; the runner records it as a failure event."""

    def __init__(self, error_type: str, message: str, recoverable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.recoverable = recoverable


class Provider:
    name = "base"
    provider_kind = "real"  # "fixture" for deterministic stand-ins; never present fixtures as real runs
    model = ""

    def complete(self, request: dict) -> dict:
        """request: {prompt, evidence:[{text,...}]}; returns {text, meta}"""
        raise NotImplementedError
