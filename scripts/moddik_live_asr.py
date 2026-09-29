"""Live microphone -> local ASR -> TranscriptEvent -> existing Moddik workflow (successor lane; the admitted typed-input demo is untouched).

  Step 1 (operator, Terminal panel; macOS asks for microphone permission interactively; this script cannot and does not bypass it):
      python3 scripts/moddik_live_asr.py capture [--seconds 8] [--device :1]
      -> records the Mac mic, transcribes LOCALLY with LFM2.5-Audio (isolated .venv-asr), prints the text, writes .local/asr/<id>.json (+ the wav). Nothing acts on it yet.
  Step 2 (after you read the transcript):
      python3 scripts/moddik_live_asr.py run <id> [--model lfm2p6b]
      -> feeds the confirmed transcript into the existing workflow as an ordinary transcript evidence event (transcript_source=LOCAL_ASR:lfm2.5-audio-1.5b),
         with the mic recording as an audio artifact. The only 'action' the workflow can produce is a SIMULATED recommendation (actuation NONE).
The wav and transcript live in gitignored .local/asr/ (private speech). LIVE_ASR=PASS is claimed only if all of it executes; see docs/LIVE_ASR_ACCEPTANCE.md."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_foundry import asr  # noqa: E402

ASR_DIR = ROOT / ".local" / "asr"
ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
c = sub.add_parser("capture")
c.add_argument("--seconds", type=int, default=8)
c.add_argument("--device", default=":1", help="avfoundation audio device index (see: ffmpeg -f avfoundation -list_devices true -i '')")
c.add_argument("--wav", help="transcribe an existing wav instead of the microphone (NOT a LIVE_ASR test)")
r = sub.add_parser("run")
r.add_argument("id")
r.add_argument("--model", default="lfm2p6b")
a = ap.parse_args()
ASR_DIR.mkdir(parents=True, exist_ok=True)

if a.cmd == "capture":
    aid = "asr" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    wav = ASR_DIR / f"{aid}.wav"
    rec = {"id": aid, "state": "STARTED", "source": "EXISTING_WAV" if a.wav else "LOCAL_MIC"}
    if a.wav:
        wav = Path(a.wav)
    else:
        print(f"START capture {a.seconds}s from mic device {a.device}: speak after the countdown", flush=True)
        for i in (3, 2, 1):
            print(f"  {i}...", flush=True)
            time.sleep(1)
        print("  RECORDING", flush=True)
        try:
            asr.capture_wav(wav, a.seconds, a.device)
        except Exception as e:
            rec.update(state="FAILED", stage="capture", reason=str(e)[-300:])
            (ASR_DIR / f"{aid}.json").write_text(json.dumps(rec, indent=1))
            print("FAIL capture:", rec["reason"])
            sys.exit(2)
    print("RUNNING local ASR (LFM2.5-Audio in .venv-asr; first load can take minutes)", flush=True)
    t0 = time.time()
    try:
        res = asr.transcribe(wav)
    except Exception as e:
        rec.update(state="FAILED", stage="asr", reason=str(e)[-400:], wav=str(wav))
        (ASR_DIR / f"{aid}.json").write_text(json.dumps(rec, indent=1))
        print("FAIL asr:", rec["reason"])
        sys.exit(3)
    meta, _ = asr.transcript_and_audio_event(wav, res["text"], res["engine"])
    rec.update(state="TRANSCRIBED_AWAITING_CONFIRMATION", text=res["text"], asr=res, wav=str(wav), audio_digest=meta["audio_digest"], wall_s=round(time.time() - t0, 1))
    (ASR_DIR / f"{aid}.json").write_text(json.dumps(rec, indent=1))
    print(f"PASS-so-far transcript: {res['text']!r}\n  id={aid}  (asr {res['infer_s']}s on {res['device']}, model load {res['load_s']}s)\n  next: python3 scripts/moddik_live_asr.py run {aid}")
else:
    rec = json.loads((ASR_DIR / f"{a.id}.json").read_text())
    if rec.get("state") != "TRANSCRIBED_AWAITING_CONFIRMATION" or rec.get("source") != "LOCAL_MIC":
        print("REFUSED: only a confirmed-pending LOCAL_MIC transcript can be consumed (state=%s source=%s)" % (rec.get("state"), rec.get("source")))
        sys.exit(4)
    from agent_foundry import moddik_run as mr
    meta, audio_ev = asr.transcript_and_audio_event(rec["wav"], rec["text"], rec["asr"]["engine"])
    meta = {**meta, "asr_device": rec["asr"]["device"], "asr_infer_s": rec["asr"]["infer_s"], "microphone_capture": "LOCAL_MIC (ffmpeg avfoundation, 16 kHz mono)"}
    print(f"START workflow with transcript {rec['text']!r}", flush=True)
    res = mr.run_moddik(f"{a.id}-moddik", ROOT / "runs", transcript=rec["text"], transcript_source=f"LOCAL_ASR:{rec['asr']['engine']}", transcript_meta=meta, audio_events=[audio_ev],
                        model_key=a.model, label="CONTROL_RUN")
    ev = res["events"]
    tr = next(e for e in ev if e["event_type"] == "evidence" and "transcript_source" in e["payload"])
    m = next((e for e in ev if e["event_type"] == "model"), None)
    consumed = bool(m) and tr["event_id"] in m["deps"] and rec["text"] in m["payload"]["request"]["prompt"]
    rec.update(state="CONSUMED_BY_WORKFLOW" if consumed else "NOT_CONSUMED", run=str(res["run_path"]), transcript_event_id=tr["event_id"], summary=res["summary"])
    (ASR_DIR / f"{a.id}.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({"consumed_by_model_prompt": consumed, "transcript_event_id": tr["event_id"], "summary": res["summary"]}, indent=1))
    print("LIVE_ASR", "PASS" if consumed else "PARTIAL (transcript emitted but not consumed)")
