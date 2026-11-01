# Claims Ledger

Every public claim about capability, correctness, or performance must appear here with a reproducible evidence pointer. A claim without evidence is either removed or labelled **UNVERIFIED** before a release.

**Status vocabulary:** `VERIFIED` (reproduced by QAQC on the recorded platform) · `PARTIAL` (true for a narrower scope than the wording implies) · `NOT YET` (planned, not implemented) · `UNVERIFIED` (asserted but not reproduced) · `REMOVED` (withdrawn).

**Rules**
- Scope must name model family, quantization, context, hardware, and software versions.
- Performance claims require the benchmark artifact and the exact command (`audit/evidence/<gate>/...`).
- `UNVERIFIED` claims must not appear in README/marketing; `NOT YET` claims must be inline-qualified where mentioned; `PARTIAL` claims must state the limit inline.
- Update this file in the same PR as the claim change.
- Enforcement: `scripts/qa/check_claims.py` (added in 7A-6). Default CI mode is baseline-aware; `--strict` is release-blocking at G6 with an empty `audit/claims_baseline.txt`.

| ID | Claim | Status | Public match (literal) | Qualified in place? | Evidence | Scope / limit |
|---|---|---|---|---|---|---|
| 1 | Builds and installs from the sdist | **VERIFIED** | `sdist` | n/a | `audit/VERIFICATION_2026-11-01.md` §2 | gfx1150 host, ROCm 7.0.0, Python 3.14, after `setup.py` pybind11 fix |
| 2 | CPU-only suite passes (12 tests) | **VERIFIED** | `test_cpu_only.py` | n/a | `tests/test_cpu_only.py` (normal + `-O`) | GitHub `ubuntu-latest` and local CPU |
| 3 | GPU kernel/layer/E2E suites pass | **VERIFIED** | `GPU` | n/a | `audit/VERIFICATION_2026-11-01.md` §3.2 | gfx1150, synthetic models |
| 4 | `Q4_0`/`Q4_K`/`Q8_0` kernels match reference | **VERIFIED** | `Q4_0`, `Q4_K`, `Q8_0` | n/a | `tests/test_gguf_and_q4.py`, `tests/test_phase5_scale.py` | synthetic data; tolerance as tested |
| 5 | `Q6_K` tensor support (CPU + kernels) | **VERIFIED** | `Q6_K` | n/a | `tests/test_phase5_scale.py`, verification §3.2 | synthetic; real-GGUF Q6_K golden pending (7F-2) |
| 6 | Real `Q4_K_M` GGUF end-to-end | **PARTIAL** | `Q4_K_M` | yes — "tensor types; real-GGUF validation pending" | 7F-2 | all recipe tensor types wired; no real fixture/logit golden yet |
| 7 | GPT-2 byte-level `Ġ` plain-text tokenization | **VERIFIED** | `GPT-2` | n/a | `tests/test_cpu_only.py` V-6, verification §4 | plain text, multibyte, double spaces |
| 8 | Chat special tokens (`<\|im_start\|>`, etc.) | **NOT YET** | `<\|im_start\|>` | no | 7B-1 | not implemented; encode emits byte tokens |
| 9 | `tokenizer.ggml.add_bos_token` respected | **NOT YET** | `add_bos_token` | no | 7B-2 | `generate()` currently hardcodes `add_bos=True` |
| 10 | Qwen2 support | **NOT YET** | `qwen2` | yes — "metadata resolves; model support not yet verified" | 7B/7C | metadata only; chat/BOS correctness open |
| 11 | Phi-3 support | **NOT YET** | `phi3` | yes — "metadata resolves; model support not yet verified" | 7C-2 | fused `attn_qkv` missing |
| 12 | Gemma support | **NOT YET** | `gemma` | yes — "metadata resolves; model support not yet verified" | 7C-3 | embedding scale, soft-cap, `key_length` missing |
| 13 | 983 tok/s / 4.4× E2E speedup | **UNVERIFIED** | `983` | yes — "synthetic E2E, owner-verified" | 7F-3 | synthetic 2-layer; must be re-recorded or removed by G6 |
| 14 | Bounded RAM for 70B models | **UNVERIFIED** | `bounded memory` | no | 7D-1/7D-2 | `MADV_DONTNEED` does not bound page cache; policy pending |
| 15 | One synchronization per token | **NOT YET** | `one synchronization per token` | no | 7E | current path relies on NULL-stream waits |
| 16 | PEP 639 license metadata | **NOT YET** | `PEP 639` | no | 7G | `license = { file = ... }` still deprecated |
| 17 | Collision-safe package namespace | **NOT YET** | `top-level module` | no | 7G | six top-level modules |

**Last updated:** 2026-11-01 (baseline verification pass). Update during 7.0 and at every gate.

## Baseline policy

`audit/claims_baseline.txt` may list known violations during 7A–7E, one per line:

```
<claim-id> <path> <literal>
```

Every entry targets `G6`. It is a ratchet, not a waiver: default CI tolerates only exact entries, and `--strict` ignores the file entirely. At G6 the file must be empty and `check_claims.py --strict` must pass.

The `phi3`/`gemma` bullet was qualified inline on 2026-11-01 (metadata-only support), so it should not need a baseline entry. The `bounded memory` claim (ID 14) remains the known baseline item until 7D corrects the mechanism and wording.
