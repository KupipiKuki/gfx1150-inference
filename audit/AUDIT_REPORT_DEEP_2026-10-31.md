# Deep Technical Audit — `gfx1150-inference` v0.5.0

**Date:** 2026-10-31
**Scope:** full repository at `af5fff4` (post-Phase-5): 6 Python modules, 7 HIP kernels + headers, pybind11 bindings, CMake/setuptools packaging, 5 test scripts, docs.
**Relation to prior work:** this audit re-derives the `AUDIT_REPORT_v0.5.0.md` conclusions, **confirms** several, **refines** two (A-5, A-2), and adds a set of findings the previous audit did not cover — most importantly a release-blocking sdist defect, a tokenizer that silently corrupts GPT-2/`Ġ` vocabularies, a model-compatibility gap for real `Q4_K_M` files, and an execution model that is dominated by host↔device round trips.

**Verdict:** the kernel-level work is solid and internally consistent; the **engine is not yet fast enough to justify its own streaming premise, and not yet correct enough for the model families its README advertises.** Ship-blocking: D-1, D-2, C-1, C-2, C-3, S-1. Everything else is hardening.

---

## 0. Finding summary

| ID | Severity | Area | Finding |
|---|---|---|---|
| **B-1** | **Blocker** | Packaging | `sdist` contains **no `CMakeLists.txt`, no `src/kernels/*.hip`, no `bindings.cpp`** → `pip install` from sdist/PyPI cannot build. Verified. |
| **P-1** | **High** | Design/Perf | Every kernel call is a blocking H2D → launch → D2H round trip; **~1,600 blocking API calls per generated token** for a 32-layer model. |
| **P-2** | **High** | Design/Perf | Streaming+eviction is the *default* even when the model fits in RAM; for 7B Q4 (~3.8 GB) on a 32 GB APU this is ~15–20× slower than necessary. |
| **C-1** | **High** | Correctness | Standard `Q4_K_M` GGUFs contain `Q6_K` tensors (`attn_v`, `ffn_down`, `output`); `linear_project` has no `Q6_K` path → real files raise `ValueError`. |
| **C-2** | **High** | Correctness | Tokenizer ignores `tokenizer.ggml.merges` and `Ġ` (GPT-2/BPE) vocabularies; **spaces are silently dropped** and decode re-emits `Ġ`. Verified on a synthetic Llama-3-style vocab. |
| **C-3** | **High** | Correctness | All metadata keys are hardcoded to `llama.*`; `qwen2`/`phi3`/`gemma` files fail with `KeyError`. QKV bias tensors (Qwen2/2.5) are ignored. |
| **S-1** | **High** | Security/Robustness | GGUF parser trusts an untrusted file: no offset/extent validation, `general.alignment=0` → `ZeroDivisionError` (verified), truncation detected only lazily at layer *N* (verified), counts/dims unvalidated. |
| **B-2** | Medium | Build | `find_package(hipblas/rocblas REQUIRED)` although **no kernel uses them** → avoidable build failure; isolated PEP 517 build still broken (prior A-1). |
| **C-4** | Medium | Correctness | RoPE scaling (`llama.rope.scaling.*`: linear/YaRN) ignored → wrong positions for Llama-3.1/3.2, Qwen2.5 long-context. |
| **C-5** | Medium | Correctness | No sliding-window attention (Mistral), no attention biases, no per-layer `head_count_kv` arrays. |
| **C-6** | Medium | Perf/Correctness | F16/F32 weights are **transposed on the host on every call** (`ascontiguousarray(W.T)`); a tied LM head copies ~1.2 GB per token. |
| **C-7** | Medium | Correctness | `max_new_tokens=0` still emits 1 token; `decode_steps` metric is off by one; prompt length vs `max_seq_len` is not checked before a multi-minute prefill. |
| **C-8** | Medium | Robustness | Sampler accepts `repetition_penalty<=0` (verified `ZeroDivisionError` warning → `inf` → wrong argmax) and unvalidated `top_p`/`top_k`. |
| **P-3** | Medium | Perf | Quantized prefill kernel reads the whole weight matrix **once per output row** (no tiling/reuse) → 6–15× headroom; the existing tiled FP16 kernel is unused for quantized paths. |
| **P-4** | Medium | Perf | GQA attention re-reads K/V for every query head in a group and recomputes `expf` in all 32 lanes. |
| **S-2** | Medium | Security | Bindings accept non-contiguous quantized buffers, any 2-byte dtype, and read-only outputs → possible OOB read/write from Python-level misuse. |
| **S-3** | Medium | Concurrency | Process-wide `static` workspaces with GIL released → data race if two Python threads call any kernel. Singleton is a symptom, not a fix. |
| **S-4** | Medium | Security | KV `mmap` uses fixed filenames in a user directory, `w+` truncation, follows symlinks, default permissions, no crash cleanup. |
| **S-5** | Medium | Security | Every module prepends `src/` and `../build` to `sys.path` → a writable `build/matmul_module.py` shadows the real extension. |
| **D-1** | Medium | Design | `MADV_DONTNEED` on a `MAP_SHARED` file mapping does not reliably evict clean page-cache pages; the "bounded RAM" claim is overstated. |
| **R-1** | Medium | Robustness | `WeightStreamer.close()` raises `BufferError` when a view is alive and then **leaves the file descriptor open** (verified). |
| **R-2** | Medium | Robustness | `LlamaInferenceEngine` has no finalizer; constructor failure after `WeightStreamer` leaks until GC. |
| **T-1** | Medium | Testing | No CPU CI, tests are ad-hoc scripts (bool returns), hardware-gated only, absolute error/time thresholds are flaky. |
| L-1…L-8 | Low | Hygiene | Hull-based layer spans (verified 1,838 bogus bytes), duplicate tensor names, raw `KeyError` for unknown GGML types, dead naive matmul, `time.time()` metrics, GPL-3 metadata, hardcoded RPATH, unvalidated CLI numerics. |

