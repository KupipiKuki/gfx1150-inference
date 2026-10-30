# gfx1150-inference: Implementation Plan

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / AI 370)**

Built with **ROCm, HIP, and memory-mapped I/O** for overnight research workloads.

---

## 🎯 Project Overview

### **Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Instinct AI 370) by **streaming weights from SSD**, enabling inference on hardware with limited VRAM.

### **Target Use Case**
- **Overnight research/fact-checking** (8-hour runtimes acceptable)
- **Single-GPU** operation (no multi-GPU requirements)
- **Memory-efficient** via SSD offloading and quantization

### **Tech Stack**
| Component | Technology | Purpose |
|-----------|------------|---------|
| GPU Backend | ROCm 6.1+ + HIP | AMD GPU compute |
| Compute Kernels | Custom HIP C++ | Optimized matmul/attention |
| Weight Storage | Memory-mapped files (`mmap`) | Zero-copy SSD access |
| Model Format | GGML (4-bit) | Quantized weights |
| Language | Python (frontend) + C++ (kernels) | Best of both worlds |
| Build System | CMake + PyBind11 | Cross-platform |

---

## 📋 Phase Breakdown

---

### **🟢 Phase 1: Hello gfx1150** *(COMPLETED)*
**Goal**: Confirm gfx1150 works with custom HIP kernels.

#### **Tasks**
| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.1 | Verify ROCm 6.1+ installation | You | ✅ | `rocminfo \| grep gfx1150` |
| 1.2 | Write FP16 matmul HIP kernel | GLM5.3 | ✅ | `src/kernels/matmul.hip` |
| 1.3 | Add PyBind11 bindings | GLM5.3 | ✅ | `src/python_bindings/bindings.cpp` |
| 1.4 | Configure CMake build system | You | ✅ | `CMakeLists.txt` |
| 1.5 | Write test suite | Local 7B | ✅ | `tests/test_matmul.py` |
| 1.6 | Debug ROCm/HIP paths | You | ✅ | Fixed `hipconfig.cmake` paths |
| 1.7 | Fix gitignore for .hip files | You | ✅ | Removed `*.hip` from ignore |

#### **Success Criteria**
- [x] ROCm detects gfx1150
- [x] HIP kernel compiles without errors
- [x] Matmul output matches PyTorch (max error < 1e-3)
- [x] Edge cases pass (non-square, small matrices)
- [x] Throughput > 1 TFLOPS (FP16)

#### **Deliverables**
- ✅ `CMakeLists.txt` (ROCm + PyBind11 config)
- ✅ `src/kernels/matmul.hip` (FP16 matmul kernel)
- ✅ `src/python_bindings/bindings.cpp` (PyBind11 wrapper)
- ✅ `tests/test_matmul.py` (validation tests)
- ✅ Updated `README.md` (Phase 1 docs)

#### **Lessons Learned**
- ROCm HPC SDK installs to `/opt/rocm/core-10.1/` or `/opt/rocm/`
- `hipconfig.cmake` may be in `/opt/rocm/lib/cmake/hip/`
- `*.hip` files are **source code** (not binaries) → should **NOT** be gitignored
- `HSA_OVERRIDE_GFX_VERSION=11.5.0` can force gfx1150 detection
- pybind11 requires `find_package(Python COMPONENTS Interpreter Development REQUIRED)`

---

### **🟡 Phase 2: GGML Parser + SSD Loading** *(NEXT)*
**Goal**: Load quantized model weights from SSD using memory-mapped I/O.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 2.1 | Research GGML format specification | You | ⏳ | None |
| 2.2 | Write GGML parser in Python | Local 7B | ⏳ | 2.1 |
| 2.3 | Add memory-mapped file loading | GLM5.3 | ⏳ | 2.2 |
| 2.4 | Implement 4-bit dequantization | GLM5.3 | ⏳ | 2.2 |
| 2.5 | Write HIP kernel for dequantization | GLM5.3 | ⏳ | 2.4 |
| 2.6 | Add weight streaming logic | You | ⏳ | 2.3, 2.5 |
| 2.7 | Test with Llama-2-7B-4bit | QA/QC | ⏳ | 2.6 |

