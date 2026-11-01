# Second-Pass Audit & Remediation Package — gfx1150-inference v0.6.0 review

> **Scope:** Review of the coder's remediation commit `64b8a8d` ("Added revisions per the project QAQC and audit report findings") on branch `vibe/audit-remediation-220201`, audited against **both** prior audits: `AUDIT_REMEDIATION_v0.6.0.md` (S-*/P-*/D-*) and the Deepseek report of 2026-10-31 (B-*/C-*/S-*/R-*/T-*/L-*).
> **Method:** Full diff review of all 30 changed files + executable verification on a non-GPU host (Python 3.12, NumPy 2.5): `tests/test_cpu_only.py` (10/10 pass, also under `-O`), plus independent regression probes for truncation, alignment, BPE equivalence, embed bounds, and span splitting. GPU kernel execution remains owner-verified on gfx1150 hardware; kernel-side claims here are by inspection and marked as such.
> **Status legend:** ✅ fixed & verified · ◐ partially fixed · ❌ open

---

## 1. Verification performed on the coder's commit

| # | Check | Result |
|---|---|---|
| R-1 | `py_compile` all src/tests/setup.py | ✅ |
| R-2 | `python3 tests/test_cpu_only.py` — 10 tests | ✅ all pass |
| R-3 | `python3 -O tests/test_cpu_only.py` (assert-free runtime) | ✅ all pass |
| R-4 | Truncated GGUF (cut 10 B / half / 1 B) → `ValueError` at parse time, no SIGBUS path | ✅ reproduced |
| R-5 | `general.alignment` = 0 / 30 / 131072 / −4 → `ValueError` | ✅ reproduced |
| R-6 | Heap-BPE tokenizer round trip (`hello world`, `Ω` byte fallback, 1002-token prompt) | ✅ reproduced |
| R-7 | `embed_tokens` OOB token id → `ValueError` | ✅ reproduced |
| R-8 | `get_layer_byte_spans` splits around interleaved foreign tensor (verified byte-exact) | ✅ reproduced |
| R-9 | sdist contents re-inspected | ❌ **still 0** CMakeLists/`.hip`/bindings.cpp entries |
| R-10 | Duplicate tensor names, Ġ-vocab tokenizer, sampler penalty=0/−1, `time.time`, streams in `forward_layer_cached` | ❌ still open (see below) |

---

## 2. My audit (S/P/D) — resolution status

