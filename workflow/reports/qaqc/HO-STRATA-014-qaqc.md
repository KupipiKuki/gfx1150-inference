# QAQC report — HO-STRATA-014

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-014 (DeepSeek S4a: forward skeleton + block-0 layer parity), with approved deviation DR-HO-STRATA-014-1 (DEC-043) and reference amendment DEC-044 |
| **Reviewer** | QAQC (`opencode-go/gemini-4-argon`, DEC-039) |
| **Date (UTC)** | 2026-11-24 |
| **Verdict** | **PASS** |
| **Scope reviewed** | Workflow repo `/home/kupipi/Documents/git/gfx1150-inference` on branch `wp/strata-014-deepseek-s4` @ `df10c61` (coder handoff closure @ `55122b3`, bundle @ `d0418bb`, base `main` @ `d1a974db0ace2cc78d77efd1eec123ea93bb865b`); Strata checkout `/home/kupipi/Documents/git/strata` on branch `strata-014-deepseek-s4` @ `db087d5117abd6596fe0609605344bc4cc0ad318` (base `strata-012-deepseek-s1` @ `bac859ef91fb0d432eaf9675fc769bc3afe313cf`, pin `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`) |

**Profile:** AMD Ryzen AI 9 HX 370 w/ Radeon 890M (`gfx1150`), 92 GB unified memory; Linux Mint 22.3 (Ubuntu 24.04 base), kernel `7.0.0-42-generic`; ROCm `core-10.1` (`LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`), HIP `7.16.26385`, GCC `13.3.0`, Python `3.14.10`.
- **Target pack:** `DeepSeek-MoE-16B-base` Q4_K_M (`deepseek-moe-16b-base-q4_k_m.gguf`, 10,850,181,856 B, sha256 `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`, 363 tensors).
- **Exact-arithmetic f32 reference pack (DEC-044):** `/tmp/opencode/deepseek-moe-16b-f32.gguf` (65,506,906,848 B, sha256 `8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27`, 363 F32 tensors), converted from the Q4_K_M pack above via `llama-quantize --outtype f32` at the HO-010 llama.cpp pin `78e05298f0d68abff41d08d79fa7469264b2aff0` (tag `b12527`).
- **Workload:** 4-token prompt (`--tokens 549,6077,280,7239`, `--max-new 1`, `--max-context 1024`) under `--parity-run --dump-layers`; block 0 residual stream parity (`N = 1`, 4 cells).
- **Regression pack:** `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (`55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`), 5-token prompt (`760,6511,314,9338,369`), 32 greedy tokens.
- No performance or family-support claim is made or accepted.

---

## 1. Acceptance criteria re-run

Every acceptance criterion (AC-1 through AC-10) and the DEC-044 exact-arithmetic reference regeneration were independently executed by QAQC from clean trees.

| # | Criterion | Command run by QAQC | Observed (exit code & values) | Pass? |
|---|---|---|---|---|
| **AC-1** | Builds in `build-deepseek/`; signed binary `build-hip/strata` untouched | `sha256sum build-hip/strata && cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc) && sha256sum build-hip/strata` | Build exit `0` (`Built target strata`, `model_family_test`, `gguf_geometry_test`). Pre- and post-build `build-hip/strata` sha256 = `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` (unchanged). | **PASS** |
| **AC-2** | Normal runs still refuse verbatim; `--families` unchanged | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --native <pack> --tokens 1,2,3 --max-new 32 --max-context 1024`; `./build-deepseek/strata --families` | Normal run: exit `2`; stderr is byte-for-byte identical to `HO-STRATA-012/artifacts/native-deepseek-refusal.txt`: `strata generate: --native /home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf: DeepSeek-MoE-16B-base (architecture 'deepseek') is recognised by Strata but this build does not run it yet`. `--families`: exit `0`; stdout = `qwen4exp qwen35moe`. | **PASS** |
| **AC-3** | Diagnostic `--parity-run` mode is explicit and cannot be reached by accident | **3a:** `./build-deepseek/strata --parity-run --native <pack> --tokens 1,2,3 --max-new 1 --max-context 1024`<br>**3b:** `./build-deepseek/strata --parity-run --native /tmp/opencode/unknown.gguf --dump-layers /tmp/opencode/qa-dummy.bin --tokens 1,2,3 --max-new 1 --max-context 1024`<br>**3c:** `./build-deepseek/strata --parity-run --native <pack> --dump-layers /tmp/opencode/qa.bin --tokens 549,6077,280,7239 --max-new 1 --max-context 1024` | **3a:** exit `2`; stderr = `strata generate: --parity-run requires --dump-layers PATH`.<br>**3b:** exit `2`; stderr = `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight`.<br>**3c:** exit `0`; stderr prints the single line `strata generate: parity run: architecture 'deepseek' is not supported; this path exists for HO-STRATA-014/015 parity only`; stdout prints `layers dumped: /tmp/opencode/qa.bin (1 layer + the input x 1 streams x 2048)`. | **PASS** |
| **AC-4** | Dump obeys the layout contract (`k × (N+1) × 2048 × 4` B, `N=1`, finite) | `stat -c%s /tmp/opencode/qa.bin`; `python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py --shape-only --oracle workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin --dump /tmp/opencode/qa.bin` | File size = `81920` B (`5 records × 2 slots × 2048 floats × 4 B`, i.e., `16,384` B/position for `N=1`). `compare_layers.py --shape-only`: exit `0`, `engine dump: 5 records, 2 slots/record, N=1 blocks computed`, `oracle: 4 records, 28 blocks`, `non-finite values in kept dump: 0`, `RESULT: PASS (shape only)`. | **PASS** |
| **AC-5a (gate)** | **Layer parity, block 0** against exact-f32 oracle (`≤ 5e-3` over 4 cells), plus Q4_K informative floor | **Stored dump:** `compare_layers.py --oracle …/deepseek_f32_p1_4_layers.bin --dump …/dump-run-1.bin`<br>**Fresh QAQC dump:** `compare_layers.py --oracle /tmp/opencode/qaqc_f32_layers.bin --dump /tmp/opencode/qa.bin`<br>**Informative floor:** `compare_layers.py --oracle workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin --dump /tmp/opencode/qa.bin` | **Gate (stored & fresh QAQC dump identical):** exit `0`; `N=1`, 4 cells, 0 non-finite:<br>• `(layer=0, pos=0)`: `9.757537e-05`<br>• `(layer=0, pos=1)`: `5.944078e-05`<br>• `(layer=0, pos=2)`: `6.385591e-05`<br>• `(layer=0, pos=3)`: `5.652541e-05`<br>`median rel L2 = 6.164835e-05`, `max rel L2 = 9.757537e-05 at (layer=0, pos=0)` (**≤ 5e-3**, ~51× margin), `RESULT: PASS`.<br>**Informative Q4_K floor (not gated per DEC-044):** exit `1`; `(0,0)=1.939394e-02`, `(0,1)=1.257641e-02`, `(0,2)=2.054810e-02`, `(0,3)=1.333939e-02`; `median = 1.636667e-02`, `max = 2.054810e-02 at (layer=0, pos=2)`. | **PASS** |
| **AC-5a (ref)** | **Independent regeneration and weight verification of the DEC-044 f32 reference** | Rebuild `scripts/oracle_nodes.cpp` against `/tmp/opencode/llama-ref` @ `78e05298…`; regenerate `/tmp/opencode/qaqc_f32_layers.bin` from `/tmp/opencode/deepseek-moe-16b-f32.gguf` and `/tmp/opencode/qaqc_q4k_layers.bin` from `<Q4_K_M pack>`; `cmp` against committed oracle dumps; verify f32 GGUF tensor bytes against `dequantize_row_q4_K`/`q6_K` of Q4_K_M pack | `g++` build exit `0`. Regenerated `/tmp/opencode/qaqc_f32_layers.bin` matches `artifacts/runs/deepseek_f32_p1_4_layers.bin` (`a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49`) byte-for-byte (`cmp` exit `0`). Regenerated `/tmp/opencode/qaqc_q4k_layers.bin` matches signed `HO-STRATA-010` `deepseek_p1_4_layers.bin` (`db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73`) byte-for-byte (`cmp` exit `0`). Raw tensor bytes in `deepseek-moe-16b-f32.gguf` for `blk.0.attn_q.weight` and `blk.0.attn_v.weight` match `dequantize_row_q4_K` / `dequantize_row_q6_K` of the Q4_K_M pack byte-for-byte (`True`/`True`). | **PASS** |
| **AC-6** | Determinism across runs | Run AC-3c twice to `/tmp/opencode/qa.bin` and `/tmp/opencode/qa2.bin`; `cmp /tmp/opencode/qa.bin /tmp/opencode/qa2.bin`; `cmp /tmp/opencode/qa.bin workflow/evidence/HO-STRATA-014/artifacts/dump-run-1.bin` | Both runs exit `0`; `cmp` exits `0` between `/tmp/opencode/qa.bin` and `/tmp/opencode/qa2.bin`, and `0` against committed `dump-run-1.bin` and `dump-run-2.bin` (all four have sha256 `d534fdcb44026b2d244942ed7a23a163fcae8c89d3182516c1ba7bf30e998a0d`). | **PASS** |
| **AC-7** | Qwen regression exact (32 HO-007 token IDs) + unit tests green | `./build-deepseek/strata --native /home/kupipi/Documents/models/gguf/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 760,6511,314,9338,369 --n 32 --max-context 1024`; `./build-deepseek/model_family_test`; `./build-deepseek/gguf_geometry_test` | Qwen run: exit `0`; emits `gen: 11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919` (32/32 identical to HO-007/HO-012). `model_family_test`: exit `0` (`ALL PASSED`, 39 checks incl. new S4a dense-first-block and `--parity-run` checks). `gguf_geometry_test`: exit `0` (`all passed`). | **PASS** |
| **AC-8** | Patch measured, exported, applies cleanly to `baf16363` + `0001` | `git -C strata diff --stat bac859ef9..db087d511`; `git -C strata diff --stat baf16363..db087d511`; `cmp` live diff vs `patches/0002-s4-forward.patch`; `git worktree add --detach /tmp/opencode/qaqc-strata-clean baf16363`, apply `0001-deepseek-family.patch`, `git apply --check` & apply `0002-s4-forward.patch`, remove worktree | S4a delta (`bac859ef9..db087d511`): **10 files changed, 839 insertions(+)** (`cmp` vs `0002-s4-forward.patch` exit `0`). Cumulative overlay (`baf16363..db087d511`): **14 files changed, 1073 insertions(+), 31 deletions(-)** (stated in `manifest.md` §6). Clean `baf16363` worktree: `0001` applies (`exit 0`), `0002` `--check` and apply pass (`exit 0`), worktree removed (`exit 0`). | **PASS** |
| **AC-9** | Evidence gate `check_bundle.py --strict` green + fresh archive hash check | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-014 --strict`; `git archive HEAD \| tar -x -C /tmp/opencode/qaqc-014-archive && sha256sum -c workflow/evidence/HO-STRATA-014/hashes.txt` | `check_bundle.py --strict`: exit `0`, `RESULT: PASS (31 checks, 0 warnings)`. Fresh `git archive` `sha256sum -c`: **23/23 OK** (exit `0`). All three commit pins in `hashes-notes.txt` verified via `git show <commit>:<path> \| sha256sum` (see Minor finding **F1**). | **PASS** |
| **AC-10** | Early architecture checkpoint & deviation before code | Inspect `artifacts/plan.md`, `artifacts/llama-ref-graph.md`, `workflow/handoffs/DR-HO-STRATA-014-1.md`, and git history (`36256b6` before engine code) | `artifacts/plan.md` and `artifacts/llama-ref-graph.md` (with `file:line` citations into `78e05298…`) were committed at `36256b6` and `DR-HO-STRATA-014-1` approved in `672beee` (DEC-043) before the Strata engine commit `ad214242a`. | **PASS** |

---

## 2. Explicit technical judgments required by QAQC brief

### 2.1 (a) Is the exact-f32 reference a legitimate gate (DEC-044), or does it hide a divergence the Q4_K reference would have caught?

**Judgment: The exact-f32 reference is a legitimate, strictly sharper gate — in fact, it *exposed* a real semantic bug (NEOX vs NORM RoPE pairing) that the Q4_K layer reference had masked.**

1. **Same weights, proven byte-for-byte:** QAQC verified that the input Q4_K_M pack (`f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`) and the f32 converted pack `/tmp/opencode/deepseek-moe-16b-f32.gguf` (`8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27`) hold identical model weights: dequantizing `blk.0.attn_q.weight` (Q4_K) and `blk.0.attn_v.weight` (Q6_K) from the Q4_K_M pack with llama.cpp's `dequantize_row_q4_K` / `dequantize_row_q6_K` matches the F32 tensor payloads in `deepseek-moe-16b-f32.gguf` byte-for-byte (`True`/`True`). Rebuilding `scripts/oracle_nodes.cpp` against `/tmp/opencode/llama-ref` @ `78e05298f0d68abff41d08d79fa7469264b2aff0` and running `--tokens 549,6077,280,7239 --n 0 --dump-layers` reproduces both `artifacts/runs/deepseek_f32_p1_4_layers.bin` (`a4c56b9d…`) and `HO-STRATA-010`'s `deepseek_p1_4_layers.bin` (`db6eccb3…`) byte-for-byte (`cmp` exit `0`).
2. **Why the Q4_K CPU layer dump has a ~2e-2 noise floor:** When llama.cpp's CPU backend evaluates `ggml_mul_mat` on quantized weights (`Q4_K`, `Q6_K`, `Q8_0`), it quantizes the incoming f32 activation vector to `Q8_K` (`quantize_row_q8_K_ref`) and runs integer dot products (`ggml_vec_dot_q4_K_q8_K_generic`, `ggml_vec_dot_q6_K_q8_K_generic`). As documented in `artifacts/diagnosis.md` Step 14, that `Q8_K` activation quantization matches the Q4_K oracle's `Qcur-0` to `1.24e-7` and `Vcur-0` to `3.30e-7`, whereas the true f32 product of the dequantized weights differs from the `Q8_K`-activation product by `4.44e-3` on `Qcur-0` and `5.78e-2` on `Vcur-0` at `p=0`. Across block 0, that CPU activation-quantization rounding creates an irreducible `1.26e-2 … 2.05e-2` floor against any exact-f32 activation path.
3. **What the exact-f32 reference caught that the Q4_K reference hid:** Under the Q4_K oracle, the `~2e-2` activation-quantization error at `p=0` and the `~5e-2 … 1.2e-1` errors at `p=1..3` looked like compounding activation-quantization drift. Once DEC-044 switched the layer reference to the exact-f32 conversion of the same pack, `p=0` (where RoPE is the identity) dropped immediately to `9.76e-5`, while `p=1..3` stayed at `~1e-2`. That sharp contrast isolated a genuine bug in the engine: `src/deepseek/` was applying NEOX-style half-split RoPE `(i, i + head_dim/2)` instead of llama.cpp's `LLAMA_ROPE_TYPE_NORM` consecutive-pair RoPE `(2i, 2i+1)` (`src/models/deepseek.cpp:109`). Switching to `k_rope_norm` collapsed `p=1..3` from `~1e-2` to `5.65e-5 … 6.39e-5`. Had the gate instead widened the Q4_K bound to `~1e-1`, the RoPE bug could have hidden inside the bound. Keeping the `5e-3` bound against the exact-f32 layer reference for S4 while keeping the Q4_K pack as the S5 token authority (DEC-044) is sound engineering.

### 2.2 (b) Does a 9.76e-5 agreement at block 0 support the *claim* being made — "block 0 computes correctly", not "DeepSeek runs"?

**Judgment: Yes.**

- The claim made by HO-STRATA-014 (S4a) is strictly scoped to block 0's forward arithmetic on the 4-token prompt (`549,6077,280,7239`): embedding gather (`token_embd.weight` Q4_K → f32), pre-attention RMSNorm (`eps = 1e-6`), Q/K/V projections (`Q4_K`/`Q6_K`), NORM-style RoPE (`base = 1e4`, `head_dim = 128`, consecutive pairs), causal MHA (`16/16` heads, scale `1/sqrt(128)`), output projection (`Q4_K`) + residual add, pre-FFN RMSNorm, and block 0's dense SwiGLU FFN (`ffn_gate`/`ffn_up` Q4_K width `10944`, `silu(gate) * up`, `ffn_down` Q8_0) + residual add.
- All 4 cells `(layer=0, pos=0..3)` agree with the exact-f32 oracle at `9.757537e-05`, `5.944078e-05`, `6.385591e-05`, and `5.652541e-05` (max `9.76e-5 ≤ 5e-3`, >50× margin). Because positions `1..3` exercise non-trivial RoPE angles and causal multi-position KV attention, this is strong evidence that block 0 computes correctly.
- Neither the handoff nor the manifest claims that DeepSeek-MoE-16B runs end-to-end: blocks 1–27 (MoE router, top-6 without renormalisation, 2 shared experts) are explicitly deferred to S4b (`HO-STRATA-015`), and token/logit parity + the support flag flip are deferred to S5 (`HO-STRATA-016`).

### 2.3 (c) Is `--parity-run` an acceptable gate for a family whose refusal must stay honest?

**Judgment: Yes.**

- `model_family_runs()` (`include/strata/artifact/model_family.hpp:61-63`) is unchanged and still returns `true` only for `ModelFamily::Qwen4Exp`.
- Normal `--native <deepseek-pack>` runs without `--parity-run` exit `2` with the verbatim HO-STRATA-012 refusal message, and `--families` prints `qwen4exp qwen35moe`.
- `--parity-run` requires `--dump-layers PATH` (refused with exit `2` if omitted on a DeepSeek pack), never bypasses the unknown-architecture refusal (AC-3b exits `2`), prints an explicit stderr warning (`strata generate: parity run: architecture 'deepseek' is not supported; this path exists for HO-STRATA-014/015 parity only`), dumps only the `N+1 = 2` computed slots per position (no padded uncomputed layers), and prints no generated tokens.

---

## 3. Diff and guard-rail review

### 3.1 Strata diff reviewed (`baf16363..db087d511` and S4a delta `bac859ef9..db087d511`)

- **S4a delta (`git -C /home/kupipi/Documents/git/strata diff --stat bac859ef9..db087d511`):**
  ```text
   cmake/strata_gpu_engine.cmake      |  12 +
   include/strata/deepseek/engine.hpp |  10 +
   src/deepseek/ds_engine.cu          | 474 +++++++++++++++++++++++++++++++++++++
   src/deepseek/ds_f32_matvec.cu      | 129 ++++++++++
   src/deepseek/ds_f32_matvec.cuh     |  28 +++
   src/deepseek/ds_kernels.cu         |  81 +++++++
   src/deepseek/ds_kernels.cuh        |  24 ++
   src/deepseek/ds_main.cpp           |   4 +
   src/program/generate.cpp           |  37 +++
   tests/core/model_family_test.cpp   |  40 ++++
   10 files changed, 839 insertions(+)
  ```
- **Cumulative overlay (`git -C /home/kupipi/Documents/git/strata diff --stat baf16363..db087d511`):**
  ```text
   cmake/strata_gpu_engine.cmake            |  12 +
   include/strata/artifact/gguf_reader.hpp  |  18 ++
   include/strata/artifact/model_family.hpp |   9 +-
   include/strata/core/family_layout.hpp    | 121 +++++++-
   include/strata/core/geometry.hpp         |   6 +
   include/strata/deepseek/engine.hpp       |  10 +
   src/deepseek/ds_engine.cu                | 474 +++++++++++++++++++++++++++++++
   src/deepseek/ds_f32_matvec.cu            | 129 +++++++++
   src/deepseek/ds_f32_matvec.cuh           |  28 ++
   src/deepseek/ds_kernels.cu               |  81 ++++++
   src/deepseek/ds_kernels.cuh              |  24 ++
   src/deepseek/ds_main.cpp                 |   4 +
   src/program/generate.cpp                 |  47 +++
   tests/core/model_family_test.cpp         | 141 +++++++--
   14 files changed, 1073 insertions(+), 31 deletions(-)
  ```

### 3.2 Guard-rail checklist

- [x] Diff is within scope; no unrelated files. In Strata, all 839 S4a lines are in the new `src/deepseek/**` + `include/strata/deepseek/engine.hpp` files (750 lines) plus the 3 minimal shared-file hunks approved by DEC-043 (`cmake/strata_gpu_engine.cmake` +12, `src/program/generate.cpp` +37, `tests/core/model_family_test.cpp` +40). `dsref.cu` was excluded per DEC-043 condition 2.
- [x] No edits under `src/core/**`, shared kernels (`include/strata/kernels/**`, `src/kernels/**`), `src/qwen35/**`, the tokenizer (`tools/strata_tokenizer.py`), or `model_family_runs()` / refusal text / `--families`.
- [x] `build-hip/strata` is untouched (`d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`).
- [x] Diagnostic dumps in `src/deepseek/ds_engine.cu` are compiled out (`#ifdef STRATA_DEEPSEEK_DIAG`, verified inert at runtime: no `/tmp/opencode/diag_*` files created).
- [x] The pre-registered `5e-3` bound (§12) was not widened, and the HO-STRATA-010 oracle bundle was not modified.
- [x] No prior signed `workflow/evidence/HO-STRATA-0xx/` bundle was edited. In the workflow repo, coder commits touched only `workflow/evidence/HO-STRATA-014/**`, `workflow/handoffs/HO-STRATA-014.md`, and `workflow/handoffs/DR-HO-STRATA-014-1.md` (`workflow/DECISIONS.md` and `workflow/STATUS.md` were edited only by the architect in `0df301a`, `672beee`, `4c29e94`, `df10c61`).
- [x] No new dependencies without approval (`compare_layers.py` uses Python stdlib only: `argparse`, `math`, `os`, `struct`, `sys`).
- [x] No secrets/tokens in the diff, logs, or evidence (`PASS B7-secrets`).
- [x] Tests are meaningful; no skips hidden as passes (`model_family_test` runs the live `build-deepseek/strata` binary to verify `--parity-run` without `--dump-layers` exits non-zero).
- [x] Evidence matches the commands that were run and reproduces byte-for-byte.

---

## 4. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| **F1** | Minor | In `workflow/evidence/HO-STRATA-014/hashes-notes.txt:12`, the third commit pin (`4c29e9458ffcf2bf268f3cd3191f1f26f1beee18:workflow/evidence/HO-STRATA-012/patches/0001-deepseek-family.patch`) writes `(see HO-STRATA-012 hashes.txt)` instead of inlining the 64-hex SHA-256 digest (`9a7b280f5d8c8e2bd22e6b9e908b1bf9a4ae9ed599d611cf16e45dccf1c4e869`), whereas HO-STRATA-014 §5 specifies `<commit>:<path>` with the full 64-hex digest. Additionally, because `hashes-notes.txt` uses flat `<commit>:<path>  <sha256>` lines (matching HO-014 §5's line-format text) rather than a `## Commit pins` Markdown table (`check_bundle.py:617-679`), `check_bundle.py --strict` skips `B6-pins` table parsing (reporting 31 checks, 0 `B6-pins` rows). QAQC manually verified all three commit pins via `git show <commit>:<path> \| sha256sum` (`DECISIONS.md` → `a717e143…`, `deepseek_p1_4_layers.bin` → `db6eccb3…`, `0001-deepseek-family.patch` → `9a7b280f…`). | `workflow/evidence/HO-STRATA-014/hashes-notes.txt:5-13`; `workflow/tools/check_bundle.py:528-539` | None for HO-STRATA-014 (all 3 pins resolve and match their digests); in `HO-STRATA-015` (S4b), format `hashes-notes.txt` with a `## Commit pins` Markdown table and inline all 64-hex digests so `B6-pins` executes mechanically. |
| **F2** | Minor | In `src/program/generate.cpp:3678-3704`, the check `if (dump_path.empty())` (`:3697`) is nested inside `if (deepseek)` (`:3696`), and `o.parity_run` (`:817`, `:3768`) is not read after the main CLI option loop. Consequently, `--parity-run` without `--dump-layers` is properly refused with exit `2` (`--parity-run requires --dump-layers PATH`) when `--native` points to a DeepSeek GGUF (AC-3a and `model_family_test`), and is refused by the PLE/family guard on an unknown-arch GGUF (AC-3b), but would be silently ignored if passed alongside a supported `qwen4exp` model without `--dump-layers`. | `src/program/generate.cpp:3696-3702`, `:3768` | None for S4a (all AC-3 cases and unit tests pass); in `HO-STRATA-015` (S4b), hoist `if (dump_path.empty())` above `if (deepseek)` or enforce `if (o.parity_run && o.dump_layers.empty())` after the CLI loop. |
| **F3** | Minor | In `src/deepseek/ds_engine.cu:82-107`, `upload_weight()` uploads both the raw quantized GGUF payload (`w.d`) and the host-dequantized f32 matrix (`w.f32 = upload_weight_f32(gm, name)`), and `alloc_buffers()` allocates `b.q8_1_scratch` (`:167`), even though `matvec()` (`:109-112`) uses only `w.f32`. For S4a (block 0 only), the extra allocation is ~290 MB and harmless. However, scaling eager f32 pre-dequantization of all weights to all 28 blocks in S4b (`HO-STRATA-015`, ~16B parameters ≈ 64 GB f32 plus 10.8 GB quantized) would approach the 92 GB unified memory limit on `gfx1150`. | `src/deepseek/ds_engine.cu:82-112`, `:167` | None for S4a; in `HO-STRATA-015` (S4b), drop the unused `w.d`/`q8_1_scratch` or dequantize routed expert weights on demand / in device kernels so all 28 blocks fit comfortably. |

No Blocker or Major findings.

---

## 5. Verdict and next state

- **PASS** → `AUDIT_REVIEW`; attach this report and the evidence path.

### QAQC_TO_AUDITOR (embedded per DEC-018)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-014-QAQC (embedded in `workflow/reports/qaqc/HO-STRATA-014-qaqc.md`) |
| **Type** | QAQC_TO_AUDITOR |
| **State** | AUDIT_REVIEW |
| **Date (UTC)** | 2026-11-24 |
| **From → To** | QAQC (`opencode-go/gemini-4-argon`, DEC-039) → Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) |
| **Handoff** | `workflow/handoffs/HO-STRATA-014.md` (with `workflow/handoffs/DR-HO-STRATA-014-1.md`, DEC-042, DEC-043, DEC-044) |
| **Branch / commits** | Workflow: `wp/strata-014-deepseek-s4` @ `df10c61` (handoff `55122b3`, bundle `d0418bb`, base `d1a974db`); Strata: `strata-014-deepseek-s4` @ `db087d511` (base `bac859ef9`, pin `baf16363b`) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-014-qaqc.md` |
| **Evidence bundle** | `workflow/evidence/HO-STRATA-014/` (`check_bundle.py --strict` → `RESULT: PASS (31 checks, 0 warnings)`; `sha256sum -c hashes.txt` → 23/23 OK from working tree and fresh `git archive`; all 3 commit pins in `hashes-notes.txt` verified via `git show`) |
| **Summary** | Independently re-ran AC-1 through AC-10 and regenerated the DEC-044 exact-arithmetic f32 oracle dump from `/tmp/opencode/deepseek-moe-16b-f32.gguf` (`8cd778a7…`, verified byte-identical to dequantized Q4_K_M weights `f00ecd83…`) using a freshly compiled `scripts/oracle_nodes.cpp` against `/tmp/opencode/llama-ref` @ `78e05298…`. Regenerated f32 oracle dump is byte-identical (`a4c56b9d…`) to `artifacts/runs/deepseek_f32_p1_4_layers.bin`. Two fresh QAQC engine dumps (`/tmp/opencode/qa.bin`, `/tmp/opencode/qa2.bin`) are byte-identical to each other and to `artifacts/dump-run-{1,2}.bin` (`d534fdcb…`), passing AC-5a with max relative L2 = `9.757537e-05` (`≤ 5e-3`, >50× margin) over the 4 block-0 cells. Normal refusal, `--families`, signed binary (`d58ee239…`), and 32-token Qwen regression are unchanged; patch (`0002-s4-forward.patch`, 10 files / +839 lines; cumulative 14 files / +1073 / -31) applies cleanly to a fresh `baf16363` worktree after `0001`. Three Minor findings (F1–F3), zero Blockers/Majors. |

---

## 6. Statement

I did not modify code, tests, docs, evidence, handoffs, or configuration. This report (`workflow/reports/qaqc/HO-STRATA-014-qaqc.md`) is the only artifact I wrote.
