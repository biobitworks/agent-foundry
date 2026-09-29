"""LFM2.5-Audio-1.5B ASR worker. Runs ONLY inside the isolated .venv-asr (liquid-audio, torch). No cloud calls after the weights are cached.
Usage: .venv-asr/bin/python scripts/asr_worker.py <wav> [--device mps|cpu]
Follows the vendor ASR recipe (liquid-audio README): sequential generation, fixed system prompt 'Perform ASR.'. Prints ONE JSON line on stdout."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / ".local" / "hf"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # weights must already be cached; never fetch during a run
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from liquid_audio import ChatState, LFM2AudioModel, LFM2AudioProcessor  # noqa: E402

wav_path = sys.argv[1]
device = sys.argv[sys.argv.index("--device") + 1] if "--device" in sys.argv else ("mps" if torch.backends.mps.is_available() else "cpu")
HF_REPO = "LiquidAI/LFM2.5-Audio-1.5B"
t0 = time.time()
processor = LFM2AudioProcessor.from_pretrained(HF_REPO, device=device).eval()
model = LFM2AudioModel.from_pretrained(HF_REPO, device=device).eval()
t_load = time.time() - t0
wav, sr = sf.read(wav_path, dtype="float32")
if wav.ndim > 1:
    wav = wav.mean(axis=1)
chat = ChatState(processor)
chat.new_turn("system")
chat.add_text("Perform ASR.")
chat.end_turn()
chat.new_turn("user")
chat.add_audio(torch.from_numpy(wav).unsqueeze(0), sr)
chat.end_turn()
chat.new_turn("assistant")
t1 = time.time()
out = []
with torch.no_grad():
    for t in model.generate_sequential(**chat, max_new_tokens=256):
        if t.numel() == 1:
            out.append(processor.text.decode(t))
import re  # noqa: E402
text = re.sub(r"<\|[^|>]*\|>", "", "".join(out)).strip()  # strip special tokens such as <|im_end|> (recorded: raw output contained one)
print(json.dumps({"text": text, "raw_text": "".join(out), "engine": "lfm2.5-audio-1.5b", "model": HF_REPO, "device": device, "load_s": round(t_load, 1), "infer_s": round(time.time() - t1, 1),
                  "audio_s": round(len(wav) / sr, 2), "sample_rate": sr}))
