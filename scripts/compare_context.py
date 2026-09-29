"""Same frozen Vithia context -> two backends. Subcommands (all deterministic except the model calls):
  freeze                         magicPRObox: EvidenceSet -> Vithia (once) -> frozen CanonicalContext bytes + FCOs + prep run
  verify-context FILE SHA BYTES  recompute byte count + sha256 of an exact context file (stdlib only; also runnable on Studio)
  run-openjev --which primary|control [--port N]   OpenJEV arm on THIS machine against the frozen bytes (project runtime, bearer token stays local)
  run-liquid  --which primary|control --endpoint URL --model TAG --host NAME --topology TEXT    LiquidAI arm against the frozen bytes
  import-arm FILE                verify + register an arm-result file (e.g. produced on magicSTUDIObox)
  compare --a FILE --b FILE --which primary|control   normalize both arms, verify identity, compare, write streams + FCOs + receipt
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "demo" / "recorded" / "context_compare" / "eca_v01"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha_file(p):
    b = Path(p).read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def wj(p: Path, obj):
    if p.exists() and json.loads(p.read_text()) != obj:
        raise SystemExit(f"REFUSED: {p} exists with different content (append-only)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


ap = argparse.ArgumentParser()
sp = ap.add_subparsers(dest="cmd", required=True)
sp.add_parser("freeze")
v = sp.add_parser("verify-context")
v.add_argument("file"); v.add_argument("sha256"); v.add_argument("bytes", type=int)
o = sp.add_parser("run-openjev")
o.add_argument("--which", default="primary"); o.add_argument("--port", type=int, required=True); o.add_argument("--out")
l = sp.add_parser("run-liquid")
l.add_argument("--which", default="primary"); l.add_argument("--endpoint", default="http://127.0.0.1:11434"); l.add_argument("--model", required=True)
l.add_argument("--host", default=platform.node()); l.add_argument("--topology", default="local"); l.add_argument("--label", required=True); l.add_argument("--model-identity", default=""); l.add_argument("--out")
im = sp.add_parser("import-arm")
im.add_argument("file")
c = sp.add_parser("compare")
c.add_argument("--a", required=True); c.add_argument("--b", required=True); c.add_argument("--which", default="primary"); c.add_argument("--name", default="pro_openjev_vs_liquid")
a = ap.parse_args()

if a.cmd == "verify-context":
    h, n = sha_file(a.file)
    ok = h == a.sha256 and n == a.bytes
    print(json.dumps({"file": a.file, "byte_count": n, "sha256": h, "expected_byte_count": a.bytes, "expected_sha256": a.sha256, "CONTEXT_IDENTITY_MATCH": "PASS" if ok else "FAIL"}, indent=1))
    sys.exit(0 if ok else 1)

from agent_foundry import backend_compare as bc, compare_fco as cf, dataset_fco as dfco  # noqa: E402

if a.cmd == "freeze":
    mods, up = bc.upstream()
    rows, info = bc.load_corpus_rows()
    assert info["bytes_match_manifest"], "corpus bytes do not match their own manifest"
    idx, row = bc.select_row(rows)
    contexts, ctxs = {}, {}
    for label, arm in (("primary", bc.PRIMARY_ARM), ("control", bc.CONTROL_ARM)):
        pkg = bc.build_context(mods, row, arm)  # Vithia executes here, once per arm
        b = bc.compact(pkg)
        contexts[label] = (arm, b)
    ts = now()
    sw = "sha256:" + hashlib.sha256(b"".join((ROOT / "agent_foundry" / f).read_bytes() for f in ("backend_compare.py", "compare_fco.py"))).hexdigest()
    fcos, edges, man = cf.build_freeze(mods, up, info, idx, row, contexts, ts, "eca-v01-freeze", sw)
    OUT.mkdir(parents=True, exist_ok=True)
    for label, (arm, b) in contexts.items():
        p = OUT / f"context_{label}.json"
        if p.exists() and p.read_bytes() != b:
            raise SystemExit(f"REFUSED: {p} exists with different bytes (frozen)")
        p.write_bytes(b)
    for f in fcos.values():
        wj(ROOT / "fco" / "objects" / "context_compare" / f"{f['content_hash'].split(':')[1]}.json", f)
    ep = ROOT / "fcg" / "edges" / "context_compare" / "CONTEXT_COMPARE_eca_v01.jsonl"
    ep.parent.mkdir(parents=True, exist_ok=True)
    if not ep.exists():
        ep.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edges))
    wj(OUT / "context_manifest.json", man)
    ev = cf.run_prep(fcos, edges, man, OUT, "eca-v01-prep", ts, mods, up, row)
    print(json.dumps({"CONTEXT_FILE": {k: f"demo/recorded/context_compare/eca_v01/{v['file']}" for k, v in man["contexts"].items()}, "CONTEXT_BYTE_COUNT": {k: v["byte_count"] for k, v in man["contexts"].items()},
                      "CONTEXT_SHA256": {k: v["sha256"] for k, v in man["contexts"].items()}, "CONTEXT_CONTENT_ID": {k: v["content_id"] for k, v in man["contexts"].items()},
                      "EVIDENCE_IDS": [i["evidence_id"] for i in bc.evidence_items(mods, row)], "QUESTION": mods["beh"].QUESTION["instructions"], "state_id": row["state_id"], "row_index": idx,
                      "upstream_commit": up["commit"], "corpus_sha256": info["sha256"], "prep_events": len(ev)}, indent=1))
