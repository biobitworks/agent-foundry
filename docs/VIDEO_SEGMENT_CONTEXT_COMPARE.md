# Video segment: same frozen context, two backends (45-60 s)

Status of what is TRUE today (verified): the context was frozen once on magicPRObox before any model ran; OpenJEV (verified MLX 4-bit runtime) executed on magicPRObox against the frozen bytes;
LiquidAI (LFM2.5-1.2B-Instruct, local Ollama) executed on magicPRObox against the same bytes as a PROVISIONAL arm; both arms saw the identical hash. The Studio LiquidAI arm is NOT executed yet.
OpenJEV could not be reached through Studio: OPENJEV_STUDIO_CONNECTIVITY=FAILED (preserved as a receipt).

## Segment A: safe to record TODAY (~50 s, ~120 words)

"Vithia turns the same governed evidence into one canonical context. We freeze and hash it before any model runs: eight hundred thirty-five bytes, and both backends report the same hash.
OpenJEV could not execute through our Studio compute lane, so Agent Foundry preserves that failed route instead of hiding it. We ran OpenJEV on the control machine, and gave LiquidAI the same context bytes.
Agent Foundry records both executions in one provider-neutral event format. The first behavioral divergence is here, at the decision: OpenJEV chose LEFT, LiquidAI chose STAY. OpenJEV's own probabilities actually tie LEFT and STAY, and neither model cites evidence, so we don't claim either is better. But we know exactly where they forked, and that everything before it was identical."

Click path: Compare backends -> (context select: Vithia context) -> read the hash line -> point at ModelEvent (raw stream divergence, the backend) -> click the highlighted DecisionEvent on each side -> point at the "Preserved failure" line.

## Segment B: ONLY after the Studio arm is imported and `verify` passes

Replace the second sentence with: "We then ran OpenJEV on the control machine and LiquidAI on the Studio, while giving both the exact same Vithia-produced context bytes. The context hash matches on both machines. Any downstream difference therefore begins after the model and runtime fork."
Do NOT say the machines are identical environments (different machines, runtimes and quantizations).

## Do not say
- that one model is better, or that either is right or wrong (no preregistered evaluation; the corpus reference labels were never shown to a model and are not used here)
- that the models cited evidence (typed choice has no citation channel: evidence used = NOT_AVAILABLE for both)
- "LiquidAI on the Studio" before the Studio arm exists; "OpenJEV on Studio"; anything about G*/DeltaG* (NOT_COMPUTED, not used)
- that OpenJEV is JEV (labels: OPENJEV, NON_TYPESAFE_JEV)
