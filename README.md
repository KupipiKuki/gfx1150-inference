# gfx1150-inference

> **SSD-offloaded LLM inference engine for AMD gfx1150 (Radeon 890M / Ryzen AI 9 HX 370)**

Built with **ROCm, HIP, and memory-mapped I/O (`mmap` + `madvise`)** for overnight research workloads.

---

## 🚀 **Project Goal**
Run large language models (7B–70B parameters) on **AMD gfx1150 GPUs** (e.g., Radeon 890M, Ryzen AI 370) by **streaming quantized weights (`Q4_0`, `Q4_K_M` (`Q4_K` + `Q6_K`), `Q8_0`) directly from NVMe SSD** on unified-memory hardware. 7B-class models are verified on hardware; the 70B path exists but **no real 70B GGUF has ever been run** (UNVERIFIED — ledger ID 18; real-GGUF/70B evidence belongs to 7F-2), so no "without OOM" guarantee is claimed for 70B.

**Target Use Case**: Fact-checking and research tasks where a **small resident-memory footprint and long runtimes are prioritized**. Memory behavior is **best-effort** (kernel page-cache advice; see the residency policy below — it is not a hard RAM bound, ledger ID 14, withdrawn), and the 8-hour runtimes goal has **no endurance measurement yet** (UNVERIFIED — ledger ID 19; a timed soak with telemetry belongs to 7F-3/7F-4).

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
├── PHASE7_7A-6_FOLLOWUP_BRIEF.md
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
    ├── test_build_configure.py
    └── fixtures/
        └── PROVENANCE.md
