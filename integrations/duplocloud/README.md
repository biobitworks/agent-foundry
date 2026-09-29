# DuploCloud integration boundary

- **Canonical product:** `biobitworks/agent-foundry`. It owns the event schema, runner, comparison, replay, inspector, and canonical evidence records.
- **Wrapper:** `biobitworks/agent-foundry-duplo` (private), derived from `duplocloud/devkit` and pinned in `provenance/DUPLOCLOUD_UPSTREAM_LOCK.json`.
- **DuploCloud role:** external Hack Day development/execution substrate. It is **not** the canonical provenance authority.

## Current verified status

**PARTIAL — materially participating, with the Duplo agent lane failed.**

Preserved receipts establish that:

- all six Duplo containers were running during the integration pass;
- the `extension-dev` workspace was verified through the platform API;
- extension `biobitworks.agentfoundry` v0.1.1 built and hot-loaded;
- the container could reach the canonical Agent Foundry API;
- creating an Agent Foundry extension resource through the Duplo API returned HTTP 201 and created a ticket/resource;
- the Duplo agent dispatch failed with `401 Missing Authentication header` from the LLM gateway;
- an **explicitly labeled direct-skill fallback** invoked the canonical Agent Foundry API with a real local Liquid model and wrote the result back into Duplo as `Complete`.

This means DuploCloud participated as the workspace/resource/extension/result substrate, but the claim **does not** extend to successful Duplo-agent LLM dispatch.

Receipts:

- `provenance/BREAKPOINT_DUPLO_THIN_EXTENSION_016.json`
- `provenance/rehearsal/duplo_rehearsal_20260929T143948Z.json`
- `provenance/DUPLOCLOUD_UPSTREAM_LOCK.json`

## Boundary mapping

| DuploCloud | Agent Foundry | Status |
| --- | --- | --- |
| Ticket / `AgentFoundryRun` | Run boundary | EXECUTED; resource id not retained in canonical receipt |
| Provider / scope | ExecutionContext | PARTIAL |
| Skill | Capability | EXECUTED via direct fallback |
| Persona | AgentRole / policy | NOT_TESTED |
| Workspace (`extension-dev`) | ExecutionEnvironment | EXECUTED |
| MCP call | ToolEvent | NOT_OBSERVED in canonical Duplo receipt |
| model output | ModelEvent | EXECUTED in canonical Agent Foundry run |
| retrieval | EvidenceEvent | NOT_TESTED |
| checkpoint | ReplayCheckpoint | NOT_TESTED |
| comparison | Evaluation/comparison result | EXECUTED by Agent Foundry and written back to Duplo |

The wrapper stays thin: it does not reimplement comparison, Antigence, provenance, or FCO/FCG logic.

## Failure preservation

The failed Duplo agent dispatch remains part of the record. The direct fallback is never represented as a successful Duplo-agent execution. Credentials are represented only as presence/absence and are not retained.
