import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
README = (ROOT / "README.md").read_text()


def tracked():
    return subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT).stdout.splitlines()


def test_readme_states_executed_reality_not_the_old_baseline():
    assert "baseline only" not in README.lower() and "nothing is implemented" not in README.lower()
    assert README.startswith("# Agent Foundry\n\n**Debug your AI agents like software.**")
    for h in ("## Hack Day demo", "## Key result", "## Provider comparison", "## Architecture", "## Provenance discipline", "## Reproduce", "## Known limitations", "## Security", "## Team"):
        assert h in README
    for must in ("SIMULATED", "Physical actuation = NONE", "first 68", "10.197", "12.697", "MEDIUM_EXCHANGE_RECOMMENDED", "NO_INTERVENTION", "LEFT and STAY are a top-probability tie", "NOT_AVAILABLE",
                 "Studio LiquidAI arm remains **`NOT_TESTED`**", "OPENJEV_STUDIO_CONNECTIVITY=FAILED", "ACCESS_BLOCKED", "not canonical provenance", "0748ed93", "835 bytes",
                 "**PARTIAL**", "FAILED_AUTH", "`NOT_EXECUTED`", "`NOT_COMPUTED`", "raw private media is **not committed**"):
        assert must in README, must


def test_readme_relative_links_resolve():
    for target in re.findall(r"\]\(([^)#\s]+)\)", README):
        if not target.startswith(("http", "mailto:")):
            assert (ROOT / target.rstrip("/")).exists(), target


def test_no_team_emails_or_secrets_or_private_audio_in_tracked_files():
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")
    for f in tracked():
        p = ROOT / f
        if not p.is_file():
            continue
        assert not f.lower().endswith((".wav", ".mp3", ".m4a", ".aiff", ".flac", ".ogg", ".opus", ".zip", ".npz")), f
        try:
            t = p.read_text()
        except UnicodeDecodeError:
            continue
        assert not [m for m in email.findall(t) if m != "noreply@anthropic.com"], f
        assert ("BEGIN PRIVATE" + " KEY") not in t and not re.search(r"AKI" + r"A[0-9A-Z]{16}", t), f


def test_gitleaks_ignore_additions_cover_only_the_verified_tokenizer_sha_false_positives():
    lines = [l.strip() for l in (ROOT / ".gitleaksignore").read_text().splitlines() if l.strip() and not l.startswith("#")]
    pinned = "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523"
    cc = [l for l in lines if l.startswith("demo/recorded/context_compare/")]
    assert len(cc) == 6
    for l in cc:
        path, rule, n = l.rsplit(":", 2)
        assert rule == "generic-api-key"
        line = (ROOT / path).read_text().splitlines()[int(n) - 1]
        assert re.search(r'"tokenizer\.json":\s*"' + pinned + '"', line), l  # exactly the pinned tokenizer file's sha256, nothing else


def test_required_breakpoints_exist():
    for b in ("BREAKPOINT_PREHACKATHON.json", "BREAKPOINT_VITHIA_OPENJEV_LIQUID_COMPARE_001.json", "BREAKPOINT_HACKDAY_POSTSUBMISSION_FINAL.json"):
        assert (ROOT / "provenance" / b).exists(), b
    f = json.loads((ROOT / "provenance" / "BREAKPOINT_HACKDAY_POSTSUBMISSION_FINAL.json").read_text())
    assert f["plaud"]["status"] == "PARTIAL" and f["plaud"]["private_artifacts_in_git"].startswith("NONE")
    assert f["HACKERSQUAD_SUBMITTED"] == "YES" and f["submission_time_operator_reported"].startswith("2026-09-29T15:29:41") and f["submission_commit"].startswith("NOT_ESTABLISHED")


def test_malformed_historical_route_timestamp_is_preserved_and_superseded_by_a_correction():
    import hashlib
    d = ROOT / "demo" / "recorded" / "context_compare" / "eca_v01"
    c = json.loads((d / "route_failure_receipt_correction_001.json").read_text())
    assert c["original_files_modified"] is False and c["corrected_time_of_original_tunnel_probe"] == "UNKNOWN" and c["bounds"]["exact_time"] == "UNKNOWN"
    for x in c["corrects"]:
        b = (ROOT / x["file"]).read_bytes()
        assert hashlib.sha256(b).hexdigest() == x["file_sha256"] and x["malformed_value"].encode() in b  # the original is untouched and still contains the malformed value
    assert all(p["utc"].endswith("Z") and "x" not in p["utc"] for p in c["fresh_probe_at_release_closure"]["probes"])
