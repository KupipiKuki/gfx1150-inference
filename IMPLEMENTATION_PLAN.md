# gfx1150-inference: Implementation Plan

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / Ryzen AI 9 HX 370)**

Built with **ROCm, HIP, and memory-mapped I/O (`mmap` + `madvise`)** for overnight research workloads on unified-memory AMD APUs.

---

## 🎯 Project Overview

### **Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Ryzen AI 370) by **streaming quantized weights directly from NVMe SSD**, enabling inference on hardware with limited unified RAM/VRAM without OOM errors.

### **Target Use Case**
- **Overnight research/fact-checking** (8-hour runtimes acceptable)
- **Single-GPU / APU** operation (aware of unified system memory / ROCm GTT)
- **Strictly bounded memory footprint** via layer-wise SSD streaming, page-cache eviction (`MADV_DONTNEED`), and fused 4-bit dequantization

### **Tech Stack**
| Component | Technology | Purpose |
|-----------|------------|---------|
| GPU Backend | ROCm 6.1+ + HIP | AMD GPU compute (`gfx1150`, Wave32) |
| Compute Kernels | Custom HIP C++17 | Fused Q4 matmul/GEMV, RMSNorm, RoPE, GQA, SwiGLU |
| Weight Storage | `mmap` + `madvise` (`WILLNEED`/`DONTNEED`) | Bounded-RAM NVMe SSD streaming with prefetching |
| Model Format | **GGUF** (`Q4_0` / `Q4_K_M`) | Page-aligned quantized weights + embedded metadata/tokenizer |
| Language | Python (frontend/orchestration) + C++/HIP (kernels) | Rapid iteration + native GPU speed |
| Build System | CMake 3.21+ + PyBind11 (`pybind11::module`) | Native HIP language compilation |

---

## 📋 Phase Breakdown

---

### **🟢 Phase 1: Hello gfx1150** *(COMPLETED)*
**Goal**: Confirm `gfx1150` works with custom HIP kernels and Python bindings.

#### **Tasks**
| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.1 | Verify ROCm installation & `gfx1150` detection | You | ✅ | `rocminfo \| grep gfx1150` |
| 1.2 | Write FP16 matmul HIP kernels (`matmul.h` / `matmul.hip`) | GLM5.3 / Argon | ✅ | 16×16 tiled + 64×64 2D register-blocked (`4×4`/thread) |
| 1.3 | Add PyBind11 module bindings | GLM5.3 / Argon | ✅ | `src/python_bindings/bindings.cpp` |
| 1.4 | Configure CMake build system (`matmul_module`) | You / Argon | ✅ | `CMakeLists.txt` with `pybind11::module` & RPATH |
| 1.5 | Write & validate test suite | Local 7B / Argon | ✅ | `tests/test_matmul.py` (1.12 TFLOPS, max error `6.1e-5`) |
| 1.6 | Document remediation & lessons learned | You / Argon | ✅ | `audit/remediation_plan.md`, `LESSONS_LEARNED.md` |

#### **Success Criteria**
- [x] ROCm detects `gfx1150`
- [x] HIP kernel compiles with 0 errors and 0 warnings
- [x] Matmul output matches FP32-accumulated reference (`max_error < 1e-3`, achieved `6.1e-5`)
- [x] Edge cases pass (`1×1024`, `1024×1`, `1×1`, `1023×1023`, `16×16`, `1024×512×256`)
- [x] End-to-end throughput > 1 TFLOPS (achieved **1.12 TFLOPS** including host-device transfers)

#### **Deliverables**
- ✅ [CMakeLists.txt](CMakeLists.txt) (ROCm + PyBind11 `MODULE` config)
- ✅ [src/kernels/matmul.h](src/kernels/matmul.h) & [src/kernels/matmul.hip](src/kernels/matmul.hip) (Register-blocked FP16 matmul + workspace cache)
- ✅ [src/python_bindings/bindings.cpp](src/python_bindings/bindings.cpp) (PyBind11 wrapper with GIL release)
- ✅ [tests/test_matmul.py](tests/test_matmul.py) (Validation & benchmark suite)
- ✅ [remediation_plan.md](audit/remediation_plan.md) & [LESSONS_LEARNED.md](LESSONS_LEARNED.md)