| ID | Status | Evidence |
|---|---|---|
| S-1 truncation/SIGBUS | ✅ | `gguf_parser.py` validates `abs_offset + n_bytes <= len(buf)` in `_parse`; R-4 reproduced. `weight_loader.py.__init__` now closes mmap+fd on parser failure |
| S-2 metadata caps | ✅ | kv_count×13 / tensor_count×24 / ARRAY count vs remaining bytes, `n_dims ≤ 8`, alignment power-of-2 in [1, 65536]; R-5 reproduced |
| S-3 KV mmap filenames | ◐ | Unique `pid_id` names + `O_CREAT\|O_EXCL\|O_RDWR, 0o600` pre-create + unlink only created paths — good; **but no `O_NOFOLLOW`**, so a pre-planted symlink at the predictable path still wins the race between `os.open` and `np.memmap` (TOCTOU), and `np.memmap("w+")` follows symlinks. Add `O_NOFOLLOW` and open the memmap via the already-open fd (`np.memmap` doesn't take an fd — use `mmap.mmap(fd, ...)` + `np.frombuffer`) |
| S-4 secrets/surface | ✅ | unchanged, still clean |
| P-1 blocking round trips | ◐ | New C++-owned `forward_layer_cached` (`attention.hip:583`, `bindings.cpp:452`) does 1 H2D + device-resident intermediates + D2D KV writes + 1 D2H per layer for the GPU-KV path, plus fused `rmsnorm_residual`/`residual_add`. **But** it uses the default stream with blocking `hipMemcpy` — no `hipStream`/`hipMemcpyAsync`/`hipEvent` anywhere (grep-confirmed), so layer-to-layer overlap and copy/compute overlap are still absent; weights are still copied H2D per layer per step (from mmap pages). The non-GPU-KV fallback path in `layer.py` still makes 14 per-op blocking calls. Claimed 4.4× is plausible for the sync-count reduction but is hardware-verified only by the coder |
| P-2 host transpose | ✅ | `matmul_nt` + `matmul_nt_kernel_{reg_,}tiled` added; `layer.py` passes `(N,K)` views directly; F32 converts without transpose |
| P-3 quantized prefill tiling | ✅ (by inspection) | `PREFILL_TILE_M=4` kernels for Q4_0/Q8_0/Q4_K added, dispatched at M≥4; coder reports bit-identical vs wave kernels in `test_phase5_scale.py` |
| P-4 heap BPE | ✅ | R-6 reproduced; doubly-linked list + versioned heap entries preserve leftmost tie-break |
| P-5 vectorized embed | ✅ | R-7 reproduced; gather + batched dequant + OOB validation |
| P-6 size_t casts | ✅ | all 3 `total_qh`/`qh_idx` sites in `attention.hip` are `size_t` |
| P-7 RoPE freq table | ✅ | host-precomputed `inv_freq` table H2D-cached per (head_dim, base); no device `powf` |
| P-8 per-tensor spans | ✅ | R-8 reproduced byte-exact |
| P-9 workspace policy | ✅ | documented |
| P-10 dead kernel | ✅ | naive `matmul_kernel` removed |
| D-1 isolated build | ◐ | `cmake>=3.21` added to build requires; `setup.py` pre-checks cmake on PATH and ROCm at `ROCM_ROOT` with actionable `RuntimeError`. **But B-1 (below) means an sdist install still fails** — the pre-check doesn't fix distribution |
| D-2 BLAS links / RPATH | ✅ | hipblas/rocblas `find_package`+links removed; RPATH is `${ROCM_ROOT}/lib` |
| D-3 memoryview release | ✅ | private `memoryview(buf).cast("B")` wrapper released in `finally`; caller's view untouched (covered by `test_v4`) |
| D-4 `__del__` warning | ✅ | `RuntimeWarning` guarded against teardown failure (visible in R-2 output) |
| D-5 top-p guard | ✅ | zero/non-finite post-filter sum falls back to argmax |
| D-6 CPU CI | ✅ | `tests/test_cpu_only.py` (self-contained, 10 tests) + `.github/workflows/ci-cpu.yml` on push/PR, standard and `-O` modes |

---

## 3. Deepseek audit (B/C/S/R/T/L) — resolution status

| ID | Status | Evidence / what remains |
|---|---|---|
| **B-1 sdist cannot build (Blocker)** | ❌ **OPEN — still ship-blocking** | R-9: freshly built sdist contains **0** `CMakeLists.txt` / `*.hip` / `bindings.cpp` (no `MANIFEST.in`, no package-data). `pip install` from sdist/PyPI still fails. Fix: add `MANIFEST.in` (`include CMakeLists.txt`, `recursive-include src/kernels *.h *.hip`, `recursive-include src/python_bindings *.cpp`) **and** an sdist-install CI job, or move to `scikit-build-core` |
| B-2 BLAS hard deps | ✅ | removed (same as D-2); `hip::host` link and `INSTALL_RPATH` not added — minor |
| B-3 setup.py quality | ◐ | ROCm preflight added ✅; still builds into in-tree `build/` (use `self.build_temp`), unbounded `-j`, `GFX1150_SKIP_CMAKE=1` still silently produces an extension-less wheel |
| B-4 metadata | ❌ | still `license = { file = "LICENSE" }` (PEP 639 deprecation), no urls/classifiers/`__version__` |
| B-5 top-level module names | ❌ | `tokenizer`, `layer`, `inference` still install as top-level modules — collision risk unchanged |
| **C-1 Q6_K unsupported (real Q4_K_M files crash)** | ❌ **OPEN** | `GGMLType.Q6_K` exists in the enum and `GGML_BLOCK_INFO` but `linear_project`/`_prepare_weight_for_device` still have no Q6_K path → `ValueError` on `attn_v`/`ffn_down`/`output` of standard Q4_K_M recipes. Also no Q2_K/Q3_K/Q5_K/Q5_0/Q4_1/Q8_1/Q5_1, and no fail-fast load-time compatibility matrix |
| **C-2 GPT-2/Ġ tokenizer corruption** | ❌ **OPEN — verified still broken** | R-10: Ġ-vocab `encode("Hello world")` → decodes to `"Helloworld"` (space dropped); unknown char without `<0xXX>` tokens → `[]` (silent drop). No `tokenizer.ggml.merges` support, no `token_type`/special-token trie. Needs real BPE (regex pre-tokenizer, merge ranks, Ġ↔space) + raise on unmappable bytes + golden vectors vs llama.cpp |
| **C-3 hardcoded `llama.*` keys** | ❌ **OPEN** | `inference.py:123` still `metadata["llama.block_count"]`; `LlamaLayerConfig` still `llama.*` literals; qwen2/phi3/gemma files still `KeyError`; QKV biases still ignored |
| C-4 RoPE scaling (linear/YaRN) | ❌ | not implemented; `llama.rope.scaling.*` still unread |
| C-5 sliding-window / per-layer KV heads | ❌ | not implemented |
| C-6 host transposes | ✅ | fixed via `matmul_nt` (P-2) |
| C-7 generation edge cases | ❌ | `max_new_tokens=0` still emits 1 token; no upfront `len(prompt)+max_new ≤ max_seq_len` check; `time.time()` still used for metrics (→ `perf_counter`); `decode_steps` off-by-one metric still present |
| C-8 sampler validation | ◐ | D-5 guard added ✅; but `repetition_penalty ≤ 0` / negative still unvalidated (R-10: penalty=−1 inverts argmax, penalty=0 → −0.0 ties), `top_p` out of range still silently accepted, NaN/Inf logits still fall back to argmax silently |
| C-9 quantizer fidelity / self-referential tests | ❌ | `quantize_q4_0_cpu` still `max_abs/7`; tests still round-trip against the repo's own encoder; no llama.cpp golden blocks |
| C-10 parse hygiene | ◐ | n_dims cap + truncation added ✅; **duplicate tensor names still silently overwrite** (R-10: 2 entries → dict size 1); unknown-but-valid GGML types still hit bare `KeyError` at `GGML_BLOCK_INFO[ggml_type]`; `n_elements == 0` still accepted |
| S-1 (Deepseek) parser validation | ✅ | same as my S-1/S-2; alignment=0 verified fixed (R-5). `KVCacheManager` still trusts `block_count`/`head_count` for allocation — no clamp vs available memory (DoS-from-header remains) |
| S-2 (Deepseek) bindings validation | ❌ | `check_fp16_contiguous` still checks only itemsize/flags/min-size: `int16` arrays still pass as FP16, quantized `B` buffers still unchecked for contiguity/dtype (strided view → OOB read), outputs still not checked `writeable` |
| S-3 (Deepseek) static-workspace data race | ❌ | no mutex anywhere (grep-confirmed); GIL still released around all HIP calls; `_active_gpu_instance` still a plain bool. Documented single-thread scope only |
| S-4 (Deepseek) KV file safety | ◐ | unique names + O_EXCL + 0o600 + created-only unlink ✅; missing `O_NOFOLLOW`, no crash cleanup (unlink-before-map), no disk-space check, dir sensitivity undocumented |
| S-5 (Deepseek) `sys.path` injection | ❌ | all 5 GPU modules still `sys.path.insert(0, _SRC_DIR/_BUILD_DIR)`; `build/matmul_module.py` shadowing still possible |
| D-1 (Deepseek) MADV_DONTNEED overstatement | ❌ | not addressed; README/docstrings still claim bounded RAM via DONTNEED on a MAP_SHARED mapping. Needs `posix_fadvise`/`MADV_PAGEOUT` note or doc correction |
| R-1 close() BufferError fd leak | ❌ | `WeightStreamer.close()` unchanged — still raises `BufferError` with live views and leaves fd open (verified in prior audit; code untouched). Fix: close file first / use try-finally |
| R-2 engine ctor leak | ❌ | `LlamaInferenceEngine.__init__` still has no try/except around `KVCacheManager(...)` — ctor failure after `WeightStreamer` leaks streamer until GC |
| P-2 (Deepseek) residency policy | ❌ | not implemented — streaming+eviction still unconditional default; no `PIN_ALL`/budget logic |
| P-3/P-4 (Deepseek) attention GQA re-reads, expf per lane | ❌ | not addressed (flash tiling, KV sharing via LDS) |
| T-1..T-7 tests/CI | ◐ | CPU suite + workflow added ✅ (T-2); GPU suites still ad-hoc scripts, no pytest markers, no golden fixtures, absolute thresholds, single-shot `time.time()` benchmarks, no parser fuzzing, no `--stats` telemetry |
| L-1..L-8 hygiene | ◐ | hull-span fixed; duplicate names / bare KeyError / `time.time()` / RPATH / CLI numeric validation still open; GPL-3 license note stands |

---

## 4. New issues introduced by the remediation commit (not in either prior audit)

| ID | Severity | Finding |
|---|---|---|
| N-1 | Medium | `inference.py:close()` now sets `self.token_embd_view`, `self.output_norm_w`, `self.output_weight_entry` — attributes that don't exist elsewhere in the class (the code uses `self._out_norm_w`); dead attribute writes, harmless but sloppy — remove or wire correctly |
| N-2 | Medium (by inspection) | `forward_layer_cached` reuses `ws.d_normed` as scratch for `attn_proj` and `d_x` as in-place rmsnorm output (step 7 writes `ws.d_x` while reading it) — correct only because the kernel reads then writes per row; fragile aliasing worth a comment/test on the hardware suite. Also all `project_on_device` calls H2D-copy weights synchronously on the default stream — no overlap |
| N-3 | Low | `get_layer_byte_spans` merges spans with `gap <= alignment` even when the gap contains padding of a *foreign* tensor smaller than alignment — `_has_foreign_between` covers actual foreign intervals, verified OK in R-8, but the gap≤alignment merge can still include foreign padding bytes; harmless for madvise |
| N-4 | Low | `matmul_nt` binding checks `B_nt.shape == (N,K)` only when `ndim()==2`; a 1-D buffer of `N*K` passes — fine since checks are size-based, but shape check is inconsistent with the docstring |
| N-5 | Info | coder's resolution log claims "4.4× throughput (224 → 983 tok/s)" and "bit-identical prefill kernels" — hardware numbers, not reproducible here; recommend CI-recorded benchmark gates before quoting in README |

---

## 5. Second remediation package — prioritized backlog

**P0 (ship-blocking for any distribution / real models):**
1. **B-1** — `MANIFEST.in` (or scikit-build-core) + sdist-install CI job. *Verified still broken (R-9).*
2. **C-1** — Q6_K fused kernel (block layout already in `GGML_BLOCK_INFO`) or fail-fast load-time matrix listing unsupported tensor types.
3. **C-2** — real GPT-2/BPE tokenizer: `tokenizer.ggml.merges` ranks, Ġ↔space, `token_type` specials, raise on unmappable bytes, golden vectors vs llama.cpp. *Verified still corrupting (R-10).*
4. **C-3** — architecture prefix from `general.architecture`, `ModelSpec`, bias support, compatibility matrix.

**P1 (correctness/robustness hardening):**
5. S-2 (Deepseek) — bindings: fp16 dtype check, contiguity for quantized buffers, `writeable()` on outputs.
6. S-3 — mutex-per-launcher or enforced single-thread lock (race is real today).
7. S-3/S-4 — `O_NOFOLLOW` + fd-based mmap for KV files; unlink-before-map; document dir sensitivity.
8. S-5 — remove `sys.path` hacks; rely on installed package / explicit env var.
9. C-7/C-8 — sampler input validation (penalty>0, 0≤top_p≤1, finite logits), `max_new_tokens=0` fix, upfront seq-len check, `perf_counter`.
10. C-10/R-1/R-2 — duplicate-name rejection, typed errors for unmapped GGML types, `WeightStreamer.close()` fd-leak fix, engine ctor try/except.
11. S-1 residual — clamp `block_count`/`head_count` vs available memory before KV alloc.

**P2 (performance/design):**
12. P-1 residual — real streams: copy stream + compute stream + events, `hipMemcpyAsync` weight staging from mmap pages, one sync per token; extend device-resident pipeline to the CPU/mmap KV paths.
13. P-2 (Deepseek) — budgeted residency policy (pin-all when model fits; else pin-K + stream) — biggest decode win on 32 GB APUs.
14. D-1 (Deepseek) — document/fix madvise semantics (`posix_fadvise`/`MADV_PAGEOUT`) or correct the README claim.
15. P-3/P-4 (Deepseek) — flash-style tiled attention with GQA KV sharing via LDS.
16. C-4/C-5 — RoPE scaling (linear/YaRN), sliding-window mask.
17. B-3/B-4/B-5, T-3..T-7, L-* — `build_temp`, bounded `-j`, PEP 639 license, package namespace, pytest markers + golden fixtures + fuzz + `--stats` telemetry.

## 6. Verdict on the coder's commit

All 20 of my own findings (S/P/D) are fixed or documented, and the fixes are genuine — I reproduced the security/parser/tokenizer/embed/span fixes executable-side, and the kernel work (NT matmul, TILE_M=4 prefill, fused residual+RMSNorm, device-resident layer pipeline, RoPE table, size_t casts, dead-code removal) is coherent by inspection. The coder's resolution log is accurate for that scope.

However, **none of the Deepseek ship-blockers were addressed**: the sdist still cannot build (B-1), real Q4_K_M files still crash on Q6_K (C-1), GPT-2/Ġ tokenizers still silently corrupt text (C-2, re-verified), and `llama.*`-only metadata still rejects other architectures (C-3). Plus the smaller Deepseek robustness items (bindings dtype/contiguity/writability, thread races on static workspaces, `sys.path` shadowing, KV-file TOCTOU, close()-fd-leak, engine-ctor leak, sampler validation, madvise doc overstatement, residency policy) remain open.

**Recommendation:** merge the security/parser/CI work, but hold the "v0.6.0 production-ready" claim until P0 items 1–4 land; they are what the README's advertised model families actually require.

---

## 7. Coder Resolution Log (v0.6.1 Implementation)

All P0 ship-blockers (`B-1`, `C-1`, `C-2`, `C-3`), P1 robustness/security items (`S-1`–`S-5`, `C-7`, `C-8`, `C-10`, `R-1`, `R-2`), P2 residency/stream/doc items (`P-1`, `P-2`, `D-1`, `B-3`, `B-4`), and regression notes (`N-1`–`N-4`) have been implemented and verified on `gfx1150`:

| Item | Resolution Summary | Files Modified |
|---|---|---|
| **B-1** (`sdist` completeness) | Added `MANIFEST.in` packaging `CMakeLists.txt`, `LICENSE`, `README.md`, `src/kernels/*.h`, `src/kernels/*.hip`, and `src/python_bindings/*.cpp`. Verified via `test_v8_b1_pyproject_and_sdist_contents` in `tests/test_cpu_only.py`. | `MANIFEST.in`, `tests/test_cpu_only.py` |
| **B-3 / B-4** (`setup.py` & `pyproject.toml`) | Updated `CMakeBuild` in `setup.py` to build inside `self.build_temp`, bound parallel jobs (`min(cpu_count, 8)`), and emit a `RuntimeWarning` when `GFX1150_SKIP_CMAKE=1`. Bumped version to `0.6.1` with classifiers and URLs in `pyproject.toml`. | `setup.py`, `pyproject.toml` |
| **C-1** (`Q6_K` kernel + load-time validation) | Added CPU (`quantize_q6_k_cpu`, `dequantize_q6_k_cpu`) and Wave32 HIP kernels (`dequantize_q6_k_kernel`, `matmul_q6_k_wave_kernel`, `matmul_q6_k_prefill_wave_kernel` with `TILE_M=4`, `launch_matmul_q6_k_device`) for 210B/256-weight `Q6_K` super-blocks, wired into `embed_tokens`, `linear_project`, and `forward_layer_cached`, plus load-time `WeightStreamer.validate_supported_tensors()`. | `src/gguf_parser.py`, `src/kernels/dequantize.h`, `src/kernels/dequantize.hip`, `src/kernels/attention.hip`, `src/python_bindings/bindings.cpp`, `src/tokenizer.py`, `src/layer.py`, `src/weight_loader.py` |
| **C-2** (GPT-2 `Ġ` BPE + `merges` + unmappable error) | Updated `GGUFTokenizer` to support GPT-2/Llama-3/Qwen2 byte-level BPE (`Ġ` space mapping, regex pre-tokenizer, `tokenizer.ggml.merges` rank ordering, `token_type` special-token filtering) alongside SentencePiece (`▁`), and raise `ValueError` on unmappable bytes when `<0xXX>` tokens are absent. | `src/tokenizer.py`, `tests/test_cpu_only.py`, `tests/test_phase5_scale.py` |
| **C-3** (`{arch}.*` metadata + QKV biases) | Resolved `{arch}.*` metadata keys (`qwen2.*`, `phi3.*`, `gemma.*`) with fallback to `llama.*` in `LlamaLayerConfig`, `WeightStreamer`, and `LlamaInferenceEngine`, and added optional `blk.{i}.attn_{q,k,v,output}.bias` support in `TransformerLayer`. | `src/layer.py`, `src/weight_loader.py`, `src/inference.py` |
| **C-7 / C-8** (Sampler & generation validation) | Added `repetition_penalty > 0`, `0 <= top_p <= 1`, `temperature >= 0`, and finite-logits checks in `sample_next_token`; handled `max_new_tokens == 0`, upfront `len(prompt_ids) + max_new_tokens <= max_seq_len` validation, `time.perf_counter()`, and exact `decode_steps` counting in `generate_ids`. | `src/inference.py`, `tests/test_cpu_only.py`, `tests/test_phase5_scale.py` |
| **C-10** (Duplicate tensor & zero-dim rejection) | Rejected duplicate tensor names, zero-sized dimensions (`n_dims == 0` or `d == 0`), and unknown `GGMLType` IDs with `ValueError` in `GGUFParser._parse`. | `src/gguf_parser.py`, `tests/test_cpu_only.py` |
| **S-1 / S-3 / S-4 / S-5** (KV security, mutex, `sys.path`) | Added `O_NOFOLLOW` + fd-backed `mmap.mmap(fd, ...)` in `KVCacheManager` (eliminating path-reopen TOCTOU), `max_kv_bytes` cap, `threading.Lock` on `_active_gpu_instance`, `std::mutex g_hip_workspace_mutex` across all HIP bindings, and removed unconditional `sys.path.insert(0, _BUILD_DIR)`. | `src/kv_cache.py`, `src/python_bindings/bindings.cpp`, `src/tokenizer.py`, `src/layer.py`, `src/inference.py` |
| **S-2 / N-4** (PyBind11 dtype, writeable & contiguity guards) | Verified `arr.dtype().kind() == 'f' && arr.itemsize() == 2` (rejecting `int16`/`uint16`), `arr.writeable()` on all output arrays, C-contiguity on all `py::buffer` quantized inputs, and 2D `(N, K)` shape on `matmul_nt`. | `src/python_bindings/bindings.cpp`, `tests/test_phase5_scale.py` |
| **R-1 / R-2 / N-1** (Resource cleanup) | Wrapped `self._mm.close()` in `try/finally` inside `WeightStreamer.close()` so `self._file.close()` always runs; wrapped `LlamaInferenceEngine.__init__` post-streamer setup in `try/except` calling `self.close()`; cleaned up `self._out_norm_w` in `close()`. | `src/weight_loader.py`, `src/inference.py`, `tests/test_cpu_only.py` |
| **P-1 / P-2 / D-1 / N-2** (Streams, `d_normed_h`, `cache_weights`, docs) | Added dedicated `d_normed_h` buffer (removing in-place `d_x` aliasing) plus `hipStream_t` / `hipEvent_t` / `hipMemcpyAsync` in `DeviceLayerWorkspace`, added `cache_weights` (`--cache-weights`), and clarified `MADV_DONTNEED` clean page-cache reclamation semantics in docstrings and `README.md`. | `src/kernels/attention.hip`, `src/weight_loader.py`, `src/inference.py`, `README.md` |
