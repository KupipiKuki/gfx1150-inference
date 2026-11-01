# Third-Pass Audit & Remediation Package — gfx1150-inference v0.6.1 review

> **Scope:** Review of the coder's second remediation commit `c75914b` ("Added additional code implementations per remediation comments") on branch `vibe/audit-remediation-220201`, audited against `AUDIT_REMEDIATION_v0.6.1.md` (which reconciles my S/P/D findings with the Deepseek B/C/S/R/T/L report).
> **Method:** Full diff review of all 17 changed files + executable verification on a non-GPU host (Python 3.12, NumPy 2.5): `tests/test_cpu_only.py` (12/12 pass, also under `-O`), an independently rebuilt sdist, and fresh probes for the GPT-2 tokenizer, arch-prefixed metadata, Q6_K round trip, duplicate names, and sampler validation. GPU kernel execution remains owner-verified on gfx1150 hardware; kernel claims here are by inspection and marked.
> **Status legend:** ✅ fixed & verified · ◐ partially fixed · ❌ open

---

## 1. Verification performed on `c75914b`

| # | Check | Result |
|---|---|---|
| R-1 | `py_compile` all src/tests/setup.py | ✅ |
| R-2 | `python3 tests/test_cpu_only.py` — 12 tests (now incl. B-1 sdist completeness) | ✅ all pass |
| R-3 | `python3 -O tests/test_cpu_only.py` | ✅ all pass |
| R-4 | sdist rebuilt independently: now contains `CMakeLists.txt`, `MANIFEST.in`, all 6 `*.hip`, `bindings.cpp` (8 build-source entries, was 0) | ✅ B-1 fixed |
| R-5 | GPT-2 byte-level BPE round trips: `Hello world`, `Hello  world`, `Ω café`, `hello, world! 123` all decode exactly; unmappable char raises `ValueError` | ✅ C-2 fixed (my probe) |
| R-6 | SentencePiece path unchanged and still correct | ✅ |
| R-7 | `qwen2.*` arch-prefixed metadata → `LlamaLayerConfig` builds (hidden 128, heads 4, kv 2, neox auto) | ✅ C-3 core fixed |
| R-8 | Q6_K CPU quantize→dequantize round trip: max err 0.0047, exact 840-byte packing | ✅ C-1 CPU side; fused HIP `matmul_q6_k`/`dequantize_q6_k` + device variant present by inspection |
| R-9 | Duplicate tensor names → `ValueError` at parse | ✅ reproduced |
| R-10 | Sampler rejects `repetition_penalty ≤ 0`, `temperature < 0`, `top_p ∉ [0,1]` | ✅ reproduced |
| R-11 | `max_new_tokens=0` returns `[]`; upfront `len(prompt)+max_new ≤ max_seq_len` check; `time.perf_counter` metrics | ✅ by inspection |

---

## 2. Finding-by-finding resolution (v0.6.1 backlog → `c75914b`)

### P0 ship-blockers — all addressed

| ID | Status | Evidence |
|---|---|---|
| **B-1 sdist cannot build** | ✅ | `MANIFEST.in` added (`include CMakeLists.txt`, `recursive-include src/kernels *.h *.hip`, `recursive-include src/python_bindings *.cpp`); R-4 verified 8 build sources in the tarball; `test_v8` asserts sdist completeness in CI. Residual: no CI job that *installs from* the sdist (only archive listing) — add `pip install dist/*.tar.gz --no-build-isolation` smoke on a ROCm runner |
| **C-1 Q6_K unsupported** | ✅ | `block_q6_k` (210 B) + `dequantize_q6_k_kernel` + `matmul_q6_k_wave_kernel` + `_device` variants in `dequantize.hip`; `matmul_q6_k` binding; `layer.py` routes `GGMLType.Q6_K`; CPU `quantize/dequantize_q6_k_cpu` (R-8). Other K-quants (Q2_K/Q3_K/Q5_K) and Q4_1/Q5_0/Q5_1/Q8_1 still unsupported — acceptable if a fail-fast load-time matrix lists them |
| **C-2 GPT-2/Ġ tokenizer** | ✅ | GPT-2 byte-level BPE: `bytes_to_unicode` table, pre-tokenizer regex, `tokenizer.ggml.merges` ranks, `token_type` specials, Ġ↔space decode, raise on unmappable bytes (R-5/R-6). Residual: no golden-vector tests vs llama.cpp yet (Deepseek T-3) |
| **C-3 hardcoded `llama.*`** | ◐→✅ core | `_get_arch_meta(metadata, arch, suffix)` with `llama.*` fallback in `layer.py`; `inference.py` reads `{arch}.block_count` (R-7); optional QKV biases applied in the Python layer path (`layer.py:269-281`). **Gap:** the fused `forward_layer_cached` path is skipped when biases exist (`not has_bias`) — Qwen2 models silently fall back to the slow per-op path; bias support inside the C++ pipeline is the follow-up |

