"""Identity helpers. Hashes establish identity, not truth."""
import hashlib
import json


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_id(event_type: str, actor: dict, payload: dict) -> str:
    """CONTENT_ID: independent of run, position, time, meta and deps."""
    return "cid:sha256:" + sha256_hex(canonical_json({"event_type": event_type, "actor": actor, "payload": payload}))


def occurrence_id(run_id: str, seq: int, cid: str) -> str:
    """OCCURRENCE_ID: one appearance of a content in one run at one position."""
    return "occ:sha256:" + sha256_hex(f"{run_id}|{seq}|{cid}")
