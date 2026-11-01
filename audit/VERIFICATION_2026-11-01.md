# Build & Hardware Verification — 2026-11-01

**Target:** `gfx1150-inference` at `9b2deb0` (branch `Argon_Phase_6` / `origin/vibe/audit-remediation-220201`) plus the `setup.py` pybind11-discovery fix made during this pass.
**Purpose:** Independently confirm the claim that the remediation package builds and runs on the target platform, and reconcile the result with `AUDIT_REPORT_DEEP_2026-10-31.md`, `REVIEW_v0.6.1_c75914b.md`, and `AUDIT_REMEDIATION_v0.6.2.md`.

**Verdict:** The package **builds and installs from the sdist on this gfx1150 host**, and all CPU and GPU test suites pass. The release scope remains the narrow one stated in v0.6.2: **text-only llama-family `Q4_0`/`Q4_K`/`Q8_0` GGUFs**. The v0.6.2 §6 P0 backlog (chat special tokens, `add_bos_token`, Phi-3/Gemma, residency/stream honesty) is **still open**; this pass did not change those code paths.

---

## 1. Environment

| Item | Value |
|---|---|
| Host | AMD Ryzen AI 9 HX 370 w/ Radeon 890M |
| GPU | `gfx1150` (reported by `rocminfo`) |
| ROCm | 7.0.0 |
| HIP | 7.16.26385 |
| CMake | 3.28.3 |
| Python | 3.14.10 |
| NumPy | 2.5.3 |
| pybind11 | 3.1.0 |

Unlike the DeepSeek/review environments, this host has working ROCm + gfx1150, so the kernel claims could be executed rather than inspected.

---

## 2. Build results

| Check | Result |
|---|---|
| `cmake -S . -B <build> -DCMAKE_BUILD_TYPE=Release` | ✅ configure succeeds (with `pybind11_DIR` supplied) |
| `cmake --build <build> -j 8` | ✅ `matmul_module.so` (592 KB) links |
| `python setup.py sdist` | ✅ 112 KB tarball contains `CMakeLists.txt`, `MANIFEST.in`, all 6 `*.hip`, `bindings.cpp` |
| `pip install <sdist>` (full CMake build, clean venv, `--no-build-isolation`) | ✅ wheel builds and installs |
| Installed imports | ✅ `matmul_module`, `gguf_parser`, `weight_loader`, `layer`, `kv_cache`, `tokenizer`, `inference` |
| Installed CLI | ✅ `gfx1150-infer --help` |

### 2.1 Packaging defect found and fixed in this pass

A clean `pip install` from the sdist previously failed at `find_package(pybind11)`:

```
CMake Error at CMakeLists.txt:17 (find_package):
  Could not find a package configuration file provided by "pybind11"
```

`setup.py` invoked CMake without `-Dpybind11_DIR=...`. This is masked when pybind11's CMake config is installed system-wide or when `CMAKE_PREFIX_PATH` already contains it, which is why the direct/owner build worked. Fixed by querying `pybind11.get_cmake_dir()` and passing it to CMake. This closes the "sdist *install* is never exercised" gap called out in both the DeepSeek report (B-1/B-3) and the independent review (§2.7). A CI job that performs a real install (not just an archive listing) should be added per Phase 7A-5.

---

## 3. Test results

### 3.1 CPU suite

`python3 tests/test_cpu_only.py` → **12/12 pass** (also under `-O`).

### 3.2 GPU suites (executed on gfx1150)

| Suite | Result | Selected evidence |
|---|---|---|
| `test_matmul.py` | ✅ pass | 1024³ max error `6.1e-5`; all edge cases; `matmul_nt` shape guard |
| `test_gguf_and_q4.py` | ✅ pass | GGUF v3 + `madvise`; Q4_0 dequant exact; fused Q4_0 matmul max error `≤6.1e-5` |
| `test_layer.py` | ✅ pass | RMSNorm, RoPE (Llama + NeoX), GQA prefill/decode, SwiGLU, end-to-end layer |
| `test_full_model.py` | ✅ pass | 2-layer E2E prefill/decode; `788.6 tok/s` (decode `859.3 tok/s`) on the synthetic model |
| `test_phase5_scale.py` | ✅ pass | Q8_0/Q4_K/Q6_K kernels; 70B-dim `1×1024×8192` in `1.21 ms`; chunked-vs-full and KV-mode equivalence; `TILE_M=4` bit-identical; bindings guards; Qwen2 + Q6_K + bias path |

All five hardware suites exit `0`. The throughput figures above are single-run synthetic measurements, not the unevidenced 983 tok/s claim; they are recorded here only as a smoke-test observation.

---

## 4. Reconciliation with the open backlog

Re-probed on this tree; these are **not** fixed by the current code:

| Item | Status | Evidence |
|---|---|---|
| Tokenizer special-token **encode** | ❌ open | `encode("<\|im_start\|>")` with a control token at id 0 emits byte tokens `[64,128,109,...]`, not `[0]` |
| `tokenizer.ggml.add_bos_token` | ❌ open | never read; `generate()` / `generate_batch_ids()` hardcode `add_bos=True` |
| Phi-3 fused `attn_qkv` | ❌ open | `layer.py` still requires `attn_q.weight` / `attn_k.weight` / `attn_v.weight` |
| Gemma embedding scale / soft-cap / `attention.key_length` | ❌ open | no code paths (`grep` = 0) |
| `posix_fadvise` / `MADV_PAGEOUT` | ❌ open | only `MADV_DONTNEED`; `cache_weights` remains a boolean that skips it |
| True copy/compute stream overlap | ❌ open | `attention.hip` still does `hipStreamWaitEvent(0, ...)` and launches kernels on stream 0 |
| KV allocation clamp to free RAM/cgroup | ❌ open | only `DEFAULT_MAX_KV_BYTES = 32 GiB` sanity cap |
| `close()` / constructor exception masking | ◐ partial | fd closed in `finally`; `_mm` left open on `BufferError` |
| PEP 639 license / `__version__` / namespace package | ❌ open | `license = { file = "LICENSE" }`; no `__version__`; six top-level modules |
| Golden llama.cpp tokenizer/quant vectors, fuzz corpus, GPU CI gate | ❌ open | CPU suite remains self-referential |

These match `AUDIT_REMEDIATION_v0.6.2.md` §6 and `REVIEW_v0.6.1_c75914b.md` §2–3. No new regressions were found in the verified paths.

---

## 5. Release statement

Buildable, installable, and hardware-tested on gfx1150. Suitable for **text-only llama-family `Q4_0`/`Q4_K`/`Q8_0`** use. Do **not** claim Qwen2/Llama-3 chat, Phi-3, or Gemma support, and do not quote throughput as a benchmark, until the v0.6.2 P0 items and the Phase 7 evidence gates land.
