# HO-STRATA-014 S4a bisection log

## Run conditions

- Pack: `~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf`
- Tokens: `549,6077,280,7239`
- Engine binary: `/home/kupipi/Documents/git/strata/build-deepseek/strata`
- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`
- Command used for every dump:
  ```bash
  ./build-deepseek/strata --parity-run --native <pack> --dump-layers /tmp/opencode/s4-dump.bin --tokens 549,6077,280,7239 --max-new 1 --max-context 1024
  ```
- Strata commit at the time of these runs: `ad214242a9c26c0ca54d5338e9024c2c83429bf3`

## Step 1 — embedding / gather / type check

Goal: rule out that the engine puts the wrong vectors into slot 0.

Independent dequant: `/tmp/opencode/check_embedding.py` reads `token_embd.weight` Q4_K rows for the four prompt tokens using only `tools/gguf_reader.py` and the documented Q4_K block layout.

Command:
```bash
python3 /tmp/opencode/check_embedding.py
```

Result:
```
tok 549:  rel L2 = 0.000000e+00   max abs diff = 0.000000e+00
tok 6077: rel L2 = 0.000000e+00   max abs diff = 0.000000e+00
tok 280:  rel L2 = 0.000000e+00   max abs diff = 0.000000e+00
tok 7239: rel L2 = 0.000000e+00   max abs diff = 0.000000e+00
```

Verdict: **embedding gather and f32 type are correct**.  
Note: the first attempt of the script returned `nan` because the Q4_K block offset was read from byte 12 instead of byte 0; fixing the offset gave exact agreement.

## Step 2 — Q6_K reference validation

Goal: verify the Python Q6_K dequant used for `attn_q/k/v` and `attn_output` weights.

Reference: `/tmp/opencode/ref_q6k.c` is a minimal standalone C dequant taken from llama.cpp `dequantize_row_q6_K` (`ggml-quants.c:1939`).

Commands:
```bash
# locate blk.0.attn_v.weight row 0 / block 0 absolute offset
python3 /tmp/opencode/q6k_block_offset.py   # -> abs_offset_row0 = 301085408

# compile and run the independent reference
gcc -O2 -o /tmp/opencode/ref_q6k /tmp/opencode/ref_q6k.c -lm
/tmp/opencode/ref_q6k <pack> 301085408 > /tmp/opencode/ref_q6k_block0.bin

# compare against the Python reference
python3 /tmp/opencode/compare_q6k.py
```

Finding: the Python reference in `/tmp/opencode/check_nodes.py` appended the four quants in write order (`q1,q2,q3,q4`) instead of writing them to their actual memory positions within the 256-element chunk:

```text
logical positions:  q1 -> l,      q2 -> l+32,  q3 -> l+64,  q4 -> l+96
```

The C reference writes to those positions, so its memory dump is sequential `y[0], y[1], ..., y[255]`. The Python reference produced a shuffled vector and therefore reported `v rel L2 ≈ 2.1`.

Fix applied to `dequant_q6_K_row()`:
```python
chunk[base + l +  0] = d * scales[is_ + 0] * q1
chunk[base + l + 32] = d * scales[is_ + 2] * q2
chunk[base + l + 64] = d * scales[is_ + 4] * q3
chunk[base + l + 96] = d * scales[is_ + 6] * q4
```

After the fix, the same 256-element block from `ref_q6k_block0.bin` matches the Python dequant exactly.

Trustworthiness:
- Numbers labelled "before Q6_K fix" are **not trustworthy** for `q/k/v/attn_wo` comparisons.
- Numbers from this point on use the corrected Python reference.

## Step 3 — AC-5a layer comparison (current state, post-FFN-skip revert)

Command:
```bash
python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py \
  --oracle workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin \
  --dump /tmp/opencode/s4-dump.bin
```

Result:
```text
engine dump: 5 records, 2 slots/record, N=1 blocks computed
oracle: 4 records, 28 blocks
non-finite values in kept dump: 0
  cell (layer=0, pos=0): rel L2 = 1.929518e-02
  cell (layer=0, pos=1): rel L2 = 5.350500e-02
  cell (layer=0, pos=2): rel L2 = 5.834546e-02
  cell (layer=0, pos=3): rel L2 = 1.227524e-01
median rel L2 = 5.592523e-02
max rel L2    = 1.227524e-01 at (layer=0, pos=3)
first cell above bound 0.005: (layer=0, pos=0)
RESULT: FAIL
```

Bound: max relative L2 ≤ 5e-3 over the 4 cells of block 0.  
All four cells are above the bound, so this is a real arithmetic divergence, not a threshold artefact.

## Open hypotheses

1. **Q8_1 activation quantization.** The engine quantizes the residual to Q8_1 before every matvec; the oracle runs f32 activations. Position 0 exercises `embedding → attn_norm → q/k/v → (v) → wo → residual → ffn_norm → gate/up/down → residual`, so a ~1e-3 per-projection quantization error could compound to the observed 1.9e-2 at p=0.
2. **Projection/orientation error that only shows from p=1 onward.** The growth from p=0 (1.93e-2) to p=3 (1.23e-1) is too large for a pure fixed-point activation error; it suggests an attention orientation or KV-indexing issue that is masked at p=0 because RoPE at position 0 is the identity and there is only one key/value.

## Next command

Run the corrected per-node reference against the engine dumps at p=0 to separate hypothesis 1 from hypothesis 2:

```bash
python3 /tmp/opencode/check_nodes.py
```

Expected output columns:
```text
attn_norm rel L2
q rel L2
k rel L2
v rel L2
attn_wo rel L2
post_attn rel L2
block0 rel L2
oracle block0 pos0 vs engine
oracle block0 pos0 vs python
```

Decision rule:
- If `attn_norm` is clean (≤ ~1e-6) and `q/k/v` are clean (≤ ~1e-3) but `attn_wo`/`block0` are not, the residual error is downstream of the attention inputs (wo or FFN).
- If `q/k/v` are already ~1e-2, the dominant source is the Q8_1 activation path; add a local f32 matvec in `src/deepseek/` and re-measure.
