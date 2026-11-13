# Phase 7C Coder Brief — Model-Family Support (Gate G3)

**To:** GLM5.3 (coder)
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-06
**Branch:** `wp/7C-model-families`
**Base:** the tip of `vibe/phase7-220201` that contains this brief (`git log -1 --oneline`; do not start from an older SHA)
**Gate:** G3. **7C is authorized after G2 (2026-11-06). 7D is not authorized.**
**Prior gates:** G1 signed with C-G1-3 (GPU runner) remaining; G2 signed; C-G1-4 closed. The 7B tokenizer is accepted — do not reopen it in this package.

---

## 0. Read first

1. `audit/REVIEW_v0.6.1_c75914b.md` §2.2 and `audit/AUDIT_REMEDIATION_v0.6.2.md` §2.2/§6 P0-2 — the original Phi-3/Gemma finding.
2. The pinned llama.cpp source at `149f5641b931aaf33697d70f9abc90c3e5300247`:
   - `src/models/phi3.cpp` — fused QKV, fused `ffn_up`, optional rope factors.
   - `src/models/gemma.cpp` — `sqrt(n_embd)` embedding scale, GELU-gated FFN, tied output.
   - `src/models/gemma2.cpp` — final/attention softcaps and SWA (out of scope unless explicitly listed).
   - `src/llama-model.cpp` `create_tensor_qkv` — fused-vs-separate QKV and bias rules.
   - `src/llama-arch.cpp` — the authoritative `%s.*` metadata and `blk.%d.*` tensor names.
3. `PHASE7_IMPLEMENTATION_HANDOFF.md` §1 (roles), §2 (one package/one gate), §7 (evidence contract), and the 7C section.
4. Current builders: `tests/test_full_model.py`, `tests/test_layer.py`, `tests/test_phase5_scale.py` (`write_synthetic_gguf`), and `src/layer.py` / `src/inference.py`.

**Authority:** real GGUF header dumps beat this brief on tensor names/shapes. The pinned llama.cpp source beats prose on graph semantics. If they conflict, record the dump and stop for an auditor decision.

---

## 1. Objective and non-goals

**Objective:** add a model-spec/tensor map and make the Phi-3 and Gemma forward paths
correct against an independent reference, while keeping the llama-family path
byte-for-byte unchanged. Publish an honest compatibility matrix and fix the public
claims.

**Non-goals (do not bundle):**
- Qwen2 support claims. Qwen2 metadata/bias support must not regress, but row 10 stays
  `NOT YET`; Qwen2 is a regression test, not a 7C acceptance target.
- Gemma 2/3 attention softcap, sliding-window attention, or other extra features unless
  explicitly added to the package and evidenced. Fail fast with a clear message if the
  file requires them.
- Real-GGUF support claims. Synthetic fixture correctness is necessary but not
  sufficient; real-GGUF golden logits/tokens are 7F-2. The matrix must say which is which.
- Chat templates, 7D memory work, 7E streams, performance tuning, new quant formats.
- Rewriting the tokenizer, parser, CMake/packaging, or CI (except a new 7C kernel target
  as allowed in §2).

---

## 2. Allowed files

- `src/model_spec.py` (new, preferred) **or** `src/layer.py` for the `ModelSpec`/tensor map.
- `src/layer.py` — layer execution, fused/separate paths, activations, shape checks.
- `src/inference.py` — model-spec use, embedding scale, final-logit softcap, dims.
- `src/gguf_parser.py` — **only** if metadata access needs a small helper; do not change
  parser validation/fail-closed behavior.
- `src/kernels/**`, `src/python_bindings/bindings.cpp`, `CMakeLists.txt` — **only** if a
  new kernel is required for fused QKV/FFN or GeGLU. Register only that target; no other
  build/packaging/CI changes. If a correct host-side path is used instead, document the
  performance limitation and do not add a kernel.
- `tests/**` — including a new `tests/test_model_families.py` and an independent
  reference helper.
- `tests/fixtures/**` — synthetic GGUF fixtures and small header dumps with provenance.
- `README.md` — tokenizer/model-family wording and the compatibility matrix.
- `audit/CLAIMS_LEDGER.md` — rows 10/11/12 only.
- `audit/evidence/G3/7C/**`.
- docs (`PHASE7_IMPLEMENTATION_HANDOFF.md` only if the process/status changes).

