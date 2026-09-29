# LiquidAI arm on magicSTUDIObox (operator steps): exact frozen bytes, GitHub transfer

Status: NOT EXECUTED by the agent (the workspace cannot reach Studio: `ssh` is guarded and the tunnel ports are down). Until the result is imported, the Liquid arm in the comparison is
`LIQUIDAI_PRO_LOCAL_PROVISIONAL` (magicPRObox), and the topology sentence "LiquidAI on the Studio" is NOT safe to say on camera.

Frozen contexts (created once on magicPRObox; Vithia is NOT re-run on Studio):

| context | file | bytes | sha256 |
|---|---|---|---|
| primary (A5_VITA01_FULL) | `demo/recorded/context_compare/eca_v01/context_primary.json` | 835 | `0748ed93c648903e64aa5295bc75cd4c5c979b089065a2447e250e06d5f88402` |
| raw control (A0_RAW) | `demo/recorded/context_compare/eca_v01/context_control.json` | 451 | `a0098d3793f0bd47602040f9d866742182aecd9bb6ed4f80362e2be49ca85068` |

Freeze commit (before any model ran): `7c1370a40546d2e7ae098830e95c5704e244013c` on branch `compare/vithia-openjev-liquid-v01`.

## On magicSTUDIObox (Terminal)

```bash
cd ~/projects/active/agent-foundry
git fetch origin && git checkout compare/vithia-openjev-liquid-v01 && git pull --ff-only
python3 scripts/compare_context.py verify-context demo/recorded/context_compare/eca_v01/context_primary.json 0748ed93c648903e64aa5295bc75cd4c5c979b089065a2447e250e06d5f88402 835
python3 scripts/studio_liquid_arm.py --context demo/recorded/context_compare/eca_v01/context_primary.json --sha256 0748ed93c648903e64aa5295bc75cd4c5c979b089065a2447e250e06d5f88402 --bytes 835 --host magicSTUDIObox --endpoint http://127.0.0.1:11437 --model liquid-vithia-1.2b:latest --label LIQUIDAI_STUDIO --model-identity "Ollama liquid-vithia-1.2b:latest; GGUF Q4_0 sha256 2ea801949d760cdf1a2cc04a54262c22c3c0c54f0769d57760c9adeb0e59233f (per jev-space-invaders scripts/liquid_runtime.py)" --out demo/recorded/context_compare/eca_v01/arm_liquid_studio_primary.json
python3 scripts/studio_liquid_arm.py --context demo/recorded/context_compare/eca_v01/context_control.json --sha256 a0098d3793f0bd47602040f9d866742182aecd9bb6ed4f80362e2be49ca85068 --bytes 451 --host magicSTUDIObox --endpoint http://127.0.0.1:11437 --model liquid-vithia-1.2b:latest --label LIQUIDAI_STUDIO --out demo/recorded/context_compare/eca_v01/arm_liquid_studio_control.json
git add demo/recorded/context_compare/eca_v01/arm_liquid_studio_*.json && git commit -m "arm: LiquidAI on magicSTUDIObox against the frozen context" && git push
```

`studio_liquid_arm.py` is stdlib-only and fail-closed: it recomputes byte count and sha256 of the exact file first and STOPS (no model call, no output file) on any mismatch; it refuses non-loopback endpoints and never reads credentials.
If `verify-context` prints `CONTEXT_IDENTITY_MATCH: FAIL`, stop and report it: do not run the arm.

## Back on magicPRObox (import + compare)

```bash
git pull --ff-only
python3 scripts/compare_context.py compare --a demo/recorded/context_compare/eca_v01/arm_openjev_pro_primary.json --b demo/recorded/context_compare/eca_v01/arm_liquid_studio_primary.json --which primary --name studio_primary
python3 scripts/compare_context.py compare --a demo/recorded/context_compare/eca_v01/arm_openjev_pro_control.json --b demo/recorded/context_compare/eca_v01/arm_liquid_studio_control.json --which control --name studio_control
python3 scripts/compare_context.py verify --write-receipt
```

The comparison stops (`CONTEXT_IDENTITY_MATCH=FAIL`) unless both arms saw the same bytes, the same hash, the same question and requests derived from those bytes. Machine, runtime and quantization differences (Studio: Q4_0 GGUF; Pro provisional: Q4_K_M) are recorded as context, not evidence.
