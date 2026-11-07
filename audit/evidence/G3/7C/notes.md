# 7C notes — what changed, design decisions, limitations, provenance

## What changed (Phase 7C, Gate G3)

1. **`src/model_spec.py` (new)** — `ModelSpec` + `resolve_model_spec(metadata, tensors)`:
   resolves family hparams (including separate per-head `key_dim`/`value_dim` from
   `{arch}.attention.key_length`/`value_length` with `rope.dimension_count` fallback),
   FFN activation family (`swiglu`/`geglu`), Phi-3 fused gate+up flag, gemma
   `sqrt(hidden)` embedding scale, optional `{arch}.final_logit_softcapping`, tied
   output, and the fused/separate QKV layout actually present in the file.
   Fail-fast validation: unknown arch (names the supported set), gemma2/gemma3
   variants, Phi-3 rope factors, gemma2-style softcap/SWA, `key_length !=
   value_length` (kernel/cache constraint, documented), missing block_count, and a
   *file-wide* tensor validation that lists every missing required tensor in one
   error and every shape mismatch with name/expected/actual. qwen2 resolves
   through the llama-family tensor layout as a metadata/bias regression target
   only (row 10 stays NOT YET).

2. **`src/layer.py`** — `TransformerLayer` consumes the spec. New paths:
   - fused QKV: one projection with N = q_dim + 2*kv_dim rows, then exact column
     slicing of the output (valid for quantized fused tensors too — the weight is
     never reshaped as three tensors); fused `attn_qkv.bias` or separate q/k/v
     biases alongside fused weights (llama.cpp `create_tensor_qkv` rules);
   - Phi-3 fused `ffn_up` (rows = 2*inter): single projection, contiguous-half
     split (silu(first half) * second half — `ggml_swiglu` semantics), optional
     `ffn_up.bias`/`ffn_down.bias`;
   - GeGLU (`gelu_tanh(gate) * up`, exact `ggml_gelu_f32` constants) for gemma;
   - attention uses q_dim = heads*key_dim and kv_dim = kv_heads*value_dim
     (`hidden//heads` is never assumed).
   - The C++ fast path (`forward_layer_cached`) is now explicitly gated to the
     llama-family layout (separate Q/K/V, no biases, separate SwiGLU gate/up);
     llama performance is unchanged.

3. **`src/inference.py`** — engine resolves the spec at load (fail-fast through
   `resolve_model_spec`), applies the family embedding scale (gemma
   `sqrt(hidden)`), and the optional final-logit softcap (`c*tanh(logits/c)`).
   Tied output handling (output.weight absent -> token_embd.weight) was already
   present and is now spec-validated.

4. **Tests** — `tests/test_model_spec.py` (CPU lane, 16 spec/fail-fast tests),
   `tests/test_model_families.py` (GPU lane, 10 engine tests), shared builders in
   `tests/model_spec_helpers.py` + `tests/family_fixtures.py`, and the independent
   FP32 NumPy reference `tests/reference_model.py`. `tests/test_harness_contract.py`
   `EXPECTED_LANES` gained both modules (cpu/gpu).

5. **Claims** — README: qualified in-bullet wording + the compatibility matrix;
   ledger rows 10/11/12 updated (10 stays NOT YET, 11/12 -> PARTIAL
   synthetic-fixture verified); the `10 README.md qwen2` baseline entry was
   removed (the site is now qualified in place).

## Design decisions

- **Tensor names/shapes come from real header dumps** recorded in
  `header-dumps/` (Phi-3-mini-4k-instruct-q4; gemma-2b-it Q4_K_M via the public
  `MaziyarPanahi/gemma-2b-it-GGUF` mirror of `google/gemma-2b-it`, whose
  upstream repo is gated — see `header-dumps/PROVENANCE.md`), cross-checked
  against the pinned llama.cpp source (phi3.cpp, gemma.cpp, llama-graph.cpp,
  llama-model.cpp `create_tensor_qkv`, llama-arch.cpp). No name was invented.
- **Fused GLU semantics**: contiguous halves, not interleaved pairs
  (`ggml_glu_impl` with a single input), matching the pinned llama.cpp.
- **Reference independence**: `tests/reference_model.py` never imports
  `layer`/`inference`/`model_spec`; it resolves family parameters itself from
  the GGUF metadata and computes the full graph in FP32 NumPy. The only
  production code it touches is `gguf_parser`'s format layer (header access +
  block dequantizers to read weight values).
- **No new GPU kernel** (allowed in §2): GeGLU runs host-side in NumPy FP32
  (`layer.geglu_host`) — documented performance limitation in the matrix. Fused
  QKV/FFN need no kernel: one wider matmul + output column slicing.

## Limitations (all fail fast, all documented in the matrix)

- `key_length != value_length` files are rejected: the GQA kernels and
  `KVCacheManager` assume one head dim; every supported file (llama/qwen2/phi3/
  real gemma) has equal dims. Extending `kv_cache.py` is out of 7C's allowed set.
- gemma2/gemma3, attention soft-capping, sliding-window attention, Phi-3
  long/short rope factors are rejected with explicit errors.
- Real-GGUF Phi-3/Gemma runs are 7F-2; no real-model support is claimed.
- Chat templates remain out of scope (row 8).

## Evidence provenance

- Header dumps: HTTP range requests (see `header-dumps/PROVENANCE.md` for URLs,
  revisions, byte ranges, sha256). No weights committed.
- Red log: clean parent worktree at 8426ec6 + the 7C test files copied in
  (no src changes). Family tests fail on the documented pre-7C defects
  (phi3 missing fused path -> `KeyError: 'blk.0.attn_q.weight'`; gemma head_dim
  resolved to hidden//heads=24 instead of key_length=32 and no embedding scale /
  GeGLU / softcap -> wrong logits, max err 8.7 on the quantized fixture).
- Green log: same tests + probes on the candidate.
- Llama regression: `qaqc-probes/probe_llama_regression.py` is self-contained and
  runs on both commits; its output is byte-identical (logits sha256
  a31dfc6f224d495966da14f2d06161ae2b18bf93ed7a6d5cbe8009c56f32441b, greedy ids
  [9, 15, 9, 0, 3, 9, 14, 9]); the repo test pins those parent goldens.
- Tolerances: engine runs FP16 activations vs the FP32 reference; family logits
  tolerance 6e-3 absolute. Coder-fixture max errs: phi3 F16 2.7e-3, phi3
  Q4_K/Q6_K 2.9e-3, gemma F16 2.0e-3/Q4_K 2.1e-3. The independent auditor probe
  (different fixture) observed phi3 F16 3.4e-3, phi3 Q4_K/Q6_K 4.9e-3, gemma
  F16 3.5e-3, gemma Q4_K 5.9e-3; the README/ledger cite the 6e-3 tolerance and
  the observed maxima, not the smaller coder-fixture numbers.

## Self-checks (allowed/forbidden set)

Only files permitted by the brief §2 were touched:
`src/model_spec.py` (new), `src/layer.py`, `src/inference.py`,
`tests/**` (incl. `tests/test_harness_contract.py` `EXPECTED_LANES`,
required by its own contract test), `README.md`, `audit/CLAIMS_LEDGER.md` (rows
10/11/12 only), `audit/claims_baseline.txt` (removal of the resolved row-10
entry, which the header comment explicitly assigns to 7B/7C), and
`audit/evidence/G3/7C/**`. `src/gguf_parser.py`, `src/kv_cache.py`, kernels,
CMake, CI, and the tokenizer were NOT changed.
