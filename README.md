# gfx1150-inference

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / AI 370)**

Built with **ROCm, HIP, and memory-mapped I/O** for overnight research workloads.

---

## 🚀 **Project Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Instinct AI 370) by **streaming weights from SSD**, enabling inference on hardware with limited VRAM.

**Target Use Case**: Fact-checking and research tasks where **8-hour runtimes are acceptable**.

---

## 📌 **Phase 1: Hello gfx1150** *(Current Focus)*
**Goal**: Confirm gfx1150 works with a custom HIP kernel (matrix multiplication).

### ✅ Success Criteria
- [ ] ROCm 6.1+ detects gfx1150 (`rocminfo   grep gfx1150`)
- [ ] HIP kernel for FP16 matmul (1024×1024) compiles and runs
- [ ] Output matches PyTorch (`max_error < 1e-3`)
- [ ] Edge cases pass (non-square matrices, M=1, etc.)

### 📁 Structure