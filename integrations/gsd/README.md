# GSD bridge

GSD Core (`open-gsd/gsd-core` v1.15.0, MIT, pinned in `provenance/GSD_UPSTREAM_LOCK.json`) is an
**external development tool**. It is not canonical provenance, not a replacement for FCO/FCG, HydraDG or
Glasswork, not the product, and not a source of historical truth.

- `.planning/` is operational planning state. It may be content-addressed and referenced by FCOs; it is not the FCG.
- Where `.planning/` disagrees with `provenance/`, `provenance/` wins.
- GSD is installed project-local (`.claude/`, gitignored except manifest + install state). Reinstall:
  `npx @opengsd/gsd-core@1.15.0 --claude --local`
- The `Skill` tool resolves to a **global GSD 1.8.0**. For version-true work, follow the pinned local
  workflow files under `.claude/gsd-core/workflows/` and run `.claude/gsd-core/bin/gsd-tools.cjs` (Node >= 24).
- Onboarding status: projection run with pinned tools; `new-project` artifacts authored inline from
  `docs/PRODUCT_BRIEF.md` (research subagents skipped). Recorded honestly as PARTIAL, not as a full `/gsd-onboard`.
