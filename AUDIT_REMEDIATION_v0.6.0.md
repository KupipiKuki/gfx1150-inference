# Audit & Remediation Status — gfx1150-inference (post-v0.5.0 audit)

> **Scope:** Full-repository audit of `main` @ `af5fff4` (v0.5.0): 6 Python modules, 7 HIP kernels, 1 bindings file, 5 test suites, build/packaging, docs, git history.
> **Method:** Static review of all sources + executable verification of every non-GPU component (no AMD GPU in this environment; kernel execution remains owner-verified on gfx1150 hardware).
> **Status legend:** OPEN = not yet fixed; all items below are OPEN and queued for v0.6.0 unless noted.

---

## 1. Verification performed (all pass)

| # | Check | Result |
|---|---|---|
| V-1 | `python3 -m py_compile` on all src modules, tests, `setup.py` | ✅ |
| V-2 | CPU imports: `gguf_parser`, `weight_loader`, `tokenizer` | ✅ |
| V-3 | GPU-dependent modules raise actionable ImportError (build instructions) when `matmul_module` absent | ✅ |
| V-4 | GGUF v3 writer→parser round trip (metadata, tensor offsets, aligned data section — exact payload match at `abs_offset`) | ✅ |
| V-5 | Q4_0 / Q8_0 / Q4_K CPU quantize→dequantize round trips: max err 0.028 / 0.0015 / 0.021 (within 4/8-bit grid bounds) | ✅ |
| V-6 | Tokenizer: BPE highest-score merge, decode round trip, SentencePiece `▁` normalization, `<0xXX>` byte fallback | ✅ |
| V-7 | Sampler: greedy, `top_k=1`≡greedy, seeded reproducibility, repetition penalty diverts argmax, flat-logits degenerate case | ✅ |
| V-8 | Repo hygiene: no CI (`.github/` absent), no TODO/FIXME, no secrets in tree/history, clean `main`, `.gitignore` covers `__pycache__`/`build`/models | ✅ |

## 2. Security findings

| ID | Severity | Finding | Location | Status |
|---|---|---|---|---|
| S-1 | **Medium** | No validation of tensor extents vs. actual file size. `WeightStreamer` mmaps the whole file; a truncated GGUF (interrupted download) raises **SIGBUS** on first page touch during streaming — process kill, not a catchable `ValueError`. Header/EOF checks cover only the metadata section. **Fix:** at parse time assert `file_size >= data_offset + max(rel_offset + n_bytes)` over all tensors. | `src/gguf_parser.py:_parse`, `src/weight_loader.py:43` | OPEN |
| S-2 | Low | Untrusted metadata drives sizes: `general.alignment`, `tensor_count`, `kv_count`, and ARRAY counts are uncapped — a hostile GGUF can force large allocation/time loops before EOF checks trip. **Fix:** cap counts against remaining buffer bytes before looping. | `src/gguf_parser.py:155-189` | OPEN |
| S-3 | Low | `--kv-mmap-dir` uses predictable filenames (`kv_cache_k.mmap`/`kv_cache_v.mmap`) created `w+` and **deleted on `close()`** — pointing the flag at a directory with same-named files silently destroys them. **Fix:** only remove files the manager created, or use unique names. | `src/kv_cache.py:66-72,191-196` | OPEN |
| S-4 | Info | No secrets/credentials/keys in tree or history (scanned). Model file is mmap'd read-only (`ACCESS_READ`). CLI is local-path only; no network surface. Strict UTF-8 decode of metadata fails closed. | — | ✅ verified |

## 3. Performance findings & optimization recommendations