---

## 1. Method and evidence

Static review of every source file, plus **executable probes** of the CPU-only surface on a non-GPU host (Python 3.14, NumPy 2.5) with a stubbed `matmul_module`:

| Probe | Result |
|---|---|
| `compileall` over `src/`, `tests/`, `setup.py` | pass |
| Quantize↔dequantize round trips (Q4_0/Q8_0/Q4_K, σ=0.1) | max err 0.028 / 0.0016 / 0.024 — consistent with 4-bit/8-bit grids |
| `general.alignment = 0` | `ZeroDivisionError` |
| Truncated GGUF (10 bytes short) | loads fine; first tensor access raises `ValueError: buffer is smaller than requested size`; `prefetch_layer` silently no-ops |
| Interleaved non-layer tensor | layer span over-covers by 1,838 bytes (hull, not ownership) |
| Live view + `close()` | `BufferError`; `_file.closed == False` (fd leak) |
| GPT-2/`Ġ` vocab `encode("Hello world")` | `['H','e','l','l','o','w','o','r','l','d']` → **space lost**; `decode` → `"Helloworld"` |
| Unknown non-ASCII char, no `<0xXX>` tokens | `[]` (silent token loss) |
| `repetition_penalty=0` | NumPy divide-by-zero warning, wrong token selected |
| `sdist` | 71 KB tarball containing only `*.py`, README, LICENSE, pyproject — **no C/C++/HIP/CMake sources** |

GPU behaviour cannot be executed here (no gfx1150/ROCm in this environment). All kernel-level observations below are **by inspection** and are explicitly marked; everything marked *verified* was reproduced.

---

## 2. As-built architecture

```
CLI (inference.main)
  └─ LlamaInferenceEngine
       ├─ WeightStreamer ── mmap(file, ACCESS_READ) ── GGUFParser (header only)
       │     └─ madvise(WILLNEED / DONTNEED) per layer + per global tensor
       ├─ GGUFTokenizer ── tokens/scores from metadata (BPE merge by score)
       ├─ TransformerLayer (LlamaLayerConfig from llama.* metadata)
       │     for each layer:
       │       layer_context()  ── prefetch L+1, yield zero-copy views
       │       rmsnorm → Q/K/V → rope ×2 → GQA(+KV) → o_proj → residual
       │       rmsnorm → gate/up → swiglu → down → residual
       │       finally: MADV_DONTNEED(L)
       └─ KVCacheManager
             GPU pool (kv_cache_init/gqa_attention_cached)  [default]
             host pool  (gqa_attention, O(context) H2D/step) [--offload-kv-cpu]
             memmap pool (same as host, disk-backed)         [--kv-mmap-dir]
```

Each Python call into `matmul_module` owns a host buffer, copies it to a device buffer, launches one kernel, copies the result back, and returns. Device memory is managed by **six independent static workspace singletons** (`matmul.hip`, `dequantize.hip`, `rmsnorm.hip`, `rope.hip`, `attention.hip`, `mlp.hip`) plus `DeviceKVCachePool`.

**What is genuinely good:** the phase boundaries are clean, kernels use FP32 accumulation, Wave32 shuffles are correct for RDNA3.5, Q4_0/Q4_K packing matches GGML's `get_scale_min_k4` layout, the Q4_K builder↔reader pair is self-consistent, input validation at the binding layer is present, GIL is released around device work, and the layer/streaming API is coherent. The code reads as one design executed incrementally — the prior audit's consistency matrix is accurate.

**The structural problem:** the engine was designed as a *chain of stateless host functions*. That is a fine way to validate kernels, but it is the wrong execution model for inference: it makes every operator a synchronization point, makes device memory a process-global singleton, and makes the host the bottleneck. The kernels are ready for a better runtime; the runtime is what needs redesign.

---

## 3. Design review

### 3.1 The streaming premise is inverted for the target hardware

`gfx1150` (Radeon 890M / Ryzen AI 9 HX 370) ships in 16–32 GB unified-memory machines. A 7B `Q4_0` model is **~3.8 GB**; a 14B `Q4_K_M` is **~8.5 GB**; KV for 8k context with GQA-8 is < 1 GB. All of that fits comfortably in 32 GB.

