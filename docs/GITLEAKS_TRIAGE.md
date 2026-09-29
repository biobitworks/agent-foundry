# Gitleaks triage

`gitleaks detect --no-git` on the GSD install reported 5 `generic-api-key` findings, all in
`.claude/gsd-file-manifest.json` (lines 21, 213, 235, 278, 753). Each key is a GSD file path whose NAME contains
"api", "secret" or "token" (e.g. `secrets.cjs`, `token-scanner.cjs`); each value is a 64-char lowercase hex
SHA-256 (verified). Classification: FALSE_POSITIVE. Allowlisted by exact fingerprint in `.gitleaksignore`
(not by path or rule), so any new finding still fails. Redacted report reviewed; nothing committed from it.
