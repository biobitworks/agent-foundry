# PLAUD exported-audio custody: operator runbook

Scope of what this lane can ever claim: **`PLAUD_EXPORTED_AUDIO_CUSTODY`** = the exact bytes of an audio file the operator exported from PLAUD were hashed and recorded, linked to a Moddik run.
It does **not** imply PLAUD MCP, SDK, API, transcription-API or live-integration PASS. Agent Foundry never authenticates to PLAUD, never reads PLAUD tokens (`~/.plaud`), and never downloads from PLAUD. You export; the importer sees only a file.
Status today: importer IMPLEMENTED and unit-tested on SYNTHETIC audio; **no real PLAUD recording has been imported (NOT_TESTED / PARTIAL)**.

## Record and export (operator)

1. Start the PLAUD recording, note the wall-clock time, then run the rehearsal on the Mac. Speak the question aloud: "What changed, and does this culture need intervention?".
2. Stop the PLAUD recording. Use the PLAUD app's own audio export/share function (or the account tooling you authorize yourself) and save the file to `.local/plaud/` (gitignored; **never commit the audio**, it may contain private speech). Keep the original file name.

## Capture the Moddik run as a recording (Mac)

```bash
python3 scripts/moddik_rehearsal.py --tag live2 --model lfm2p6b --record rehearsal_2
```

## Import the exported audio

```bash
python3 scripts/plaud_import.py --parent demo/recorded/moddik/rehearsal_2/control.jsonl --audio ".local/plaud/<exported file>" --attest-plaud-export --session-note "PLAUD recording started HH:MM local"
cp runs/live2-moddik-plaud.jsonl demo/recorded/moddik/rehearsal_2/plaud_addendum.jsonl
python3 scripts/plaud_import.py --verify demo/recorded/moddik/rehearsal_2/plaud_addendum.jsonl --audio ".local/plaud/<exported file>"
python3 scripts/moddik_verify.py demo/recorded/moddik/rehearsal_2 --plaud-audio ".local/plaud/<exported file>"
```

Optional: `--recording-id ID --transcript-json FILE` for a PLAUD transcript export; the transcript is tied to the recording only if the id appears in both the JSON and the file name, otherwise the relationship is recorded as UNKNOWN.

## What is recorded (all from the exact file)

source file name, exact byte count, sha256 of the exact bytes, import timestamp (UTC), ffprobe descriptive metadata (not identity), the parent run id and the sha256 of the parent run log, and the relation
`PARALLEL_CAPTURE/SAME_SESSION (operator-declared; not verified)`. If a Mac-microphone capture exists, its relation is also `same_bytes=false`; if the parent used typed text, `same_bytes_as_local_capture=NOT_APPLICABLE`.
Without `--attest-plaud-export`, or if the file is not decodable media, the import is reported `IMPORTED_NOT_ADMITTABLE`.

The inspector shows it as "independent audio custody" on the evidence path (`http://localhost:8765/?moddik=recorded:rehearsal_2`).
A hash proves identity of the exported bytes; it does not prove what was said, who said it, or that PLAUD's clock matches the Mac's.
