# Two-endpoint path divergence (bounded prototype): AGENT_FOUNDRY_TWO_ENDPOINT_PATH_DIVERGENCE_001

Program name: GSTAR_PROGRAM_UNNAMED (not Hydra DeltaG*; "Gibbs Fold" is historical provenance only). G*/DeltaG* are dimensionless graph/state surrogates, never thermodynamic Gibbs free energy.

- Input: the recorded Moddik nominal/perturbed pair (`demo/recorded/moddik/rehearsal_1`). Roles are DECLARED: nominal = predicted, perturbed = observed.
- Output: two `PathDivergenceFCO` objects (T1 one step tick 8->9; T2 two-endpoint path tick 8->10), 5 `EndpointState` FCOs, 2 `RunLog` FCOs, FCG edges (`derived_from`, `compared_with`; both in ontology v1.3.0). Stored under `fco/objects/path_divergence/`, `fcg/edges/path_divergence/`.
- Run: `demo/recorded/path_divergence/moddik_v01/` (PATH_DIVERGENCE_DIAGNOSIS). API: `GET /api/path_divergence/moddik_v01`.
- Build/verify: `python3 scripts/path_divergence_moddik.py build|verify [--write-receipt]`.
- Definitions used (sha256 recorded in `docs/source_intake.manifest.jsonl`): cloudmer `delta_graph_star.py` (DeltaG* is a component VECTOR, default NOT_EXECUTED, no scalarization, no hash distance), `anticube.py`, CORE_MSM_FCG_ANTICUBE_DELTA_G_MODEL_v1.md, PROJECT_INTENT_QUADRANT_CONTRACT_v1.md.
- NOT defined in the recovered artifacts (so NOT_COMPUTED): EPISTEMIC_STATE and DISPOSITION as Anticube dimensions, G*, DeltaG*, S*[Gamma] terms/weights/tau, q, M_A, P(Gamma) (PROPOSED only). The fco-r18 `path_sum.py` S* code is labelled an editorial heuristic with unfrozen weights over a different graph and is not reused.
- Limits: the simulator has no state dynamics (readings are scripted functions of tick), so the tick-10 endpoint agreement after a tick-9 perturbation is a property of the script. FCG edges declare relationships, not causality. Merkle/hash equality is identity, not distance.
- IEEE DMF vector analysis: DEFERRED_ACCESS (metadata FCOs only; frame0..frame15 candidate observation FCOs require the raw dataset).
