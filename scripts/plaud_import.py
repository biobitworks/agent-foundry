"""Import an operator-exported PLAUD recording into a custody ADDENDUM run linked to a Moddik run.
  python3 scripts/plaud_import.py --parent demo/recorded/moddik/<name>/control.jsonl --audio .local/plaud/<file> --attest-plaud-export
        [--recording-id ID] [--transcript-json FILE] [--out-dir DIR] [--session-note TEXT]
  python3 scripts/plaud_import.py --verify <addendum.jsonl> --audio <file>      # re-hash the exported bytes against the recorded digest
Never contacts PLAUD, never reads PLAUD credentials/tokens. The audio file itself is never committed (it may hold private speech); only the addendum
run (filename, byte count, sha256, import time, relation to the parent run) is. Relation is PARALLEL_CAPTURE/SAME_SESSION, never byte identity with a local capture."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_foundry.plaud_import import import_into_addendum, sha256_file  # noqa: E402
from agent_foundry.recorder import read_run  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--parent")
ap.add_argument("--audio", required=True)
ap.add_argument("--verify")
ap.add_argument("--recording-id")
ap.add_argument("--transcript-json")
ap.add_argument("--attest-plaud-export", action="store_true", help="operator attests the file is a PLAUD export (recorded, not verified)")
ap.add_argument("--session-note")
ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent.parent / "runs"))
a = ap.parse_args()
if a.verify:
    art = next(e for e in read_run(a.verify) if e["event_type"] == "artifact")["payload"]
    h, n = sha256_file(a.audio)
    ok = art["digest"] == f"sha256:{h}" and art["size_bytes"] == n
    print(json.dumps({"recorded_digest": art["digest"], "recorded_size_bytes": art["size_bytes"], "file_digest": f"sha256:{h}", "file_size_bytes": n, "MATCH": ok}, indent=1))
    sys.exit(0 if ok else 1)
if not a.parent:
    ap.error("--parent is required unless --verify")
print(json.dumps(import_into_addendum(a.parent, a.audio, a.out_dir, recording_id=a.recording_id, transcript_json=a.transcript_json, attest_plaud_export=a.attest_plaud_export,
                                      session_note=a.session_note), indent=1))
