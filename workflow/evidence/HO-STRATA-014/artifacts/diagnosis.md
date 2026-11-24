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

## Step 6 — per-node oracle harness

Derived `workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp` from the signed HO-STRATA-010 harness:

```bash
cp workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp \
   workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp
sha256sum workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp
# bdc9303d6d884452175e199fff3a894836409543ef6f5f390a4e7eb9ab9b8f33
```

Added `--dump-node NAME[,NAME]` that uses the existing `graph_get_cb` filter (`cparams.cb_eval`) to capture any named tensor, not just `l_out-<il>`. The HO-STRATA-010 bundle was not modified.

Build commands (copied from HO-STRATA-010 §1, adapted to `/tmp/opencode/llama-ref`):

```bash
cmake -S /tmp/opencode/llama-ref -B /tmp/opencode/llama-ref/build \
  -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/opencode/llama-ref/build -j$(nproc)
g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp \
  -o /tmp/opencode/oracle_nodes \
  -I/tmp/opencode/llama-ref/include -I/tmp/opencode/llama-ref/ggml/include \
  -L/tmp/opencode/llama-ref/build/bin -lllama -lggml -lggml-base -lggml-cpu -lpthread
```

Note: the `llama` app target fails to link (`-lllama-server-impl` / `-lllama-cli-impl` missing because examples/server are disabled), but the shared libraries `libllama.so`, `libggml.so`, `libggml-base.so`, `libggml-cpu.so` are built and sufficient for the harness.

## Step 7 — engine-vs-oracle node table at p=0

Oracle command:

```bash
cd /tmp/opencode
LD_LIBRARY_PATH=/tmp/opencode/llama-ref/build/bin ./oracle_nodes \
  --model <pack> --tokens 549,6077,280,7239 --n 0 \
  --dump-node Qcur-0,Kcur-0,Vcur-0,ffn_inp-0,ffn_norm-0,ffn_out-0,l_out-0
```

Engine diagnostic dumps are from commit `2ace4d3f8` (local f32 matvec). `ffn_out-0` is computed as `l_out-0 - ffn_inp-0` for both sides.

| node | engine vs oracle rel L2 (p=0) | verdict |
|---|---|---|
| `attn_norm-0` | 4.03e-08 | **match** — embedding and norm are correct |
| `Qcur-0` | 4.44e-03 | **first diverge** |
| `Kcur-0` | 6.89e-03 | diverge |
| `Vcur-0` | 5.78e-02 | diverge |
| `ffn_inp-0` (post-attn residual) | 3.64e-02 | downstream of attention |
| `ffn_out-0` | 2.64e-02 | downstream |
| `l_out-0` / block0 | 1.94e-02 | downstream |

`attn_norm-0` first 10 values and norms agree to machine precision, so the divergence starts **inside the Q/K/V projections**, not before them.

## Step 8 — checking the activation-quantization hypothesis

Because the f32 reference and the f32-matvec engine agree to ~1e-6, they share the same reading of the weights and the input. The divergence from the oracle must therefore be in how llama.cpp evaluates the matmul itself. A plausible explanation is that the CPU oracle quantizes activations to Q8_1/Q8_K for its quantized matmuls, even though the weights are the same bytes.

Quick test: switch only the Q/K/V projections back to the engine's native Q8_1 matvec (`K::native_mmvq`) and compare again:

| node | f32 matvec | native Q8_1 q/k/v only |
|---|---|---|
| `Qcur-0` | 4.44e-03 | 4.19e-03 |
| `Kcur-0` | 6.89e-03 | 6.30e-03 |
| `Vcur-0` | 5.78e-02 | 5.34e-02 |

The native Q8_1 path is slightly closer to the oracle, which supports the activation-quantization hypothesis, but the residual is still large. The exact quantization path used by the CPU backend (Q8_1 vs Q8_K, scale computation, summation order) needs to be identified and matched.

## Step 9 — permutation test on Q/K/V outputs

Because `Vcur-0` error (5.8e-2) is ~10× larger than `Qcur-0` (4.4e-3) and `Kcur-0` (6.9e-3) despite the same `attn_norm-0` input, a layout/permutation bug was tested. The engine dump is reshaped as `[n_head=16][head_dim=128]` and compared to the oracle `Vcur-0/Kcur-0/Qcur-0[p=0]` under several explicit orderings.

Permutation rel L2 table (engine vs oracle, p=0):