---

### **🟢 Phase 2: GGUF Parser + Bounded-RAM SSD Streaming + Q4 Kernels** *(COMPLETED)*
**Goal**: Parse GGUF quantized models, stream layer weights from SSD with bounded RAM using `mmap` + `madvise`, and execute 4-bit dequantization and fused Q4 matrix multiplication on `gfx1150`.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 2.1 | Implement zero-dependency GGUF v2/v3 header & tensor index parser | Argon / Local 7B | ✅ | None |
| 2.2 | Implement `WeightStreamer` with `mmap` + `madvise` (`WILLNEED` prefetch / `DONTNEED` eviction) | Argon | ✅ | 2.1 |
| 2.3 | Write HIP kernel for `Q4_0` dequantization (`src/kernels/dequantize.hip`) | Argon / GLM5.3 | ✅ | None |
| 2.4 | Write **fused `Q4_0` × `FP16` matmul/GEMV HIP kernel** (in-register dequantization, avoiding 4× FP16 memory expansion) | Argon / GLM5.3 | ✅ | 2.3 |
| 2.5 | Expose `dequantize_q4_0` and `matmul_q4_0` in PyBind11 (`bindings.cpp`) | Argon | ✅ | 2.3, 2.4 |
| 2.6 | Write synthetic GGUF + Q4 kernel validation & memory-bound test suite | QA/QC / Argon | ✅ | 2.1–2.5 |

#### **Success Criteria**
- [x] Parse GGUF v2/v3 metadata key-values and 32-byte aligned tensor offsets accurately
- [x] Stream layer weights via `mmap` and evict completed layers with `MADV_DONTNEED` (keeping resident RAM delta < 500 MB)
- [x] `dequantize_q4_0` kernel matches CPU reference exactly (`max_error < 1e-3`, achieved `0.000000`)
- [x] Fused `matmul_q4_0` kernel matches dequantized FP16 matmul while using 4× less weight memory traffic (`0.50 ms` for `1×4096×4096`)
- [x] All Phase 2 unit tests (`tests/test_gguf_and_q4.py`) pass

#### **Deliverables**
- `src/gguf_parser.py` (GGUF v2/v3 header, metadata, and tensor offset parser)
- `src/weight_loader.py` (`WeightStreamer` with `mmap` + `madvise` page-cache lifecycle control)
- `src/kernels/dequantize.h` & `src/kernels/dequantize.hip` (`Q4_0` block dequantization + fused `matmul_q4_0` kernel)
- `tests/test_gguf_and_q4.py` (GGUF parser, `madvise` streaming, and Q4 kernel test suite)

#### **Technical Design: Bounded-RAM Streaming on Unified Memory (`gfx1150`)**
```python
class WeightStreamer:
    def __init__(self, model_path: str):
        self.file = open(model_path, "rb")
        self.mm = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.gguf = GGUFParser(self.mm)

    def prefetch_layer(self, layer_idx: int) -> None:
        """Advise OS kernel to asynchronously read layer pages from NVMe SSD."""
        offset, length = self.gguf.get_layer_byte_span(layer_idx)
        self.mm.madvise(mmap.MADV_WILLNEED, offset, length)

    def release_layer(self, layer_idx: int) -> None:
        """Evict completed layer pages from Linux page cache to prevent APU RAM exhaustion."""
        offset, length = self.gguf.get_layer_byte_span(layer_idx)
        self.mm.madvise(mmap.MADV_DONTNEED, offset, length)
```

---

