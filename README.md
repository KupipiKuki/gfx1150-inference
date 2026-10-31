# gfx1150-inference

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / Ryzen AI 9 HX 370)**

Built with **ROCm, HIP, and memory-mapped I/O (`mmap` + `madvise`)** for overnight research workloads.

---

## 🚀 **Project Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Ryzen AI 370) by **streaming quantized weights (`Q4_0`, `Q4_K_M`, `Q8_0`) directly from NVMe SSD**, enabling inference on unified-memory hardware without OOM errors.

**Target Use Case**: Fact-checking and research tasks where **bounded memory footprint and 8-hour runtimes are prioritized**.

---

## 📁 Structure
```text
gfx1150-inference/
├── CMakeLists.txt
├── pyproject.toml
├── setup.py
├── README.md
├── IMPLEMENTATION_PLAN.md
├── LESSONS_LEARNED.md
├── remediation_plan.md
├── HANDOFF_PHASE2.md
├── QAQC_FINAL_REPORT_PHASE5.md
├── src/
│   ├── inference.py
│   ├── gguf_parser.py
│   ├── weight_loader.py
│   ├── layer.py
│   ├── kv_cache.py
│   ├── tokenizer.py
│   ├── kernels/
│   │   ├── matmul.h
│   │   ├── matmul.hip
│   │   ├── dequantize.h
│   │   ├── dequantize.hip
│   │   ├── rmsnorm.h
│   │   ├── rmsnorm.hip
│   │   ├── rope.h
│   │   ├── rope.hip
│   │   ├── attention.h
│   │   ├── attention.hip
│   │   ├── mlp.h
│   │   └── mlp.hip
│   └── python_bindings/
│       └── bindings.cpp
└── tests/
    ├── test_matmul.py
    ├── test_gguf_and_q4.py
    ├── test_layer.py
    ├── test_full_model.py
    └── test_phase5_scale.py
```

---

## 🛠️ Build, Install & Test

### 1. CMake Build & Test Suite
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
PYTHONPATH=build python3 tests/test_matmul.py
PYTHONPATH=build:src python3 tests/test_gguf_and_q4.py
PYTHONPATH=build:src python3 tests/test_layer.py
PYTHONPATH=build:src python3 tests/test_full_model.py
PYTHONPATH=build:src python3 tests/test_phase5_scale.py
```

### 2. Editable Python Package & CLI Installation
`setup.py` invokes `cmake` automatically during `pip install` to compile the `matmul_module` HIP extension:
```bash
pip install -e . --no-build-isolation
gfx1150-infer --model /path/to/model.gguf --prompt "Hello" --max-new-tokens 32
```

---

## ⚙️ Runtime Modes & Architecture Notes
- **KV Cache Storage Modes (`KVCacheManager`)**:
  - **Default (GPU-resident pool)**: Pre-allocates the GQA KV cache in GPU/GTT memory (`kv_cache_init` / `gqa_attention_cached`); only the newly generated `q_len` K/V rows are copied H2D per step (`O(1)` per decode step).
  - **`--offload-kv-cpu` / `--kv-mmap-dir <dir>`**: Memory-saving modes for ultra-long-context 70B runs. Keeps persistent GPU KV pool usage at `0` bytes by storing the KV cache in host RAM or a disk-backed `mmap` file, trading per-step H2D KV transfer bandwidth (`O(context_len)`) for a minimal GPU memory footprint.
- **Sequential Multi-Prompt Batching (`generate_batch`)**: Processes multiple prompts sequentially while reusing the initialized `WeightStreamer` and `KVCacheManager` without re-allocating GPU/mmap resources.
- **Single-Engine / Single-Threaded Scope**: Kernel device workspaces and `DeviceKVCachePool` use process-wide static buffers; only one active GPU-resident `LlamaInferenceEngine` / `KVCacheManager` instance is permitted per process at a time (enforced at runtime).
- **RoPE Layout Compatibility**: Supports both GGUF-Llama adjacent-pair rotation (default for `llama`) and NeoX half-dimension rotation (auto-detected from GGUF metadata `llama.rope.neox` / architecture or enabled via `--rope-neox`).