The current default evicts every layer after use (`layer.py:272` → `weight_loader.py:79-93`), forcing a full model re-read **per token**. At an optimistic 3.5 GB/s NVMe that is ~1.1 s/token (~0.9 tok/s) for 7B and ~11 s/token (~0.09 tok/s) for 70B. The README calls this "overnight research", which is honest, but the software never checks whether streaming is *necessary* — and on the primary hardware it almost never is.

**Design recommendation:** make residency a budgeted policy, not a fixed behaviour.

```
ResidencyPolicy = AUTO | PIN_ALL | STREAM
budget = min(available GTT/RAM) − kv_bytes − activation_peak − safety(1 GB)
if model_bytes ≤ budget:            upload/pin everything, never evict
else:                               pin the first K layers, stream the rest with
                                    N-layer lookahead; K chosen to fill budget
```

For 7B on 32 GB this alone moves decode from ~1 s/token to ~50–80 ms/token (weights read from RAM at ~90 GB/s, not SSD). For 70B it degrades gracefully into today's behaviour.

### 3.2 No device-resident tensor pipeline

`layer.py` allocates every intermediate in host NumPy (`np.empty_like`) and hands it to a launcher that copies it to the device. Activations, KV writes, and weights all cross the bus. The target is an **APU with coherent memory** — the copy is pure overhead, and there is no reason to end every operator with a D2H copy except that the API was shaped that way.

**Recommended target pipeline:**

```
host:  sample ← logits ← [single D2H per token]
device: embed → per layer: rmsnorm → qkv → rope → attn → o → rmsnorm → mlp
        weights: staged asynchronously (double-buffered) on a copy stream,
                 or zero-copy from a registered mmap window
```

Concretely:
* allocate one activation arena per session and keep it device-resident;
* add `*_into(out_dev_ptr, ...)` variants or a `Session` class owning the buffers;
* use `hipMemcpyAsync` + `hipEvent` on a dedicated copy stream, one `hipStreamSynchronize` per token;
* optionally `hipHostRegister(ptr, len, hipHostRegisterMapped)` for the mmap window so kernels read weights directly from the page cache (eliminates the 3.8 GB/token H2D). Caveat: the range must be resident and pinnable (`ulimit -l`, `mlock` limits), and registration pins it — which is exactly what you want in `PIN_ALL`, and exactly what you must *not* do in `STREAM` mode.

### 3.3 Process-global state instead of a context object

Six static workspaces + one static KV pool are why the README has to forbid two engines and why threading is unsafe. Move them into a `DeviceContext` (RAII, passed by reference). Benefits: multiple engines, tests in parallel, no shutdown-order surprises, explicit memory accounting, and no "high-water mark never shrinks" behaviour.

### 3.4 Configuration surface

`LlamaLayerConfig` reads `llama.*` directly and freezes a single `head_dim`. A model-family adapter (`arch.*` prefix, bias presence, RoPE scaling, SWA window, per-layer KV heads, EOS set) is the missing abstraction that would make the README's architecture claims true.

### 3.5 Missing runtime features (for "research workloads")

Streaming output callback, stop strings, multiple EOS, `min_p`, logit bias, seed-per-request isolation, prompt cache, true continuous batching (`generate_batch` is a sequential loop today), request timeouts, and structured telemetry.

---

## 4. Build, packaging and setup

### B-1 (Blocker, verified) — sdist cannot be installed
`python setup.py sdist` produces a tarball with only `src/*.py`, `tests/*.py`, README, LICENSE, pyproject, setup.py. `CMakeLists.txt`, `src/kernels/*.{h,hip}`, and `src/python_bindings/bindings.cpp` are absent because setuptools does not include them by default and there is no `MANIFEST.in` / `package-data` entry. A `pip install gfx1150-inference` from PyPI (or `pip install .` from the sdist) fails at `cmake -S .` with *"does not appear to contain CMakeLists.txt"*.

Minimum fix:
```toml
# pyproject.toml
[tool.setuptools]
package-dir = {"" = "src"}
py-modules = ["gguf_parser", "weight_loader", "layer", "kv_cache", "tokenizer", "inference"]

[tool.setuptools.package-data]
"*" = ["../CMakeLists.txt", "../src/kernels/*", "../src/python_bindings/*"]
# better: move CMakeLists/kernels under a real package and use package-data
```
or add `MANIFEST.in`:
```
include CMakeLists.txt
recursive-include src/kernels *.h *.hip
recursive-include src/python_bindings *.cpp
```
**Recommended:** replace the hand-rolled hook with `scikit-build-core`, which solves sdist inclusion, build isolation, `build_temp`, install RPATH, and wheel tags in one move.

### B-2 (Medium) — unnecessary hard dependencies
`CMakeLists.txt:17-26` requires `hipblas` and `rocblas` and fails if either is missing; the comment itself says "no current kernel calls them yet". Distributions split these packages. Drop them (or gate behind `option(GFX1150_ENABLE_BLAS OFF)`), and link `hip::host` explicitly for the CXX bindings TU. Also set `INSTALL_RPATH` (not just `BUILD_RPATH`) and stop hardcoding `core-10.1` (`CMakeLists.txt:65`), which only exists on ROCm 6.x.

