# HackerSquad video script: Agent Foundry (target 150-210 s)

LOCAL SIMULATION (source=SIMULATED). Thresholds ILLUSTRATIVE. Recommendation SIMULATED. ACTUATION=NONE. Neo4j = rebuildable projection. Merkle = integrity over declared leaves, not sensor truth. PLAUD is not part of this video (real export not imported).

Narration seconds are ESTIMATES (words / 2.5 per second = 150 wpm), plus roughly 4 s of pause per click.

## PROBLEM (60 words, ~24.0s)

"When an AI agent behaves differently, you get logs and a shrug. Which reading changed? Which evidence did the model see? Could we reproduce it? Agent Foundry lets you debug agents like software: what evidence did it use, where did the run first diverge, and can we reproduce it? Here is a fully simulated Moddik cell-culture plate, streaming sensor data."

## STACK (47 words, ~18.8s)

"Agent Foundry is the canonical run recorder and debugger. A Liquid AI model runs locally on this laptop, with no cloud, and does the reasoning. Neo4j is a rebuildable graph of the evidence. Everything you see is simulated. No hardware was connected, and the thresholds are illustrative."

## SENSOR_EVIDENCE (31 words, ~12.4s)
*CLICK 1: group 'evidence x7 - tick 9' in the timeline. CLICK 2: row 'nutrient = 10.197 mM - SIMULATED'.*

"Every sensor observation becomes its own event. Each observation is independently addressable evidence. This is the nutrient reading at tick nine: marked simulated, with its own event ID and content hash."

## BREAKPOINT (34 words, ~13.6s)
*CLICK 3: 'Show / hide the 7 committed sensor leaves' (right column, step 2).*

"At a checkpoint, the ordered sensor-state leaves are committed into a verified hardware-state Merkle breakpoint. Seven leaves, one root, recomputed from the stored leaf bytes and passing. That proves integrity of these values, not that they are true."

## NEO4J (37 words, ~14.8s)
*CLICK 4: 'Query Neo4j projection'.*

"Neo4j is not our canonical provenance store. It is a rebuildable projection that lets us inspect the evidence graph. We can delete it and rebuild it from the run log, and the run itself does not change."

## MODEL_DECISION (48 words, ~19.2s)
*CLICK 5: right column step 4 'local model decision', then point at step 5 and step 6.*

"The local Liquid AI model receives bounded evidence: nutrient, waste, and a policy check. Agent Foundry shows which evidence it was given and cited, a deterministic verifier checks those citations, and the result is a simulated medium exchange recommendation. The thresholds are illustrative. There is no physical actuation."

## FIRST_DIVERGENCE (56 words, ~22.4s)
*CLICK 6: 'Replay with one sensor difference'. CLICK 7: the red FIRST DIVERGENCE row.*

"Now the payoff. We changed one evidence value, nutrient at tick nine, from ten point two to twelve point seven, and re-ran from the same seed. Everything before it is identical, including the earlier breakpoint. Agent Foundry identifies the first event where behavior diverged. Downstream, the model now says no intervention, and no action is produced."

## CODE (40 words, ~16.0s)
*Show 3 files (see operator card).*

"The code is small. The simulator is deterministic and seeded. Breakpoints use an ordered Merkle commitment recomputed from stored leaf bytes. And the Neo4j projection is rebuilt from the run log, never the other way around. Seventy nine tests pass."

## CLOSE (22 words, ~8.8s)

"So: the evidence, the first divergence, and a way to reproduce it. Debug your AI agents like software. This is Agent Foundry."

**Total: 375 words, ~150 s narration + ~28 s click pauses.**

## Wording guardrails
- Say "re-ran from the same seed; everything before that reading is identical", not "resumed from a stored checkpoint" (the simulator is deterministic and re-executed; the earlier breakpoint root is verified identical).
- Say "evidence it was given and cited", not that the model "understood" it. The verifier proves the cited IDs were in the prompt, not that the recommendation is biologically correct.
- The question was typed operator text (transcript_source=OPERATOR_TEXT_INPUT). Do not say it was spoken or transcribed.
- Do not claim PLAUD, live ASR, real Moddik hardware, validated thresholds, or actuation.

## VIDEO OPERATOR CARD (one screen)

**START** (terminal): `cd ~/projects/active/agent-foundry && scripts/moddik_neo4j.sh up && python3 -m uvicorn api.server:app --host 127.0.0.1 --port 8765`
**OPEN**: `http://localhost:8765/?moddik=recorded:rehearsal_1` (window >= 1300 px wide so the 3 columns sit side by side; scroll ~250 px so the amber SIMULATION banner is at the top)

**CLICK PATH**
1. Timeline (center): click the group **"evidence x7 - tick 9"**, then the row **"nutrient = 10.197 mM"** (event 68) -> inspector shows SIMULATED + event id.
2. Right column, step 2: click **"Show / hide the 7 committed sensor leaves"** -> root f56b0104..., "re-verified now: PASS".
3. Right column: click **"Query Neo4j projection"** -> label counts + route.
4. Right column: click step **4 (local model decision)**; point at step 5 (verifier PASS) and step 6 (MEDIUM_EXCHANGE_RECOMMENDED, actuation NONE).
5. Top: click **"Replay with one sensor difference"**, then the red **FIRST DIVERGENCE** row (event 68: 10.197 -> 12.697).

**CODE FILES** (20-30 s): `agent_foundry/moddik_sim.py` lines 34-52 (`_noise`, `reading`: seeded, source=SIMULATED) | `agent_foundry/merkle.py` lines 16-44 (`CONSTRUCTION`..`merkle_root`) | `agent_foundry/moddik_graph.py` lines 91-131 (`project_run`: MERGE projection, USED_EVIDENCE/RECOMMENDED, no causal edges). Tests: `make test` -> 79 passed.

**DO NOT CLICK**: "Run live now" (model took 47 s to 135 s under memory pressure) | the amber Antigence "Run live" strip and the Scenario dropdown at the top of the page (older feature, will distract) | any PLAUD / ASR claim (not tested).

**BACKUP**: Neo4j button says UNAVAILABLE -> say "the graph is a projection; the canonical run is right here" and continue; the evidence path is drawn from the run log, not from Neo4j. Page blank -> restart the server command above. Divergence view fails -> `http://localhost:8765/api/moddik/pair/recorded:rehearsal_1` shows the same JSON; or narrate from the run log rows 68 (nutrient) and 80 (decision vs abstention).

**KNOWN-GOOD COMMIT**: see the final push receipt (main on GitHub).
