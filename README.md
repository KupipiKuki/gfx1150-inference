# gfx1150-inference

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / Ryzen AI 9 HX 370)**

Built with **ROCm, HIP, and memory-mapped I/O (`mmap` + `madvise`)** for overnight research workloads.

---

## 🚀 **Project Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Ryzen AI 370) by **streaming quantized weights (`Q4_0`, `Q4_K_M` (`Q4_K` + `Q6_K`), `Q8_0`) directly from NVMe SSD**, enabling inference on unified-memory hardware without OOM errors.

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
├── PHASE7_IMPLEMENTATION_HANDOFF.md
├── PHASE7_7A_CODER_BRIEF.md
├── PHASE7_7A-1_FOLLOWUP_BRIEF.md
├── LESSONS_LEARNED.md
├── audit/                     # audit & remediation reports
│   ├── AUDIT_REPORT_v0.5.0.md
│   ├── AUDIT_REPORT_DEEP_2026-10-31.md
│   ├── AUDIT_REMEDIATION_v0.6.0.md
│   ├── AUDIT_REMEDIATION_v0.6.1.md
│   ├── REVIEW_v0.6.1_c75914b.md
│   ├── AUDIT_REMEDIATION_v0.6.2.md
│   ├── VERIFICATION_2026-11-01.md
│   ├── CLAIMS_LEDGER.md
│   ├── claims_baseline.txt
│   ├── evidence/
│   ├── remediation_plan.md
│   ├── HANDOFF_PHASE2.md
│   └── QAQC_FINAL_REPORT_PHASE5.md
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
    ├── test_cpu_only.py
    ├── test_matmul.py
    ├── test_gguf_and_q4.py
    ├── test_layer.py
    ├── test_full_model.py
    ├── test_phase5_scale.py
    └── fixtures/
        └── PROVENANCE.md
```

---

## 🛠️ Build, Install & Test

### 1. CMake Build & Test Suite
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
python3 tests/test_cpu_only.py
PYTHONPATH=build python3 tests/test_matmul.py
PYTHONPATH=build:src python3 tests/test_gguf_and_q4.py
PYTHONPATH=build:src python3 tests/test_layer.py
PYTHONPATH=build:src python3 tests/test_full_model.py
PYTHONPATH=build:src python3 tests/test_phase5_scale.py
```

### 2. Editable Python Package & CLI Installation
`setup.py` invokes `cmake` automatically during `pip install` to compile the `matmul_module` HIP extension.
Use `--no-build-isolation` so the build uses the host's installed `cmake`, `pybind11`, and `/opt/rocm` toolchain (full PEP 517 isolated builds require `cmake` and ROCm headers/compilers to be visible inside the isolated build environment):
```bash
pip install -e . --no-build-isolation
gfx1150-infer --model /path/to/model.gguf --prompt "Hello" --max-new-tokens 32
```

---

## ⚙️ Runtime Modes & Architecture Notes
- **Weight Residency Policy (`WeightStreamer(cache_weights=...)` / `--cache-weights`)**:
  - **Default (`cache_weights=False`)**: Issues `MADV_WILLNEED` ahead of layer execution and `MADV_DONTNEED` after layer completion to advise the Linux kernel to reclaim clean file-backed page-cache pages for 70B models that exceed physical RAM.
  - **`--cache-weights` (`cache_weights=True`)**: Skips `MADV_DONTNEED` eviction so models that fit in unified RAM (e.g. 7B–30B on 32 GB+ APUs) stay warm in the OS page cache across decode tokens.
- **KV Cache Storage Modes (`KVCacheManager`)**:
  - **Default (GPU-resident pool)**: Pre-allocates the GQA KV cache in GPU/GTT memory (`kv_cache_init` / `gqa_attention_cached`); `forward_layer_cached` keeps layer activations on-device and updates K/V via D2D `hipMemcpyAsync`.
  - **`--offload-kv-cpu` / `--kv-mmap-dir <dir>`**: Memory-saving modes for ultra-long-context 70B runs. Keeps persistent GPU KV pool usage at `0` bytes by storing the KV cache in host RAM or a private (`0600`, `O_NOFOLLOW`) disk-backed `mmap` file, trading per-step H2D KV transfer bandwidth (`O(context_len)`) for a minimal GPU memory footprint.
- **Tokenizer & Architecture Support**:
  - Supports both SentencePiece (`▁`) and GPT-2 / Llama-3 / Qwen2 byte-level (`Ġ`, `tokenizer.ggml.merges`) BPE vocabularies, `{arch}.*` GGUF metadata keys (`llama`, `qwen2`, `phi3`, `gemma`; only `llama` is in the verified release scope, and `qwen2`/`phi3`/`gemma` model support is **not yet verified**), and optional QKV attention biases (`blk.{i}.attn_{q,k,v,output}.bias`).
  - **Verified release scope:** text-only **llama-family `Q4_0` / `Q4_K` / `Q8_0`** GGUFs. Metadata for `qwen2`/`phi3`/`gemma` resolves, but those families are **not** yet fully supported: chat special-token encoding and `add_bos_token` are not implemented, Phi-3's fused `attn_qkv` is missing, and Gemma's embedding scale / logit soft-cap / `attention.key_length` are absent. See `audit/AUDIT_REMEDIATION_v0.6.2.md` §6 and `audit/VERIFICATION_2026-11-01.md` §4.
- **Sequential Multi-Prompt Batching (`generate_batch`)**: Processes multiple prompts sequentially while reusing the initialized `WeightStreamer` and `KVCacheManager` without re-allocating GPU/mmap resources.
- **Single-Engine / Thread-Guarded Workspaces**: Kernel device workspaces and `DeviceKVCachePool` use process-wide static buffers guarded by a C++ mutex (`g_hip_workspace_mutex`); only one active GPU-resident `LlamaInferenceEngine` / `KVCacheManager` instance is permitted per process at a time (enforced at runtime).
- **RoPE Layout Compatibility**: Supports both GGUF-Llama adjacent-pair rotation (default for `llama`) and NeoX half-dimension rotation (auto-detected from GGUF metadata `{arch}.rope.neox` / architecture or enabled via `--rope-neox`).