### P1 hardening — mostly addressed

| ID | Status | Evidence |
|---|---|---|
| S-2 bindings validation | ✅ | `check_fp16_contiguous` now checks `dtype().kind()=='f' && itemsize==2`, `require_writeable` for outputs, and stride==itemsize contiguity for buffers (bindings.cpp:24-44) |
| S-3 static-workspace race | ✅ | `std::mutex g_hip_workspace_mutex` in bindings + `_gpu_lock` in `kv_cache.py` (by inspection; no Python-level test possible without GPU) |
| S-4 KV file safety | ✅ | `O_CREAT\|O_EXCL\|O_RDWR\|O_NOFOLLOW, 0o600`, fd-based `mmap.mmap(fd, …, ACCESS_WRITE)`, created-only unlink |
| S-5 `sys.path` injection | ✅ | changed from `insert(0, …)` to `append(…)` and only when the dir exists; `build/` no longer shadows installed packages at position 0. Residual: `append` still allows a writable `build/matmul_module.py` to be imported if the real one is absent — acceptable for a dev checkout, note in docs |
| C-7 generation edges | ✅ | `max_new_tokens < 0` raises, `== 0` returns empty, seq-len pre-check before prefill, `perf_counter` (R-11) |
| C-8 sampler validation | ✅ | R-10 reproduced |
| C-10 duplicate names | ✅ | R-9 reproduced; unknown GGML types: `GGML_BLOCK_INFO` covers all enum values now, but an out-of-enum id still raises `ValueError` from the ctor — acceptable message |
| R-1 `WeightStreamer.close()` fd leak | ✅ | `close()` now closes `_file` in `finally` even when `_mm.close()` raises `BufferError` |
| R-2 engine ctor leak | ✅ | `try/except` around init with cleanup (`self.close()`-style) present in `__init__` |
| S-1 residual KV alloc clamp | ❌ | `KVCacheManager` still trusts `block_count`/`head_count`/`max_seq_len` for allocation size — no clamp vs available memory (header-driven OOM/DoS remains). Low likelihood, easy fix with `os.sysconf` free-RAM check |
| B-3 setup.py | ✅ | `build_temp` used, `-j min(cpu,8)`, loud `RuntimeWarning` on `GFX1150_SKIP_CMAKE=1`; version bumped 0.6.1, classifiers + urls added (B-4 partial: `license = { file = … }` still PEP-639-deprecated) |
| B-5 module namespace | ❌ | still six top-level modules (`tokenizer`, `layer`, …) — collision risk unchanged |

### P2 performance/design

| ID | Status | Evidence |
|---|---|---|
| P-1 residual async pipeline | ◐ | `DeviceLayerWorkspace` now creates a dedicated `hipStream_t` + `hipEvent_t` and uses `hipMemcpyAsync` + `hipEventRecord` + `hipStreamWaitEvent` for weight/x/norm staging (attention.hip:460-686). **But** the wait is `hipStreamWaitEvent(0, …)` — i.e. the *default* (legacy) stream waits on the copy stream, and all kernels are still launched on stream 0, so copies and compute remain serialized within a layer; there is still one blocking D2H per layer. No layer-to-layer overlap, no double-buffered weight prefetch on the copy stream. Real win so far is reduced API overhead, not true overlap |
| P-2 residency policy | ◐ | `WeightStreamer(cache_weights=…)` / `--cache-weights` added: default still evicts, flag keeps page cache warm; README documents it. **But** it's a boolean, not the budgeted `AUTO`/`PIN_ALL`/`STREAM` policy the Deepseek report recommends (pin the model in GTT when it fits, stream only what doesn't) — on a 32 GB APU with a 7B model the default is still the slow path |
| D-1 madvise overstatement | ◐ | README/docstring wording softened ("advise the kernel to reclaim"), but no `posix_fadvise`/`MADV_PAGEOUT` and no deterministic `preadv` staging — the "bounded RAM" guarantee is still page-cache-dependent for >RAM models |
| P-3/P-4 flash attention, GQA sharing | ❌ | not implemented (no flash tiling, per-head K/V re-reads remain) |
| C-4 RoPE scaling / C-5 SWA | ❌ | `rope.scaling.*` still unread (grep 0); no sliding-window mask |
| T-* pytest/golden/fuzz/telemetry | ◐ | CPU suite is unittest-based and self-contained (good), but GPU suites remain ad-hoc scripts; no llama.cpp golden tokens/blocks; no `--stats`/`--json` telemetry |