#### **Success Criteria**
- [ ] Parse GGML headers correctly
- [ ] Memory-map model weights from SSD
- [ ] Dequantize 4-bit weights on GPU
- [ ] Stream weights for one layer at a time
- [ ] Load Llama-2-7B-4bit without OOM errors

#### **Deliverables**
- `src/kernels/ggml_parser.py` (GGML format handling)
- `src/kernels/dequantize.hip` (4-bit dequantization kernel)
- `src/weight_loader.py` (SSD streaming logic)
- `tests/test_ggml.py` (parser validation)

#### **Technical Details**
```python
# Pseudocode for weight streaming
class WeightStreamer:
    def __init__(self, model_path):
        self.file = open(model_path, "rb")
        self.mmap = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        self.ggml = GGMLParser(self.mmap)

    def load_layer(self, layer_idx):
        weights = self.ggml.get_layer_weights(layer_idx)
        return self._dequantize(weights)  # On GPU via HIP
```

---

### **🟡 Phase 3: Layer-wise Inference**
**Goal**: Implement forward pass for a single transformer layer with SSD-streamed weights.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 3.1 | Implement attention kernel | GLM5.3 | ⏳ | Phase 2 |
| 3.2 | Implement MLP kernel | GLM5.3 | ⏳ | Phase 2 |
| 3.3 | Add layer normalization | GLM5.3 | ⏳ | Phase 2 |
| 3.4 | Write inference loop for one layer | You | ⏳ | 3.1-3.3 |
| 3.5 | Test with single-layer model | QA/QC | ⏳ | 3.4 |

#### **Success Criteria**
- [ ] Attention kernel runs on gfx1150
- [ ] MLP kernel runs on gfx1150
- [ ] Layer-wise inference produces correct outputs
- [ ] Weights are loaded/evicted correctly

#### **Deliverables**
- `src/kernels/attention.hip` (attention kernel)
- `src/kernels/mlp.hip` (MLP kernel)
- `src/kernels/layer_norm.hip` (layer norm kernel)
- `src/inference.py` (main inference loop)
- `tests/test_layer.py` (layer validation)

---

### **🟡 Phase 4: Full Model Inference**
**Goal**: Run end-to-end inference for a complete model with all weights streamed from SSD.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 4.1 | Implement token generation loop | You | ⏳ | Phase 3 |
| 4.2 | Add KV cache management | GLM5.3 | ⏳ | Phase 3 |
| 4.3 | Optimize SSD I/O (prefetching) | You | ⏳ | Phase 3 |
| 4.4 | Test with Llama-2-7B | QA/QC | ⏳ | 4.1-4.3 |
| 4.5 | Benchmark performance | You | ⏳ | 4.4 |

#### **Success Criteria**
- [ ] Generate 100 tokens from Llama-2-7B
- [ ] Throughput > 0.5 tokens/sec
- [ ] No GPU OOM errors
- [ ] SSD I/O < 50% of total time

#### **Deliverables**
- Updated `src/inference.py` (full model support)
- `src/kernels/kv_cache.hip` (KV cache management)
- `tests/test_full_model.py` (end-to-end validation)
- Performance benchmarks

---

### **🟡 Phase 5: Polish and Scale**
**Goal**: Optimize performance, add features, and prepare for production use.

#### **Tasks**
| # | Task | Owner | Status | Dependencies |
|---|------|-------|--------|--------------|
| 5.1 | Optimize HIP kernels (tuning) | GLM5.3 | ⏳ | Phase 4 |
| 5.2 | Add multi-batch support | You | ⏳ | Phase 4 |
| 5.3 | Support 8-bit quantization | GLM5.3 | ⏳ | Phase 4 |
| 5.4 | Add CPU offload for KV cache | You | ⏳ | Phase 4 |
| 5.5 | Test with 13B/30B/70B models | QA/QC | ⏳ | Phase 4 |
| 5.6 | Package as Python library | You | ⏳ | Phase 4 |
| 5.7 | Write documentation | You | ⏳ | Phase 4 |

