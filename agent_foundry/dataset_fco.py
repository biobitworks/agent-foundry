"""External-dataset intake as FCO/FCG objects (metadata level).

FCO objects conform to the sibling repo's fco_minimum_schema.json (v1.3.0 tree, pinned copy in schemas/fco/ with source commit + sha256).
FCG edges use the ontology names from that package (derived_from, licensed_under, ...). `part_of` is NOT in the v1.3.0 ontology list; it is used
and flagged ontology_status=PROPOSED_EXTENSION rather than silently assumed. Edges declare relationships; they never assert causality.

Identity rules:
  * a SourcePageSnapshot's CONTENT_ID is the sha256 of the exact saved page bytes (scope: the PAGE, never the dataset payload);
  * every other object's CONTENT_ID = sha256(canonical_json({"object_type", "body"})): independent of run, time, status and parents;
  * OCCURRENCE (context) identity lives in Agent Foundry events (occ:sha256:...), never inside the FCO content identity.
Hashes establish identity/deduplication, not scientific truth. Neo4j is a projection of these files, not their source.
"""
import hashlib
import html as htmllib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .ids import canonical_json, sha256_hex

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "fco" / "fco_minimum_schema.v1.3.0.json"
FCO_VERSION = "1.3.0"
PROJECT_ID = "agent-foundry"
ONTOLOGY_V130 = {"derived_from", "captured_by", "captured_with", "measured_by", "processed_by", "trained_on", "evaluated_on", "annotated_by", "reviewed_by", "approved_by",
                 "authorized_by", "calibrated_against", "compared_with", "supports", "contradicts", "fails_to_support", "supersedes", "corrects", "invalidates", "exported_to",
                 "acknowledged_by", "licensed_under", "restricted_by", "generated_by_prompt", "executed_in_environment", "part_of_release", "witnessed_by"}
PROPOSED_EXTENSIONS = {"part_of"}
CANON_METHOD = "agent_foundry.ids.canonical_json(sorted keys, compact separators, UTF-8) over {object_type, body}"
SNAPSHOT_METHOD = "sha256 over the exact saved response bytes"


