# MSM + DAISY hardware / privacy / controlled-unlock protocol

Status: DESIGN SUCCESSOR. This document does not mutate the executed Agent Foundry Hack Day evidence on `main`.

Base repository state reviewed: Agent Foundry main at `caaae178bede2c314ab9e4fc9f2528e69b2a858c`.
Existing executed use case: deterministic simulated Moddik-style sensor stream -> ordered HardwareBreakpoint -> Neo4j rebuildable projection -> local model -> deterministic verifier -> simulated decision -> perturbed replay / first divergence.
Real hardware remains NOT_CONNECTED in the reviewed main state.

## Scientific question

Can MSM + DAISY preserve exact scientific and hardware state while:
1. hiding identity or nuisance information during discovery;
2. allowing useful stable/scoped linkage without exposing PHI;
3. freezing a model hypothesis before privileged data are revealed;
4. selectively unlocking additional evidence through an authenticated access transition;
5. detecting path divergence, corruption, replay, or provenance mismatch;
6. reproducing the same governed result from the same finite breakpoint;
7. preserving null, negative, blocked, unknown and not-computed outcomes?

## Core distinction

`AoKID != ResearchToken != OccurrenceFCO != HardwareBreakpoint != AccessCredential`.

- AoKID: intrinsic exact-content identity.
- ResearchToken: scoped pseudonymous analytical identity.
- OccurrenceFCO: contextual use/observation.
- HardwareBreakpoint: bounded finite hardware/process state.
- AccessCredential: authorization/decryption capability; never used as intrinsic data identity.

## State machine

```text
H0 RECOVER / VERIFY EXECUTED BASELINE
   ↓
H1 HARDWARE / RUNTIME ATTESTATION
   ↓
H2 PRIVACY TOKENIZATION + POINTER PROJECTION
   ↓
H3 BLIND DATASET FREEZE
   ↓
H4 MODEL DISCOVERY + HYPOTHESIS FREEZE
   ↓
H5 CONTROLLED UNLOCK / HANDSHAKE
   ↓
H6 STRATIFIED BIAS / CONFOUNDING CHALLENGE
   ↓
H7 TAMPER + REPLAY + FIRST-DIVERGENCE TESTS
   ↓
H8 REAL-HARDWARE ADAPTER (when available)
   ↓
H9 SCALE / MODEL COMPARISON
```

Every stage emits a typed result/status and a bounded Merkle breakpoint when exact ordered leaves, construction and independent verification exist.

## H0 — baseline recovery

Recover Agent Foundry main and verify the existing recorded Moddik run without mutation.

Required:
- exact repo/commit/tree;
- canonical event stream hashes;
- HardwareBreakpoint leaf bytes/order/construction;
- Neo4j delete -> rebuild equivalence;
- nominal/perturbed first-divergence receipt;
- explicit `source=SIMULATED`.

Do not upgrade simulated sensors to hardware evidence.

## H1 — hardware/runtime attestation

Add `AttestationEvidenceFCO` and `AttestationResultFCO`.

Target fields:
- device_id / device_key_id;
- host class and architecture;
- firmware/OS/kernel measurement;
- application commit/tree;
- container/runtime/model artifact digests;
- secure-boot / hardware-root state when available;
- nonce/freshness;
- attestation scheme/profile;
- verifier policy and result.

For hardware that supports a hardware root of trust, map to a standard attestation architecture (RATS/EAT; TPM/DICE-compatible evidence as available).
For ordinary Macs without an admitted hardware quote, record software/runtime measurements but label hardware-root attestation `NOT_TESTED`.

Attestation proves measured state under its trust assumptions; it does not prove sensor truth.

## H2 — privacy-preserving research identity

Use three identity layers:

```text
IDENTITY_ID
  PHI vault only

LINKAGE_ID
  keyed deterministic token / protected linkage service

RESEARCH_ID
  random or study-scoped surrogate exposed to the research lane
```

Recommended defaults:
- public/scientific AoKID remains deterministic and unsalted;
- PHI-derived linkage uses a keyed PRF/HMAC inside the protected linkage service;
- research-visible identity uses a random 256-bit surrogate when a protected crosswalk is acceptable;
- different study scopes receive different research IDs / keys;
- raw PHI hashes are not placed in public Merkle leaves.

Pointer files may expose:
- research token;
- artifact AoKID;
- data class;
- content pointer;
- access-policy ID;
- key-envelope ID;
- source identity = WITHHELD.

## H3 — blind dataset breakpoint

Construct `BlindDatasetBreakpoint` only from research-allowed leaves.

Required inclusion set:
- ResearchToken / ResearchID;
- permitted feature atoms;
- permitted outcomes or masked outcomes according to preregistration;
- units / normalization / quantization specs;
- pointer metadata;
- data-class and access-policy references.

Explicit exclusion manifest:
- PHI;
- linkage crosswalk;
- private keys;
- plaintext DEKs;
- fields intentionally blinded for discovery.

A successful breakpoint allows an auditor to verify exactly which information was available to the model.

## H4 — model discovery / hypothesis freeze

