# IEEE DataPort "Digital Microfluidics Datasets": FCO/FCG admission (metadata level)

Status: EXECUTED at metadata level; raw payload ACCESS_BLOCKED (DEFERRED_ACCESS). Branch `dataset/ieee-dmf-fco-v01`.

- Source page bytes (outside git): `.local/sources/ieee_dmf/`. Capture manifest: `fco/manifests/ieee_dmf_v01_source_capture.json` (SOURCE_BYTES_HASH is the PAGE hash, not the dataset payload).
- Canonical objects: `fco/objects/*.json` (schema `schemas/fco/fco_minimum_schema.v1.3.0.json`, sha256 04db1d2a..., from fractal-custody-objects eb77ffe). Edges: `fcg/edges/IEEE_DMF_v01.jsonl`.
- Run: `demo/recorded/external_datasets/ieee_dmf_v01/`. Inspect: `http://localhost:8765/` then "Dataset custody (IEEE DMF)".
- Rebuild/verify: `python3 scripts/ieee_dmf_admit.py verify [--write-receipt]` (deletes ONLY the `ieee_dmf_fco_v01` projection, rebuilds it from the canonical files and run log, compares).
- Gates: SOURCE_PAGE_ACCESS public; DATA_BYTES_ACCESS ACCESS_BLOCKED; LICENSE declared CC BY 4.0 in page JSON-LD, UNVERIFIED; REDISTRIBUTION/DERIVATIVE/COMMERCIAL UNKNOWN; DATASET_MERKLE_ROOT NOT_COMPUTED.
