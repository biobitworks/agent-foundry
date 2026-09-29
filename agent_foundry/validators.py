"""Output validators. Return None if valid, else an error string. No repair, no coercion."""
import json


def injection_json(text: str):
    t = text.strip()
    try:
        obj = json.loads(t)
    except json.JSONDecodeError as e:
        return f"not valid JSON: {e.msg}"
    if not isinstance(obj, dict) or set(obj) != {"injection"} or not isinstance(obj["injection"], bool):
        return 'expected exactly {"injection": true|false}'
    return None


VALIDATORS = {"injection_json": injection_json}
