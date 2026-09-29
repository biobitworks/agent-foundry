# Per-phase governance gate

Cadence: SPEC, DISCUSS, PLAN, EXECUTE, VERIFY, GOVERNANCE CHECK, COMMIT, BREAKPOINT.

Before every phase commit: tests, gitleaks, `git status`, artifact inventory, state classification.
After commit: push, fetch, verify local == origin. Milestones then require magicSTUDIObox fast-forward
(`MAGICPRO_HEAD == GITHUB_HEAD == MAGICSTUDIO_HEAD` only proves synchronization).

Before each execution phase: a HydraDG-compatible checkpoint descriptor. After: checkpoint_before/after,
git_head_before/after, inputs, outputs, failure_state, replayability. Replayability is claimed only after a real replay.

Stop and preserve state on: exposed secret, unclear license, unexpected repo, non-fast-forward divergence,
dirty predecessor mutation, human-action login, GSD writing outside this repo, destructive DuploCloud change.
Use BLOCKED / HUMAN_ACTION_REQUIRED / FAILED / UNKNOWN.
