# QA/QC Final Report — Phase 5 Review (`Argon_Phase_5`, commit `5a62d98`)

> **Status:** PASS with conditions · **Scope:** Phase 5 (k-quants, KV offload, batching, packaging) plus accumulated findings from Phases 2–4 still open.
> **Hardware verification:** Build + test suite passed on target gfx1150 machine (owner-run). Sandbox review was static only (no AMD GPU available).
> **Audience:** Primary Coder (Argon/GLM5.3) — items below are the actionable backlog. An overall package audit will follow the Phase 5 merge.

---

## 1. Phase 5 Deliverables — Verified

| Deliverable | Files | Verdict |
|---|---|---|
| Q8_0 dequant + fused matmul kernels | `src/kernels/dequantize.hip` (+366) | ✅ Block layout (34B/32 elems) and scale math match GGML reference |
| Q4_K (Q4_K_M/S) super-block kernels | `src/kernels/dequantize.hip` | ✅ `get_scale_min_k4` 6-bit scale/min packing, `d*q − dm` formulation, 256-elem/144B super-blocks all correct |
| KV cache: CPU-offload + mmap modes | `src/kv_cache.py` | ✅ Bounds-checked; `device_bytes` correctly reports 0 when offloaded |
| Chunked prefill + multi-prompt batch | `src/inference.py` (+233) | ✅ Intermediate chunks skip logits (`compute_logits=False`); batch mode reuses streamer/cache |
| Packaging + CLI | `pyproject.toml`, `gfx1150-infer` | ⚠️ See Gap G-1 |
| CPU reference dequantizers (test refs) | `src/gguf_parser.py` (+118) | ✅ |
| Scale/offload test suite | `tests/test_phase5_scale.py` | ✅ Determinism checks (chunked vs. full prefill, GPU vs. CPU vs. mmap KV) are well designed |

**Accuracy thresholds observed in tests:** dequant < 1e-3 (exact-class kernels), fused matmul < 1e-2 (Q8_0) / < 2e-2 (Q4_K) — consistent with the FP16 precision limits documented in `LESSONS_LEARNED.md`.

### 1.1 Prior review notes correctly addressed in Phase 5
- ✅ PR #5 note 1: `output_norm.weight` now cached once in host RAM; embedding pages evicted after prefill; LM head prefetched during last-layer compute and evicted after projection (`prefetch_tensor` / `release_tensor` added to `WeightStreamer`).
- ✅ PR #5 note 2 documented (static singletons, single-threaded scope) — still open as O-3 below.

---

## 2. Gaps — Must Address (blocking for "production-ready" claim, not for merge)

### G-1: `pip install` cannot produce a working package
`pyproject.toml` declares `gfx1150-infer = "inference:main"` and the six Python modules, but **`matmul_module` (the HIP C extension) is not built by the pip build**. A fresh `pip install gfx1150-inference` yields a package that throws `ModuleNotFoundError: matmul_module` at import.
**Required fix (coder):** one of
1. CMake-backed build step (`scikit-build-core` with `CMakeLists.txt` as the backend), or
2. `cffi`/`setuptools` custom build_ext invoking the existing CMake flow, or
3. Minimum viable: document prominently (README + `pyproject.toml` description) that the extension must be built first via `cmake -B build && cmake --build build` and `build/` placed on `PYTHONPATH` — and gate the CLI entry point with a clear error message if `matmul_module` is missing.
The Phase 5 success criterion "installable via `pip install -e .`" is only partially met as written.

### G-2: `assert` used for runtime control flow
`src/inference.py` (`prefill_tokens`, `generate_ids` decode loop) uses `assert logits is not None`. Under `python -O` these vanish and `None` propagates into `sample_next_token`. Replace with explicit `raise RuntimeError(...)` — this is a CLI product now, so `-O` flag is a realistic runtime.

---

## 3. Open Concerns — Should Address (non-blocking, tracked from prior reviews)

### O-1: CPU/mmap KV-offload path re-uploads the full context every step
`kv_cache.py` `attend()` in offload modes passes the whole layer view into `gqa_attention` (the Phase 3 non-cached kernel), which copies `total_kv_len × num_kv_heads × head_dim` H2D per token per layer. RAM is saved but the Phase 4 copy-elimination is traded back. Acceptable for long-context research use; document the throughput trade-off in the README next to `--offload-kv-cpu`/`--kv-mmap-dir` (they are throughput-negative, memory-positive).

### O-2: `generate_batch_ids` is sequential, not continuous batching
Prompts run one after another on the shared engine. Matches the plan wording ("multi-batch prompt processing"), but the README/plan should not imply concurrent batching. True continuous batching would need batched kernels (M > 1 with per-row positions) — significant kernel work, defer to a Phase 6 if needed.

### O-3: Static singletons across all `.hip` workspaces + device KV pool
All kernel workspaces and the device KV pool are function-local statics. Single-threaded only; also a second `KVCacheManager` in the same process silently shares the underlying device pool (init would resize it). Guard with an active-instance check or documented single-engine constraint.

### O-4: `rope_neox` hard-coded `False` in `LlamaLayerConfig.from_gguf_metadata`
Carried from Phase 3 review. Kernel supports NeoX; config never reads it from metadata. Fine for Llama-1/2 GGUFs; wrong rotation pairing for Llama-3/Mistral-style models. Read the appropriate GGUF metadata key (or add a constructor flag) when those models are targeted.

