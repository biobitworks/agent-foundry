"""Append-only run recorder and verifier.

Verification proves internal consistency (schema, ordering, id recomputation).
It does not prove authenticity (no signing) or the truth of any payload.
"""
import json
import os
from pathlib import Path

from .events import build_event, validate_event
from .ids import content_id, occurrence_id

DEFAULT_STATE = {
    "failure": "FAILED",
    "abstention": "NOT_COMPUTED",
    "evidence": "OBSERVED",
    "model": "EXECUTED",
    "tool": "EXECUTED",
}


class RunRecorder:
    def __init__(self, run_id: str, directory, phase_id=None):
        self.run_id = run_id
        self.phase_id = phase_id
        self.path = Path(directory) / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"run log already exists (append-only, refusing to overwrite): {self.path}")
        self.seq = 0
        self.last_id = None
        self.ids = []

    def record(self, event_type, actor, payload, state=None, deps=(), meta=None, ts=None) -> dict:
        state = state or DEFAULT_STATE.get(event_type, "OBSERVED")
        for d in deps:
            if d not in self.ids:
                raise ValueError(f"dep {d} is not an earlier event of run {self.run_id}")
        ev = build_event(self.run_id, self.seq, event_type, actor, payload, state, deps, self.last_id, self.phase_id, meta, ts)
        validate_event(ev)  # never persist an invalid event
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.ids.append(ev["event_id"])
        self.last_id = ev["event_id"]
        self.seq += 1
        return ev


def read_run(path, verify=True) -> list:
    events = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if verify:
        verify_run(events)
    return events


def verify_run(events: list) -> None:
    seen = set()
    prev = None
    run_id = events[0]["run_id"] if events else None
    for i, ev in enumerate(events):
        validate_event(ev)
        if ev["run_id"] != run_id:
            raise ValueError(f"seq {i}: mixed run_id")
        if ev["seq"] != i:
            raise ValueError(f"seq gap or reorder at position {i} (seq={ev['seq']})")
        if ev["prev_event_id"] != prev:
            raise ValueError(f"seq {i}: prev_event_id chain broken")
        cid = content_id(ev["event_type"], ev["actor"], ev["payload"])
        if cid != ev["content_id"]:
            raise ValueError(f"seq {i}: content_id does not match content (tampered or edited)")
        if occurrence_id(ev["run_id"], ev["seq"], cid) != ev["event_id"]:
            raise ValueError(f"seq {i}: event_id does not match run/seq/content")
        for d in ev["deps"]:
            if d not in seen:
                raise ValueError(f"seq {i}: dep {d} is not an earlier event")
        seen.add(ev["event_id"])
        prev = ev["event_id"]
