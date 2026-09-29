# Live demo runbook (rehearsed steps; each is NOT_TESTED until a timed run is recorded)

0. `git fetch && python3 scripts/preflight.py`. It warms LFM2.5-1.2B, so the first live click is ~15 s, not ~60 s. Cold-load on this 16 GB Mac is 30-150 s.
1. Start the inspector: `python3 -m uvicorn api.server:app --host 127.0.0.1 --port 8765`, open http://localhost:8765
2. Recorded, real: pick "REAL: Antigence core vs lfm350m · adv-ignore" -> the deterministic core flags the attack, the 350M model does not. Open the model event, then the field diff, then the affected claim.
3. Live, real: click **Run live** with the default injection text (1.2B model). Then a benign input -> headline reads "Same answer, different responder".
4. Failure kept: pick "REAL: Antigence core vs lfm2p6b" -> INVALID OUTPUT is visible as a failure event; nothing is repaired or hidden.
5. Replay: pick "REAL: same local model, evidence changed", press "Replay same config (verify)". Only a real re-execution sets replayable.
6. Export lineage: declared edges only; no causality, no signature, no Merkle/MMR claims.
7. Sponsor path (blocked until DuploCloud is READY): see integrations/duplocloud/EXTENSION_SMOKE_SPEC.md.

Fallbacks: model cold or Ollama down -> use recorded scenarios (all real, hash-checked in tests); never present a fixture as a real model.
