# Evidence manifest — HO-STRATA-014 (S4a)

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-014 |
| **Type / state** | ARCHITECT_TO_CODER / CODER_DONE |
| **Workflow commit / branch** | `4c29e9458ffcf2bf268f3cd3191f1f26f1beee18` / `wp/strata-014-deepseek-s4` |
| **Strata commit / branch** | `db087d5117abd6596fe0609605344bc4cc0ad318` / `strata-014-deepseek-s4` |
| **Base commits** | workflow `main` @ `d1a974db0ace2cc78d77efd1eec123ea93bb865b`; Strata `bac859ef91fb0d432eaf9675fc769bc3afe313cf` (S1–S3) |
| **Author / date (UTC)** | `coder-primary` (`opencode-go/kimi-k2.7-code`) / 2026-11-24 |
| **Environment** | Linux Mint 22.3 (Ubuntu 24.04 LTS base); kernel 7.0.0-42-generic; ROCm 10.1 (`core-10.1`); HIP 7.16.26385; AMD clang 24.0.0git; GCC 13.3.0; Python 3.14.10 |
| **Hardware profile** | AMD Ryzen AI 9 HX 370 w/ Radeon 890M; gfx1150; 92 GB unified memory |
| **Working directory** | `/home/kupipi/Documents/git/strata` |

## 1. Commands

All commands run from `/home/kupipi/Documents/git/strata` with `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`.

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)` | Strata | 0 | `test-output.txt` §AC-1 |
| 2a | `./build-deepseek/strata --native <pack> --tokens 1,2,3 --max-new 32 --max-context 1024` | Strata | 2 | `artifacts/refusal.txt` |
| 2b | `./build-deepseek/strata --families` | Strata | 0 | `artifacts/families.txt` |
| 3a | `./build-deepseek/strata --parity-run --native <pack> --tokens 1,2,3 --max-new 1 --max-context 1024` | Strata | 2 | `test-output.txt` §AC-3a |
| 3b | `./build-deepseek/strata --parity-run --native /tmp/opencode/unknown.gguf --dump-layers /tmp/opencode/dummy-dump.bin --tokens 1,2,3 --max-new 1 --max-context 1024` | Strata | 2 | `test-output.txt` §AC-3b |
| 3c | `./build-deepseek/strata --parity-run --native <pack> --dump-layers /tmp/opencode/s4-dump.bin --tokens 549,6077,280,7239 --max-new 1 --max-context 1024` | Strata | 0 | `test-output.txt` §AC-3c |
| 4 | `python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py --shape-only --oracle <f32-oracle> --dump /tmp/opencode/s4-dump.bin` | Strata | 0 | `test-output.txt` §AC-4 |
| 5a (gate) | `python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py --oracle <f32-oracle> --dump /tmp/opencode/s4-dump.bin` | Strata | 0 | `artifacts/compare-layers.txt` |
| 5a (floor) | `python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py --oracle <q4k-oracle> --dump /tmp/opencode/s4-dump.bin` | Strata | 1 (informative floor, not gated) | `test-output.txt` §AC-5a floor |
| 6 | Run AC-3c twice to `/tmp/opencode/s4-dump-1.bin` and `/tmp/opencode/s4-dump-2.bin`; `cmp` them | Strata | 0 | `test-output.txt` §AC-6 |
| 7a | `./build-deepseek/strata --native <qwen-pack> --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | Strata | 0 | `artifacts/qwen-regression.txt` |
| 7b | `./build-deepseek/model_family_test` | Strata | 0 | `artifacts/model_family_test-output.txt` |
| 7c | `./build-deepseek/gguf_geometry_test` | Strata | 0 | `artifacts/gguf_geometry_test-output.txt` |
| 8 | `git diff --stat bac859ef9..HEAD`; `git diff --stat baf16363..HEAD`; `git apply --check` of `0001` then `0002` in a clean `baf16363` worktree | Strata | 0 | `artifacts/patch-stat.txt`, `patches/apply-check.txt` |
| 9 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-014 --strict` | Workflow | 0 | `test-output.txt` §AC-9 |
| 10 | `artifacts/plan.md` present | — | — | `artifacts/plan.md` |
| diag | `ls /tmp/opencode/diag_*` before/after a `--parity-run --dump-layers` invocation | Strata | 0 | `artifacts/diag-inert.txt` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Build in `build-deepseek`; signed binary untouched | `cmake --build build-deepseek ...` | build exit 0; `build-hip/strata` = `d58ee239…` | PASS |
| AC-2 | Normal run refuses; `--families` unchanged | AC-2a/b | exit 2 with named DeepSeek refusal; `--families` prints exactly `qwen4exp qwen35moe` | PASS |
| AC-3 | `--parity-run` without `--dump-layers` refused; unknown-arch refused; with dump accepted | AC-3a/b/c | 3a exit 2 usage; 3b exit 2 refusal; 3c exit 0 + one stderr warning line | PASS |
| AC-4 | Dump layout contract | `stat` + `compare_layers.py --shape-only` | size 81920 B = 5 × 2 × 2048 × 4 (N+1=2 slots); 0 non-finite | PASS |
| AC-5a | Layer parity, block 0 vs f32 oracle | `compare_layers.py` | max rel L2 = 9.76e-5 ≤ 5e-3; 4 cells; `RESULT: PASS` | PASS |
| AC-5a floor | Q4_K floor (informative) | `compare_layers.py` vs HO-010 Q4_K | max = 2.05e-2; reported, not gated | (informative) |
| AC-6 | Deterministic | two dumps + `cmp` | byte-identical | PASS |
| AC-7 | Qwen regression + tests green | HO-007 command; unit tests | 32 IDs identical to HO-007; both tests exit 0 | PASS |
| AC-8 | Patch stats and clean apply | `git diff --stat`; `git apply --check` | S4: 10 files / +839; cumulative: 14 files / +1073 / −31; applies cleanly | PASS |
| AC-9 | `check_bundle.py --strict` PASS | `python3 workflow/tools/check_bundle.py ...` | `RESULT: PASS` | PASS |
| AC-10 | `artifacts/plan.md` present | inspection | present, references shape (B), file list, T2 impact, llama.cpp citations | PASS |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| Q4_K_M pack (input) | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| f32 converted pack (throwaway) | `/tmp/opencode/deepseek-moe-16b-f32.gguf` | `8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27` |
| f32 layer oracle (gate) | `workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin` | `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49` |
| Q4_K layer oracle (floor) | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin` | `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73` |
| Qwen pack | `/home/kupipi/Documents/models/gguf/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` |
| Engine dump run 1 | `workflow/evidence/HO-STRATA-014/artifacts/dump-run-1.bin` | (in `hashes.txt`) |
| Engine dump run 2 | `workflow/evidence/HO-STRATA-014/artifacts/dump-run-2.bin` | (in `hashes.txt`) |
| S4 patch | `workflow/evidence/HO-STRATA-014/patches/0002-s4-forward.patch` | (in `hashes.txt`) |
| Signed binary | `build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| llama.cpp pin | `78e05298f0d68abff41d08d79fa7469264b2aff0` (tag `b12527`) | commit pin |

**f32 conversion command** (produced `/tmp/opencode/deepseek-moe-16b-f32.gguf`):
```bash
cd /tmp/opencode/llama-ref && git checkout 78e05298f0d68abff41d08d79fa7469264b2aff0  # tag b12527
# build llama.cpp per HO-010 CPU-only recipe
/tmp/opencode/llama-ref/build/bin/llama-quantize --outtype f32 \
  <Q4_K_M pack> /tmp/opencode/deepseek-moe-16b-f32.gguf