**Forbidden:** 7D/7E source work, unrelated refactors, weakening/deleting any existing
test, changing the tokenizer/parser gates, ledger arithmetic outside rows 10–12, CI
workflow changes (except a kernel target in the existing build).

---

## 3. Work packages

### 7C-1 — `ModelSpec` / tensor map

Add a small, data-driven spec that resolves, for a loaded GGUF:

- architecture (`general.architecture`) and `{arch}.block_count`;
- `hidden`, `intermediate`, `num_heads`, `num_kv_heads`;
- **separate `key_dim` and `value_dim`** (`{arch}.attention.key_length` /
  `{arch}.attention.value_length`, falling back to `rope.dimension_count` only where
  correct; do not default to `hidden // num_heads` when an explicit key length exists);
- `rms_norm_eps`, `rope_freq_base`, `rope_neox`/rope pattern;
- FFN activation: `swiglu` (llama/qwen2/phi3) or `geglu` (gemma);
- embedding scale: `1.0` (llama/qwen2/phi3) or `sqrt(hidden)` (gemma);
- final-logit softcap: `None` or the metadata value (`{arch}.final_logit_softcapping`);
- tied output (`output.weight` absent → `token_embd.weight`);
- required/optional tensor names, fused-QKV/fused-FFN flags, and bias names.

Validation rules:

- Unknown architecture → explicit `ValueError` naming the architecture and the supported
  set (llama, phi3, gemma; qwen2 metadata regression only).
- Missing required tensors → **one** error listing every missing name (not the first
  `KeyError`), with the architecture and expected names.
- Missing optional tensors → no error; the spec records the optional feature as absent.
- Shape mismatch → error with tensor name, expected shape, actual shape.
- Shape rules: fused QKV rows = `q_dim + 2*kv_dim` (or the header’s documented split);
  fused Phi-3 `ffn_up` rows = `2*inter`; Gemma `q_dim = n_heads*key_dim`,
  `kv_dim = n_kv_heads*value_dim`; `attn_output` input = `q_dim`, output = `hidden`.
- `llama` path unchanged: same tensors, same `LlamaLayerConfig` values, same logits/tokens.

`TransformerLayer`/`LlamaInferenceEngine` consume the spec rather than hardcoded
`llama.*`/`prefix + "attn_q.weight"` lookups.

### 7C-2 — Phi-3 (`general.architecture = "phi3"`)

Use the real header names; the expected reference layout is:

- `blk.N.attn_qkv.weight` and `.bias` fused (legacy files may carry separate
  `attn_q/k/v.weight` and separate biases — support both);
- `blk.N.attn_output.weight` (+ optional bias);
- `blk.N.ffn_up.weight` **fused gate+up** (rows = `2*inter`), `blk.N.ffn_down.weight`;
  optional FFN biases per the header (`ffn_up.bias`/`ffn_down.bias`; do not invent names);
- norms as `blk.N.attn_norm.weight` / `blk.N.ffn_norm.weight`;
- Phi-3 uses NeoX RoPE (already in `_NEOX_ROPE_ARCHS`); `rope_factors_long/short` are
  optional — if present and not implemented, fail fast for that file rather than silently
  ignoring them.

Implementation:

- Fused QKV: for F16/F32, slice rows without dequantization; for quantized tensors,
  add a fused/offset matmul path **or** a documented dequantize/split path. Do not
  silently reshape a quantized fused tensor as if it were three separate tensors.
- Fused gate/up: split/slice the gate and up halves (F16/F32) or add a fused path for
  quantized tensors; feed the existing SwiGLU.
- Apply optional QKV and FFN biases with the same FP32-add-then-FP16 behavior as the
  existing bias path.
- Validate the fused/separate equivalence and the bias/no-bias equivalence in tests.

### 7C-3 — Gemma (`general.architecture = "gemma"`)

Required semantics (from the pinned `gemma.cpp` and `llama-arch.cpp`):

- embedding lookup is scaled by `sqrt(hidden_size)` before layer 0;
- **GeGLU**, not SwiGLU: `gelu(ffn_gate(x)) * ffn_up(x)` then `ffn_down`; add a GeGLU
  kernel or a documented host path;
- **NeoX RoPE** (llama.cpp returns `LLAMA_ROPE_TYPE_NEOX` for `LLM_ARCH_GEMMA`; the
  current `_NEOX_ROPE_ARCHS` does not include `gemma`);
