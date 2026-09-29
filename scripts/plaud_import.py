"""Import an operator-exported PLAUD recording into a custody ADDENDUM run linked to a Moddik run.
  python3 scripts/plaud_import.py --parent runs/<tag>-moddik.jsonl --audio <exported audio file> [--recording-id ID] [--transcript-json FILE]
Never contacts PLAUD, never reads PLAUD credentials/tokens. Prints the exact-bytes digest."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_foundry.plaud_import import import_into_addendum  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--parent", required=True)
ap.add_argument("--audio", required=True)
ap.add_argument("--recording-id")
ap.add_argument("--transcript-json")
ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent.parent / "runs"))
a = ap.parse_args()
print(json.dumps(import_into_addendum(a.parent, a.audio, a.out_dir, recording_id=a.recording_id, transcript_json=a.transcript_json), indent=1))
