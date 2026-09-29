# Moddik local physical-system / agent-provenance demo: MVP design

Status: PROPOSED (design written before implementation; implementation status is tracked in the execution receipt, not here).
Parent breakpoint: `AGENT_FOUNDRY_DUPLO_THIN_EXTENSION_016` (repo HEAD `2e43abc`).
This is an Agent Foundry demonstration scenario. It is a LOCAL SIMULATION. No Moddik hardware was contacted; no sensor was physically tested.

## Question the demo answers

"Why did this local AI agent decide the simulated Moddik plate needed intervention, exactly what physical/audio evidence did it use, and can we inspect the evidence chain?"

## Source-claim discipline

- The Moddik deck (`Moddik Partnering Deck - Non-confidential - 260923.pdf`) is NOT in this repo and is NOT committed. Its concepts (unified plate/actuator, microenvironment sensing of pH, O2, CO2, nutrient/waste, mechanical stress, adaptive medium exchange) are used only as the SHAPE of the scenario. A deck claim is not a local experiment.
- Thresholds and trajectories are `SCENARIO_PARAMETER = ILLUSTRATIVE`: they come from neither the deck nor a publication and are not calibrated. They exist so the scripted scenario crosses a rule; they are declared in the run's first event and never presented as biology.
- All simulator observations carry `source=SIMULATED`.

## Official-source findings (observed 2026-09-29)

| Vendor | Finding | Consequence |
|---|---|---|
| Liquid AI, LFM2.5-2.6B model card (huggingface.co/LiquidAI/LFM2.5-2.6B) | Pure reasoning model: the chat template inserts `<think>` and it always thinks before answering. Recommended generation: temperature 0.1, top_k 50, repetition_penalty 1.1. Function calling defaults to Pythonic calls. Recommended for agentic workloads, tool use, extraction, RAG. | The earlier 0/4 strict-JSON result (64 and 512 token caps) is consistent with the reasoning preamble consuming the budget. A larger budget plus a DECLARED post-`</think>` extraction contract is a different contract than the earlier strict one; it is tested and reported separately, and 1.2B-Instruct stays the labeled fallback. |
| Liquid AI, LFM2.5-Audio-1.5B model card | End-to-end speech+text model, English only, `liquid-audio` package (PyTorch), sequential generation mode for ASR, llama.cpp GGUFs exist. | Local ASR is possible but needs a new pip package and multi-GB weights (17 GB disk free). Investigated AFTER the core passes; not on the critical path. |
| Neo4j Python driver (Context7 `/neo4j/neo4j-python-driver`, 6.x) | `GraphDatabase.driver(uri, auth=...)`, `driver.execute_query(cypher, params, database_=...)`, `MERGE` for idempotent projection. Driver 6.1.0 already installed. | Projection is idempotent MERGE; rebuildable from the canonical JSONL at any time. |
| PLAUD developer docs (dev.plaud.ai, docs.plaud.ai) | The "no public API" premise is only partly right. There is a developer platform (iOS/Android BLE SDK + a transcription API, sign-up and API keys required) and a Plaud MCP server (`npx @plaud-ai/mcp`) whose tools are `list_files`, `get_file`, `get_note`, `get_transcript`. `get_file` returns a `presigned_url` (audio, valid 24 h) plus `source_list` transcript segments. Install requires a browser OAuth sign-in to a PLAUD account and writes local client config and tokens under `~/.plaud`. | The account-linked path is a standing config + OAuth grant + an audio download, so it needs explicit operator authorization; NOT done. What is built: an importer for an operator-exported audio file (+ optional transcript JSON) that hashes the exact bytes. |

## Minimal architecture

```
moddik_sim (frozen seed, scripted trajectory, source=SIMULATED)
  -> per-reading canonical leaf -> RunRecorder  (event_type=evidence, deterministic ts = sim time)
  -> merkle.py (ordered, FCO construction) -> HardwareBreakpoint (event_type=checkpoint) + verification receipt
  -> operator transcript (typed / ASR) -> evidence event (source recorded)
  -> Neo4j projection (rebuildable; container is project-local)
  -> orchestrator-run bounded Cypher queries (event_type=tool)
  -> local Liquid model over ONLY {transcript, latest sensor evidence, retrieved history}  (event_type=model)
  -> deterministic verifier (evidence ids in context, cited values match, policy check, no causal wording)
  -> decision (SIMULATED_ACTION) -> next HardwareBreakpoint -> inspector
```

### Event mapping (existing schema, no new event format)

| Concept | Existing `event_type` |
|---|---|
| sensor reading | `evidence` (payload = canonical leaf) |
| HardwareBreakpoint | `checkpoint` |
| transcript segment | `evidence` |
| PLAUD recording / audio | `artifact` |
| Neo4j query | `tool` |
| Liquid inference | `model` |
| deterministic verifier verdict | `evaluation` |
| simulated recommendation | `decision` (state PROPOSED: never actuated) |

### Merkle / breakpoint

Reused construction: `fractal-custody-objects/training/fco_train/custody.py` (`leaf_hash` = sha256(0x00 || sha256(bytes)), `node_hash` = sha256(0x01 || l || r), odd node promoted, empty = genesis, `order_independent=False`). Ordered mode is used because sensor order is part of the state. Leaf bytes = `agent_foundry.ids.canonical_json(leaf)` UTF-8. The root is only reported when leaf bytes, order, hashes, construction and a verification receipt all exist; otherwise `MERKLE_ROOT=NOT_COMPUTED`. The Agent Foundry implementation is cross-checked against the FCO reference implementation when that checkout is present (cross-check is a receipt field, not a dependency).

A hash proves identity and integrity, not physical truth.

### Model-consumption honesty

Retrieval is executed by the orchestrator as bounded, logged Cypher queries. It is NOT model-initiated tool calling (that stays NOT_TESTED). The model sees short aliases (`S1..Sn`) for evidence; the full prompt bytes are recorded in the `model` event, so "evidence consumed" means: present in the recorded prompt AND cited in the output AND resolved by the verifier.

## File-level plan

| File | Purpose |
|---|---|
| `agent_foundry/moddik_sim.py` | deterministic simulator, leaf construction |
| `agent_foundry/merkle.py` | ordered Merkle, proof, verification receipt |
| `agent_foundry/moddik_run.py` | builds the run through `RunRecorder`, breakpoints, agent step, verifier |
| `agent_foundry/moddik_graph.py` | Neo4j projection + bounded queries + rebuild |
| `agent_foundry/asr.py`, `agent_foundry/plaud_import.py` | transcript source lane, PLAUD custody import |
| `api/server.py` | `/api/moddik/...` endpoints (thin) |
| `app/index.html` | Moddik mode reusing the inspector helpers (left sensors, center timeline, right evidence path) |
| `scripts/moddik_neo4j.sh`, `scripts/moddik_rehearsal.py` | project-local Neo4j, deterministic end-to-end rehearsal |
| `tests/unit/test_moddik_*.py` | determinism, Merkle vectors, tamper, verifier |

## Explicitly DEFERRED

Real Moddik hardware; actuation; account-linked PLAUD import (needs operator OAuth); PLAUD REST/SDK transcription API; model-initiated tool calls; Neo4j embedded visualization beyond a simple rendered evidence path; multi-user auth; cloud inference.