- explicit `attention.key_length` / `value_length`: `q_dim = n_heads*key_dim`,
  `kv_dim = n_kv_heads*value_dim`; with Gemma 7B, `hidden/heads != key_dim`, so the
  current `hidden//heads` default is wrong;
- final-logit softcap when `{arch}.final_logit_softcapping` is present:
  `logits = c * tanh(logits / c)`; if absent, no cap;
- tied output (`output.weight` usually absent; use `token_embd.weight`);
- optional QKV biases / fused QKV per the header, same fused/separate rules as §7C-2.

**Gemma 2/3 features are out of scope:** if `gemma2`/`gemma3` metadata, attention
softcap, sliding-window attention, or an unsupported rope pattern is present, fail fast
with a clear "unsupported gemma variant/feature" error. Do not apply a partial graph and
call it supported. The matrix must name the exact architecture tested (`gemma`, not
`gemma2`/`gemma3`).

### 7C-4 — Compatibility matrix and claims

Publish a matrix in `README.md` (and evidence) with rows for:

- llama (Q4_0/Q4_K/Q8_0; real-GGUF/hardware baseline — existing release scope);
- phi3 (synthetic fixture only; list the quant types actually run);
- gemma (synthetic fixture only; list the quant types actually run);
- qwen2 (metadata/bias regression; **NOT YET** as a support claim).

Columns: arch, quant, context, evidence type (real GGUF vs synthetic), status, notes.
Use `VERIFIED` only for what the evidence actually is. A synthetic logits match is
**synthetic-fixture verified**, not real-model support. Real-GGUF Phi-3/Gemma claims stay
pending 7F-2. Update `audit/CLAIMS_LEDGER.md` rows 10/11/12 with the exact scope; do not
mark Qwen2/Phi-3/Gemma `VERIFIED` on synthetic evidence alone.

Fix README wording so no unsupported family is listed as supported and the release scope
remains the verified llama-family statement.

---

## 4. Real header evidence (do not invent names)

Before coding the tensor maps, record a text dump of the real GGUF metadata and tensor
index for at least one Phi-3 and one Gemma file (for example the Q4_0 or Q4_K_M
`microsoft/Phi-3-mini-4k-instruct-gguf` and `google/gemma-2b-it-GGUF` variants; verify
the exact repo/revision at the time). The dump must include:

- `general.architecture`, all `{arch}.*` keys relevant to the spec;
- every `blk.0.*` (and global) tensor name, shape, and GGML type;
- the source URL/revision and a sha256 of the file or header slice used.

Keep the dump text-only and small; do not commit model weights. If a range request is
used, record the byte range and the parser/command. Place it under
`audit/evidence/G3/7C/header-dumps/`.

The tensor names in this brief are the expected reference names, but the dump is
authoritative for the specific files you test.

---

## 5. Fixtures and independent reference logits

- Build tiny synthetic GGUFs with `write_synthetic_gguf` (or an equivalent helper):
  hidden/heads/kv/head_dim small enough for CPU, 1–2 layers, deterministic seeded
  weights, F16/F32 and at least one quantized variant where the fused path is exercised.
- Write the exact Phi-3/Gemma tensor names from the header dump.
- Implement an **independent** NumPy reference in the test tree (do not call
  `TransformerLayer`/`LlamaInferenceEngine` to compute the expected value). The reference
  must include: Phi-3 fused QKV + fused gate/up + biases + NeoX; Gemma embedding scale +
  GeGLU + NeoX + key/value dims + softcap.
- Compare logits for a fixed token sequence with a justified tolerance. Run the reference
  in FP32 and the engine in the tested dtype; record max abs diff.
- Preferred: if a tiny real GGUF can be run through the pinned llama.cpp binary for
  logits, record that as an additional cross-check. If not feasible, the independent
  NumPy reference is the accepted reference for G3; the QAQC must verify it is not
  derived from the implementation under test.
- The tests must **fail on the parent** `8426ec6` (Phi-3 missing-tensor/`KeyError`,
  Gemma wrong logits) and pass on the candidate. Record the red log.

---

## 6. Required checks

```bash
# model spec / family tests
python -m pytest -m "not gpu" -q -k "model_spec or phi3 or gemma or compat"
python -m pytest -m gpu -q -k "phi3 or gemma or llama_regression"

# full lanes
python -m pytest -m "not gpu" -q
python -m pytest -m gpu -q
python tests/test_cpu_only.py
python -O tests/test_cpu_only.py
python scripts/qa/check_claims.py

# independent probes (write them; do not only replay the coder tests)
# - fused vs separate QKV/FFN equivalence
# - bias vs no-bias equivalence
# - unknown arch / missing required / missing optional / shape mismatch
# - Gemma key_dim != hidden/heads; embedding scale; softcap; GeGLU vs SwiGLU
# - llama regression: same token IDs/logits on the fixed prompt
```

