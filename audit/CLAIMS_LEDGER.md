# Claims Ledger

Every public claim about capability, correctness, or performance must appear here with a reproducible evidence pointer. A claim without evidence is either removed or labelled **UNVERIFIED** before a release.

**Status vocabulary:** `VERIFIED` (reproduced by QAQC on the recorded platform) · `PARTIAL` (true for a narrower scope than the wording implies) · `NOT YET` (planned, not implemented) · `UNVERIFIED` (asserted but not reproduced) · `REMOVED` (withdrawn).

**Rules**
- Scope must name model family, quantization, context, hardware, and software versions.
- Performance claims require the benchmark artifact and the exact command (`audit/evidence/<gate>/...`).
- `UNVERIFIED` claims must not appear in README/marketing; `PARTIAL` claims must state the limit inline.
- Update this file in the same PR as the claim change.

| # | Claim | Location | Evidence | Status | Scope / limit |
|---|---|---|---|---|---|
| 1 | Builds and installs from the sdist | README, audit | `audit/VERIFICATION_2026-11-01.md` §2 | **VERIFIED** | gfx1150 host, ROCm 7.0.0, Python 3.14, after `setup.py` pybind11 fix |
| 2 | CPU-only suite passes | README, CI | `tests/test_cpu_only.py` (12/12, normal + `-O`) | **VERIFIED** | GitHub `ubuntu-latest` and local CPU |
| 3 | GPU kernel/layer/E2E suites pass | README, audit | `audit/VERIFICATION_2026-11-01.md` §3.2 | **VERIFIED** | gfx1150, synthetic models |
| 4 | `Q4_0`/`Q4_K`/`Q8_0` kernels match reference | README | `tests/test_gguf_and_q4.py`, `tests/test_phase5_scale.py` | **VERIFIED** | synthetic data; tolerance as tested |
| 5 | `Q6_K` supported end-to-end | README | `tests/test_phase5_scale.py` + verification §3.2 | **PARTIAL** | CPU round-trip and synthetic GPU run; no real-GGUF Q6_K golden yet (7F-2) |
| 6 | Real `Q4_K_M` GGUF support | README | — | **PARTIAL** | all recipe tensor types are wired, but no real `Q4_K_M` fixture/logit golden has been run |
| 7 | GPT-2 byte-level `Ġ` tokenization | README | `tests/test_cpu_only.py` V-6, verification §4 | **PARTIAL** | plain text works; special-token encode and `add_bos_token` are open (7B) |
| 8 | Chat special tokens (`<\|im_start\|>`, etc.) | README (implied) | — | **NOT YET** | 7B-1 |
| 9 | `tokenizer.ggml.add_bos_token` respected | README (implied) | — | **NOT YET** | 7B-2; `generate()` currently hardcodes `add_bos=True` |
| 10 | Qwen2 support | README | — | **NOT YET** | metadata resolves; chat/BOS correctness open (7B/7C) |
| 11 | Phi-3 support | README | — | **NOT YET** | fused `attn_qkv` missing (7C-2) |
| 12 | Gemma support | README | — | **NOT YET** | embedding scale, soft-cap, `key_length` missing (7C-3) |
| 13 | 983 tok/s / 4.4× E2E speedup | IMPLEMENTATION_PLAN | — | **UNVERIFIED** | synthetic 2-layer, owner-reported; must be re-recorded under 7F-3 or removed |
| 14 | Bounded RAM for 70B models | README, IMPLEMENTATION_PLAN | — | **UNVERIFIED** | `MADV_DONTNEED` does not bound page cache; policy/residency pending (7D) |
| 15 | One synchronization per token | README (implied) | — | **NOT YET** | current path still relies on NULL-stream waits (7E) |
| 16 | PEP 639 license metadata | packaging | — | **NOT YET** | `license = { file = ... }` still deprecated (7G) |
| 17 | Collision-safe package namespace | packaging | — | **NOT YET** | six top-level modules (7G) |

**Last updated:** 2026-11-01 (baseline verification pass). Update during 7.0 and at every gate.
