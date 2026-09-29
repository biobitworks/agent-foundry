"""Checkpoint descriptors and replay.

Replay only ever sets `replayable` after a real re-execution matched the original (DIVERGENCE=NULL).
A replay that diverges is reported as REPLAY_DIVERGED. A branch (config override) is a new variant and never
sets `replayable`. Recorded runs are never mutated.
"""
from .compare import compare_runs
from .ids import canonical_json, sha256_hex
from .recorder import RunRecorder
from .runner import answer


def make_checkpoint(events: list, at_seq: int) -> dict:
    if not (0 <= at_seq < len(events)):
        raise ValueError(f"at_seq {at_seq} outside run of {len(events)} events")
    if events[at_seq]["event_type"] != "evidence":
        raise ValueError("unsupported resume point: a checkpoint must be taken immediately after an 'evidence' event")
    prefix = events[: at_seq + 1]
    cids = [e["content_id"] for e in prefix]
    nxt = events[at_seq + 1]["event_type"] if at_seq + 1 < len(events) else None
    return {
        "schema": "agent-foundry.checkpoint.v1",
        "hydradg_compatible": "UNKNOWN (HydraDG descriptor schema not inspected)",
        "checkpoint_id": f"cp:{events[0]['run_id']}@{at_seq}",
        "source_run_id": events[0]["run_id"],
        "at_seq": at_seq,
        "last_event_id": prefix[-1]["event_id"],
        "prefix_content_ids": cids,
        "prefix_digest": "sha256:" + sha256_hex(canonical_json(cids)),
        "config": events[0]["meta"]["config"],
        "task_id": events[0]["payload"]["task_id"],
        "next_event_type_in_source": nxt,
        "replayable": "NOT_TESTED",
    }


def default_checkpoint_seq(events: list) -> int:
    for i, e in enumerate(events):
        if e["event_type"] == "evidence":
            return i
    raise ValueError("run has no evidence event; nothing to checkpoint")


def replay(task: dict, events: list, out_dir, run_id: str, at_seq: int = None, override: dict = None) -> dict:
    at_seq = default_checkpoint_seq(events) if at_seq is None else at_seq
    cp = make_checkpoint(events, at_seq)
    config = {**cp["config"], **(override or {})}
    mode = "branch" if override and any(config.get(k) != cp["config"].get(k) for k in config) else "verify"
    rec = RunRecorder(run_id, out_dir)
    idmap, last = {}, None
    for i, e in enumerate(events[: at_seq + 1]):
        meta = dict(e.get("meta") or {})
        if i == 0:
            meta.update({"config": config, "label": "REPLAY_RUN", "variable": "provider_model" if mode == "branch" else "none", "replay_of": cp["checkpoint_id"], "replay_mode": mode})
        new = rec.record(e["event_type"], e["actor"], e["payload"], state=e["state"], deps=[idmap[d] for d in e["deps"]], meta=meta or None)
        idmap[e["event_id"]] = new["event_id"]
        last = new
    # true resume: the RECORDED evidence text is the input; the corpus is not consulted
    answer(rec, task, config, last, last["payload"]["excerpt"])
    from .recorder import read_run
    replayed = read_run(rec.path)
    cmp_ = compare_runs(events, replayed)
    prefix_ok = [e["content_id"] for e in replayed[: at_seq + 1]] == cp["prefix_content_ids"]
    orig_failed = any(e["event_type"] == "failure" for e in events)
    replay_failed = any(e["event_type"] == "failure" for e in replayed) and not orig_failed
    if mode == "verify" and replay_failed:
        # a provider error says nothing about reproducibility: do NOT report it as a divergence or as non-replayable
        state, replayable = "REPLAY_FAILED", "UNKNOWN"
    elif mode == "verify":
        state = "EXECUTED" if cmp_["DIVERGENCE"] == "NULL" else "REPLAY_DIVERGED"
        replayable = True if state == "EXECUTED" else False
    else:
        state, replayable = "BRANCH_EXECUTED", "NOT_APPLICABLE"
    cp = {**cp, "replayable": replayable if mode == "verify" and replayable != "UNKNOWN" else ("UNKNOWN" if replayable == "UNKNOWN" else "NOT_TESTED")}
    return {"mode": mode, "checkpoint": cp, "replay_state": state, "replayable": replayable, "prefix_identical": prefix_ok,
            "replay_run": replayed, "comparison_vs_original": cmp_,
            "limits": ["n=1 replay; nondeterminism NOT_COMPUTED", "replayable=true means: this run's suffix re-executed to identical content once; not a guarantee"]}