### **🟢 Phase 3: Transformer Layer Kernels (Llama Architecture)** *(COMPLETED)*
**Goal**: Implement the complete forward pass for a single Llama-style transformer layer on `gfx1150` with SSD-streamed `Q4_0` weights.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 3.1 | Implement **RMSNorm** HIP kernel (`src/kernels/rmsnorm.hip`) | Argon / GLM5.3 | ✅ | Phase 2 |
| 3.2 | Implement **RoPE** (Rotary Positional Embeddings) HIP kernel (`src/kernels/rope.hip`) | Argon / GLM5.3 | ✅ | Phase 2 |
| 3.3 | Implement **Grouped-Query Attention (GQA)** HIP kernel with KV cache support (`src/kernels/attention.hip`) | Argon / GLM5.3 | ✅ | 3.2 |
| 3.4 | Implement **SwiGLU** activation HIP kernel (`SiLU(gate) * up`) (`src/kernels/mlp.hip`) | Argon / GLM5.3 | ✅ | Phase 2 |
| 3.5 | Assemble single-layer forward pass (`TransformerLayer`) with streamed weights | You / Argon | ✅ | 3.1–3.4 |
| 3.6 | Validate single-layer output against reference implementation (`tests/test_layer.py`) | QA/QC / Argon | ✅ | 3.5 |

#### **Success Criteria**
- [x] `rmsnorm`, `rope`, `gqa_attention`, and `swiglu` HIP kernels compile and pass unit tests on `gfx1150`
- [x] Single transformer layer forward pass (prefill and single-token decode) matches CPU/PyTorch reference within FP16 tolerance
- [x] Layer weights are loaded, used in fused Q4 projections, and evicted cleanly

#### **Deliverables**
- ✅ [src/kernels/rmsnorm.h](src/kernels/rmsnorm.h) & [src/kernels/rmsnorm.hip](src/kernels/rmsnorm.hip) (Root Mean Square Layer Normalization)
- ✅ [src/kernels/rope.h](src/kernels/rope.h) & [src/kernels/rope.hip](src/kernels/rope.hip) (Rotary Positional Embeddings)
- ✅ [src/kernels/attention.h](src/kernels/attention.h) & [src/kernels/attention.hip](src/kernels/attention.hip) (Grouped-Query Attention with Wave32 online softmax)
- ✅ [src/kernels/mlp.h](src/kernels/mlp.h) & [src/kernels/mlp.hip](src/kernels/mlp.hip) (SwiGLU elementwise activation)
- ✅ [src/layer.py](src/layer.py) (Single transformer layer execution pipeline)
- ✅ [tests/test_layer.py](tests/test_layer.py) (Component and end-to-end single-layer tests)

---

### **🟢 Phase 4: Full Model End-to-End Inference** *(COMPLETED)*
**Goal**: Run end-to-end token generation for a complete GGUF model with double-buffered SSD prefetching and GQA KV caching.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 4.1 | Implement GGUF tokenizer & token embedding lookup | Argon / Local 7B | ✅ | Phase 3 |
| 4.2 | Implement GQA KV cache manager (GPU-resident offset pool, zero host copies) | Argon / GLM5.3 | ✅ | Phase 3 |
| 4.3 | Implement ping-pong double-buffered layer pipeline (overlap SSD prefetch of Layer $L+1$ with GPU compute of Layer $L$) | You / Argon | ✅ | Phase 2, 3 |
| 4.4 | Implement LM head projection + Top-K / Top-P / Temperature token sampler | Argon | ✅ | 4.1 |
| 4.5 | End-to-end test & benchmark with multi-layer GGUF model (`tests/test_full_model.py`) | QA/QC / Argon | ✅ | 4.1–4.4 |

#### **Success Criteria**
- [x] Generate coherent tokens end-to-end from a 4-bit GGUF model
- [x] Throughput > 0.5 tokens/sec
- [x] Peak RAM/GTT usage stays flat across all layers (zero per-step host KV slice copies)

