# Evidence manifest — HO-STRATA-015

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-015 |
| **Commit / branch** | Strata `e2e7e1b34…` / `strata-015-deepseek-s4b`; workflow `wp/strata-015-deepseek-s4b` |
| **Author / date (UTC)** | Primary Coder / 2026-11-26 |
| **Environment** | Linux 6.x, ROCm 10.1, AMD gfx1150 (Radeon 890M / Ryzen AI 9 HX 370), HIP backend, Python 3.12 |
| **Working directory** | `/home/kupipi/Documents/git/strata` for engine commands; `/home/kupipi/Documents/git/gfx1150-inference` for bundle |

## 1. Commands

See `commands.log` for the full verbatim list. Key commands:

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)` | Strata | 0 | `artifacts/ac1.log` |
| 2 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --native $PACK --tokens 549,6077,280,7239 --max-new 1` | Strata | 2 | `artifacts/ac2.log` |
| 3 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --families` | Strata | 0 | `artifacts/ac2.log` |
| 4 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --parity-run --native $PACK --dump-layers /tmp/opencode/ac3-dump.bin --tokens 549,6077,280,7239 --max-new 1 --max-context 1024` | Strata | 0 | `artifacts/ac3.log`, `artifacts/runs/s4b-free-normal.bin` |
| 5 | Teacher-forced gate (diagnostic build) — see `commands.log` §AC-5b | Strata | 0 | `artifacts/ac5.log`, `artifacts/runs/teacher_outputs.bin` |
| 6 | Free-running comparison | Strata | 1 (informational FAIL) | `artifacts/ac5b_free.log` |
| 7 | `./build-deepseek/model_family_test` | Strata | 0 | `artifacts/ac7.log` |
| 8 | `./build-deepseek/gguf_geometry_test` | Strata | 0 | `artifacts/ac7.log` |
| 9 | Qwen3.6 regression with signed `build-hip/strata` | Strata | 0 | `artifacts/ac7.log` |
| 10 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-015 --strict` | gfx1150-inference | 0 | `test-output.txt` tail |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command / check | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Build; signed binary untouched; oracle hash intact | `cmake --build build-deepseek …`; `sha256sum build-hip/strata`; `sha256sum $ORACLE` | build exit 0; `build-hip/strata` = `d58ee239…`; oracle = `a4c56b9d…` | PASS |
| AC-2 | Normal run refuses; `--families` unchanged | run with `--native $PACK`; run `--families` | exit 2, named refusal; `qwen4exp qwen35moe` | PASS |
| AC-3 | `--parity-run` gating incl. F2 fix | without `--dump-layers` on DeepSeek and Qwen; with dump | both exit 2; accepted run exit 0 + warning | PASS |
| AC-4 | Dump layout, N=28 | `stat -c%s`; `compare_layers.py --slots 28 --shape-only` | 1,187,840 B; 29 slots/record; N=28; 0 non-finite | PASS |
| AC-5b | **Teacher-forced gate** (DEC-046) | diagnostic build + `compare_layers.py --teacher-outputs` | stage 1 max 1.569942e-04; stage 2 max 1.569942e-04 at (4,3); all ≤ 5e-3; `RESULT: PASS` | PASS |
| AC-5b-info | Free-running trajectory reported | normal build + `compare_layers.py --slots 28 --dump` | first cell above bound = (19,1); stage 1 max 6.317236e-02; `RESULT: FAIL` (informational) | reported |
| AC-5b-qc | Verdict consistency check | `grep` each PASS-cited artifact for its verdict | all contain expected PASS / passed line | PASS |
| AC-6 | Deterministic | two dumps; `cmp` | byte-identical, 1,187,840 B | PASS |
| AC-7 | Qwen regression + tests green | `model_family_test`; `gguf_geometry_test`; HO-007 command | both tests ALL PASSED; 32 token IDs match HO-007 exactly | PASS |
| AC-8 | Memory + precision accounting | `cudaMemGetInfo` after alloc; dequant spot-check | 23.124 GiB used / 45.970 GiB total; max abs diff 0.0 | PASS |
| AC-9 | Geometry assertions (HO-012 F2) | startup assertion output | 28 / 2048 / 16 / 16 / 64 / 6 / 2 / 1408 / 1 / 1e4 / 1e-6 all ok | PASS |
| AC-10 | Patch exported and applies | `git format-patch db087d511..HEAD`; apply-check on `baf16363 + 0001 + 0002` | 0003 applies cleanly; S4b + cumulative stats recorded | PASS |
| AC-11 | Evidence gate | `check_bundle.py … --strict` | `RESULT: PASS` | PASS |
| AC-12 | Carried audit/QAQC criteria | A1–A4, A6–A8 in bundle | commands.log has A1; `hashes-notes.txt` has `## Commit pins`; bound printed; `--slots`/N=28 enforced; A6 statement below; A7/A8 in manifest | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| Q4_K_M pack (external) | `/home/kupipi/.cache/huggingface/hub/…/deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| f32 pack (external) | `/tmp/opencode/deepseek-moe-16b-f32.gguf` | `8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27` |
| Exact-f32 oracle (gate) | `workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin` | `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49` |
| Free-running engine dump | `artifacts/runs/s4b-free-normal.bin` | `4214269ecbbfd116c11ad4738f57cd9a04c27ef39b51c210ecb605398b097739` |
| Teacher-forced outputs | `artifacts/runs/teacher_outputs.bin` | `e0b6aa02061ad14ef854ff12988cf3571464de76e117493fca607ff020d79394` |
| Teacher-forced input residuals | `artifacts/runs/teacher_inputs.bin` | `d386c2d4344c9181297898e933128fab66d7e3b0046ce0a0b17f84551bda4b52` |
| Teacher-forced K/V history | `artifacts/runs/teacher_kv.bin` | `62ca264d1a6907c8656f22efee78b010bd8a107d69aed074994942ee9261b543` |
| Teacher input generator | `scripts/gen_teacher_inputs.py` | (computed after commit) |
| RW-1 regenerate proof | `artifacts/rw1-regenerate.txt` | (computed after commit) |
| MoE reference notes | `artifacts/llama-ref-moe.md` | `218a828915bfa3642fb7264fd829a7f694e2a506ca2e916450e674f5dd3a3a2c` |
| Patch apply-check record | `artifacts/apply-check.txt` | `07b81c899d7dfa0bc9c6858d66142ca82762445cae6e1f2541fd1c0f5ff4095d` |
| AC-5b teacher comparison | `artifacts/ac5.log` | `94e52860bf5fd1d12dcfc51f539d2757b84038c5fb08dc6641589a325583a707` |
| AC-5b stale-path attempt | `artifacts/ac5-stale-attempt.log` | `d334bce97d34547147d009be3628537f5363943fc08d58c065b062e9e03f6b1a` |
| AC-5b free-running comparison | `artifacts/ac5b_free.log` | `fba216bf0d2462800ab96e6c11bc8c7ef27eaecaf7b987e3c3c4fcd2e66169a7` |
| Verdict consistency check | `artifacts/verdict-consistency.txt` | `139cec21d3bcc273df2988cb594b221f97ccc24fe4295ac1c4d90b836a615995` |
| AC-7 tests/regression | `artifacts/ac7.log` | `72eb8fae286593dc2e135ee6adc1262efebac9acde3f18945b690c571cd7d18b` |
| AC-8 memory/dequant | `artifacts/ac8.log` | `a1ff604d485d8b3aceaa89f042bc7cf3514e469b5b021135a3a6989fd40f7400` |
| AC-9 geometry | `artifacts/ac9.log` | `60593cb9ef164a1b2a3225bdfcc55cc4615c5b7dddbfda1835696aa2dd15ccb5` |
| AC-10 patch stats | `artifacts/ac10.log` | `aabc959f4bc96437a4800fad7c8a5770e70ca454e4ce6c4a55fc8884d6b8e597` |
| Diagnostic unreachable proof | `artifacts/diag_unreachable.log` | `5f7cb282e336ecc34f29f40e88880b5924aafeefa5069ab21c28fa088877d578` |
| S4b patch | `patches/0003-s4b-moe.patch` | (computed after commit) |
| Comparison script | `scripts/compare_layers.py` | (computed after commit) |