### B-3 (Medium) — setup.py quality
* `build/` is created **inside the source tree** (`setup.py:38`); use `self.build_temp`.
* `cmake --build ... -j` is unbounded → OOM on high-core machines. Use `CMAKE_BUILD_PARALLEL_LEVEL` or `-j N`.
* No ROCm preflight: emit a targeted error (`ROCM_ROOT` unset and `/opt/rocm` absent) before invoking CMake (this is the concrete fix for prior finding A-1).
* `GFX1150_SKIP_CMAKE=1` silently produces a wheel without the extension; make it fail loudly at `build_ext` unless explicitly allowed for metadata-only builds.
* `[build-system] requires` lacks `cmake` and `ninja`; isolated builds cannot work.

### B-4 (Low) — metadata
`license = { file = "LICENSE" }` is deprecated under PEP 639 (setuptools ≥ 77 warns). Use `license = "GPL-3.0-only"` + `license-files = ["LICENSE"]`. Note that GPL-3 makes the *library* copyleft for downstream importers; if the intent is a reusable engine, Apache-2.0/MIT may be preferable (legal decision, not an audit call). Add `[project.urls]`, classifiers, `[project.optional-dependencies] test/dev`, and a `__version__`.

### B-5 (Low) — namespace
Distribution is `gfx1150-inference` but it installs six **top-level** modules, including `tokenizer`, `layer`, and `inference`. These names collide easily. Move to a package (`gfx1150/…`) with relative imports; keep `matmul_module` as `gfx1150._kernels`.

### Setup guidance (document in README)
* ROCm 6.2+ recommended for native `gfx1150`; `HSA_OVERRIDE_GFX_VERSION=11.5.0` only if the runtime does not list the device.
* `ROCM_ROOT=/opt/rocm` (or distro path) and `-DCMAKE_HIP_ARCHITECTURES=gfx1150`.
* `pip install -e . --no-build-isolation` until B-1/B-2 are fixed.
* For APU GTT: raise `amdgpu.gttsize` / TTM page limit; `ulimit -l unlimited` if pinning; NVMe `mq-deadline`→`none`, `read_ahead_kb` 4096–8192.
* `vm.swappiness=10`, and *do not* run with `vm.overcommit_memory=2`.

---

## 5. Correctness and model compatibility

### C-1 (High) — `Q4_K_M` is not actually supported
`linear_project` (`layer.py:99-112`) handles `Q4_0`, `Q8_0`, `Q4_K`, `F16`, `F32`. Standard `Q4_K_M` recipes (llama.cpp) assign **`Q6_K`** to `attn_v`, `ffn_down`, and typically `output.weight`. Those tensors hit the `else` branch and raise `Unsupported weight quantization type: GGMLType.Q6_K`. The synthetic Phase-5 test uses a `Q4_K` + `Q8_0` mix, so the suite never exercises the real recipe. `Q5_K`, `Q4_1`, `Q5_0`, `Q2_K`, `Q3_K` are likewise absent.

Fix: add `Q6_K` (and ideally `Q5_K`) fused kernels — the block layout is already in `GGML_BLOCK_INFO` — and add a compatibility matrix + fail-fast at load time listing unsupported tensor types **before** streaming begins.

### C-2 (High, verified) — tokenizer breaks GPT-2/`Ġ` vocabularies
`tokenizer.py`:
* never reads `tokenizer.ggml.merges` (structurally required for BPE; merge ranks are not derivable from scores);
* detects SentencePiece only via `▁`, so GPT-2-style vocabs (`Ġ`, Llama-3, Qwen2.5) skip the space mapping;
* then the literal space is not a token, has no `<0x20>` fallback in those vocabs, and is **silently dropped**;
* `decode` never converts `Ġ` back to a space.

Verified: `encode("Hello world")` → `H e l l o w o r l d`, `decode` → `"Helloworld"`. This alone makes every generated answer wrong for the most common modern GGUFs.

Fix: implement GPT-2 BPE properly (pre-tokenization regex, merge-rank queue from `tokenizer.ggml.merges`, `Ġ`↔space, special-token trie from `tokenizer.ggml.token_type`), and validate against llama.cpp golden vectors for at least Llama-2, Llama-3, Qwen2.5. Also: raise on unmappable characters instead of dropping them.

### C-3 (High) — architecture keys hardcoded to `llama.*`
`inference.py:120` (`self.metadata["llama.block_count"]`) and `LlamaLayerConfig.from_gguf_metadata` (`layer.py:58-64`) use the literal `llama.` prefix. A `qwen2` GGUF has `qwen2.block_count` → `KeyError` at load. `general.architecture` is only consulted for RoPE style (`layer.py:70-71`). In addition, `attn_q.bias`/`attn_k.bias`/`attn_v.bias` (Qwen2/2.5) are ignored by `forward_with_weights`, and `llama.attention.head_count_kv` is assumed scalar.