#### **Deliverables**
- ✅ [src/tokenizer.py](src/tokenizer.py) (GGUF metadata tokenizer, detokenizer & row-wise Q4_0 embedding lookup)
- ✅ [src/kv_cache.py](src/kv_cache.py) (GPU-resident offset-addressed Grouped-Query Attention KV cache manager)
- ✅ [src/inference.py](src/inference.py) (Full model generation loop with ping-pong prefetching & sampling)
- ✅ [tests/test_full_model.py](tests/test_full_model.py) (End-to-end generation and KV cache validation)

---

### **🟢 Phase 5: Polish, Quantization Extensions & Scale to 70B** *(COMPLETED)*
**Goal**: Add `Q4_K_M` / `Q8_0` k-quant support, CPU/mmap KV-cache offloading for long contexts, chunked prefill & batching, and package as an installable CLI/library.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 5.1 | Add `Q4_K_M` (`Q4_K` 256-element super-block) and `Q8_0` HIP kernels | Argon / GLM5.3 | ✅ | Phase 4 |
| 5.2 | Add chunked prompt prefill (`prefill_chunk_size`) & sequential multi-prompt batch processing (`generate_batch`) | You / Argon | ✅ | Phase 4 |
| 5.3 | Add CPU RAM & NVMe `mmap` offload options for large KV caches (long context research runs) | You / Argon | ✅ | Phase 4 |
| 5.4 | Validate & benchmark `Q4_K` / `Q8_0` & 70B-dimension (`K=8192`) kernels (`tests/test_phase5_scale.py`) | QA/QC / Argon | ✅ | 5.1–5.3 |
| 5.5 | Package as installable Python package (`pyproject.toml` + `setup.py` CMake hook) + `gfx1150-infer` CLI | You / Argon | ✅ | Phase 4 |

#### **Success Criteria**
- [x] `dequantize_q8_0` and `dequantize_q4_k` match CPU reference with `max_error = 0.000000`
- [x] Fused Wave32 `matmul_q4_k` executes 70B hidden dimension (`1×1024×8192`) in `2.76 ms` (`max_error < 2e-3`)
- [x] Mixed `Q4_K_M` (`Q4_K` + `Q8_0`), chunked prefill, and CPU/`mmap` KV-cache offload pass equivalence tests
- [x] Installable via `pip install -e .` with `gfx1150-infer` CLI entry point

#### **Deliverables**
- ✅ [src/kernels/dequantize.h](src/kernels/dequantize.h) & [src/kernels/dequantize.hip](src/kernels/dequantize.hip) (`Q8_0` and `Q4_K` super-block dequantization & Wave32 fused matmul kernels)
- ✅ [src/kv_cache.py](src/kv_cache.py) (GPU pool, CPU RAM offload, and NVMe `mmap`-backed KV cache modes)
- ✅ [src/inference.py](src/inference.py) (Chunked prefill, batch inference, global tensor page eviction, and `gfx1150-infer` CLI)
- ✅ [pyproject.toml](pyproject.toml) & [setup.py](setup.py) (Python package, CMake `build_ext` hook, & CLI entry point configuration)
- ✅ [tests/test_phase5_scale.py](tests/test_phase5_scale.py) (Phase 5 k-quant, 70B-dimension, chunked prefill, and KV-offload validation suite)

---