## 4. Failures, skips, limits

- The free-running trajectory fails the 5e-3 bound at layer 19 position 1 (rel L2 2.668110e-02). This is **not treated as a handoff failure**: DEC-046 ruled it a router near-tie (6th/7th probability margin 2.80e-4, logit margin 6.62e-3). The teacher-forced run for the same cell is 2.372101e-05, proving the block arithmetic is correct. The free-running result is reported informationally in `artifacts/ac5b_free.log` and `artifacts/llama-ref-moe.md`.
- `artifacts/ac5-stale-attempt.log` preserves an earlier capture that accidentally used a non-existent dump path; it is **not** the cited gate artifact and is kept only for audit trail.
- No skips. All 112 teacher-forced cells were evaluated.

## 5. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` required for the HIP runtime.
- The signed `build-hip/strata` (hash `d58ee239…`) was never rebuilt; all DeepSeek development used `build-deepseek/`.
- The diagnostic teacher-forcing mode requires a temporary build with `#define STRATA_DEEPSEEK_DIAG` in `src/deepseek/ds_engine.cu`; it is not reachable in the committed tree.

## 6. Statement (A6)

This parity gate validates the **dequantise-to-f32-then-GEMV** path used by the DeepSeek parity engine. It does **not** validate Strata's production quantised-activation GEMM path. The exact-f32 oracle, the f32 pack, and the `ds_f32_matvec` implementation are the arithmetic reference; the dequant spot-check in AC-8 confirms the resident quantised payload dequantises to the same f32 values as a direct dequant.