# ---------------------------------------------------------------- extraction (declared fields only; missing -> UNKNOWN)
def _text(h: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def _dd_after(html: str, dt: str):
    m = re.search(r"<dt>\s*" + re.escape(dt) + r"\s*</dt>\s*<dd>(.*?)</dd>", html, re.S)
    return _text(m.group(1)) if m else None


def extract_page_metadata(page_bytes: bytes) -> dict:
    """Extract only what the page declares. Anything not found is the string UNKNOWN. Volatile counters are deliberately not extracted
    (views/downloads are absent from the server HTML; they appear only in the rendered DOM)."""
    html = page_bytes.decode("utf-8", "replace")
    U = "UNKNOWN"
    ld = None
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if m:
        try:
            ld = next((x for x in json.loads(m.group(1)).get("@graph", []) if x.get("@type") == "Dataset"), None)
        except ValueError:
            ld = None
    title = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    doi = re.search(r"https://dx\.doi\.org/(10\.\d{4,9}/[^\"'\s<]+)", html)
    created = re.search(r'<dt>Date Created:</dt>\s*<dd>\s*<time datetime="([^"]+)"', html)
    updated = re.search(r'<dt>Last updated:</dt>\s*<dd>\s*<time datetime="([^"]+)"', html)
    label = re.search(r"<h2 class=\"title\">\s*Datasets\s*<h3>(.*?)</h3>", html, re.S)
    fmt = re.search(r'href="/data-formats/[^"]+"[^>]*>([^<]+)</a>', html)
    files = re.findall(r'<li class="(?:zip|[a-z]+) list-group-item"><a [^>]*>([^<]+?) \(Size: ([^)]+)\)</a>', html)
    inst = re.search(r"A dataset of droplet splitting.*?previous research", _text(html))
    # the visible abstract (the JSON-LD description is a comma-split copy and is deliberately not used)
    abst = next((m for m in re.finditer(r"Digital microfluidics are a unique technique.*?droplet monitoring and control\.", _text(html)) if '"' not in m.group(0)), None)
    st = _text(html)
    n = lambda pat: (int(re.search(pat, st).group(1).replace(",", "")) if re.search(pat, st) else U)
    structure = {"samples": n(r"comprises (\d[\d,]*) samples"), "frames_per_sample": n(r"each represented as a (\d+)-frame"), "data_points": n(r"total of ([\d,]+) data points"),
                 "split_test": n(r"(\d+) test samples"), "split_train": n(r"(\d+) training samples"), "split_validation": n(r"(\d+) validation samples")}
    return {
        "title": _text(title.group(1)) if title else (ld or {}).get("name", U),
        "dataset_label_on_page": _text(label.group(1)) if label else U,
        "doi": doi.group(1) if doi else U,
        "citation_authors": [a for a in [_dd_after(html, "Citation Author(s):")] if a] or [U],
        "submitted_by": _dd_after(html, "Submitted by:") or U,
        "date_created_utc": created.group(1).replace("+0000", "+00:00") if created else U,
        "last_updated_utc": updated.group(1).replace("+0000", "+00:00") if updated else U,
        "data_format_declared": fmt.group(1) if fmt else U,
        "declared_files": [{"name": a, "size_text": b} for a, b in files] or [U],
        "abstract": abst.group(0) if abst else U,
        "instructions_excerpt": inst.group(0) if inst else U,
        "declared_structure": structure,
        "camera_declared": "DAVIS346" if "DAVIS346" in st else U,
        "operations_declared": "droplet splitting, merging and movement" if "droplet splitting, merging and movement" in st else U,
        "files_require_login": "LOGIN TO ACCESS DATASET FILES" in html,
        "file_folder_marked_restricted": bool(re.search(r'class="folder restricted"', html)),
        "json_ld": {"present": ld is not None, "creator": ((ld or {}).get("creator") or {}).get("name", U), "license": (ld or {}).get("license", U), "citation": (ld or {}).get("citation", U)},
    }


# ---------------------------------------------------------------- FCO / FCG construction
def content_hash_of(object_type: str, body: dict) -> str:
    return "sha256:" + sha256_hex(canonical_json({"object_type": object_type, "body": body}))


def build_fco(object_type: str, body: dict, *, content_hash: str = None, parent_hashes=(), created_at: str, run_id: str, source_or_derivative: str, claim_ceiling: str,
              actor_id: str, software_hash: str = None, canonicalization_method: str = CANON_METHOD, notes: str = None) -> dict:
    ch = content_hash or content_hash_of(object_type, body)
    fco = {"fco_version": FCO_VERSION, "object_type": object_type, "object_id": "fco:" + ch, "canonicalization_method": canonicalization_method, "content_hash": ch,
           "parent_hashes": list(parent_hashes), "created_at": created_at, "actor_id": actor_id, "device_or_instrument_id": None, "project_id": PROJECT_ID, "run_id": run_id,
           "authorization_basis": "operator task IEEE_DIGITAL_MICROFLUIDICS_DATASET_FCO_ADMISSION_001 (metadata-level intake; no credentials used)",
           "anticube_state": {"identity": "non-self", "safety": "unknown"}, "source_or_derivative": source_or_derivative, "software_hash": software_hash, "environment_hash": None,
           "signature": None, "encryption": None, "claim_ceiling": claim_ceiling, "status": "draft", "body": body}
    if notes:
        fco["notes"] = notes
    validate_fco(fco)
    return fco


_validator = None


def validate_fco(fco: dict):
    global _validator
    if _validator is None:
        _validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    errs = sorted(_validator.iter_errors(fco), key=lambda e: list(e.path))
    if errs:
        raise ValueError("FCO fails fco_minimum_schema: " + "/".join(str(p) for p in errs[0].path) + ": " + errs[0].message)


def build_edge(rel: str, src: str, dst: str, *, basis: str, relationship_status: str, created_at: str, run_id: str) -> dict:
    if rel not in ONTOLOGY_V130 and rel not in PROPOSED_EXTENSIONS:
        raise ValueError(f"relationship {rel} is neither in the FCG ontology v1.3.0 nor a declared proposed extension")
    eid = "fcgedge:sha256:" + sha256_hex(canonical_json({"src": src, "rel": rel, "dst": dst}))
    return {"edge_id": eid, "rel": rel, "src_content_hash": src, "dst_content_hash": dst, "basis": basis, "relationship_status": relationship_status,
            "ontology_status": "FCG_ONTOLOGY_V1.3.0" if rel in ONTOLOGY_V130 else "PROPOSED_EXTENSION (not in v1.3.0 ontology list)", "causal": False, "created_at": created_at, "run_id": run_id}


BYTE_TYPES = ("SourcePageSnapshot", "RunLog")


def verify_fco_hash(fco: dict, snapshot_bytes_lookup=None) -> bool:
    """Recompute CONTENT_ID from the stored body. SourcePageSnapshot identity is over saved bytes (only checkable if the bytes are available)."""
    if fco["object_type"] == "RunLog":  # the committed run log is in the repo, so the bytes can actually be re-hashed
        return "sha256:" + hashlib.sha256((ROOT / fco["body"]["path"]).read_bytes()).hexdigest() == fco["content_hash"]
    if fco["object_type"] == "SourcePageSnapshot":
        if snapshot_bytes_lookup is None:
            return fco["canonicalization_method"] == SNAPSHOT_METHOD and re.fullmatch(r"sha256:[0-9a-f]{64}", fco["content_hash"]) is not None
        return "sha256:" + hashlib.sha256(snapshot_bytes_lookup(fco)).hexdigest() == fco["content_hash"]
    return content_hash_of(fco["object_type"], fco["body"]) == fco["content_hash"] and fco["object_id"] == "fco:" + fco["content_hash"]


# ---------------------------------------------------------------- canonical lineage traversal
def trace(fcos: dict, edges: list, start: str, follow=("part_of", "derived_from")) -> dict:
    """Follow outgoing containment/derivation edges from `start` (content hash) to a root object. Returns the chain and the authoritative source URL if reached."""
    out = {}
    for e in edges:
        if e["rel"] in follow:
            out.setdefault(e["src_content_hash"], []).append(e)
    chain, seen, cur, hops = [start], {start}, start, []
    while True:
        nxt = sorted(out.get(cur, []), key=lambda e: (follow.index(e["rel"]), e["dst_content_hash"]))
        if not nxt or nxt[0]["dst_content_hash"] in seen:
            break
        e = nxt[0]
        hops.append({"rel": e["rel"], "from": e["src_content_hash"], "to": e["dst_content_hash"], "edge_id": e["edge_id"]})
        cur = e["dst_content_hash"]
        chain.append(cur)
        seen.add(cur)
    root = fcos[cur]
    return {"chain": chain, "chain_types": [fcos[c]["object_type"] for c in chain], "hops": hops, "root_object_type": root["object_type"], "source_url": (root.get("body") or {}).get("source_url", "UNKNOWN")}


def load_canonical(directory: Path = None):
    d = directory or ROOT
    fcos = {}
    for p in sorted((d / "fco" / "objects").glob("*.json")):
        f = json.loads(p.read_text())
        fcos[f["content_hash"]] = f
    edges = []
    for p in sorted((d / "fcg" / "edges").glob("*.jsonl")):
        edges += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return fcos, edges


def load_canonical_sub(sub: str, directory: Path = None):
    """Load a sub-collection (fco/objects/<sub>/, fcg/edges/<sub>/) so separate admissions never mix in the top-level loader."""
    d = directory or ROOT
    fcos = {}
    for p in sorted((d / "fco" / "objects" / sub).glob("*.json")):
        f = json.loads(p.read_text())
        fcos[f["content_hash"]] = f
    edges = []
    for p in sorted((d / "fcg" / "edges" / sub).glob("*.jsonl")):
        edges += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    seen, uniq = set(), []
    for e in edges:  # an edge is identified by its content-derived edge_id
        if e["edge_id"] not in seen:
            seen.add(e["edge_id"])
            uniq.append(e)
    return fcos, uniq


def closure(edges: list, start: str, rels=("derived_from",)) -> set:
    out, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for e in edges:
            if e["src_content_hash"] == cur and e["rel"] in rels and e["dst_content_hash"] not in out:
                out.add(e["dst_content_hash"])
                stack.append(e["dst_content_hash"])
    return out