Fix: `prefix = metadata["general.architecture"] + "."`, a `ModelSpec` dataclass, bias support (optional add after projection), and an allow-list with explicit errors for unsupported families.

### C-4/C-5 (Medium) — long-context and SWA
`rope_freq_base` is read, but `llama.rope.scaling.type`/`factor`/`yarn_*` are not. Llama-3.1/3.2 and Qwen2.5 long-context GGUFs will be wrong beyond the base context. Mistral's sliding-window mask is not implemented, so >window contexts diverge from the reference. State both as limitations or implement.

### C-6 (Medium) — host transposes on the dense path
`layer.py:106-110`: `np.ascontiguousarray(w_view.reshape(N, K).T)` copies and transposes the entire weight matrix **per call**. For a tied LM head (`output.weight` absent → `token_embd.weight` reused, `inference.py:139-143`) that is ~1.2 GB of host copy per generated token. Add an `matmul_nt` kernel that consumes `(N, K)` directly, or cache the transposed tensor once.

### C-7 (Medium) — generation edge cases
* `max_new_tokens=0` still returns one token (`inference.py:290` appends before the loop).
* `decode_steps = max(len(new_ids)-1, 1)` inflates tok/s when only one token is generated.
* `generate_ids` does not check `len(prompt_ids) + max_new_tokens ≤ kv_cache.max_seq_len` up front; the failure surfaces inside `attend()` after the entire prompt has been streamed.
* `time.time()` is used for metrics (non-monotonic); use `perf_counter`.

### C-8 (Medium, verified) — sampler input validation
`repetition_penalty=0` → divide-by-zero (`RuntimeWarning`), `inf` logits, arbitrary token. Negative penalty inverts the sign of logits. `top_p` outside `(0,1]` silently disables nucleus sampling. Add validation (`penalty > 0`, `temperature ≥ 0`, `0 ≤ top_p ≤ 1`, `top_k ≥ 0`) and reject NaN/Inf logits explicitly rather than falling back to `argmax`.

### C-9 (Low) — quantizer fidelity
`quantize_q4_0_cpu` uses `d = max_abs/7` for every block, i.e. a symmetric 15-level grid (the `-8` level is never used). llama.cpp uses the sign of the extreme value (`d = max/-8`), gaining one level. Consequence: ~6 % coarser quantization in the worst case, and — more importantly — **tests compare the GPU kernel against the repository's own encoder**, so encoder/decoder errors cancel and real GGUF agreement is never proven. Add golden-byte tests against llama.cpp-produced blocks.

### C-10 (Low) — parse hygiene
Duplicate tensor names silently overwrite (`gguf_parser.py:193`); unknown `ggml_type` raises a bare `KeyError`; `n_dims > 4` is not rejected; `math.prod` accepts zero/negative dims (negative impossible for uint64, zero possible → `n_bytes=0`, silently accepted).

---

## 6. Performance

### 6.1 The dominant cost is synchronization, not FLOPs

Per layer, the current call graph issues **51 host API calls, ~26 of them blocking copies** (RMSNorm ×2 = 8, seven projections = 28, RoPE ×2 = 6, attention = 5, SwiGLU = 4). For a 32-layer model that is **~1,600 blocking calls per token**, before I/O. At a conservative 5–20 µs per HIP API call that is **8–32 ms/token of pure overhead** — a hard ceiling of ~30–120 tok/s with infinitely fast hardware.

Add the data volume: a 7B Q4 model re-copies **~3.8 GB of weights H2D per token** (~76 ms at 50 GB/s unified). The kernel then reads the same 3.8 GB again from device memory. Nothing is reused between tokens.

### 6.2 Prefill: no weight reuse in the quantized kernels

`matmul_q4_0_wave_kernel` (`dequantize.hip:87-138`) maps one wave to one `(m, n)` pair and the grid's `y` dimension to `M`. Each wave streams the full weight row for its `n`; the same weight is therefore read **M times** from DRAM. For a 512-token prefill of a 7B model:

| Path | Weight traffic | Time @ ~100 GB/s |
|---|---|---|
| Current (no tiling) | 3.8 GB × 512 ≈ **1.9 TB** | ~19 s |
| 64-row tile (existing `matmul_kernel_reg_tiled` pattern) | 3.8 GB × 8 ≈ 240 GB | ~2.4 s |
| 128-row tile + `half2`/int4 vectorization | ~120 GB | ~1.2 s |
| Compute bound (8.6 TFLOPS) | — | ~0.8 s |

The tiled FP16 kernel already exists (`matmul.hip:92-177`) but is **not used for quantized paths**. This is the single largest kernel-side win.

### 6.3 Attention
* Each `(m, h)` wave re-reads the whole K/V for its head; with GQA `group_size=4`, four query heads read the same KV head → **4× redundant traffic**. Share via LDS per group.
* `expf` and the softmax scalars are recomputed in all 32 lanes per key; compute once and `__shfl` broadcast, or use the standard "one wave per block of keys, reduce at the end" flash layout.
* No key-block tiling → no LDS reuse, no `half2`, no matrix cores. For 8k context this is the decode bottleneck after weights.

