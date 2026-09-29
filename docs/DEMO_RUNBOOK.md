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

## Moddik local-simulation evidence demo (2-4 min) — LOCAL SIMULATION, source=SIMULATED

Prep (once): `scripts/moddik_neo4j.sh up` (project-local Neo4j, rebuildable projection) and `ollama run hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M ""` to warm the model (a cold load on this 16 GB Mac can be slow).
Start the inspector **from your own terminal** (the app's preview sandbox blocks the Neo4j socket): `python3 -m uvicorn api.server:app --host 127.0.0.1 --port 8765`, open `http://localhost:8765/?moddik=recorded:rehearsal_1`.

1. Press **Play stream**: the deterministic simulator's sensor state advances (nutrient falls, waste rises; amber = illustrative rule).
2. Center column: every sensor observation is an independently addressable event; click a tick group to expand it, click an event to see its canonical payload.
3. Right column: sensor leaves -> HardwareBreakpoint (root, re-verified now) -> transcript -> local Liquid decision -> deterministic verifier -> SIMULATED action -> next breakpoint. Expand the 7 committed leaves.
4. Say / type "What changed, and does this culture need intervention?" and press **Run live now** (about 1-3 min; recorded run is the fallback: it is a real execution, not a mock).
5. **Query Neo4j projection** shows the same route from the graph; deleting the projection loses nothing (`python3 scripts/moddik_verify.py --neo4j`).
6. Bonus: **Replay with one sensor difference** opens the paired inspector: identical prefix (same nominal breakpoint root), first divergence = the changed nutrient reading, no action derived downstream.

Not part of the demo (state): live microphone/ASR NOT_TESTED; PLAUD custody lane NOT_TESTED on a real recording; real Moddik hardware NOT_CONNECTED.
Re-verify offline: `python3 scripts/moddik_verify.py` (add `--neo4j`, `--write-receipt`).