### **🟢 Phase 6 (`v0.6.0`): Security Hardening, Device-Resident Layer Pipeline & CI** *(COMPLETED)*
**Goal**: Remediate all findings from the v0.5.0 independent audits ([AUDIT_REPORT_v0.5.0.md](audit/AUDIT_REPORT_v0.5.0.md) and [AUDIT_REMEDIATION_v0.6.0.md](audit/AUDIT_REMEDIATION_v0.6.0.md)): harden GGUF parsing and `mmap` KV-cache lifecycle against malformed/truncated inputs, eliminate per-op host-device activation round-trips and host `.T` weight transposes, add `TILE_M = 4` multi-row quantized prefill kernels, optimize CPU tokenization/embeddings, and establish CPU-only CI.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 6A.1 | GGUF tensor bounds validation (`S-1` / `A-5`), metadata/alignment caps (`S-2`), and private `memoryview` wrapper lifecycle (`D-3`) | Argon | ✅ | Phase 5 |
| 6A.2 | `KVCacheManager` `O_CREAT \| O_EXCL` `mmap` file safety (`S-3`) & `__del__` `RuntimeWarning` (`D-4` / `A-4`) | Argon | ✅ | Phase 5 |
| 6A.3 | Build & packaging cleanup (`D-1` / `A-1`, `D-2`) and Top-P underflow guard (`D-5`) | Argon | ✅ | Phase 5 |
| 6B.1 | $O(L \log L)$ priority-queue BPE merge (`P-4`) & vectorized, bounds-checked `embed_tokens` (`P-5`) | Argon | ✅ | Phase 5 |
| 6B.2 | Multi-span layer page eviction `get_layer_byte_spans` (`P-8` / `A-3`) & CPU-only test suite + CI (`D-6` / `A-7`) | Argon | ✅ | 6A.1–6B.1 |
| 6C.1 | Native-layout FP16 `matmul_nt` kernels (`P-2`), dead `matmul_kernel` removal (`P-10`), `size_t` GQA indexing (`P-6` / `A-2`), and host-cached RoPE `inv_freq` (`P-7`) | Argon | ✅ | Phase 5 |
| 6C.2 | Multi-row (`TILE_M = 4`) quantized prefill Wave32 kernels for `Q4_0`, `Q8_0`, and `Q4_K` (`P-3`) | Argon | ✅ | Phase 5 |
| 6C.3 | Fused `rmsnorm_residual` + `residual_add` kernels (`6C-i`) and C++-owned device-resident layer pipeline `forward_layer_cached` with D2D KV-cache writes (`6C-ii` / `P-1`) | Argon | ✅ | 6C.1–6C.2 |

#### **Success Criteria**
- [x] Truncated or malformed GGUF files raise `ValueError` at parse time with zero `SIGBUS` or leaked file descriptors — the nested metadata-array class tracked as BLOCKER-7A4-1 was fixed by 7A-9 (`audit/evidence/G1/7A-9/`); the parser is fail-closed for every malformed class the suite covers
- [x] `TILE_M = 4` quantized prefill kernels match `M = 1` Wave32 kernels with `max_diff == 0.0` across `Q4_0`, `Q8_0`, and `Q4_K`
- [x] C++-owned device-resident layer pipeline (`forward_layer_cached`) increases end-to-end throughput on `tests/test_full_model.py` from `~224 tok/s` to **`983.4 tok/s` (`decode: 1107.9 tok/s`)**
- [x] Self-contained CPU-only test suite ([tests/test_cpu_only.py](tests/test_cpu_only.py)) passes under both `python3` and `python3 -O`

#### **Deliverables**
- ✅ [src/gguf_parser.py](src/gguf_parser.py), [src/weight_loader.py](src/weight_loader.py), [src/kv_cache.py](src/kv_cache.py), [src/tokenizer.py](src/tokenizer.py) (Hardened parser, multi-span `madvise`, `O_EXCL` mmap safety, $O(L \log L)$ BPE, vectorized embeddings)
- ✅ [src/kernels/matmul.hip](src/kernels/matmul.hip), [src/kernels/dequantize.hip](src/kernels/dequantize.hip), [src/kernels/rmsnorm.hip](src/kernels/rmsnorm.hip), [src/kernels/rope.hip](src/kernels/rope.hip), [src/kernels/attention.hip](src/kernels/attention.hip) (`matmul_nt`, `TILE_M=4` prefill, `rmsnorm_residual`, `forward_layer_cached`)
- ✅ [tests/test_cpu_only.py](tests/test_cpu_only.py) & [.github/workflows/ci-cpu.yml](.github/workflows/ci-cpu.yml) (CPU-only regression suite & GitHub Actions workflow)

---

## 📊 Performance Targets

