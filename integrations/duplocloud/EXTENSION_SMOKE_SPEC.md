# AGENT_FOUNDRY_DUPLO_SMOKE: contract (PROPOSED)

Built in the WRAPPER via `/duplo-extension` (choose **local**) after the platform is READY. It is a smoke of the extension
loop, not the product. It must NOT reimplement Agent Foundry.

**Does:** accept one canonical task; execute one configured model/provider; capture RunEvent, ModelEvent, ToolEvent,
EvidenceEvent, FailureEvent in the Agent Foundry event shape; show a minimal timeline.

**Boundary:** call the canonical API (`POST /api/pair`, `POST /api/replay`, `GET /api/recorded/{id}`) served by this repo on
loopback, or import `agent_foundry` as a package. Event shape: `schemas/events/event.schema.json`. Do not fork the schema.

**Rules:** a provider failure is a `failure` event (no hidden fallback, no fabricated response). If a local model is used as a
fallback it must be explicit: `FALLBACK_OCCURRED=true`, `FALLBACK_SOURCE=<model>`, and the original failure stays visible.
Credentials: record `NAME=PRESENT|ABSENT` only.

**Acceptance (all NOT_TESTED):** extension appears in the portal menu; one run recorded and read back through the verifier;
one forced failure visible in the timeline.
