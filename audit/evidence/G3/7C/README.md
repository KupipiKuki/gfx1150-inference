# G3 / 7C — Model-family support evidence bundle

This directory is the coder/QAQC bundle for Phase 7C (Gate G3). The primary audit
report and signoff will be added by the auditor; do not pre-fill an audit verdict here.

## Required files

| File | Contents |
|---|---|
| `env.txt` | OS/kernel, ROCm/HIP, `rocminfo` GPU line, Python, NumPy, pybind11, CMake, `git rev-parse HEAD` |
| `parent-sha.txt` | `8426ec6` (the G2-signed base) or the brief base if it differs |
| `candidate-sha.txt` | the frozen work commit under review |
| `diffstat.txt` | file delta; the allowed/forbidden sets |
| `red.log` | the new Phi-3/Gemma tests failing on the parent (missing tensor/`KeyError`, wrong logits) |
| `green.log` | the same tests passing on the candidate |
| `header-dumps/` | text dumps of real Phi-3 and Gemma GGUF metadata + tensor names/shapes/types, with source URL/revision and hash |
| `model-spec.log` | `ModelSpec` resolution and fail-fast probes (unknown arch, missing required/optional, shape mismatch) |
| `phi3.log` | fused QKV + fused gate/up + bias tests; fused-vs-separate equivalence |
| `gemma.log` | embedding scale, GeGLU, NeoX, key/value dims, softcap, tied output; logits vs the independent reference |
| `llama-regression.log` | token IDs and logits unchanged on the fixed prompt/seed |
| `compat-matrix.md` | arch × quant × context, with **synthetic fixture** vs **real GGUF** and status; qwen2 stays NOT YET |
| `cpu-lane.log` | `pytest -m "not gpu" -q` |
| `gpu-lane.log` | `pytest -m gpu -q` |
| `cpu-only.log` | `tests/test_cpu_only.py` and `-O` |
| `claims.log` | `scripts/qa/check_claims.py` |
| `qaqc-probes/` | independent QAQC probes/logs (real names, fused/separate, biases, Gemma math, llama regression) |
| `notes.md` | what changed, design decisions, limitations, and the evidence provenance |

## Rules

- **Real tensor names.** Do not invent Phi-3/Gemma tensor names. The header dumps are
  authoritative; record the source and hash. Keep dumps text-only (no model weights).
- **Independent reference.** The expected logits must come from an independent NumPy
  reference or the pinned llama.cpp binary, never from the code under test. State the
  tolerance and the max abs diff.
- **Synthetic vs real.** A synthetic-fixture logits match is not a real-model support
  claim. Real-GGUF Phi-3/Gemma evidence belongs to 7F-2. The matrix and README must say
  which is which.
- **Red before green.** The new family tests must fail on the parent `8426ec6` for the
  expected reason and pass on the candidate.
- **Fail-fast.** Unknown architecture, missing required tensors, missing optional
  tensors, and shape mismatches each have a distinct, actionable error; missing required
  lists all missing names.
- **No scope creep.** 7C only. Do not include 7D/7E work, tokenizer/parser rewrites, or
  performance claims.
- **Claims.** Update only `audit/CLAIMS_LEDGER.md` rows 10/11/12. Qwen2 stays `NOT YET`;
  Phi-3/Gemma use the exact evidence type (synthetic fixture, pending real-GGUF 7F-2).
- **Fallback.** If a family cannot be evidenced, keep it unsupported, implement fail-fast,
  document the limitation, and stop for the auditor. Do not weaken tests or overclaim.

## Gate exit (G3)

- ModelSpec + Phi-3/Gemma synthetic logits pass against the independent reference.
- Llama behavior unchanged.
- Matrix/README/claims are honest.
- Unsupported families/features fail fast.
- CPU/GPU/claims lanes green; evidence complete.