| ordering | Qcur-0 | Kcur-0 | Vcur-0 |
|---|---|---|---|
| identity (head-major) | 4.19e-03 | 6.30e-03 | 5.34e-02 |
| element-major transposed | 1.42e+00 | 1.42e+00 | 1.43e+00 |
| reverse head order | 1.43e+00 | 1.42e+00 | 1.45e+00 |
| shift heads +1 | 1.40e+00 | 1.40e+00 | 1.38e+00 |
| shift within-head +1 | 1.39e+00 | 1.42e+00 | 1.42e+00 |

No tested ordering collapses the error. Identity is the best ordering for all three projections. The error is therefore not a simple head-ordering bug.

## Step 10 — weight type audit

GGML types from the pack header (`tools/gguf_reader.py`):

| tensor | type | shape |
|---|---|---|
| `token_embd.weight` | Q4_K | [2048, 102400] |
| `blk.0.attn_q.weight` | Q4_K | [2048, 2048] |
| `blk.0.attn_k.weight` | Q4_K | [2048, 2048] |
| `blk.0.attn_v.weight` | **Q6_K** | [2048, 2048] |
| `blk.0.attn_output.weight` | Q4_K | [2048, 2048] |
| `blk.0.ffn_gate.weight` | Q4_K | [2048, 10944] |
| `blk.0.ffn_up.weight` | Q4_K | [2048, 10944] |
| `blk.0.ffn_down.weight` | Q8_0 | [10944, 2048] |

`attn_v.weight` is the **only Q6_K** tensor among Q/K/V/output. This explains why V diverges more than Q/K: the V projection uses a different quantized type whose dequantisation or block-layout path is suspect, not the activation path.

## Step 11 — cross-check: Python f32 matvec from oracle's own `attn_norm-0`

To separate "engine input path" from "weight read/dequant/layout", we recomputed Q/K/V in Python from the pack's quantized weights using the oracle's own `attn_norm-0[p=0]` vector as input. No engine tensors were used.

| node | Python f32 (from oracle input) vs oracle |
|---|---|
| `Qcur-0` | 4.44e-03 |
| `Kcur-0` | 6.89e-03 |
| `Vcur-0` | 5.78e-02 |

These numbers match the engine-vs-oracle divergence almost exactly. Therefore:

- The engine's staging of `attn_norm-0` is **not** the problem (`attn_norm-0` already matched).
- The engine's f32 matvec arithmetic is **not** the problem (Python's independent f32 dot product gives the same divergence).
- The problem is either in how the **weights are read/dequantised/laid out** from the GGUF, especially for the **Q6_K** `attn_v.weight`, or in the oracle's own quantized-activation matmul.

## Step 12 — adjudicate with llama.cpp's own `dequantize_row_q6_K`

We copied `dequantize_row_q6_K` verbatim from `/tmp/opencode/llama-ref/ggml/src/ggml-quants.c` (commit `78e05298…`) into `/tmp/opencode/ref_q6k_llama.c`, compiled it with gcc, and dequantised the entire `blk.0.attn_v.weight` matrix from the raw GGUF bytes. The same was done for `blk.0.attn_q.weight` (Q4_K) as a control, using `dequantize_row_q4_K`.

Commands:

```bash
gcc -O2 -o /tmp/opencode/ref_q6k_llama /tmp/opencode/ref_q6k_llama.c -lm
/tmp/opencode/ref_q6k_llama /path/to/deepseek-moe-16b-base-q4_k_m.gguf 301085408 4194304 \
  > /tmp/opencode/ref_q6k_llama_wv.bin

gcc -O2 -o /tmp/opencode/ref_q4k_llama /tmp/opencode/ref_q4k_llama.c -lm
/tmp/opencode/ref_q4k_llama /path/to/deepseek-moe-16b-base-q4_k_m.gguf 298726112 4194304 \
  > /tmp/opencode/ref_q4k_llama_wq.bin
```

The dequantised matrices were then matveced with the oracle's own `attn_norm-0[p=0]` vector and compared with the engine's `diag_q.bin` / `diag_v.bin` and the oracle's `Qcur-0` / `Vcur-0`.

### Q4_K Qcur-0 3×3 rel L2 table