#### **Success Criteria**
- [ ] 70B model runs without OOM
- [ ] Throughput > 0.1 tokens/sec for 70B
- [ ] Python package installable via `pip`
- [ ] Comprehensive documentation

#### **Deliverables**
- Optimized kernels
- `gfx1150_inference` PyPI package
- Full documentation
- CI/CD pipeline

---

## 👥 Roles & Workflow

| **Role** | **Assigned LLM** | **Responsibilities** | **Key Skills** |
|----------|------------------|----------------------|----------------|
| Project Architect | You | Define phases, milestones, design decisions | System design, tradeoff analysis |
| Primary Coder | GLM5.3 | Core kernels (HIP/C++), performance paths | HIP, C++, GPU optimization |
| Secondary Coder | Local 7B | Utilities, tests, prototyping | Python, quick iteration |
| QA/QC | Gemini Pro | Test cases, edge-case validation | Testing, debugging |
| Auditor | Kimi | Code reviews, ROCm compatibility | Code review, GPU architecture |

### **Workflow**
```
[Architect] → Defines task + success criteria
       ↓
[Primary Coder] → Implements core logic
       ↓
[Secondary Coder] → Parallel work (utilities, tests)
       ↓
[QA/QC] → Writes tests + validates edge cases
       ↓
[Auditor] → Reviews code, flags risks
       ↓
[Architect] → Approves merge or requests changes
```

---

## 📊 Performance Targets

| **Model** | **Quantization** | **SSD Size** | **Target Tokens/sec** | **Estimated Time for 1K Tokens** |
|-----------|------------------|--------------|-----------------------|-----------------------------------|
| 7B        | 4-bit            | ~3.5 GB      | 5–10                  | 2–4 minutes                       |
| 13B       | 4-bit            | ~7 GB        | 2–5                   | 5–10 minutes                      |
| 30B       | 4-bit            | ~15 GB       | 0.5–1                 | 30–60 minutes                     |
| 70B       | 4-bit            | ~35 GB       | 0.1–0.5               | 3–8 hours                         |

*(Assumes gfx1150 at ~20 TFLOPS FP16 and SSD at 6 GB/s.)*

---

## 📅 Milestones

| **Phase** | **Start Date** | **Target Completion** | **Status** |
|-----------|----------------|-----------------------|------------|
| Phase 1   | Today          | +1 week               | ✅ Complete |
| Phase 2   | After Phase 1  | +2 weeks              | ⏳ Pending |
| Phase 3   | After Phase 2  | +3 weeks              | ⏳ Pending |
| Phase 4   | After Phase 3  | +5 weeks              | ⏳ Pending |
| Phase 5   | After Phase 4  | +8 weeks              | ⏳ Pending |

---

## 🔗 Dependencies

### **Hardware**
- AMD GPU with gfx1150 (Radeon 890M, Instinct AI 370)
- SSD with >50 GB free (for 70B models)
- 16+ GB RAM (for staging)

### **Software**
- Ubuntu 22.04+ (recommended)
- ROCm 6.1+
- CMake 3.10+
- Python 3.8+
- PyTorch (for validation)
- PyBind11

---

## 📚 References
- [AMD ROCm Documentation](https://docs.amd.com/en/latest/)
- [HIP Programming Guide](https://docs.amd.com/en/latest/ROCm_HIP_v6.1.0/hip-programming-guide.html)
- [GGML Format Specification](https://github.com/ggerganov/ggml/blob/master/docs/ggml.md)
- [PyBind11 Documentation](https://pybind11.readthedocs.io/)
- [CMakeLists.txt for HIP](https://github.com/ROCm/ROCm/blob/develop/CMakeLists.txt)

---

## 📝 Notes
- This is a **living document**—update it as you progress through phases.
- Each phase should have its own **detailed design doc** (e.g., `PHASE2_DESIGN.md`).
- Track **blockers** and **decisions** in this file for future reference.
