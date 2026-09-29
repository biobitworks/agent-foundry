# Agent Foundry

**Debug your AI agents like software.**

A provider-neutral developer reliability and debugging product for AI agents.
Central question: *why did this agent behave differently, where did the run first
diverge, what evidence/tools influenced it, and can the behavior be replayed under
another provider?*

Status: **baseline only** (AI Conference Hack Day 2026-09-29). Nothing is implemented yet.
See `provenance/` for pre-existing components, source commits, and upstream locks.

Pre-existing systems are consumed through adapters (HydraDG, Glasswork, Ollarma, FCO/FCG).
DuploCloud is the external execution substrate; GSD Core is a development accelerator only.