---

## 7. QAQC adversarial checks

- **Real names:** every required/optional tensor name is taken from a recorded real GGUF
  header, not invented; the header dump is in the evidence.
- **Fail-fast quality:** unknown arch, missing required tensor, missing optional tensor,
  and shape mismatch each produce a distinct, actionable error; missing required lists all
  missing names.
- **Fused/separate:** Phi-3 fused `attn_qkv` and fused `ffn_up`, and legacy separate
  tensors, produce the same logits (within tolerance); the bias path and no-bias path
  agree where both are valid.
- **Quantized fused:** a quantized fused QKV/FFN fixture runs (or the limitation is
  explicitly documented and the file fails fast — do not silently mis-shape).
- **Gemma math:** `gemma.attention.key_length` != `hidden/heads` (7B-style) reshapes
  correctly; `sqrt(hidden)` embedding scale; final-logit softcap; GeGLU (not SwiGLU);
  NeoX RoPE; tied output.
- **Phi-3 math:** fused QKV bias, fused gate/up split, optional FFN biases, NeoX; long-rope
  factors fail fast if unsupported.
- **Llama regression:** identical token IDs and logits on the fixed prompt/seed.
- **Qwen2 regression:** metadata/bias path unchanged; claim remains NOT YET.
- **Claims/matrix:** no synthetic-fixture result is presented as real-model support; the
  README/matrix/ledger agree; `check_claims.py` is clean.
- **Red/green:** the new family tests fail on the parent and pass on the candidate.

---

## 8. Acceptance / G3 exit

- [ ] `ModelSpec` resolves llama/phi3/gemma and fails fast for unknown/missing/shape errors.
- [ ] Phi-3 synthetic fixture runs; logits match the independent reference; fused and
      separate paths agree; biases handled.
- [ ] Gemma synthetic fixture runs; logits match the independent reference with embedding
      scale, GeGLU, NeoX, key/value dims, softcap, tied output.
- [ ] Llama-family behavior is unchanged (token IDs + logits).
- [ ] Compatibility matrix and README are accurate; synthetic vs real is explicit.
- [ ] Unsupported families/features fail fast with a clear message.
- [ ] CPU/GPU lanes, `test_cpu_only` both modes, and claims checker are green.
- [ ] Evidence bundle complete and red/green recorded.

**Fallback:** if Phi-3 or Gemma cannot be evidenced, do **not** merge a partial support
claim. Keep the family explicitly unsupported, implement the fail-fast path, document the
limitation, and stop for the auditor’s scope decision. Do not weaken the tests or mark a
family supported to make G3 close.

---

## 9. Evidence bundle — `audit/evidence/G3/7C/`

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
red.log                      # new family tests fail on parent 8426ec6
green.log                    # same tests pass on candidate
header-dumps/                # real Phi-3/Gemma metadata + tensor names (text)
model-spec.log
phi3.log  gemma.log
llama-regression.log
compat-matrix.md
cpu-lane.log  gpu-lane.log  cpu-only.log
claims.log
qaqc-probes/                 # independent QAQC scripts/logs
notes.md
```

See `audit/evidence/G3/7C/README.md` for the contract.

---

## 10. Stop / handoff

Stop at G3. Do not start 7D. Do not merge to `vibe/phase7-220201`; the auditor merges
only after G3 is signed. 7F-2 owns real-GGUF Phi-3/Gemma golden tokens/logits; 7C must
not claim them.

---

## 11. Start-here checklist

1. `git switch wp/7C-model-families` (created from the brief commit) and confirm
   `git rev-parse HEAD` / `git log -1 --oneline`.
2. Read §0 sources; record the two real header dumps before writing tensor names.
3. Implement 7C-1 first; get the llama regression green before touching Phi-3/Gemma.
4. Add the parent-red tests and record `red.log` from a clean worktree at `8426ec6`.
5. Implement 7C-2/7C-3 in that order; keep the fused/separate and bias probes.
6. Run the required checks; write the matrix/claims; assemble the evidence bundle.
7. Stop for QAQC; do not start 7D or claim real-model support.
