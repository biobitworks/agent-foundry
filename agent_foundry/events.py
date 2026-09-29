import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from .ids import content_id, occurrence_id

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "events" / "event.schema.json"
SCHEMA_VERSION = "agent-foundry.event.v1"
_validator = None


def validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        _validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    return _validator


def validate_event(event: dict) -> None:
    errors = sorted(validator().iter_errors(event), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        loc = "/".join(str(p) for p in e.path) or "<root>"
        raise ValueError(f"invalid event at {loc}: {e.message}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_event(run_id, seq, event_type, actor, payload, state, deps=(), prev_event_id=None, phase_id=None, meta=None, ts=None) -> dict:
    cid = content_id(event_type, actor, payload)
    ev = {
        "schema_version": SCHEMA_VERSION,
        "event_id": occurrence_id(run_id, seq, cid),
        "content_id": cid,
        "run_id": run_id,
        "seq": seq,
        "prev_event_id": prev_event_id,
        "ts": ts or now_iso(),
        "event_type": event_type,
        "state": state,
        "actor": actor,
        "payload": payload,
        "deps": list(deps),
    }
    if phase_id is not None:
        ev["phase_id"] = phase_id
    if meta:
        ev["meta"] = meta
    return ev