| ID | Severity | Finding | Location | Status |
|---|---|---|---|---|
| P-1 | **High** | Every GPU op is a blocking H2D→kernel→D2H round trip on the default stream (implicit sync per op). A decode step serializes ~20 such ops per layer. **Fix:** dedicated HIP stream, queue layer ops back-to-back, `hipMemcpyAsync` layer L+1 weights from mmap pages overlapping layer L compute, single D2H per step. Biggest available throughput win. | `src/kernels/*.hip` launchers (e.g. `matmul.hip:233,272`) | OPEN |
| P-2 | High | FP16/FP32 weight path does `np.ascontiguousarray(w_view.reshape(N,K).T)` **on host, per tensor, per layer, per step** — materializes full transposed weights in RAM, defeating the bounded-memory SSD-streaming design for F16 models. Quantized paths avoid this. **Fix:** fused FP16 kernel reading `W (N,K)` in native layout (same shape as the wave kernels' B). | `src/layer.py:106,109,119,121` | OPEN |
| P-3 | Medium | Quantized wave GEMM kernels are GEMV-shaped (one wavefront per output column, whole K loop per output; grid `(N/8, M)`). No tiled/split-K quantized GEMM for prefill. **Fix:** add quantized tiled BM×BN kernel with split-K reduction for prefill. | `src/kernels/dequantize.hip` (`matmul_q4_0/q8_0/q4_k_wave_kernel`) | OPEN |
| P-4 | Medium | Tokenizer BPE merge rescans all adjacent pairs per iteration — O(L³) char work on long prompts. **Fix:** heap-based priority-queue merge, O(L log L). | `src/tokenizer.py:100-113` | OPEN |
| P-5 | Medium | Embedding lookup is a Python loop per token; quantized embd rows dequantized on CPU per token. **Fix:** vectorized `table[ids]` gather for F16/F32; batch CPU dequant for quantized embd. | `src/tokenizer.py:embed_tokens` | OPEN |
| P-6 | Low | `int` overflow exposure: `total_qh = q_len * num_heads` at three sites; overflows past 2³¹ at extreme prefill batch. Unreachable today (single-stream + chunking) but cheap defense-in-depth. **Fix:** cast to `size_t`. | `src/kernels/attention.hip:48,253,343` | OPEN |
| P-7 | Low | RoPE recomputes `powf/cosf/sinf` per pair per call. **Fix:** cache inv-freq table in shared/constant memory. | `src/kernels/rope.hip:36-38` | OPEN |
| P-8 | Low | `get_layer_byte_span` takes the byte hull `[min,max]`; interleaved non-layer tensors would be prefetched/evicted by `madvise`. **Fix:** sum per-tensor spans. | `src/gguf_parser.py:208-213` | OPEN |
| P-9 | Low | Grow-only singleton workspaces never shrink — one huge prefill pins max-sized device buffers permanently (acceptable under documented single-engine scope). `DeviceKVCachePool.init` silently keeps the larger pool when re-inited smaller. | `src/kernels/*.hip`, `attention.hip:init` | OPEN (document) |
| P-10 | Info | Naive `matmul_kernel` is dead code (only `_tiled`/`_reg_tiled` launched). Residual adds could be fused into the following RMSNorm to save a pass (ties into P-1). | `src/kernels/matmul.hip`, `src/layer.py:186,219` | OPEN |

## 4. Design / packaging / reliability findings

| ID | Severity | Finding | Location | Status |
|---|---|---|---|---|
| D-1 | **Medium** | Isolated PEP 517 builds fail: `pyproject.toml` build requires lack `cmake`, and the CMake hook needs the host ROCm toolchain (`amdclang++`, HIP headers, `CMAKE_PREFIX_PATH=/opt/rocm`) which an isolated env won't have. `pip install .` on a clean machine errors confusingly; only `--no-build-isolation` works. `setup.py` gives no targeted error when ROCm is absent. **Fix:** add `cmake>=3.21` to build requires; pre-check `ROCM_ROOT`/`/opt/rocm` in `setup.py` with a clear message. | `pyproject.toml:2`, `setup.py:41-54`, `CMakeLists.txt` | OPEN |
| D-2 | Low | `CMakeLists.txt` links `roc::hipblas`/`roc::rocblas` but no kernel calls them (dead link dep, build fragility). `BUILD_RPATH` hardcodes a `core-10.1` path. **Fix:** drop the BLAS links or wire them in; derive RPATH from `${ROCM_ROOT}` only. | `CMakeLists.txt:23-27,62-65` | OPEN |
| D-3 | Low | `GGUFParser.__init__` releases the caller's `memoryview` (`self._buf.release()`) — surprising side effect for any caller passing a `memoryview` they still hold. **Fix:** don't release a buffer the parser doesn't own. | `src/gguf_parser.py:124` | OPEN |
| D-4 | Low | `KVCacheManager.__del__` swallows all exceptions — masks genuine driver/double-free errors at shutdown. **Fix:** `warnings.warn` instead of silent `pass`. | `src/kv_cache.py:200-203` | OPEN |
| D-5 | Low | Sampler top-p re-normalizes `sorted_probs` without a zero-sum guard after filtering (safe today because the argmax element always survives, but one line of defense). | `src/inference.py` (`sample_next_token`) | OPEN |
| D-6 | Info | All runtime test suites are hardware-gated; CPU-verifiable logic (parser/tokenizer/sampler/packaging — V-2/V-4..V-7) has no automated home and there is no CI at all. **Fix:** add `tests/test_cpu_only.py` + CPU-only GH Actions smoke job; self-hosted gfx1150 runner for kernel suites. | `tests/`, repo root | OPEN |

## 5. Prioritized v0.6.0 backlog

1. **S-1** — file-size vs. tensor-extent validation at parse time (kills SIGBUS on truncated models)
2. **P-1** — async stream + batched H2D/D2H, single sync per decode step
3. **S-3** — stop deleting files the KV mmap dir didn't create
4. **D-1** — `cmake` in build requires + ROCm pre-check in `setup.py`
5. **P-2** — fused FP16 native-layout GEMM (kill per-layer host transpose)
6. **P-3** — quantized tiled/split-K GEMM for prefill
7. **S-2, P-4, P-5, P-6, P-8, D-2..D-5** — metadata caps, heap BPE, vectorized embed gather, `size_t` casts, per-tensor spans, BLAS link cleanup, mmap-ownership, `__del__` warning, sampler guard
8. **D-6** — CPU-only CI smoke job + `tests/test_cpu_only.py`

## 6. Verdict

Well-architected, internally consistent, numerically sound (FP32 accumulation throughout; quantization errors within published bounds), and fail-closed on malformed headers. No correctness bugs in the compute path. The headline risks are the **SIGBUS on truncated model files (S-1)** and **per-op blocking copies + per-layer host transposes (P-1/P-2)** as the main throughput limiters. All findings are hardening/performance items queued above for v0.6.0.