Give the exact BlindDatasetBreakpoint projection to heterogeneous models or deterministic baselines.

At minimum:
- deterministic/script baseline;
- local Qwen or Qwen Math/logic model where appropriate;
- Liquid local model where appropriate;
- optional independent frontier reviewer.

Freeze:
- exact input root;
- model/runtime identity;
- prompt/input bytes;
- seed/sampling config;
- output bytes;
- proposed signal/hypothesis;
- `HypothesisBreakpoint`.

Model agreement is not the oracle.

## H5 — controlled unlock

Use a separate signing key and encryption/key-agreement key.

Do not put private keys or plaintext data-encryption keys into Merkle leaves.

Objects:
- `PublicKeyFCO`;
- `KeyEnvelopeFCO`;
- `AccessPolicyFCO`;
- `AccessHandshakeFCO`;
- `UnlockReceiptFCO`.

Flow:
```text
BlindDatasetBreakpoint
  + HypothesisBreakpoint
  + fresh challenge nonce
  + requester key ID
  + authorization policy
       ↓
authenticated handshake / policy evaluation
       ↓
authorized additional leaves become available
       ↓
UnblindedDatasetBreakpoint
```

The successor breakpoint commits the prior root reference, unlock receipt and newly authorized leaves. It does not rewrite the blind state.

## H6 — bias/confounding challenge

After hypothesis freeze, reveal one field family at a time according to a preregistered order, e.g.:
1. treatment arm;
2. batch / instrument;
3. site;
4. age/sex or other scientifically justified strata;
5. other protected/sensitive attributes only where ethically and legally authorized.

For each unlock stage test:
- effect direction and magnitude;
- equivalence/stability within preregistered bounds;
- site/batch dependence;
- subgroup calibration/performance;
- missingness/confounding changes;
- whether the frozen signal survives.

Use statistical equivalence testing when the claim is "same within epsilon"; do not interpret `p > 0.05` as equivalence.

## H7 — tamper, replay and error-correction battery

Inject independently:
- one sensor-value mutation;
- one content-bit mutation;
- wrong ResearchToken mapping;
- wrong HOME_REF / occurrence context;
- altered graph edge/parent;
- stale/replayed unlock nonce;
- unauthorized access request;
- missing/corrupted leaf;
- model output citing unavailable evidence.

Require:
- first divergence localized;
- correct failure layer classified;
- predecessor remains addressable;
- no in-place repair;
- correction emitted as successor state;
- deterministic replay from the preceding valid breakpoint;
- status preserved if recovery is impossible.

Merkle/hash detects integrity divergence; storage recovery, semantic correction and scientific correction remain separate mechanisms.

## H8 — real-hardware adapter

The first real-hardware implementation should preserve the existing Agent Foundry event schema.

Adapter contract:
`HardwareObservation -> canonical SensorEvent -> HardwareBreakpoint`.

Minimum real-hardware requirements:
- sensor/device serial or opaque hardware ID;
- calibration metadata;
- units;
- monotonic/device timestamp and host receipt time;
- raw payload bytes or immutable pointer;
- firmware/software measurement;
- device attestation evidence when available;
- transport/authentication state;
- source = REAL_HARDWARE;
- actuator state recorded separately from recommendation.

No actuator command should be inferred from a model recommendation without an explicit human/policy gate.

## H9 — model / scale comparison

Only after H0-H7 pass should model-quality or DAISY-learning comparisons be promoted.

Use matched exact inputs and separately frozen contexts. Compare:
- deterministic baseline;
- Qwen;
- Liquid;
- other authorized models;
- DAISY D0-D6 arms when that experiment is authorized.

Primary statistical units must be independent trajectories/scenarios or seed-by-held-out-scenario aggregates, not tokens or individual correlated events.

## Merkle / FCG relationships

Suggested FCG edges:
- `TOKENIZED_AS`
- `RANDOMIZED_AS`
- `INCLUDED_IN`
- `ATTESTED_BY`
- `MEASURED_ON`
- `MODEL_OBSERVED`
- `FROZEN_AS`
- `AUTHORIZED_UNLOCK`
- `CHALLENGED_BY`
- `REPLAYED_FROM`
- `FIRST_DIVERGENCE_FROM`
- `CORRECTS`
- `COMMITTED_IN`

Edges are declared relationships, not causality.

## Stop rules

Stop promotion on:
- predecessor root mismatch;
- attestation freshness failure;
- private-key / PHI leak;
- blind-manifest inclusion violation;
- unlock replay accepted;
- unauthorized field released;
- deterministic replay mismatch;
- cross-host exact-output mismatch for exact invariants;
- Merkle independent recomputation failure;
- secret scan failure.

## Claim ceiling

Until real hardware is connected and verified:
- hardware use case = executed simulation + proposed real-hardware adapter;
- privacy/tokenization/unlock lane = specification until executed;
- hardware-root attestation = NOT_TESTED unless a real quote/token is verified;
- DAISY learning benefit = NOT_TESTED unless separately executed;
- Merkle inclusion = integrity/custody, not physical truth or scientific correctness.
