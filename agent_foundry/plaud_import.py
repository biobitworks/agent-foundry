"""PLAUD audio CHAIN-OF-CUSTODY lane.

Hashes the EXACT bytes of an operator-supplied PLAUD export and records it as an `artifact` event in a small append-only ADDENDUM run
that names its parent run (id + sha256 of the parent log). Nothing here talks to PLAUD: the account-linked path (PLAUD MCP/CLI OAuth,
`get_file` presigned URL download) is a standing config + OAuth grant + download and needs explicit operator authorization; it is DEFERRED.

Relationship semantics (never upgraded):
  * a PLAUD recording and the local microphone capture are different captures of the same session:
      relation = PARALLEL_CAPTURE / SAME_SESSION, same_bytes = false. Their bytes are never claimed identical.
  * a transcript is attached to a recording only if the evidence is recorded (recording id present in the export JSON AND in the file name);
    otherwise relationship = UNKNOWN.
"""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .ids import canonical_json
from .recorder import RunRecorder, read_run

PLAUD_ACTOR = {"kind": "tool", "name": "plaud-export-import", "provider": "plaud", "provider_kind": "real"}
SYSTEM = {"kind": "system", "name": "agent-foundry-plaud-import"}


def sha256_file(path) -> tuple:
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def probe_media(path) -> dict:
    """Descriptive container metadata via ffprobe (NOT identity; identity is the sha256 of the exact bytes). {} if ffprobe is unavailable or the file is not media."""
    if not shutil.which("ffprobe"):
        return {"available": False}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration:stream=codec_name,sample_rate,channels", "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
    try:
        j = json.loads(r.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        return {"available": True, "is_media": bool(j.get("format")), "container": (j.get("format") or {}).get("format_name"), "duration_s": float((j.get("format") or {}).get("duration") or 0) or None,
                "codec": st.get("codec_name"), "sample_rate": st.get("sample_rate"), "channels": st.get("channels")}
    except (ValueError, TypeError):
        return {"available": True, "is_media": False}


def audio_artifact_payload(path, *, capture: str, exported_via: str = None, recording_id: str = None, transcript: dict = None, parallel_capture_of: str = None) -> dict:
    """Payload for an `artifact` event. digest = sha256 of the exact file bytes as they sit on disk."""
    digest, size = sha256_file(path)
    p = {"artifact_type": "audio", "ref": Path(path).name, "source_filename": Path(path).name, "digest": f"sha256:{digest}", "size_bytes": size, "capture": capture,
         "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "media_probe": probe_media(path)}
    if exported_via:
        p["exported_via"] = exported_via
    if recording_id:
        p["recording_id"] = recording_id
    if transcript:
        p["transcript"] = transcript
    if parallel_capture_of:
        p["parallel_capture_of"] = parallel_capture_of  # content_id of the other capture
        p["relation"] = "PARALLEL_CAPTURE/SAME_SESSION"
        p["same_bytes"] = False
    return p


def load_transcript_json(path, recording_id: str = None, audio_name: str = None) -> dict:
    """Hash the exact export bytes and record what relationship evidence actually exists. Expects PLAUD get_file/get_transcript-shaped JSON but does not require it."""
    digest, size = sha256_file(path)
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    rid = doc.get("id") if isinstance(doc, dict) else None
    segs = doc.get("source_list") if isinstance(doc, dict) else None
    evidence = []
    if rid and recording_id and rid == recording_id:
        evidence.append("transcript JSON id equals the declared recording id")
    if recording_id and audio_name and recording_id in audio_name:
        evidence.append("recording id appears in the audio file name")
    return {"ref": Path(path).name, "digest": f"sha256:{digest}", "size_bytes": size, "segment_count": len(segs) if isinstance(segs, list) else None,
            "relationship_to_recording": "SUPPORTED_BY_RECORDED_EVIDENCE" if len(evidence) == 2 else "UNKNOWN", "relationship_evidence": evidence}


def import_into_addendum(parent_run_path, audio_path, out_dir, *, recording_id: str = None, transcript_json=None, exported_via: str = "operator-supplied file export (PLAUD app/MCP/CLI)",
                         parallel_capture_of_content_id: str = None, addendum_id: str = None, attest_plaud_export: bool = False, session_note: str = None) -> dict:
    """Creates <parent>-plaud-<n>.jsonl. The parent log is never modified."""
    parent = read_run(parent_run_path)  # verifies the parent
    parent_sha = hashlib.sha256(Path(parent_run_path).read_bytes()).hexdigest()
    run_id = addendum_id or f"{parent[0]['run_id']}-plaud"
    rec = RunRecorder(run_id, out_dir)
    start = rec.record("run_started", SYSTEM, {"task_id": "moddik-plaud-custody-addendum", "parent_run_id": parent[0]["run_id"], "parent_log_sha256": parent_sha,
                                              "relation_to_parent": "SAME_SESSION (operator-declared)", "limits": ["hash proves identity of the exported bytes, not their content or authenticity of the recorder"]},
                       meta={"config": {"source": "operator_supplied_export"}, "label": "CONTROL_RUN"})
    tr = load_transcript_json(transcript_json, recording_id, Path(audio_path).name) if transcript_json else None
    payload = audio_artifact_payload(audio_path, capture="PLAUD_DEVICE", exported_via=exported_via, recording_id=recording_id, transcript=tr, parallel_capture_of=parallel_capture_of_content_id)
    payload["relation_to_parent_run"] = "PARALLEL_CAPTURE/SAME_SESSION (operator-declared; not verified)"
    payload["same_bytes_as_local_capture"] = False if parallel_capture_of_content_id else "NOT_APPLICABLE (no local audio capture in the parent run; it used typed operator text)"
    payload["operator_attestation"] = "operator attests this file was exported from a PLAUD recording" if attest_plaud_export else "NOT_ATTESTED"
    if session_note:
        payload["session_note"] = session_note
    art = rec.record("artifact", PLAUD_ACTOR, payload, state="OBSERVED", deps=[start["event_id"]])
    rec.record("run_completed", SYSTEM, {"status": "completed"}, state="EXECUTED", deps=[art["event_id"]])
    return {"run_path": str(rec.path), "digest": payload["digest"], "size_bytes": payload["size_bytes"], "artifact_event_id": art["event_id"], "transcript_relationship": tr and tr["relationship_to_recording"], "source_filename": payload["source_filename"], "attested": attest_plaud_export,
            "status": "PLAUD_EXPORTED_AUDIO_CUSTODY=PASS_CANDIDATE (operator-attested exact-bytes import; scoped: no MCP/SDK/API/live-integration claim)" if attest_plaud_export and payload["media_probe"].get("is_media") else "IMPORTED_NOT_ADMITTABLE (missing attestation or not decodable media)"}