### New issues in `c75914b`

| ID | Severity | Finding |
|---|---|---|
| N-1 | Low | `tokenizer._chars_to_symbols` raises on any unmappable char, but the SentencePiece fallback branch (`except ValueError` → per-word) can still silently drop a word's chars if the word itself isn't in vocab and its chars aren't either — narrow, but the raise path should be uniform |
| N-2 | Low | GPT-2 pre-tokenizer maps bytes via `_GPT2_B2U` then requires each mapped char in vocab; synthetic/minimal vocabs without all 256 byte chars will raise even when `<0xXX>` tokens exist (the GPT-2 branch doesn't try `<0xXX>` fallback before raising) — R-5 used a full byte vocab; edge vocabs need the fallback tried first |
| N-3 | Info | `forward_layer_cached` bias skip (`not has_bias`) means Qwen2/2.5 models never get the fast path — bias add inside the C++ pipeline should be next |

---

## 3. Remaining backlog (third remediation package)

**P0 (before claiming real-model support):**
1. Golden-vector tests for the GPT-2 tokenizer and Q6_K dequant against llama.cpp-produced artifacts (Deepseek T-3/C-9) — currently everything round-trips against the repo's own encoder.
2. Fail-fast load-time compatibility matrix listing unsupported tensor types (Q2_K/Q3_K/Q5_K/Q4_1/Q5_x/Q8_1) instead of mid-run `ValueError`.
3. sdist *install* smoke test in CI (not just archive listing).

**P1:**
4. KV allocation clamp vs free RAM (`os.sysconf`) before `kv_cache_init`/host alloc.
5. Bias support inside `forward_layer_cached` so Qwen2 keeps the fused path.
6. Uniform unmappable-byte handling in both tokenizer branches (try `<0xXX>` before raising).
7. PEP 639 `license = "GPL-3.0-only"`, package namespace (`gfx1150/`) to fix top-level module collisions.

**P2:**
8. True overlap in the layer pipeline: launch kernels on the dedicated stream (not stream 0), double-buffer weight staging on the copy stream, single sync per token.
9. Budgeted residency policy (`AUTO` pin-if-fits vs `STREAM`) replacing the boolean `cache_weights`.
10. `posix_fadvise(DONTNEED)`/`MADV_PAGEOUT` or `preadv` double-buffer for >RAM models; correct the bounded-RAM wording accordingly.
11. Flash-style tiled attention with GQA KV sharing; RoPE scaling (linear/YaRN); sliding-window mask.
12. pytest conversion + `@pytest.mark.gpu` gating, multi-seed relative tolerances, hipEvent-based benchmark gates, `--stats`/`--json` metrics.

## 4. Verdict on `c75914b`

All four P0 ship-blockers from the Deepseek report are now genuinely fixed and I verified B-1 (sdist contents), C-1 (Q6_K round trip + kernel wiring by inspection), C-2 (byte-exact GPT-2 round trips incl. spaces/unicode + raise-on-unmappable), and C-3 core (arch-prefixed metadata) by execution. The P1 hardening round is likewise real: bindings dtype/contiguity/writability, workspace mutex, `O_NOFOLLOW` KV files, `sys.path` de-prioritized, sampler validation, generation edge cases, `perf_counter`, duplicate-name rejection, close()-fd-leak, and ctor-leak fixes are all in the diff and the executable ones reproduce cleanly. `tests/test_cpu_only.py` is 12/12 green in standard and `-O` modes.

The package is now in a defensible state for v0.6.1: parser is fail-closed on malformed/truncated input, tokenizer handles both major vocab families, Q4_K_M's Q6_K tensors are supported, and distribution via sdist contains the build sources. What remains is P1/P2 polish (KV clamp, fused-path biases, golden tests, real stream overlap, budgeted residency, flash attention, RoPE scaling/SWA, pytest/telemetry) — none of it blocks a v0.6.1 release for llama-family Q4_0/Q4_K/Q8_0 models on gfx1150.