| **Model** | **Quantization** | **SSD Size** | **Active RAM Cap** | **Target Tokens/sec** | **Estimated Time for 1K Tokens** |
|-----------|------------------|--------------|--------------------|-----------------------|-----------------------------------|
| 7B        | `Q4_0` / `Q4_K`  | ~3.8 GB      | < 1.5 GB           | 5–10                  | 2–4 minutes                       |
| 13B       | `Q4_0` / `Q4_K`  | ~7.3 GB      | < 2.0 GB           | 2–5                   | 5–10 minutes                      |
| 30B       | `Q4_0` / `Q4_K`  | ~16.5 GB     | < 3.0 GB           | 0.5–1.5               | 15–35 minutes                     |
| 70B       | `Q4_0` / `Q4_K`  | ~38.0 GB     | < 4.5 GB           | 0.1–0.5               | 1–3 hours                         |

---

### 🟣 Phase 7 (`v0.6.2` → v0.7.0): Testing Phase & Evidence Gates *(IN PROGRESS)*
**Goal**: Convert the ad-hoc GPU test scripts into a gated, reproducible test phase with golden data, fuzzing, sdist-install CI, and a self-hosted gfx1150 hardware gate — per the finalized [audit/AUDIT_REMEDIATION_v0.6.2.md](audit/AUDIT_REMEDIATION_v0.6.2.md) §6 backlog and the independent review of `c75914b`.

> **Execution is governed by [PHASE7_IMPLEMENTATION_HANDOFF.md](PHASE7_IMPLEMENTATION_HANDOFF.md).** That document defines the coder/QAQC/auditor roles, the one-work-package-per-gate workflow, hard stop points, the evidence contract, and the handoff templates. This section is the roadmap summary only.

#### Sub-phases and gates

| Phase | Focus | Gate | Stop after |
|---|---|---|---|
| **7.0** | Freeze baseline; record environment; verify current green state; create evidence layout and claims ledger | **G0** | Baseline signed; tree clean; all suites recorded |
| **7A** | Test infrastructure: pytest harness + markers, golden data with provenance, parser fuzz, CPU/sdist-install CI, GPU CI scaffold (`continue-on-error`), claims checker + baseline, clean-clone build entry point (7A-8, C-1) | **G1** | Tests provably fail on parent; CI + sdist install green; GPU workflow exists; claims checker default mode green; documented `cmake` succeeds from a fresh clone; no `src/` diff |
| **7B** | Tokenizer P0: special-token encode, `add_bos_token`, GPT-2 spec regex, uniform byte fallback | **G2** | Golden vectors pass; no silent byte loss |
| **7C** | Model families P0: `ModelSpec`/tensor map, Phi-3 fused QKV, Gemma scale/soft-cap/key length, honest compatibility matrix | **G3** | Per-arch fixtures + reference logits pass; llama unchanged |
| **7D** | Memory honesty & robustness: `posix_fadvise`/`MADV_PAGEOUT`, budgeted residency policy, KV clamp, crash-safe files, exception masking | **G4** | Memory behavior matches docs; hostile inputs fail closed |
| **7E** | Stream topology: compute stream + events, double-buffered staging, pinned host, sync-before-free | **G5** | Event graph reviewed; race/stress test passes; overlap evidenced |
| **7F** | Evidence & release: promote GPU CI to required, real-GGUF golden tokens/logits, benchmark baseline, telemetry, **release-blocking claims check with empty baseline** | **G6** | CPU+GPU CI green with GPU required; claims `--strict` green; auditor release signoff |
| **7G** | Post-release P2 polish (packaging, flash attention, RoPE scaling/SWA, batching) — **deferred** | **G7** | Only after v0.7.0 ships |

