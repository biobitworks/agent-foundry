"""Local audio capture + ASR lane. STATE: IMPLEMENTED as an interface, NOT_TESTED end to end.

  * capture: `ffmpeg -f avfoundation` from the Mac microphone. Needs the macOS microphone permission for the calling app (operator action).
  * ASR engine "lfm2.5-audio": LiquidAI/LFM2.5-Audio-1.5B through the `liquid-audio` package (sequential generation, ASR). Needs `pip install liquid-audio`
    plus multi-GB weights; NOT installed here, so importing it raises EngineUnavailable. No cloud fallback is attempted.
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


def transcribe(wav_path, engine: str = "lfm2.5-audio") -> dict:
    if engine != "lfm2.5-audio":
        raise EngineUnavailable(f"unknown engine {engine}")
    try:
        import liquid_audio  # noqa: F401
    except ImportError as e:
        raise EngineUnavailable("liquid-audio is not installed; LFM2.5-Audio ASR is NOT_TESTED") from e
    raise EngineUnavailable("engine wiring intentionally left unexecuted until an operator-approved install and a demonstrated reliable transcription")


def transcript_and_audio_event(wav_path, text: str, engine: str) -> tuple:
    """Returns (transcript_meta, audio_event_spec) for run_moddik(transcript_source=f'LOCAL_ASR:{engine}', ...)."""
    payload = audio_artifact_payload(wav_path, capture="LOCAL_MIC")
    return ({"audio_digest": payload["digest"], "asr_engine": engine},
            {"actor": {"kind": "tool", "name": "local-mic-capture", "provider": "ffmpeg-avfoundation", "provider_kind": "real"}, "payload": payload})
