"""Ordered Merkle commitment over canonical leaves.

Construction is the FCO reference construction (fractal-custody-objects training/fco_train/custody.py, order_independent=False):
  leaf  = sha256(0x00 || sha256(leaf_bytes))      (double hash, 0x00 domain)
  node  = sha256(0x01 || raw(left) || raw(right)) (0x01 domain)
  odd node at a level is promoted unchanged; empty tree = sha256(0x02) (genesis)
Leaf bytes are agent_foundry.ids.canonical_json(leaf) encoded as UTF-8; leaf ORDER is part of the commitment.

A root proves integrity/identity over the declared leaves, not that their contents are true.
A root is only reported when build_commitment() also produced every ingredient of the receipt; otherwise NOT_COMPUTED.
"""
import hashlib

from .ids import canonical_json

CONSTRUCTION = "fco-ordered-v1: leaf=sha256(0x00||sha256(canonical_json_utf8)); node=sha256(0x01||l||r); odd promoted; empty=sha256(0x02); order preserved"
GENESIS = hashlib.sha256(b"\x02").hexdigest()


def _h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def leaf_bytes(leaf: dict) -> bytes:
    return canonical_json(leaf).encode("utf-8")


def leaf_hash(content: bytes) -> str:
    return hashlib.sha256(b"\x00" + _h(content)).hexdigest()


def node_hash(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hexdigest()


def merkle_root(leaf_hashes: list) -> str:
    if not leaf_hashes:
        return GENESIS
    level = list(leaf_hashes)
    while len(level) > 1:
        nxt = [node_hash(level[i], level[i + 1]) if i + 1 < len(level) else level[i] for i in range(0, len(level), 2)]
        level = nxt
    return level[0]


def inclusion_proof(leaf_hashes: list, index: int) -> list:
    """Sibling path [(side, hash)] from leaf to root; side is where the SIBLING sits. Promoted odd nodes add no step."""
    if not (0 <= index < len(leaf_hashes)):
        raise IndexError("leaf index out of range")
    level, idx, path = list(leaf_hashes), index, []
    while len(level) > 1:
        sib = idx ^ 1
        if sib < len(level):
            path.append(("R" if sib > idx else "L", level[sib]))
        level = [node_hash(level[i], level[i + 1]) if i + 1 < len(level) else level[i] for i in range(0, len(level), 2)]
        idx //= 2
    return path


def verify_inclusion(leaf_h: str, path: list, root: str) -> bool:
    h = leaf_h
    for side, sib in path:
        h = node_hash(sib, h) if side == "L" else node_hash(h, sib)
    return h == root


def build_commitment(leaves: list, cross_check=None) -> dict:
    """Commit to an ORDERED list of leaf dicts and return the full receipt.

    The receipt contains the exact leaf bytes (as text), order, individual hashes, construction and root, and a verification section
    that recomputes everything from the stored bytes alone. If any ingredient is missing the root is NOT_COMPUTED.
    `cross_check` optionally takes a callable(list[str hashes]) -> root from an independent implementation.
    """
    if not leaves:
        return {"MERKLE_ROOT": "NOT_COMPUTED", "reason": "no leaves"}
    texts = [canonical_json(x) for x in leaves]
    hashes = [leaf_hash(t.encode("utf-8")) for t in texts]
    root = merkle_root(hashes)
    receipt = {
        "schema": "agent-foundry.merkle_commitment.v1",
        "construction": CONSTRUCTION,
        "leaf_count": len(leaves),
        "leaves": [{"index": i, "canonical_bytes_utf8": t, "leaf_hash": h} for i, (t, h) in enumerate(zip(texts, hashes))],
        "MERKLE_ROOT": root,
    }
    receipt["verification"] = verify_commitment(receipt, cross_check)
    if not receipt["verification"]["PASS"]:
        receipt["MERKLE_ROOT"] = "NOT_COMPUTED"
    return receipt


def verify_commitment(receipt: dict, cross_check=None) -> dict:
    """Recompute from the stored canonical bytes only. Never trusts stored hashes or the stored root."""
    checks = {}
    try:
        stored = receipt["leaves"]
        checks["order_is_index_order"] = [x["index"] for x in stored] == list(range(len(stored)))
        rec_hashes = [leaf_hash(x["canonical_bytes_utf8"].encode("utf-8")) for x in stored]
        checks["leaf_hashes_recomputed"] = rec_hashes == [x["leaf_hash"] for x in stored]
        checks["leaf_bytes_canonical"] = all(canonical_json(_loads(x["canonical_bytes_utf8"])) == x["canonical_bytes_utf8"] for x in stored)
        root = merkle_root(rec_hashes)
        checks["root_recomputed"] = root == receipt["MERKLE_ROOT"]
        checks["inclusion_proofs_verify_every_leaf"] = all(verify_inclusion(rec_hashes[i], inclusion_proof(rec_hashes, i), root) for i in range(len(rec_hashes)))
        checks["construction_declared"] = receipt.get("construction") == CONSTRUCTION
        if cross_check is not None:
            checks["independent_implementation_agrees"] = cross_check(rec_hashes) == root
    except (KeyError, ValueError, TypeError) as e:
        checks["error"] = f"{type(e).__name__}: {e}"
    return {"PASS": bool(checks) and all(v is True for k, v in checks.items() if k != "error") and "error" not in checks, "checks": checks,
            "note": "integrity over the declared canonical leaves only; not a statement about whether the values are physically true"}


def _loads(s):
    import json
    return json.loads(s)


def fco_reference_cross_check():
    """Return a callable backed by the FCO reference implementation if that checkout is present, else None (cross-check then simply absent)."""
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "fractal-custody-objects" / "training" / "fco_train" / "custody.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("fco_custody_ref", p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return lambda hashes: mod.merkle_root(hashes, order_independent=False)
