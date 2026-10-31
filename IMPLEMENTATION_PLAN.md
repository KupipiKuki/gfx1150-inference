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
| 1.6 | Document remediation & lessons learned | You / Argon | ✅ | `remediation_plan.md`, `LESSONS_LEARNED.md` |

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
- ✅ [remediation_plan.md](remediation_plan.md) & [LESSONS_LEARNED.md](LESSONS_LEARNED.md)

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
| 5.2 | Add chunked prompt prefill (`prefill_chunk_size`) & multi-batch processing (`generate_batch`) | You / Argon | ✅ | Phase 4 |
| 5.3 | Add CPU RAM & NVMe `mmap` offload options for large KV caches (long context research runs) | You / Argon | ✅ | Phase 4 |
| 5.4 | Validate & benchmark `Q4_K` / `Q8_0` & 70B-dimension (`K=8192`) kernels (`tests/test_phase5_scale.py`) | QA/QC / Argon | ✅ | 5.1–5.3 |
| 5.5 | Package as installable Python package (`pyproject.toml`) + `gfx1150-infer` CLI | You / Argon | ✅ | Phase 4 |

#### **Success Criteria**
- [x] `dequantize_q8_0` and `dequantize_q4_k` match CPU reference with `max_error = 0.000000`
- [x] Fused Wave32 `matmul_q4_k` executes 70B hidden dimension (`1×1024×8192`) in `2.76 ms` (`max_error < 2e-3`)
- [x] Mixed `Q4_K_M` (`Q4_K` + `Q8_0`), chunked prefill, and CPU/`mmap` KV-cache offload pass equivalence tests
- [x] Installable via `pip install -e .` with `gfx1150-infer` CLI entry point

#### **Deliverables**
- ✅ [src/kernels/dequantize.h](src/kernels/dequantize.h) & [src/kernels/dequantize.hip](src/kernels/dequantize.hip) (`Q8_0` and `Q4_K` super-block dequantization & Wave32 fused matmul kernels)
- ✅ [src/kv_cache.py](src/kv_cache.py) (GPU pool, CPU RAM offload, and NVMe `mmap`-backed KV cache modes)
- ✅ [src/inference.py](src/inference.py) (Chunked prefill, batch inference, global tensor page eviction, and `gfx1150-infer` CLI)
- ✅ [pyproject.toml](pyproject.toml) (Python package & CLI entry point configuration)
- ✅ [tests/test_phase5_scale.py](tests/test_phase5_scale.py) (Phase 5 k-quant, 70B-dimension, chunked prefill, and KV-offload validation suite)

---

## 📊 Performance Targets

| **Model** | **Quantization** | **SSD Size** | **Active RAM Cap** | **Target Tokens/sec** | **Estimated Time for 1K Tokens** |
|-----------|------------------|--------------|--------------------|-----------------------|-----------------------------------|
| 7B        | `Q4_0` / `Q4_K`  | ~3.8 GB      | < 1.5 GB           | 5–10                  | 2–4 minutes                       |
| 13B       | `Q4_0` / `Q4_K`  | ~7.3 GB      | < 2.0 GB           | 2–5                   | 5–10 minutes                      |
| 30B       | `Q4_0` / `Q4_K`  | ~16.5 GB     | < 3.0 GB           | 0.5–1.5               | 15–35 minutes                     |
| 70B       | `Q4_0` / `Q4_K`  | ~38.0 GB     | < 4.5 GB           | 0.1–0.5               | 1–3 hours                         |

---

## 📅 Milestones

| **Phase** | **Focus** | **Status** |
|-----------|-----------|------------|
| Phase 1   | Hello `gfx1150` (HIP FP16 Matmul + PyBind11) | ✅ Complete (1.12 TFLOPS) |
| Phase 2   | GGUF Parser + `madvise` SSD Streaming + Fused `Q4_0` Kernels | ✅ Complete |
| Phase 3   | Llama Layer Kernels (RMSNorm, RoPE, GQA, SwiGLU) | ✅ Complete |
| Phase 4   | End-to-End Model Inference + KV Cache + Tokenizer | ✅ Complete |
| Phase 5   | K-Quants (`Q4_K_M` / `Q8_0`), 70B Scaling, KV Offload & Packaging | ✅ Complete |
