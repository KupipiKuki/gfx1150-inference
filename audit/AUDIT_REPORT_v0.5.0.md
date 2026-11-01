# Overall Package Audit — gfx1150-inference v0.5.0 (post-Phase-5 merge)

> **Auditor scope:** Full-repository review across all five phases (17 commits, 35 files, ~5,300 LOC: 6 Python modules, 7 HIP kernels, 1 bindings file, 5 test suites, build/packaging, docs).
> **Environment:** Static audit + executable verification of all non-GPU components. HIP kernel execution, GPU build, and hardware benchmarks were previously owner-verified on target gfx1150 hardware (all phases passed).

---

## 1. Executive Summary

**Verdict: APPROVED for v0.5.0.** The package is internally consistent, architected soundly, and validated across five review cycles (PRs #1, #3–#6) with every QA/QC finding resolved and verified. One **medium** packaging caveat and a small set of low-severity hardening items remain — none block the current release; all are listed for v0.6.0.

| Category | Finding count |
|---|---|
| Verified by execution (this audit) | 8 checks — all pass |
| Medium severity | 1 (A-1) |
| Low severity | 4 (A-2 – A-5) |
| Informational | 3 (A-6 – A-8) |

---

## 2. Verification Performed (this audit, executable)

| # | Check | Result |
|---|---|---|
| V-1 | `python3 -m py_compile` on all 6 src modules, 5 test files, `setup.py` | ✅ |
| V-2 | Non-GPU module imports (`gguf_parser`, `weight_loader`, `tokenizer`) | ✅ |
| V-3 | GPU-dependent modules fail with **actionable ImportError** (build instructions) when extension absent — G-1 remediation confirmed behaviorally | ✅ |
| V-4 | GGUF v3 writer→parser round trip: metadata, tensor dims/types, byte offsets, aligned data section — exact payload match at `abs_offset` | ✅ |
| V-5 | Q4_0 / Q8_0 / Q4_K CPU quantize→dequantize round trips: max err 0.23 / 0.01 / 0.16 — consistent with published 4-bit/8-bit grid quantization error bounds | ✅ |
| V-6 | Tokenizer: BPE highest-score merge (`hello world` → `<s> ▁hello ▁world`), decode round trip, SentencePiece `▁` normalization, `<0xXX>` byte fallback for non-ASCII (`Ω` → `<0xCE><0xA9>`) | ✅ |
| V-7 | Sampler: greedy/temperature=0, top_k=1≡greedy, seeded reproducibility, repetition penalty diverts argmax, degenerate flat-logits handling | ✅ |
| V-8 | Packaging metadata: `pyproject.toml` well-formed, all 6 declared `py-modules` exist on disk, script entry `inference:main` exists | ✅ |

---

## 3. Findings

### A-1 (MEDIUM): Isolated PEP 517 builds (`pip install .`) without `--no-build-isolation` will fail on clean machines
`[build-system] requires = ["setuptools>=64", "wheel", "pybind11>=2.11"]` — but the CMake hook also needs the **host ROCm toolchain** (`amdclang++`, HIP headers, `CMAKE_PREFIX_PATH=/opt/rocm`) plus `cmake` on PATH. In an isolated build env: `cmake` may be missing, and even if present, ROCm is a system install not captured in the isolated env — the CMake configure would fail on `find_package(hipblas)`.
**Impact:** The README documents `--no-build-isolation` (correct), so the documented path works. But `pip install gfx1150-inference` from a wheel/sdist on a fresh machine follows isolated build and would fail with a confusing configure error.
**Recommendation (v0.6.0):** add `cmake>=3.21` to `[build-system] requires`, and make `setup.py` emit a targeted error message if ROCm is not discoverable (`ROCM_ROOT` unset and `/opt/rocm` absent) *before* invoking CMake. Alternatively, publish a wheel-building CI job that documents the toolchain prerequisites.

### A-2 (LOW): `int` overflow exposure in attention kernel indexing
`attention.hip` computes `total_qh = q_len * num_heads` as `int` (three sites). With `q_len=4096`, `num_heads=128` (large-batch prefill), the product exceeds `INT_MAX` at extreme batch sizes. Current guardrails (single-stream, `max_seq_len` bounded, `layer.py` chunking) keep this unreachable today. **Recommendation:** cast to `size_t` at the three `total_qh` sites for defense-in-depth.

### A-3 (LOW): `get_layer_byte_span` assumes contiguous per-layer tensor layout
`gguf_parser.py:210-213` computes a layer's byte span as `[min(abs_offset), max(abs_offset + n_bytes))`. If a GGUF file interleaves layer tensors with non-layer tensors (rare but legal), `madvise` prefetch/evict would advise on foreign pages. **Recommendation:** sum per-tensor spans rather than taking a hull, or document the layout assumption.

### A-4 (LOW): `KVCacheManager.__del__` may mask genuine errors
`__del__` calls `close()` in a bare `try/except Exception: pass`. At interpreter shutdown, `matmul_module` may already be finalized, making `kv_cache_free()` throw — silently swallowed (correct outcome). But genuine double-free or driver errors are also swallowed. **Recommendation:** log at `warnings.warn` level instead of fully silent.

### A-5 (LOW): `weight_loader` file handle not fd-guarded against partial mmap
`WeightStreamer` mmaps the whole file (`mmap(fileno, 0)`) — if the GGUF is truncated (download interrupted), the first page-touch during streaming raises `SIGBUS` rather than a Python exception. The parser validates header/tensor offsets against `len(self._buf)`, so truncated files are caught **if** tensors are small — but `madvise(WILLNEED)` on a truncated tail region advises beyond EOF silently. **Recommendation:** validate `file size >= data_offset + max(rel_offset + n_bytes)` at parser time (cheap, once), converting the failure to a `ValueError` up front.

### A-6 (INFO): Contributor history is healthy — 8 owner / 6 coder (Argon-side) / 3 review-agent commits; no force-push damage on `main`; branch lifecycle (`Argon_Phase_2..5`) cleaned up post-merge.

### A-7 (INFO): **No CI pipeline exists.** All five test suites are hardware-gated (need gfx1150 + ROCm), so standard GH Actions runners cannot run them. Options for v0.6.0: (a) CPU-only smoke job running V-1/V-2/V-4–V-8 style checks (parser, tokenizer, sampler, packaging metadata) on push; (b) self-hosted runner on the gfx1150 machine. Recommend (a) now, (b) when convenient.

### A-8 (INFO): `src/__pycache__` was committed at some point (currently untracked debris from sandbox runs — `.pyc` for `gguf_parser`, `weight_loader`). Confirm `.gitignore` covers `__pycache__/` (it does) and it is not in the tree.

---

## 4. Cross-Phase Consistency Matrix

| Property | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Consistent |
|---|---|---|---|---|---|---|
| `HIP_CHECK` error macro | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ identical pattern all kernels |
| FP32 accumulation in FP16 paths | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wave32 shuffle reduction | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| `__launch_bounds__(BLOCK_THREADS)` w/ derived constant | ✅ | ✅ | ✅ | ✅ (O-5 fix) | ✅ | ✅ |
| Workspace singleton pattern | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (documented single-threaded) |
| Input validation at bindings | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GIL release around HIP calls | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `madvise` lifecycle symmetric (WILLNEED/DONTNEED) | — | ✅ | ✅ | ✅ | ✅ | ✅ |

No architectural drift between phases — the codebase reads as a single design executed incrementally.

---

## 5. Test Coverage Assessment

| Suite | Covers | Hardware-gated |
|---|---|---|
| `test_matmul.py` | FP16 matmul accuracy + edge cases + throughput | Yes |
| `test_gguf_and_q4.py` | GGUF parsing, madvise streaming, Q4_0 kernels | Yes (kernels) |
| `test_layer.py` | RMSNorm/RoPE/GQA/SwiGLU vs CPU refs, e2e layer | Yes |
| `test_full_model.py` | End-to-end generation, memory cap | Yes |
| `test_phase5_scale.py` | Q8_0/Q4_K accuracy, chunked prefill determinism, KV-mode equivalence, singleton guard, rollback | Yes |

**Gap:** all runtime suites are hardware-gated (see A-7). The pure-CPU logic verified in this audit (V-4–V-7) has no automated home. A `tests/test_cpu_only.py` would lock in parser/tokenizer/sampler behavior and run anywhere.

---

## 6. Documentation & Repository Hygiene

- README, IMPLEMENTATION_PLAN, LESSONS_LEARNED, QAQC report, handoff, remediation plan — current, cross-referenced, no stale `file://` links remaining (verified in Phase 2 remediation).
- No secrets/credentials anywhere in `src/`, tests, or history (scanned).
- No TODO/FIXME/HACK markers in any source file.
- `.gitignore` covers build artifacts, `__pycache__/`, `*.gguf` model files.

---

## 7. Recommended v0.6.0 Backlog (priority order)

1. **A-1** — isolated-build error surfacing (`cmake` in build requires, ROCm pre-check in `setup.py`)
2. **A-7** — CPU-only CI smoke job (`tests/test_cpu_only.py` + GH Actions on push)
3. **A-5** — truncation guard in `GGUFParser` (validate file size vs. tensor extents)
4. **A-2** — `size_t` casts at attention `total_qh` sites
5. **A-4** — `__del__` warning instead of silent swallow
6. **A-3** — per-tensor span summing in `get_layer_byte_span`
7. Empirical hardware coverage for the mid-allocation rollback path (noted in PR #6; C++ partial-free verified by inspection only)

---

*Audit performed on `main` @ `0b1b348` (Phase 5 merge). All executable checks reproducible from this report's commands.*
