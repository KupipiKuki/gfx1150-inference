# compat-matrix.md — model-family compatibility (Phase 7C, Gate G3)

Source of truth: `README.md` (model-family compatibility matrix) — this file
mirrors it verbatim for the evidence bundle. Status vocabulary follows
`audit/CLAIMS_LEDGER.md` (rows 10/11/12).

### Model-family compatibility matrix (Phase 7C, Gate G3)

Every row states the *actual* evidence type. A synthetic-fixture logits match
against the independent FP32 NumPy reference is **synthetic-fixture
verification** and is not real-model support; real-GGUF Phi-3/Gemma golden
logits/tokens belong to 7F-2. Unsupported architectures and unsupported
family-specific features fail fast with explicit errors
(`src/model_spec.py`, tested in `tests/test_model_families.py`).

| Architecture (`general.architecture`) | Quantizations actually run | Evidence type | Prefill + KV-cache decode + generation | Status | Notes |
|---|---|---|---|---|---|
| `llama` | `Q4_0`, `Q4_K`, `Q8_0` (release scope) + `Q6_K` kernels and mixed `Q4_K`+`Q6_K` recipe wiring | synthetic GGUFs on the gfx1150 hardware lanes vs FP32 CPU reference (G0 baseline; see ledger rows 3-6) | yes (all three) | **VERIFIED** (release scope) | unchanged by 7C: fixed-prompt logits/token-IDs byte-identical to the parent commit (`audit/evidence/G3/7C/llama-regression.log`) |
| `phi3` | `F16` and a mixed `Q4_K`+`Q6_K` build, fused `attn_qkv` and fused gate+up `ffn_up`, with and without biases | **synthetic fixture only** — independent FP32 NumPy reference (`tests/reference_model.py`), within the 6e-3 test tolerance (observed max 4.9e-3 on the independent Q4_K/Q6_K probe; F16 ≤3.5e-3) | yes (prefill, cached decode, greedy generation) · fused vs separate equivalence ≤ 1e-3 | **PARTIAL** — synthetic-fixture verified | real-GGUF goldens pending 7F-2; fused and legacy separate layouts both supported; optional `attn_qkv.bias`/`ffn_up.bias`/`ffn_down.bias`; long/short rope-factor tensors fail fast |
| `gemma` | `F16` and `Q4_K`, separate `attn_q/k/v` | **synthetic fixture only** — independent FP32 NumPy reference (`tests/reference_model.py`), within the 6e-3 test tolerance (observed max 5.9e-3 on the independent Q4_K probe; F16 ≤3.6e-3) | yes (prefill, cached decode) | **PARTIAL** — synthetic-fixture verified | real-GGUF goldens pending 7F-2; `sqrt(hidden)` embedding scale, GeGLU (host FP32 path — no new GPU kernel in 7C), NeoX rope, explicit `attention.key_length`/`value_length` (`hidden//heads` is never assumed), optional `final_logit_softcapping`, tied `token_embd` output |
| `gemma2`, `gemma3` | none | n/a | n/a | **NOT SUPPORTED** (fail fast) | attention soft-capping, sliding-window attention, and other variant features are rejected with explicit errors |
| `qwen2` | `Q4_K`/`Q6_K` metadata/bias regression fixture | synthetic regression only | metadata + bias-add path | **NOT YET** | qwen2 resolves through the llama-family tensor layout as a regression target; no support claim (chat template/BOS correctness open) |
| anything else | none | n/a | n/a | **NOT SUPPORTED** (fail fast) | `ValueError` naming the architecture and the supported set (`llama`, `phi3`, `gemma`; `qwen2` via the llama-family layout only) |

## Quant types actually run per family (synthetic fixtures, 7C)

- phi3: F16 (fused, biases and bias-free) and a mixed Q4_K + Q6_K build (fused, 256-aligned dims).
- gemma: F16 (softcap and no-softcap variants) and Q4_K (256-aligned dims).
- llama: Q4_0 (regression fixture; plus the pre-existing Q4_K/Q8_0/Q6_K suites in the GPU lane).
- qwen2: mixed Q4_K/Q6_K metadata/bias regression fixture (pre-existing test, unchanged).
