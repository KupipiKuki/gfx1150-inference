# QAQC report — HO-STRATA-012

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-012 (DeepSeek S1–S3), QAQC handoff HO-STRATA-012-QAQC |
| **Reviewer** | QAQC — seat `opencode/claude-sonnet-5-5` under DEC-036 (temporary substitution while the Gemini seat is billing-capped) |
| **Date (UTC)** | 2026-11-20 |
| **Verdict** | **PASS** |
| **Scope reviewed** | Strata patch `workflow/evidence/HO-STRATA-012/patches/0001-deepseek-family.patch` (Strata commit `bac859ef9`, base `baf16363b`), evidence bundle at gfx1150-inference `b15b4bc` |

Profile: AMD Radeon 890M (gfx1150), ROCm core-10.1, HIP Release build in a throwaway worktree. DeepSeek-MoE-16B-base Q4_K_M (`f00ecd83…`) for inspect/refusal; Qwen3.6-35B-A3B UD-Q4_K_XL for the regression. No perf claim is made or accepted; the tok/s lines in the logs are incidental.

Method: fresh `git worktree add /tmp/opencode/q12 baf16363` (a stale worktree from an earlier attempt was deleted and recreated, not reused). `git apply --check` then apply. Configure with the requested flags **plus `-DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF`** (without them the build is CPU-only and has no `strata` target). Built `strata model_family_test gguf_geometry_test` (3m07s). `build-hip/` untouched.

