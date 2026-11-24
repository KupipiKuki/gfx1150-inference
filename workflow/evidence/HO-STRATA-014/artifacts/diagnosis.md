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

## Step 4 — per-node reference table at p=0 (f32 matvec)

Command:
```bash
python3 /tmp/opencode/check_nodes.py
```

This compares the engine's diagnostic dumps at position 0 against an independent f32 reference built from dequantized weights (Q4_K/Q6_K/Q8_0) and f32 activations.

Result with the original Q8_1 activation path:
```text
attn_norm rel L2 = 2.505799e-08
q rel L2         = 1.433217e-03
k rel L2         = 2.044367e-03
v rel L2         = 2.122617e-02
attn_wo rel L2   = 1.601854e-02
post_attn rel L2 = 1.332766e-02
block0 rel L2    = 7.103667e-03
oracle block0 pos0 vs engine = 1.929518e-02
oracle block0 pos0 vs python = 1.939396e-02
```

After adding the local f32 matvec (`src/deepseek/ds_f32_matvec.cu`) and removing Q8_1 activation quantization:
```text
attn_norm rel L2 = 2.505799e-08
q rel L2         = 7.454328e-07
k rel L2         = 7.108556e-07
v rel L2         = 6.471743e-07
attn_wo rel L2   = 1.111216e-06
post_attn rel L2 = 9.256767e-07
block0 rel L2    = 1.169409e-06
oracle block0 pos0 vs engine = 1.939394e-02
oracle block0 pos0 vs python = 1.939396e-02
```

Interpretation:
- `attn_norm` is clean to ~2.5e-8.
- With Q8_1 activations, `q/k` show ~1-2e-3 noise, but `v` shows 2.1e-2.
- With f32 activations, `q/k/v/attn_wo/post_attn/block0` all agree with the f32 reference to ~1e-6.
- **The engine is now arithmetically identical to the independent f32 reference.**
- However, **both the engine and the f32 reference differ from the oracle by 1.94e-2 at p=0**.
- Therefore the Q8_1 activation path is ruled out as the dominant cause of the AC-5a failure.

## Step 5 — AC-5a after f32 matvec

Command:
```bash
python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py \
  --oracle workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin \
  --dump /tmp/opencode/s4-dump-f32.bin
```

Result:
```text
engine dump: 5 records, 2 slots/record, N=1 blocks computed
oracle: 4 records, 28 blocks
non-finite values in kept dump: 0
  cell (layer=0, pos=0): rel L2 = 1.939394e-02
  cell (layer=0, pos=1): rel L2 = 5.222241e-02
  cell (layer=0, pos=2): rel L2 = 5.988062e-02
  cell (layer=0, pos=3): rel L2 = 1.227065e-01
median rel L2 = 5.605152e-02
max rel L2    = 1.227065e-01 at (layer=0, pos=3)
first cell above bound 0.005: (layer=0, pos=0)
RESULT: FAIL
```

Bound `≤ 5e-3` is still violated.  
The residual is now a **reference-vs-oracle mismatch**, not an engine-vs-reference mismatch.

## Ruled out

1. Embedding/gather/type error — exact match.
2. Q6_K reference dequant bug — fixed; matches independent C reference.
3. Q8_1 activation quantization — bypassed with f32 matvec; AC-5a unchanged.

## Open hypotheses

The 1.94e-2 difference between the f32 reference and the oracle must come from one of the following (all at p=0, where RoPE is identity and KV indexing is trivial):
- **RMSNorm implementation difference** (eps handling, sum order, or whether the weight is applied at a different precision).
- **SwiGLU orientation** (`silu(gate)*up` vs `silu(up)*gate`, or a different `silu` rounding).
- **FFN down-projection orientation or dequant** (Q8_0 row layout).
- **An arithmetic step the oracle performs that the reference omits** (e.g., a scale factor, residual scaling, or a second norm).

## Next command

Build the per-node oracle dump harness and capture `attn_norm-0`, `attn_out-0` (or q/k/v/attention-output family), `ffn_norm-0`, `ffn_out-0`, and `l_out-0` from the pinned llama.cpp tree `78e05298…`:

```bash
# copy HO-STRATA-010 oracle_harness.cpp to workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp
# add --dump-node NAME[,NAME] support using the existing tensor-callback filter
# build into /tmp/opencode/oracle_nodes and run on the pack with the same 4-token prompt
cd /tmp/opencode/llama-ref && g++ ... -o /tmp/opencode/oracle_nodes
/tmp/opencode/oracle_nodes <pack> --dump-node attn_norm-0,attn_out-0,ffn_norm-0,ffn_out-0,l_out-0
```

Compare the first node where engine/oracle relative L2 exceeds the f32-reference-vs-engine noise floor (~1e-6). That node names the remaining arithmetic mismatch.