#### Merge discipline
- Only the auditor-approved SHA is merged; QAQC reviews a frozen commit and does not accept force-pushes mid-gate.
- One work package per branch/PR (`wp/<id>-<slug>`); no bundling of P0 correctness with P2 performance work.
- Release notes carry the verified scope verbatim: **text-only llama-family `Q4_0`/`Q4_K`/`Q8_0` GGUFs on gfx1150**; no Qwen2/Llama-3-chat, Phi-3, or Gemma claims until G2/G3 evidence exists, and no throughput numbers until G6.
- The GPU workflow (7A-7) is `continue-on-error` only until the self-hosted runner registers; **7F-1 makes it required**. The claims checker (7A-6) runs baseline-aware in CI and becomes **release-blocking at G6 with an empty `audit/claims_baseline.txt`**.
- A gate failure triggers the stop conditions and blocker report defined in the handoff document; do not "fix forward" silently.

> **G1 status (2026-11-04; revised 2026-11-06):** **signed with conditions** — all 7A packages accepted; see `audit/G1_SIGNOFF_2026-11-04.md`. The post-G1 P0 parser fix **7A-9 (BLOCKER-7A4-1)** landed and was independently accepted (`audit/AUDIT_7A-9_PARSER_FIX_DEEP_2026-11-04.md`); **C-G1-1/C-G1-2 are closed**, and the parser may be described as fail-closed for the malformed classes the suite covers. **7B tokenizer is G2-signed (2026-11-06)** after the reference-faithful greedy-merge remediation (`audit/G2_SIGNOFF_2026-11-06.md`); **C-G1-4 is closed**. The only remaining G1 carry-forward is **C-G1-3** (GPU runner via 7F-1). Release/G6 remains gated by G3 and the later phases.

---

### ⚪ Phase 8 (Stretch, post-v0.7.0): AMD Radeon 780M / `gfx1103` Portability *(PROPOSED — NOT COMMITTED)*

**Status:** stretch goal only. It is **not** part of v0.7.0, does not affect G1/G6, and starts only after v0.7.0 ships and the owner prioritizes it. No hardware, performance, or CI claim is made until the acceptance evidence below exists.

**Why:** ROCm now exposes `gfx1103` (Radeon 780M, RDNA3 integrated GPU). The engine currently hardcodes `gfx1150` in `CMakeLists.txt`, but the kernels are largely Wave32 and architecture-neutral. A port should be mostly build-target selection, portability auditing, validation, and retuning — not a rewrite.

**Target:** Radeon 780M / `gfx1103` (Ryzen 7040/8040-class APUs). Confirm the exact ROCm distribution/version that lists `gfx1103` at implementation time. Prefer the native target; if a documented fallback such as `HSA_OVERRIDE_GFX_VERSION` is ever required, document it explicitly rather than using it silently.

#### Proposed work packages

| ID | Task | Acceptance |
|---|---|---|
| 8.1 | Build-target selection: add a `GFX_ARCH` cache variable (default `gfx1150`) feeding `CMAKE_HIP_ARCHITECTURES`; support `gfx1103` and optional multi-arch (`gfx1150;gfx1103`). Keep the existing default and documented command working unchanged. | Clean configure with `-DGFX_ARCH=gfx1103` and no ambient `pybind11_DIR`; `rocminfo` reports `gfx1103`; the default `gfx1150` build is unchanged. |
| 8.2 | Kernel portability audit: check workgroup assumptions, Wave32 shuffles, LDS/occupancy, CU-count/tile thresholds, cache behavior, and any `gfx1150`-specific constants or intrinsics. Use `__gfx1103__`/architecture guards only where a measured difference requires them. | Every kernel compiles for both targets; no silent arch fallback; a written portability matrix names any guarded code and why. |
| 8.3 | Validation: run the CPU suite, all five GPU suites, quantization paths, GGUF/claims checks on a 780M host; compare correctness with the gfx1150 baseline and CPU references. | On `gfx1103`: GPU lane **18 passed / 0 skipped**, CPU 12/12, claims checker green. The full `gfx1150` suite still passes (no regression). Evidence is recorded per gate. |
| 8.4 | Performance: retune tile sizes, workgroup counts, and memory thresholds for the 780M (fewer CUs and different clocks/bandwidth than the 890M). Record a separate 780M baseline; do not reuse gfx1150 throughput figures or claim a cross-GPU ratio. | Warm-up + ≥20-iteration medians/p95 per 7F-3 discipline; 780M numbers recorded separately; no unverified performance claim in README. |
| 8.5 | CI and docs: add an optional gfx1103 runner/manual gate (or document a manual hardware gate until one exists); publish an honest compatibility matrix (arch × quant × context) and build instructions. | Matrix names exactly what was tested on gfx1103 vs gfx1150; no CI claim without a registered runner; `gfx1150` remains the primary target. |
| 8.6 | Optional packaging: multi-arch fat binary or target-specific wheels, if the multi-arch build is practical; otherwise document the single-target build. | Packaging decision recorded; sdist/app install still works for the default target. |