```

---

## 🛠️ Build, Install & Test

### 0. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| ROCm | 6.x or newer | Provides the HIP compiler (`amdclang++`) and the HIP headers/runtime the extension is built against. The build looks for it in `/opt/rocm`; override with `-DROCM_ROOT=/path/to/rocm`. Install it with AMD's [package-manager instructions](https://rocm.docs.amd.com/en/latest/install/rocm.html). |
| Python | ≥ 3.10 | Needs the development headers (`Development.Module`): on Debian/Ubuntu, `python3-dev`. |
| `pybind11` | ≥ 2.12 | A build requirement, declared in `pyproject.toml`. Install it **for the interpreter you build with**: `python3 -m pip install "pybind11>=2.12"`. The configure step locates it there, so **no `pybind11_DIR` has to be set**. |
| CMake | ≥ 3.21 | `cmake --version`. |
| C++ compiler | any C++17 | Only the HIP toolchain is used for the kernels; a host C++ compiler is still needed for the build system itself. |

### 1. CMake Build & Test Suite

From a fresh clone, with the prerequisites above installed:
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

The configure step finds `pybind11` through the Python interpreter it selected, so the
command above works on a clean tree without exporting `pybind11_DIR` and without a
pre-existing CMake cache. `tests/test_build_configure.py` is the regression test for
that, and `.github/workflows/ci-build.yml` runs the same command on every push and pull
request.

### 2. Editable Python Package & CLI Installation
`setup.py` invokes `cmake` automatically during `pip install` to compile the `matmul_module` HIP extension.
Use `--no-build-isolation` so the build uses the host's installed `cmake`, `pybind11`, and `/opt/rocm` toolchain (full PEP 517 isolated builds require `cmake` and ROCm headers/compilers to be visible inside the isolated build environment):
```bash
pip install -e . --no-build-isolation
gfx1150-infer --model /path/to/model.gguf --prompt "Hello" --max-new-tokens 32
```

---

## ⚙️ Runtime Modes & Architecture Notes
- **Weight Residency Policy (Phase 7D / Gate G4: `--residency {auto,pin,stream}` / `WeightStreamer(policy=...)`)**:
  - **`auto` (default)**: keeps the model's file pages resident in the **host page cache** when the model's weight bytes fit the measured budget, and streams otherwise. Budget: `min(free GTT from AMDGPU sysfs, MemAvailable from /proc/meminfo, cgroup v2/v1 headroom) − KV bytes − activation estimate (hidden × max_seq_len × fp16 × 4 buffers + logits + 64 MiB) − 512 MiB safety margin`; unavailable sources are skipped and recorded, and **AUTO never invents a budget — with no readable source it fails safe to STREAM**. The decision and its reason are recorded on the engine (`residency_decision`).
  - **`pin` (explicit request)**: host page-cache residency, skipping eviction; **warns when the model exceeds the budget** (explicit user request). This is **not GTT pinning**: quantized weights are still copied host-to-device per projection in every policy, and no throughput claim is made for any policy. `--cache-weights` is a deprecated alias for `--residency pin` (`cache_weights=True` → PIN, `False` → AUTO); `--residency` wins if both are given.
  - **`stream`**: issues `MADV_WILLNEED` prefetch ahead of layer execution and **best-effort page-cache eviction** after each layer/tensor: `posix_fadvise(POSIX_FADV_DONTNEED)` on the model file descriptor as the primary page-cache hint, preceded by a PTE drop of the read-only mapping span (`MADV_PAGEOUT` when the host exposes it, else `MADV_DONTNEED`, which by itself only drops page-table entries and is *not* page-cache eviction) so the kernel can act on the hint. All of this is kernel best-effort advice, **not a hard RAM bound**. Measured on a synthetic model: eviction issues real page-cache drops (re-touch after eviction re-faults from disk; `audit/evidence/G4/7D/`), and RSS stays near-baseline under STREAM vs. ~model-size growth under PIN.
  - Reproducible-test/user overrides: `--residency-budget-mb` (fixed weight budget), `--max-kv-bytes` (KV user cap).
- **KV Cache Storage Modes (`KVCacheManager`)**:
  - **Default (GPU-resident pool)**: Pre-allocates the GQA KV cache in GPU/GTT memory (`kv_cache_init` / `gqa_attention_cached`); `forward_layer_cached` keeps layer activations on-device and updates K/V via D2D `hipMemcpyAsync`. Allocation discipline (7D-3): the requested bytes are checked against `min(user cap --max-kv-bytes, free GTT sysfs, MemAvailable, cgroup headroom)` minus a 10% safety margin, and a request that cannot fit fails fast with a `ValueError` naming the requested bytes, the effective budget, and the sources — the manager never attempts an allocation that can OOM.
  - **`--offload-kv-cpu` / `--kv-mmap-dir <dir>`**: Memory-saving modes for ultra-long-context 70B runs. Keeps persistent GPU KV pool usage at `0` bytes by storing the KV cache in host RAM or a disk-backed `mmap` file (`0600`, created with `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW` so symlinks are rejected and pre-existing files are never overwritten), sized only after an `os.statvfs` free-space check, and **unlinked immediately after mapping** so a crash before `close()` leaves no files; the mapping stays usable through its open fd. Trades per-step H2D KV transfer bandwidth (`O(context_len)`) for a minimal GPU memory footprint.
- **Tokenizer & Architecture Support**:
  - Supports both SentencePiece (`▁`, reference-faithful score-priority greedy merge over the GGUF scores with `<0xXX>` byte fallback) and GPT-2 / Llama-3 / Qwen2 byte-level (`Ġ`, `tokenizer.ggml.merges`) BPE vocabularies — all verified against llama.cpp reference goldens; special tokens (`token_type` CONTROL/USER_DEFINED, longest match) are encoded as their own IDs, `tokenizer.ggml.add_bos_token` and the BOS family default are honored, and all 7A-3 llama.cpp reference goldens plus the 310-case differential corpus pass (`tests/test_goldens_tokenizer.py`, `audit/evidence/G2/7B/`). The tokenizer read path is family-agnostic: reading a `qwen2` vocabulary here does not make qwen2 model support verified (`qwen2` model support is **NOT YET**; see the compatibility matrix below). Also reads `{arch}.*` GGUF metadata keys with a fail-fast model-spec validator (`llama`, `qwen2`, `phi3`, `gemma`; unknown architectures are rejected with the supported set — see the matrix below), and optional QKV attention biases (`blk.{i}.attn_{q,k,v,output}.bias`).
  - **Verified release scope:** text-only **llama-family `Q4_0` / `Q4_K` / `Q8_0`** GGUFs (real-GGUF/hardware evidence). The `phi3` and `gemma` forward paths are **synthetic-fixture verified** against an independent FP32 NumPy reference (Phase 7C/G3: Phi-3 fused `attn_qkv` + fused gate/up `ffn_up` + biases + NeoX; Gemma `sqrt(hidden)` embedding scale + GeGLU + NeoX + `attention.key_length`/`value_length` + optional final-logit softcap + tied output) — **no real Phi-3/Gemma GGUF has been run** (golden logits/tokens belong to 7F-2), so they are **not** in the release scope. Model-specific chat special-token encoding (chat template handling) is **not** verified end-to-end for any family. `qwen2` remains a metadata/bias regression target only (**NOT YET** as a support claim). Gemma 2/3-specific features (attention soft-capping, sliding-window attention) and Phi-3 long/short rope factors fail fast with explicit errors. See `audit/evidence/G3/7C/` and the compatibility matrix below.
- **Sequential Multi-Prompt Batching (`generate_batch`)**: Processes multiple prompts sequentially while reusing the initialized `WeightStreamer` and `KVCacheManager` without re-allocating GPU/mmap resources.
- **Single-Engine / Thread-Guarded Workspaces**: Kernel device workspaces and `DeviceKVCachePool` use process-wide static buffers guarded by a C++ mutex (`g_hip_workspace_mutex`); only one active GPU-resident `LlamaInferenceEngine` / `KVCacheManager` instance is permitted per process at a time (enforced at runtime).
- **RoPE Layout Compatibility**: Supports both GGUF-Llama adjacent-pair rotation (default for `llama`) and NeoX half-dimension rotation (auto-detected from GGUF metadata `{arch}.rope.neox` / architecture or enabled via `--rope-neox`).

### Model-family compatibility matrix (Phase 7C, Gate G3)

Every row states the *actual* evidence type. A synthetic-fixture logits match
against the independent FP32 NumPy reference is **synthetic-fixture
verification** and is not real-model support; real-GGUF Phi-3/Gemma golden
logits/tokens belong to 7F-2. Unsupported architectures and unsupported
family-specific features fail fast with explicit errors
(`src/model_spec.py`, tested in `tests/test_model_families.py`).

| Architecture (`general.architecture`) | Quantizations actually run | Evidence type | Prefill + KV-cache decode + generation | Status | Notes |
|---|---|---|---|---|---|
| `llama` | `Q4_0`, `Q4_K`, `Q8_0` (release scope) + `Q6_K` kernels and mixed `Q4_K`+`Q6_K` recipe wiring | synthetic GGUFs on the gfx1150 hardware lanes vs FP32 CPU reference (G0 baseline; see ledger rows 3-6) | yes (all three) | **VERIFIED** (release scope) | unchanged by 7C: fixed-prompt logits/token-IDs byte-identical to the parent commit (`audit/evidence/G3/7C/llama-regression.log`) |
| `phi3` | `F16` and a mixed `Q4_K`+`Q6_K` build, fused `attn_qkv` and fused gate+up `ffn_up`, with and without biases | **synthetic fixture only** — independent FP32 NumPy reference (`tests/reference_model.py`), within the 6e-3 test tolerance (observed max 4.9e-3 on the independent Q4_K/Q6_K probe; F16 ≤3.5e-3) | yes (prefill, cached decode, greedy generation) · fused vs separate equivalence ≤ 1e-3 | **PARTIAL** — synthetic-fixture verified | real-GGUF goldens pending 7F-2; fused and legacy separate layouts both supported; optional `attn_qkv.bias`/`ffn_up.bias`/`ffn_down.bias`; long/short rope-factor tensors fail fast |
| `gemma` | `F16` and `Q4_K`, separate `attn_q/k/v` | **synthetic fixture only** — independent FP32 NumPy reference (`tests/reference_model.py`), within the 6e-3 test tolerance (observed max 5.9e-3 on the independent Q4_K probe; F16 ≤3.6e-3) | yes (prefill, cached decode) | **PARTIAL** — synthetic-fixture verified | real-GGUF goldens pending 7F-2; `sqrt(hidden)` embedding scale, GeGLU (host FP32 path — no new GPU kernel in 7C), NeoX rope, explicit `attention.key_length`/`value_length` (`hidden//heads` is never assumed), optional `final_logit_softcapping`, tied `token_embd` output |
| `gemma2`, `gemma3` | none | n/a | n/a | **NOT SUPPORTED** (fail fast) | attention soft-capping, sliding-window attention, and other variant features are rejected with explicit errors |
| `qwen2` | `Q4_K`/`Q6_K` metadata/bias regression fixture | synthetic regression only | metadata + bias-add path | **NOT YET** | qwen2 resolves through the llama-family tensor layout as a regression target; no support claim (chat template/BOS correctness open) |
| anything else | none | n/a | n/a | **NOT SUPPORTED** (fail fast) | `ValueError` naming the architecture and the supported set (`llama`, `phi3`, `gemma`; `qwen2` via the llama-family layout only) |
