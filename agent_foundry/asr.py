"""Local audio capture + ASR lane. STATE: IMPLEMENTED as an interface, NOT_TESTED end to end.

  * capture: `ffmpeg -f avfoundation` from the Mac microphone. Needs the macOS microphone permission for the calling app (operator action).
  * ASR engine "lfm2.5-audio": LiquidAI/LFM2.5-Audio-1.5B through `liquid-audio` in the ISOLATED .venv-asr (subprocess worker, scripts/asr_worker.py); weights cached under .local/hf.
    Successor-branch code; no cloud fallback is attempted.
The transcript that reaches the run is an ordinary `evidence` event whose transcript_source says exactly where the text came from
(OPERATOR_TEXT_INPUT vs LOCAL_ASR:<engine>). The local microphone recording and a PLAUD recording are PARALLEL captures, never the same bytes.
"""
import subprocess
from pathlib import Path

from .plaud_import import audio_artifact_payload


class EngineUnavailable(RuntimeError):
    pass


def capture_wav(out_path, seconds: int = 8, device: str = ":1") -> Path:
    """16 kHz mono wav from the default Mac microphone (avfoundation audio device index after the colon)."""
    out = Path(out_path)
    r = subprocess.run(["ffmpeg", "-y", "-f", "avfoundation", "-i", device, "-t", str(seconds), "-ac", "1", "-ar", "16000", str(out)], capture_output=True, text=True, timeout=seconds + 30)
    if r.returncode != 0 or not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("microphone capture failed (permission or device); stderr tail: " + r.stderr[-300:])
    return out


VENV_PY = Path(__file__).resolve().parent.parent / ".venv-asr" / "bin" / "python"
WORKER = Path(__file__).resolve().parent.parent / "scripts" / "asr_worker.py"


def transcribe(wav_path, engine: str = "lfm2.5-audio", device: str = None, timeout: int = 600) -> dict:
    """Runs the LFM2.5-Audio worker in the isolated venv (subprocess) and returns its JSON. No cloud fallback; if the venv/weights are absent the engine is UNAVAILABLE."""
    import json
    if not Path(wav_path).exists():
        raise FileNotFoundError(wav_path)
    if engine != "lfm2.5-audio":
        raise EngineUnavailable(f"unknown engine {engine}")
    if not VENV_PY.exists():
        raise EngineUnavailable(".venv-asr is not present; LFM2.5-Audio ASR is NOT_TESTED")
    cmd = [str(VENV_PY), str(WORKER), str(wav_path)] + (["--device", device] if device else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    line = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("{")), None)
    if r.returncode != 0 or not line:
        raise EngineUnavailable("ASR worker failed: " + (r.stderr or r.stdout)[-400:])
    return json.loads(line)


def transcript_and_audio_event(wav_path, text: str, engine: str) -> tuple:
    """Returns (transcript_meta, audio_event_spec) for run_moddik(transcript_source=f'LOCAL_ASR:{engine}', ...)."""
    payload = audio_artifact_payload(wav_path, capture="LOCAL_MIC")
    return ({"audio_digest": payload["digest"], "asr_engine": engine},
            {"actor": {"kind": "tool", "name": "local-mic-capture", "provider": "ffmpeg-avfoundation", "provider_kind": "real"}, "payload": payload})