#### Acceptance criteria (all required before any support claim)

- [ ] `cmake -B build -DCMAKE_BUILD_TYPE=Release -DGFX_ARCH=gfx1103` succeeds from a clean clone with only documented prerequisites, and the resulting extension loads on a 780M.
- [ ] All five GPU suites pass on `gfx1103` with **no skips**; CPU suite and claims checker unchanged.
- [ ] The full `gfx1150` suite still passes; no gfx1150 release regression.
- [ ] No hardcoded `gfx1150` remains outside the documented default; `gfx1103` is a first-class build target.
- [ ] Compatibility matrix and README are honest about what was actually run.
- [ ] Performance is recorded on the 780M separately; no gfx1150 number is presented as a 780M result.
- [ ] Evidence bundle and independent audit/QAQC signoff follow the same Phase 7 handoff discipline.

#### Risks and non-goals

- **Risks:** ROCm/package support for `gfx1103` varies by distribution; RDNA3 and RDNA3.5 are close but not identical (CU count, clocks, bandwidth, cache/occupancy); gfx1150-tuned tiles may be suboptimal or incorrect on 780M; a 780M CI runner may not exist; multi-arch binaries are larger; thermal/power behavior differs on laptops.
- **Non-goals:** NPU (`aie2p`) support, multi-GPU, 780M-specific maximum-performance tuning, other RDNA3 iGPUs, or expanding the supported model/quant scope. Those would need separate proposals.
- **Entry/exit:** only after v0.7.0 ships; new branch/work packages and a G8 gate; `gfx1150` remains the release baseline throughout.

---

## 📅 Milestones

| **Phase** | **Focus** | **Status** |
|-----------|-----------|------------|
| Phase 1   | Hello `gfx1150` (HIP FP16 Matmul + PyBind11) | ✅ Complete (1.12 TFLOPS) |
| Phase 2   | GGUF Parser + `madvise` SSD Streaming + Fused `Q4_0` Kernels | ✅ Complete |
| Phase 3   | Llama Layer Kernels (RMSNorm, RoPE, GQA, SwiGLU) | ✅ Complete |
| Phase 4   | End-to-End Model Inference + KV Cache + Tokenizer | ✅ Complete |
| Phase 5   | K-Quants (`Q4_K_M` / `Q8_0`), 70B Scaling, KV Offload & Packaging | ✅ Complete |
| Phase 6 (`v0.6.0`) | Audit Remediation, Security Hardening, Device-Resident Pipeline & CPU CI | ✅ Complete (983.4 tok/s synthetic E2E, owner-verified) |
| Phase 7 (`v0.6.2`→v0.7.0) | Testing phase: pytest conversion, golden data, fuzz, sdist-install CI, self-hosted gfx1150 gate, P0/P1 fixes gated by tests | 🟡 In progress |
| Phase 8 (stretch) | AMD Radeon 780M / `gfx1103` portability: configurable build target, kernel portability audit, dual-GPU validation, separate 780M performance baseline, honest compatibility matrix | ⚪ Proposed (post-v0.7.0; not committed) |