## 1. Acceptance criteria re-run

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | Family recognised | `build-qaqc/model_family_test` | `ALL PASSED`, rc 0; includes "model_family: … deepseek …", "guard accepts deepseek", "engine guard refuses DeepSeek: recognised, not supported yet" | PASS |
| 2 | Named refusal, no PLE | `strata --native <deepseek.gguf> --tokens 1,2,3 --max-new 32 --max-context 1024` | rc **2**; `DeepSeek-MoE-16B-base (architecture 'deepseek') is recognised by Strata but this build does not run it yet`; `grep -ci ple` → 0 | PASS |
| 3 | `--families` unchanged | `strata --families` | `qwen4exp qwen35moe`, rc 0 | PASS |
| 4 | 12 geometry fields | `strata --inspect <deepseek.gguf>` | rc **0**; block_count 28, embedding_length 2048, head_count 16, head_count_kv 16, expert_count 64, expert_used_count 6, expert_shared_count 2, expert_feed_forward_length 1408, feed_forward_length 10944, leading_dense_block_count 1, rope.freq_base 10000, rms_epsilon 1e-06; output is byte-identical (`cmp`) to `artifacts/inspect-deepseek.txt` | PASS |
| 5 | 363 tensors | same | `tensors: 363`; 363 tensor lines | PASS |
| 6 | Mismatch refused | `strata --inspect /tmp/opencode/deepseek-mismatched.gguf` (the coder's pre-existing modified copy, `blk.0.attn_q.weight` [2049,2048]) | rc **2**; `blk.0.attn_q.weight is [2049, 2048], the DeepSeek-MoE-16B-base layout wants [2048, 2048]` = evidence | PASS (see F3) |
| 7 | Qwen regression | `strata --native Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | rc 0; 32 IDs `11751 11 264 3177 … 54832 13 11751 369 1048 10919` **exactly equal** to `HO-STRATA-007/artifacts/generated-token-ids.txt` | PASS |
| 8 | Signed binary intact | `sha256sum build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` | PASS |
| 9 | Patch stat | `git apply --stat` / `git diff --stat bac859ef9^..bac859ef9` | 6 files, 234 insertions(+), 31 deletions(-); evidence patch sha256 `9a7b280f…` equals `git format-patch -1 bac859ef9` | PASS |
| 10 | Patch applies cleanly | `git apply --check` on clean `baf16363` | exit 0 | PASS |
| 11 | Unit tests | `model_family_test`; `gguf_geometry_test` | `ALL PASSED` (rc 0); `gguf_geometry_test: all passed` (rc 0) | PASS |
| 12 | Bundle hashes | `sha256sum -c workflow/evidence/HO-STRATA-012/hashes.txt` (repo root) | 10/10 OK | PASS |
| 13 | Fresh clone | `git archive b15b4bc \| tar -x -C /tmp/opencode/q12-fresh`; `sha256sum -c hashes.txt` | 10/10 OK, 0 failures | PASS |

## 2. Diff and guard-rail review

- [x] Diff is within scope; no unrelated files. Six files only: `gguf_reader.hpp` (deepseek key guard + dispatch), `model_family.hpp` (enum, arch/title, refusal text), `family_layout.hpp` (geometry read, layer/global tensor table, `inspect_gguf`), `geometry.hpp` (4 metadata fields), `generate.cpp` (`--inspect` flag, 10 lines), `model_family_test.cpp` (tests).
- [x] **Patch scope:** no kernel code, no forward pass, no attention/routing/RoPE/MoE compute. `--inspect` reads GGUF metadata and tensor shapes only (no GPU). Layout table only lists tensor names/shapes. `model_family_runs` is unchanged (only `Qwen4Exp`), so `--native` still refuses DeepSeek. Qwen paths: geometry branch for DeepSeek returns early; the Qwen parsing code is moved only by hoisting `bad`/`buf`; qwen layouts/guards unchanged; regression IDs identical.
- [x] No new dependencies, no downloads (all models pre-existing locally).
- [x] No secrets in the patch or bundle (grep-free review of the patch; evidence is paths/hashes/outputs).
- [x] Tests meaningful: new geometry, guard, engine-refusal, missing-tensor, wrong-shape and extra-tensor cases; no skips.
- [x] Evidence matches commands (outputs reproduced byte-identically for inspect, refusal and mismatch; regression IDs identical).
- [x] No perf claim.

## 3. Findings (severity order)

| # | Severity | Finding | File:line / evidence | Required action |
|---|---|---|---|---|
| F1 | Minor | `model_family_not_supported()` text is shared by all not-run families; the old suffix ("runs on the NVIDIA (CUDA) and AMD (HIP) builds… use a CUDA or HIP build, or a Qwen3.8-Flash-Next model file") was dropped. This also changes the refusal text for Qwen3.6 on the guard path (the test still asserts the "does not run it yet" substring). It is a message only, not behaviour, and the handoff's required refusal wording makes it necessary. Qwen3.6 generation (via the `strata-q36` path) is unaffected. | `model_family.hpp` diff | Auditor to note; no rework. |
| F2 | Minor | `check_architecture_deepseek` checks key presence/numeric only; sanity (non-zero, `n_head % n_head_kv`, dense-block range) is in `geometry_from_gguf`, reached by `--inspect`. Acceptable for S1–S3. | `gguf_reader.hpp`, `family_layout.hpp` | None. |
| F3 | Minor (process) | Criterion 6 used the coder's pre-existing 10.8 GB modified copy (`/tmp/opencode/deepseek-mismatched.gguf`); I did not regenerate it, so its provenance is the coder's command in `commands.log` C7. The refusal is independently reproduced and names tensor + both shapes. A stale `/tmp/opencode/q12` worktree with the patch already applied was found at start; I removed it and re-did step 1 on a fresh worktree. | n/a | None; the 10.8 GB file remains in `/tmp/opencode` for the owner to delete. |
| F4 | Info | The requested configure flags give a CPU-only build; `-DSTRATA_ENABLE_HIP=ON` is needed (as in the coder's C1). | n/a | None. |

No Blocker or Major findings.

## 4. Verdict and next state

**PASS** → `AUDIT_REVIEW`. No rework. `RW-HO-STRATA-012-2` not created.

### QAQC_TO_AUDITOR (embedded per DEC-018)

| Field | Value |
|---|---|
| **Type** | QAQC_TO_AUDITOR |
| **From → To** | QAQC (`opencode/claude-sonnet-5-5`, DEC-036) → Auditor |
| **Handoff** | HO-STRATA-012 (DeepSeek S1–S3) |
| **State** | AUDIT_REVIEW requested |
| **Report** | `workflow/reports/qaqc/HO-STRATA-012-qaqc.md` |
| **Evidence** | `workflow/evidence/HO-STRATA-012/` (hashes 10/10 OK at `b15b4bc`, also from a fresh `git archive`) |
| **Strata branch** | `strata-012-deepseek-s1` @ `bac859ef9`, base `baf16363b`; push still pending (HTTPS credentials), the patch file is the transport |
| **Open items** | F1 (refusal text shared with Qwen3.6 guard path), F3 (QAQC reused coder's mismatch file) |

## 5. Statement

I did not modify code, tests, docs, or configuration in the repository. All builds were in the throwaway worktree `/tmp/opencode/q12` (removed), `build-hip/` untouched, and this report is the only artifact I wrote.