| | oracle | engine | python | llama.cpp |
|---|---|---|---|---|
| oracle | 0.000000e+00 | 4.442250e-03 | 4.442188e-03 | 4.442188e-03 |
| engine | 4.451740e-03 | 0.000000e+00 | 7.488521e-07 | 7.488521e-07 |
| python | 4.451678e-03 | 7.488521e-07 | 0.000000e+00 | 0.000000e+00 |
| llama.cpp | 4.451678e-03 | 7.488521e-07 | 0.000000e+00 | 0.000000e+00 |

### Q6_K Vcur-0 3×3 rel L2 table

| | oracle | engine | python | llama.cpp |
|---|---|---|---|---|
| oracle | 0.000000e+00 | 5.777347e-02 | 5.777344e-02 | 5.777344e-02 |
| engine | 5.771256e-02 | 0.000000e+00 | 6.440568e-07 | 6.440568e-07 |
| python | 5.771254e-02 | 6.440569e-07 | 0.000000e+00 | 0.000000e+00 |
| llama.cpp | 5.771254e-02 | 6.440569e-07 | 0.000000e+00 | 0.000000e+00 |

### Interpretation

- **Engine, Python, and llama.cpp dequant all agree to machine precision** for both Q4_K and Q6_K. The engine's weight read/dequantisation is **correct**.
- The divergence from the oracle is **not** in the weight bytes, dequantisation, or f32 matvec arithmetic.
- The Q4_K control (`Qcur-0`) shows ~4.4e-3 divergence even with a perfect f32 reference. This is the oracle's own matmul precision floor for Q4_K weights.
- The Q6_K `Vcur-0` divergence is ~5.8e-2, an order of magnitude larger. Because the weight and input are identical, the difference must come from the oracle's quantized-activation matmul path, which is type-dependent (Q4_K vs Q6_K use different CPU kernels and different activation-quantization behaviour).

## Step 13 — what `Vcur-0` actually is in the oracle graph

Read `src/models/deepseek.cpp` and `src/llama-graph.cpp` at the pinned commit `78e05298…`:

- `src/models/deepseek.cpp` graph (block 0): `cur = build_norm(inpL, attn_norm, ..., LLM_NORM_RMS, il); cb(cur, "attn_norm", il);` then `auto [Qcur, Kcur, Vcur] = build_qkv(..., cur, ...); cb(Vcur, "Vcur", il);`
- `src/llama-graph.cpp` `build_qkv` (separate Q/K/V path, because this GGUF has no fused `attn_qkv.weight`): `Vcur = build_lora_mm(layer.wv, cur, layer.wv_s);`
- `build_lora_mm`: `cur_mm = build_hadamard_input(w, cur); res = ggml_mul_mat(ctx0, w, cur_mm); if (w_s) res = ggml_mul(ctx0, res, w_s);`
- For this model there is **no** `prism.hadamard` metadata and **no** `blk.0.attn_v.scale` tensor, so `build_hadamard_input` returns `cur` unchanged and `wv_s` is null.
- Therefore `Vcur-0` is exactly `attn_v.weight × attn_norm-0`, with no extra scale, bias, Hadamard transform, or permutation before the callback. The later `ggml_reshape_3d(..., 128, 16, n_tokens)` is a view on the same data and does not reorder elements.

This rules out the "Vcur is not the projection we assume" hypothesis.

## Current conclusion

- `attn_norm-0` matches exactly; the divergence starts at `Qcur-0`.
- No permutation or layout bug was found.
- The engine's weight dequantisation matches llama.cpp's reference exactly.
- The engine's f32 matvec matches a Python/llama.cpp f32 reference exactly.
- `Vcur-0` is exactly `attn_v.weight × attn_norm-0` (no hidden scale/transform).
- The remaining divergence from the oracle (~4.4e-3 for Q4_K Q/K, ~5.8e-2 for Q6_K V) is in the oracle's own quantized-activation matmul, whose error is strongly dependent on weight type.
- The 5e-3 AC-5a bound cannot be met for the Q6_K `attn_v.weight` path by fixing dequantisation or f32 arithmetic alone.

## Next action

Raise a deviation request (or architect decision) to choose between:

1. **Implement llama.cpp's exact quantized-activation matmul for Q4_K/Q6_K/Q8_0 inside `src/deepseek/`** (local to the parity engine, no shared-kernel edits), so the engine reproduces the oracle's CPU-backend arithmetic.
2. **Revisit the 5e-3 bound** for AC-5a, since the oracle's own Q6_K matmul has a ~5.8e-2 precision floor relative to a f32 reference on this pack.

No code change was made in this diagnostic round; the Strata branch remains at `2ace4d3f8`.