### O-5: `WAVES_PER_BLOCK` literal duplication
`attention.hip` uses `blockIdx.x * 8 + wave_id` while `__launch_bounds__(256)` and launch code use `waves_per_block = 8`. Derive all three from one constant to prevent silent divergence (Phase 3 note, still present in Phase 5 code).

---

## 4. Verification Commands (for the coder / audit)

```bash
# Build (gfx1150 hardware required)
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

# Full test ladder
PYTHONPATH=build python3 tests/test_matmul.py
PYTHONPATH=build:src python3 tests/test_gguf_and_q4.py
PYTHONPATH=build:src python3 tests/test_layer.py
PYTHONPATH=build:src python3 tests/test_full_model.py
PYTHONPATH=build:src python3 tests/test_phase5_scale.py

# CLI smoke
PYTHONPATH=build:src python3 -m inference --model <model.gguf> -p "Hello" -n 8
PYTHONPATH=build:src python3 -m inference --model <model.gguf> -p "Hello" -n 8 --offload-kv-cpu

# Packaging check (currently EXPECTED TO FAIL — see G-1)
pip install -e . && gfx1150-infer --model <model.gguf> -p "Hello"
```

## 5. Audit Handoff Summary

For the post-merge package audit, the highest-value areas in order:
1. **G-1 packaging gap** — the only functional defect found across all five phases.
2. **Memory-bound claims** — the < 500 MB resident-delta and flat-RAM criteria are asserted in tests via `device_bytes` logic but should be re-measured on hardware with `time -v` / `rocm-smi` during a 70B run.
3. **Thread-safety model** (O-3) — document or enforce single-engine-per-process.
4. **Model-coverage matrix** — current code paths validated against Llama-1/2 archetypes; Q4_K_M models and NeoX-style models need an explicit compatibility note (O-4).

Overall assessment: **the codebase is architecturally sound and internally consistent across all five phases; one packaging defect (G-1) and one robustness fix (G-2) remain before the v0.5.0 claim of "installable" is fully accurate.**

---

## 6. Coder Resolution Log (Phase 5 QA/QC Remediation Applied)

All blocking gaps (`G-1`, `G-2`) and open concerns (`O-1`–`O-5`) have been resolved on `Argon_Phase_5`:

| ID | Item | Resolution | Files Updated |
|---|---|---|---|
| **G-1** | `pip install` CMake extension build & import diagnostics | Added [setup.py](setup.py) with a custom `CMakeBuild(build_ext)` hook (`CMakeExtension("matmul_module")`) that automatically invokes `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` and `cmake --build build -j` during `pip install`, copying `matmul_module*.so` into the target extension path. Added explicit `ImportError` diagnostics with build instructions when `matmul_module` is missing. | [setup.py](setup.py), [pyproject.toml](pyproject.toml), [src/inference.py](src/inference.py), [src/layer.py](src/layer.py), [src/kv_cache.py](src/kv_cache.py), [README.md](README.md) |
| **G-2** | `assert` used for runtime control flow | Replaced all runtime `assert` checks (`logits is not None`, `step_logits is not None`, `_k_host is not None`) with explicit `if ... is None: raise RuntimeError(...)` checks so `python -O` execution is safe. | [src/inference.py](src/inference.py), [src/kv_cache.py](src/kv_cache.py) |
| **O-1** | CPU/`mmap` KV-offload H2D bandwidth trade-off | Documented that `--offload-kv-cpu` and `--kv-mmap-dir` trade `O(context_len)` per-step H2D KV bandwidth to keep persistent GPU KV pool usage at `0` bytes for long-context 70B runs. | [README.md](README.md), [src/kv_cache.py](src/kv_cache.py) |
| **O-2** | Sequential vs. continuous multi-prompt batching | Clarified in plan and README that `generate_batch` / `generate_batch_ids` executes sequential multi-prompt batching reusing `WeightStreamer` and `KVCacheManager`. | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [README.md](README.md) |
| **O-3** | Process-wide singleton `DeviceKVCachePool` guard | Added `KVCacheManager._active_gpu_instance` runtime guard that raises `RuntimeError` if a second GPU-resident `KVCacheManager` is instantiated before `.close()` is called on the active instance, verified by a dedicated test in `tests/test_phase5_scale.py`. | [src/kv_cache.py](src/kv_cache.py), [tests/test_phase5_scale.py](tests/test_phase5_scale.py), [README.md](README.md) |
| **O-4** | `rope_neox` GGUF metadata & CLI support | Updated `LlamaLayerConfig.from_gguf_metadata` to inspect `llama.rope.neox` and `general.architecture` (`_NEOX_ROPE_ARCHS`) or accept an explicit `rope_neox` override, and added `--rope-neox` to the `gfx1150-infer` CLI. | [src/layer.py](src/layer.py), [src/inference.py](src/inference.py), [README.md](README.md) |
| **O-5** | `WAVES_PER_BLOCK` literal duplication in `attention.hip` | Consolidated `WAVES_PER_BLOCK = 8` and `BLOCK_THREADS = WAVE_SIZE * WAVES_PER_BLOCK` across `__launch_bounds__`, wave indexing, and kernel launch grids. | [src/kernels/attention.hip](src/kernels/attention.hip) |
