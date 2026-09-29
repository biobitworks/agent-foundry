# DuploCloud integration boundary

- **Canonical product:** `biobitworks/agent-foundry` (this repo). Owns event schema, runner, comparison, replay, inspector.
- **Wrapper:** `biobitworks/agent-foundry-duplo` (private), local `/Users/byron/projects/toolchains/agent-foundry-duplo`.
  A clone of `duplocloud/devkit` adopted with `scripts/init-project.sh` (fresh history, origin repointed). **Never run that script here.**
- DuploCloud is an external Hack Day execution substrate, NOT provenance authority. Pinned in `provenance/DUPLOCLOUD_UPSTREAM_LOCK.json`.
- The wrapper must consume this product through an API/package boundary, not copy it. Smoke contract: `EXTENSION_SMOKE_SPEC.md`.

## Mapping (PROPOSED; nothing here is EXECUTED until observed inside a running platform)

| DuploCloud | Agent Foundry |
| --- | --- |
| Ticket | Run (`run_id`) |
| Provider / Credential / Scope | ExecutionContext (recorded as PRESENT/ABSENT flags only, never values) |
| Skill | Capability |
| Persona | AgentRole |
| Workspace (`extension-dev`) | ExecutionEnvironment |
| MCP call | `tool` event |
| model output | `model` event |
| retrieval | `evidence` event |
| checkpoint | `checkpoint` event / replay descriptor |
| comparison | `evaluation` event |

## Status (2026-09-29)

`INSTALLED_NOT_RUNNING`. Blocked on operator: `./run.sh` in the wrapper needs a work-domain email, an admin password, and an LLM
provider key, plus a verification-link click. `DUPLOCLOUD_PLATFORM_READY` is NOT_OBSERVED. Extension smoke: NOT_TESTED.