### 6.4 Ranked optimization plan (expected effect on 7B Q4, 32 GB APU)

| # | Change | Expected |
|---|---|---|
| 1 | Residency policy: keep the model in RAM/VRAM when it fits; disable eviction | **10–20×** decode (1 → ~15 tok/s) |
| 2 | Device-resident activations + async copies + one sync/token | 3–5× (removes 1,600 syncs) |
| 3 | Zero-copy weight access (`hipHostRegister` of mmap window) or persistent weight cache | 2× when streaming |
| 4 | Tiled quantized GEMM for prefill | 6–15× prefill |
| 5 | Tiled flash attention + GQA KV sharing | 2–4× long-context decode |
| 6 | Fuse RMSNorm+residual, RoPE into attention, SwiGLU into the down-projection epilogue | 10–20 % |
| 7 | Remove host transposes (`matmul_nt`) | removes 1.2 GB/token for tied heads |
| 8 | Vectorize `embed_tokens` (fancy-index / `gather` on GPU) | prefill only; ~5–10 % |

### 6.5 `MADV_DONTNEED` does not do what the docs claim (D-1)
`mmap` with `ACCESS_READ` is a **`MAP_SHARED`** mapping. On Linux, `MADV_DONTNEED` unmaps the range from the process, but clean file-backed pages stay in the page cache (they are still referenced by the inode's xarray). So the call reduces RSS/PTE pressure, **not** the amount of RAM occupied by the model; the kernel may keep the whole file cached and re-map it for free on the next token. The docstrings in `weight_loader.py:79-93` and the README's "RAM is never exhausted" claim overstate the guarantee. To actually drop page cache you need `posix_fadvise(fd, …, POSIX_FADV_DONTNEED)` (best-effort, only clean pages) or `MADV_PAGEOUT` (5.4+). For deterministic memory, stage with `preadv` into a fixed double buffer instead of relying on page-cache behaviour.

### 6.6 Measurement hygiene
No warm-up, `time.time()` instead of `perf_counter`, no per-kernel `hipEvent` timing, no I/O counters (`/proc/self/stat` majflt, `mem_info_gtt_used`), and single-iteration benchmarks in tests. Numbers in the README/QAQC docs are therefore not reproducible.

---

## 7. Security and robustness

Threat model: the operator runs **untrusted model files** and may point the tool at a **shared scratch directory**; prompts are untrusted text. There is no network surface, which is good.

### S-1 (High) — unvalidated GGUF input
`GGUFParser` (`gguf_parser.py:108-215`) trusts:
* `general.alignment` (verified: `0` → `ZeroDivisionError`; non-power-of-two accepted);
* `kv_count`/`tensor_count`/array `count` (no relation to remaining bytes);
* `n_dims` (no `≤ 4` cap);
* `rel_offset`/`n_bytes` (no `abs_offset + n_bytes ≤ len(buf)` check);
* duplicate names (silent overwrite);
* `ggml_type` (bare `KeyError`).

Consequences: hard crashes from malformed files, confusing late failures after long runs (verified), and metadata-driven allocation of arbitrary size (`KVCacheManager` trusts `block_count`, `head_count`, `max_seq_len` → OOM/DoS from a 200-byte header). Add a `GGUFFormatError` with:
```python
if self.alignment < 1 or self.alignment & (self.alignment - 1):
    raise GGUFFormatError(f"invalid general.alignment={self.alignment}")
...
if n_dims > 4:
    raise GGUFFormatError(f"n_dims={n_dims} exceeds GGML limit 4")
...
if abs_offset + n_bytes > len(buf):
    raise GGUFFormatError(
        f"tensor '{name}' ends at {abs_offset+n_bytes} beyond file size {len(buf)}"
    )
```
plus count-vs-bytes guards, duplicate rejection, and clamped `block_count`/`head_count`.
Also recommend `--verify-sha256` for supply-chain integrity.

### S-2 (Medium) — buffer validation at the binding boundary
`check_fp16_contiguous` (`bindings.cpp:16-26`) checks only `itemsize()==2`, C-contiguity, and a minimum size. It does not check the dtype kind (an `int16` array passes as FP16), and it is not applied to the quantized `B` buffers at all: `matmul_q4_0`/`_q8_0`/`_q4_k` accept any buffer whose *logical* `size*itemsize` is large enough (`bindings.cpp:87-92`). A non-contiguous view (e.g. `arr.T`) passes the size check while `b_info.ptr` is strided → **out-of-bounds read/garbage output**. Outputs are not checked for writability; passing a read-only array (e.g. `np.frombuffer(mm, …)`) leads to a write into read-only pages. Fix: require `py::dtype::of<py::half>()`, `info.strides` contiguous, `arr.writeable()` for outputs, and reject non-contiguous quantized buffers explicitly.

### S-3 (Medium) — data races
Every launcher uses a function-local `static` workspace and releases the GIL. Two Python threads calling any kernel concurrently write the same `d_A/d_B/d_C` or `d_buf0/1/2` → silent corruption. The `KVCacheManager._active_gpu_instance` boolean is also not atomic. Either guard each launcher with a `std::mutex` (cheap, correct) or document and *enforce* single-threaded use with a Python-side lock. The real fix is 3.3 (context object).

### S-4 (Medium) — KV cache files on disk
`kv_cache.py:70-79` writes `kv_cache_k.mmap` / `kv_cache_v.mmap` with `mode="w+"` into a user-supplied directory: predictable names, truncation of any existing file, symlink following (a symlink there can truncate an arbitrary user-writable file), default `umask` permissions (KV contents are model-derived activations and may contain prompt material), and no cleanup on crash. Use `tempfile.mkdtemp()`, `os.open(..., O_CREAT|O_EXCL|O_NOFOLLOW, 0o600)`, unlink before mapping (Linux) so the file disappears on close/crash, and document the directory's sensitivity.

### S-5 (Medium) — `sys.path` injection
Every module does:
```python
sys.path.insert(0, _SRC_DIR)          # or append
sys.path.insert(0, _BUILD_DIR)        # ../build, writable, gitignored
```
A `build/matmul_module.py` (or `build/numpy.py`) planted by anything with write access to the checkout is imported instead of the real extension — code execution. It also masks packaging defects (this is why the import error message had to be hand-written). Remove the hacks; rely on the installed package and an explicit `MATMUL_MODULE_DIR` env var for development if needed.

### S-6 (Low) — misc
* `--kv-mmap-dir` and `--model` are passed straight to `os.makedirs`/`open`; symlinked model paths are followed (acceptable, just note it).
* No model file size/permission checks; no disk-space check before creating a KV file.
* CLI prints prompts? No — but when logging is added, treat prompts as sensitive.
* No secrets in the tree or history (scanned). Good.

---

## 8. Tests, CI, observability

* **T-1** All five suites are scripts with `main()` and boolean returns; `pytest` will not collect them meaningfully (functions named `test_*` return values, and module-level `import matmul_module` aborts collection on non-GPU hosts). No `pytest.ini`/markers.
* **T-2** Every runtime assertion is hardware-gated, so **nothing runs in CI**. The CPU logic actually exercised in this audit (parser, tokenizer, sampler, quantizers, CLI parsing) has no automated home. Add `tests/test_cpu_only.py` and gate GPU tests with `@pytest.mark.gpu`.
* **T-3** Tests validate kernels against the repo's own CPU encoder (`dequantize_q4_0_cpu(quantize_q4_0_cpu(x))`), so a shared convention error would pass. Add golden blocks produced by llama.cpp and a tiny committed GGUF fixture.
* **T-4** Absolute thresholds are flaky: `test_matmul.py:82` uses `max_error < 1e-3` on FP16 1024³ output whose ULP near 1.0 is ~1e-3; `test_fused_matmul_q4_0_hip` uses the same bound regardless of K. Use relative/statistical tolerances (e.g. `max_err ≤ 2 ULP + quant error budget`) and multi-seed runs.
* **T-5** Throughput lines measure a single call with no warm-up and `time.time()`; they are not regression tests. Track `hipEvent` medians over ≥20 iterations and assert on ratios, not absolutes.
* **T-6** No fuzzing of the parser. `hypothesis` + the bounds guards in S-1 would have caught the `alignment=0` and truncation cases.
* **T-7** No observability: add `--stats` (bytes read, majflt, GTT peak, per-kernel ms, tok/s), structured logs, and a `--json` metrics output. For 8-hour runs this is not optional.

---

## 9. Remediation roadmap

### P0 — before the next release / any distribution
1. **B-1/B-2/B-3:** move to `scikit-build-core` (or add `MANIFEST.in` + `package-data`), add `cmake`/`ninja` to build requires, drop unused `hipblas`/`rocblas`, add `hip::host`, set `INSTALL_RPATH`, ROCm preflight, `build_temp`, bounded `-j`. Add an `sdist` install test to CI.
2. **S-1:** parser bounds/alignment/count/dimension validation + `GGUFFormatError` + duplicate rejection + `--verify-sha256` + hypothesis fuzz test.
3. **C-2:** real BPE (merges, `Ġ`, pre-tokenizer, special tokens, byte fallback) with golden-vector tests.
4. **C-3:** architecture prefix + `ModelSpec` + bias support + explicit compatibility matrix.
5. **C-1:** implement `Q6_K` (and ideally `Q5_K`), or fail fast at load with a list of unsupported tensors.
6. **P-1/P-2:** residency policy + device-resident activation arena + async copy stream + one sync/token. This is the release-defining work.

### P1 — next minor
7. Tiled quantized GEMM (reuse the `matmul_kernel_reg_tiled` structure) and `matmul_nt` to kill host transposes.
8. Flash-attention tiling + GQA KV sharing.
9. `DeviceContext` refactor (remove statics), mutex-per-launcher until then.
10. Bindings hardening (S-2), KV file safety (S-4), `sys.path` removal (S-5).
11. Sampler validation + `min_p` + multiple EOS + stop strings + streaming callback.
12. Metrics/telemetry, `perf_counter`, warm-up; `--stats`/`--json`.
13. pytest conversion, CPU backend, CI (CPU job on push, GPU job nightly on a self-hosted runner), performance regression gates.

### P2 — roadmap
14. True continuous batching and prompt cache.
15. `posix_fadvise`/`MADV_PAGEOUT` + `preadv` double-buffered staging for >RAM models; `io_uring`/`O_DIRECT` option.
16. Sliding-window attention, RoPE scaling (linear/YaRN), per-layer KV heads.
17. Speculative decoding; quantized KV cache; server/API wrapper.
18. README rewrite around *measured* numbers and an explicit support matrix (arch × quant × context).

---

## 10. Patch sketches

**Parser guard (S-1)**
```python
class GGUFFormatError(ValueError): ...

def _validate(self, file_size: int) -> None:
    if self.alignment < 1 or self.alignment & (self.alignment - 1):
        raise GGUFFormatError(f"invalid general.alignment={self.alignment}")
    for t in self.tensors.values():
        if t.abs_offset + t.n_bytes > file_size:
            raise GGUFFormatError(
                f"tensor '{t.name}' ends at {t.abs_offset + t.n_bytes}, "
                f"file is {file_size} bytes (truncated or corrupt)")
```

**Binding check (S-2)**
```cpp
void require_fp16(py::array& a, const char* n, py::ssize_t min_elems, bool write) {
    if (a.dtype() != py::dtype::of<py::half>())
        throw std::invalid_argument(std::string(n) + " must be float16");
    if (!(a.flags() & py::array::c_style))
        throw std::invalid_argument(std::string(n) + " must be C-contiguous");
    if (write && !a.writeable())
        throw std::invalid_argument(std::string(n) + " must be writable");
    if (a.size() < min_elems) throw std::invalid_argument(...);
}
```

**Residency policy (P-2)**
```python
def plan_residency(model_bytes, kv_bytes, activation_peak, gtt_free):
    budget = gtt_free - kv_bytes - activation_peak - 1 << 30
    if model_bytes <= budget:
        return Residency("pin_all")
    keep = max(0, budget // bytes_per_layer)
    return Residency("stream", pinned_layers=keep, lookahead=2)
```

**Async staging (P-1)**
```cpp
// one copy stream, two weight slots, one sync per token
hipMemcpyAsync(slot[next], host_layer, bytes, hipMemcpyHostToDevice, copy_stream);
hipEventRecord(ready[next], copy_stream);
hipStreamWaitEvent(compute_stream, ready[cur], 0);
launch_layer(compute_stream, slot[cur], ...);
```

**Tokenizer (C-2)**
```python
# tokenizer.ggml.model == "gpt2"
self.ranks = {pair: i for i, pair in enumerate(metadata["tokenizer.ggml.merges"])}
# apply merges by lowest rank within each pre-token from the GPT-2 regex,
# map " " -> "Ġ", fall back to <0xXX>, never drop bytes silently
```

---

## Appendix A — reproducible checks used in this audit

```bash
# packaging defect
python setup.py sdist && tar tzf dist/*.tar.gz | grep -E 'CMake|\.hip|bindings'   # → nothing

# parser defects
python - <<'PY'
# general.alignment = 0  -> ZeroDivisionError; truncated tensor -> lazy ValueError
PY

# tokenizer defect
python - <<'PY'
# GPT2-style vocab: encode("Hello world") drops the space; decode -> "Helloworld"
PY

# mmap teardown
python - <<'PY'
# v = streamer.get_tensor_view(...); streamer.close() -> BufferError, fd still open
PY
```

## Appendix B — recommended defaults

| Setting | Current | Recommended |
|---|---|---|
| Residency | always stream + evict | `auto`: pin if it fits |
| KV cache | GPU pool sized to `max_seq_len` | same, default `min(metadata.context_length, 8192)` |
| Prefetch | 1 layer ahead, `MADV_WILLNEED` | 2 layers, `preadv` double buffer (or zero-copy) |
| Sync | after every kernel | once per token |
| `max_seq_len` | 2048 fixed | from metadata, warn on override |
| Sampling | `top_k=40`, `top_p=0.95`, `T=0` | keep, but validate and add `min_p` |
| Threads | implicitly 1, unsafe | mutex or context object |

## Appendix C — risk register (residual)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Silent wrong answers from tokenizer/arch gaps | High today | High | P0 C-2/C-3 + golden tests |
| Corrupt/truncated model crashes an 8-hour run | Medium | High | P0 S-1 + preflight hash/size |
| OOM from metadata-driven allocation | Medium | Medium | clamp dimensions; budget check |
| Multi-thread corruption via statics | Low (documented) | High | mutex/context refactor |
| KV file clobber/leak | Low | Medium | S-4 |
| Supply-chain wheel without verified extension | Low | High | signed wheels, `--verify-sha256` |

---

*Audit performed on `main` @ `af5fff4`. GPU-dependent claims are inspection-based and marked; all CPU-side claims were reproduced on the host described in §1.*