## 7. A7 — extra target

The DeepSeek parity engine lives in the `strata_deepseek` CMake target and the new `src/deepseek/**` source files. No `src/core/**`, shared kernels, `src/qwen35/**`, tokenizer, or support-surface changes were made.

## 8. A8 — commit labels

- Strata final state: `e2e7e1b34…` on branch `strata-015-deepseek-s4b`.
- Workflow bundle: commit recorded in `hashes-notes.txt` `## Commit pins` table.
- Base commits: Strata `baf16363…` (main), `db087d511…` (S4a).

## 9. AC-5b self-contained reproduction

All inputs needed for the teacher-forced gate are now inside the bundle:

1. Generate `teacher_inputs.bin` and `teacher_kv.bin` (defaults write to
   `artifacts/runs/`):
   ```bash
   python3 workflow/evidence/HO-STRATA-015/scripts/gen_teacher_inputs.py
   ```
2. Build the diagnostic Strata binary (add `#define STRATA_DEEPSEEK_DIAG` in
   `src/deepseek/ds_engine.cu`, then `cmake --build build-deepseek --target strata`).
3. Run the gate:
   ```bash
   LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata \
     --parity-run --native $PACK \
     --dump-layers /tmp/opencode/teacher_dummy.bin \
     --parity-teacher-force workflow/evidence/HO-STRATA-015/artifacts/runs/teacher_inputs.bin,workflow/evidence/HO-STRATA-015/artifacts/runs/teacher_kv.bin,/tmp/opencode/teacher_outputs.bin,$ORACLE
   ```
4. Compare:
   ```bash
   python3 workflow/evidence/HO-STRATA-015/scripts/compare_layers.py \
     --oracle $ORACLE --teacher-outputs /tmp/opencode/teacher_outputs.bin
   ```

Expected: stage 1 and stage 2 max rel L2 `1.569942e-04` at `(layer=4, pos=3)`,
all 112 cells ≤ 5e-3, `RESULT: PASS`.

The RW-1 proof (`artifacts/rw1-regenerate.txt`) shows the committed script
reproduces the committed `teacher_inputs.bin` and `teacher_kv.bin` byte-for-byte.
