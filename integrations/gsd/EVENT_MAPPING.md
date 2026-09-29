# GSD to Agent Foundry event mapping (PROPOSED)

| GSD activity | Agent Foundry event | FCO / downstream |
| --- | --- | --- |
| discuss | DecisionEvent | decision FCO |
| specification | RequirementEvent / ConstraintEvent | requirement FCOs |
| plan | PlanEvent | plan FCO |
| executor spawn | AgentEvent | |
| model invocation | ModelEvent | |
| tool invocation | ToolEvent | |
| retrieved source | EvidenceEvent | |
| verification | EvaluationEvent | Glasswork evaluation |
| phase boundary | ReplayCheckpoint | HydraDG checkpoint descriptor |
| failure | FailureEvent | FAILED retained |
| ship | ArtifactEvent | git commit / receipt / breakpoint |

Artifact occurrences preserved per phase: SPEC, CONTEXT, PLAN, EXECUTION, VERIFICATION, DECISION, FAILURE, ARTIFACT.

Minimum lineage: source requirement -> requirement FCO -> GSD planning occurrence -> plan FCO -> execution events
-> result evidence -> evaluation -> claim -> demo artifact.

Rules: CONTENT_ID is kept separate from OCCURRENCE_ID, RUN_ID and PHASE_ID. Chronological order alone never
asserts a causal relationship. Implementation status: NOT_IMPLEMENTED (self-observability is P-secondary).