```

## 4. Per-cell table (AC-5a gate)

| position | rel L2 (f32 oracle) |
|---|---|
| 0 | 9.757537e-05 |
| 1 | 5.944078e-05 |
| 2 | 6.385591e-05 |
| 3 | 5.652541e-05 |

**median:** 6.164835e-05; **max:** 9.757537e-05 at `(layer=0, pos=0)`; **bound:** 5e-3; **verdict:** PASS.

## 5. Q4_K informative floor (not gated)

| position | rel L2 (Q4_K oracle) |
|---|---|
| 0 | 1.939394e-02 |
| 1 | 1.257641e-02 |
| 2 | 2.054810e-02 |
| 3 | 1.333939e-02 |

**median:** 1.636667e-02; **max:** 2.054810e-02 at `(layer=0, pos=2)`. Reported per DEC-044 §4 as the informative floor; the gate is the f32 oracle above.

## 6. Patch stats (T2)

- S4a only (`bac859ef9..HEAD`): **10 files changed, 839 insertions(+)**.
- Cumulative S1–S4a (`baf16363..HEAD`): **14 files changed, 1073 insertions(+), 31 deletions(-)**.

The S1–S3 base was already 6 files / 234 insertions / 31 deletions (DEC-034). S4a adds the `src/deepseek/**` engine path and test extensions as approved by DEC-043 (shape B, dedicated path, split into S4a/S4b).

## 7. Failures, skips, limits

- None. The Q4_K oracle comparison exits 1 by design; it is recorded as an informative floor, not a gate failure.
- AC-5b (layers 1–27, 108 cells) is explicitly out of scope and moves to HO-STRATA-015.
- Token/logit parity and the support flip are out of scope (S5 / HO-STRATA-016).

## 8. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is required for the `build-deepseek/strata` binary to find ROCm libraries.
- `STRATA_DEEPSEEK_DIAG` is undefined in the normal build; diagnostic dumps are gated behind `#ifdef STRATA_DEEPSEEK_DIAG`.
- No `HSA_OVERRIDE_GFX_VERSION` or other gfx override is used; the binary targets gfx1150 natively.
- The Q4_K_M pack path is outside the repo; only its hash and the conversion command are recorded.

## 9. Statement

- [x] Commands are reproducible.
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets, tokens, or private data in the bundle.
- [x] Every claim cites an artifact.
- [x] One profile per claim: gfx1150 / Radeon 890M / ROCm 10.1 / DeepSeek-MoE-16B Q4_K_M / 4-token prompt.
