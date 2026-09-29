# Gitleaks triage

`gitleaks detect --no-git` on the GSD install reported 5 `generic-api-key` findings, all in
`.claude/gsd-file-manifest.json` (lines 21, 213, 235, 278, 753). Each key is a GSD file path whose NAME contains
"api", "secret" or "token" (e.g. `secrets.cjs`, `token-scanner.cjs`); each value is a 64-char lowercase hex
SHA-256 (verified). Classification: FALSE_POSITIVE. Allowlisted by exact fingerprint in `.gitleaksignore`
(not by path or rule), so any new finding still fails. Redacted report reviewed; nothing committed from it.

## Context-compare arm results (2026-09-29)

6 `generic-api-key` findings, all the same false positive: the JSON key `tokenizer.json` (a file name inside the pinned OpenJEV weight identity) holds that file's sha256 (64 hex, equal to the pinned identity value `06b9509352d2af50...`). No credential is present; the bearer token is read in-process and never stored. Fingerprints added to `.gitleaksignore`.
