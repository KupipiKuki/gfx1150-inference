# Evidence manifest — HO-STRATA-016

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-016 — DeepSeek S5: exact token parity, KL, and the support claim |
| **Commit / branch (Strata)** | `3c2f895552963403a71249702a676ee61d532e3c` on `strata-016-deepseek-s5` (prev `59c83e2e8b5b24903dd087924f7bd47dcc297817`, base `e2e7e1b347b4ac39cf51e7bf3eecaaf771a933f4`) |
| **Commit / branch (workflow)** | `wp/strata-016-deepseek-s5`; the capture commit carrying every pinned bundle file: see `hashes-notes.txt` §Commit pins (C1) |
| **Author / date (UTC)** | Primary Coder / 2026-11-27 |
| **Environment** | Linux 7.0.0-42-generic · AMD gfx1150 (Radeon 890M iGPU, Ryzen AI 9 HX 370) · ROCm 10.1 (`/opt/rocm/core-10.1`, HIP 7.16.26385, clang 24.0.0git) · cmake 3.28.3 · gcc 13.3.0 · Python 3.14.10 |
| **Working directory** | `/home/kupipi/Documents/git/strata` for engine/oracle commands; `/home/kupipi/Documents/git/gfx1150-inference` for bundle commands |

## 1. Commands

`commands.log` holds the full copy-paste list (cwd, env, exit codes; DEC-041 §2:
captures to `/tmp` then move, `;` never `&&`). Key commands:

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)` | Strata | 0 | `artifacts/ac1-build.txt` |
| 2 | `sha256sum build-hip/strata` / `sha256sum workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin` | both repos | 0 | `artifacts/ac1-build.txt` |
| 3 | `LD_LIBRARY_PATH=/tmp/opencode/llama-ref/build/bin /tmp/opencode/oracle_s5 --model $PACK --tokens $T --n 16 --dump-logits-full <dump>` (×3; same for `$F32`) | gfx1150-inference | 0 | `artifacts/runs/{q4k,f32}_p{1,2,3}_tokens.txt` |
| 4 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --native $PACK --tokens $T --max-new 16 --dump-logits-full <dump>` (×3, + ×3 run2, + nodump ×1, + flip run ×1) | Strata | 0 | `artifacts/runs/engine_p*_tokens.txt`, `artifacts/determinism.txt`, `artifacts/ac7-nodump.txt`, `artifacts/flip.txt` |
| 5 | `python3 workflow/evidence/HO-STRATA-016/scripts/compute_kl.py --engine … --q4k … --f32 … --prompt P{i}` | gfx1150-inference | 0 | `artifacts/runs/kl_p{i}.txt`, `artifacts/kl_summary.txt` |
| 6 | flip pair: `./build-deepseek/strata --families`; `./build-hip/strata --families`; `./build-hip/strata --native $PACK …` | Strata | 0,0,0,2 | `artifacts/flip.txt` |
| 7 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-hip/strata --native $QWEN --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | Strata | 0 | `artifacts/qwen_regression.txt` |
| 8 | `python3 workflow/evidence/HO-STRATA-016/scripts/verdict_check.py` | gfx1150-inference | 0 | `artifacts/verdict-consistency.txt` |
| 9 | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-016 --strict` | gfx1150-inference | 0 | `artifacts/check_bundle.txt` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command / check | Observed | Pass? |
|---|---|---|---|---|
| AC-1 | Builds; signed binary + oracles untouched | cmds 1–2 | build exit 0; `build-hip/strata` = `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858`; HO-014 f32 oracle dump = `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49` | PASS |
| AC-2 | Reference set for all 3 prompts; P1 reproduces signed run1; f32 agrees | cmd 3 | P1 `8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` (= HO-010 run1.txt); P2/P3 recorded; f32 pack gives the same 3 sets (0 differences) | PASS |
| AC-3 | **Token parity — the gate**: zero mismatches vs Q4_K oracle | cmd 4, `artifacts/token_parity.txt` | **0 / 48 mismatches**. P1 as AC-2; P2 `245 919 270 185 185 185 1558 1097 7 64 11 270 1780 185 300 972`; P3 `3074 11 5501 11 285 10421 13 185 549 6663 8247 418 254 8247 344 2977` | PASS |
| AC-4 | **KL ceiling** (DEC-047): mean ≤ 1e-2, no step > 1e-1 vs f32 oracle | cmd 5, `artifacts/kl_summary.txt` | engine‖f32 — P1 mean 6.423478e-07 / max 5.986760e-06; P2 2.939280e-09 / 1.749473e-08; P3 1.190731e-08 / 3.725756e-08. Context (not gated): engine‖Q4_K P1 2.273449e-02, P2 1.398608e-03, P3 2.349162e-02; Q4_K‖f32 P1 1.774180e-02, P2 1.416297e-03, P3 3.165630e-02 | PASS |
| AC-5 | Sampler determinism | cmd 4 (run2), `cmp` | token lines identical ×3; logits dumps byte-identical ×3 (`cmp` exit 0) | PASS |
| AC-6 | **Support flip, both directions** | cmd 6, `artifacts/flip.txt` | `build-deepseek --families` → `qwen4exp qwen35moe deepseek`; `--native` runs without `--parity-run` and emits AC-3's P1; `build-hip --families` → `qwen4exp qwen35moe`; `build-hip --native` → named refusal, exit 2 | PASS |
| AC-7 | `--dump-layers` optional | `artifacts/ac7-nodump.txt` | run with no dump flags: exit 0, token line emitted, no dump file written (dir diff before/after; `ls *.bin` exit 2 = no match) | PASS |
| AC-8 | Qwen regression + tests: the 32 HO-007 IDs; both tests exit 0 incl. updated `--families`/refusal tests | cmds 4,7, `./build-deepseek/model_family_test`, `./build-deepseek/gguf_geometry_test` | `gen: 11751 11 264 3177 34756 364 1141 25438 57902 1680 430 279 242476 300 21262 11 279 9440 46890 15849 11 321 279 42027 9141 368 54832 13 11751 369 1048 10919` — `diff` vs HO-007 exit 0 (bit-identical); `model_family_test` ALL PASSED exit 0; `gguf_geometry_test` all passed exit 0 | PASS |
| AC-9 | Geometry/route assertions unchanged | startup block in `artifacts/flip.txt`, `artifacts/runs/engine_p*_tokens.txt` | the 11 fields still asserted, all `ok` | PASS |
| AC-10 | Patch measured, exported, applies | `git diff --stat e2e7e1b..HEAD` / `baf16363..HEAD`; `patches/0004-s5-tokens.patch`; apply-check | S5 delta: 5 files, +181 / −57. Cumulative through S4a+S4b+S5 (`baf16363..HEAD`): **15 files, +1,782 / −33**. 0004 applies (`git apply --check` exit 0) on `baf16363`+0001+0002+0003 (each exit 0) | PASS |
| AC-11 | Evidence gate | cmd 9 | `check_bundle.py … --strict` — `RESULT: PASS` in `artifacts/check_bundle.txt` (its own tail carries the verdict; stored via the DEC-041 §2 fixed-point loop, proof in §4 below) | PASS |
| AC-12 | Carried audit criteria (A12, A14, A18, A10/11/13/16) | `scripts/verdict_check.py`, this manifest §4 | verdict-consistency covers **all 21 PASS-cited artifact claims** with a recorded command (`artifacts/verdict-consistency.txt`, exit 0); block-0 assertion via `token_embd` present in every engine run; gap convention stated (§4); env row corrected with actual kernel/Python (A10); AC-8 wording as the handoff; no placeholders in labels (A13); generators committed and re-run (§4, A16) | PASS |
| AC-13 | No claim without an artifact | every row above cites a command in `commands.log` and a file under this bundle; the KL/parity/margin/flip/regression numbers appear verbatim in `artifacts/*` | grep-verified by QAQC re-run of the cited commands | PASS |

## 3. Artifacts and hashes

All bundle files are listed with full SHA-256 in `hashes.txt` (repo-relative).
External and immutable digests, commit pins, and provenance notes are in
`hashes-notes.txt`. Key external inputs:

| Artifact | Path | SHA256 |
|---|---|---|
| Q4_K_M pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| f32 pack (exact reference) | `/tmp/opencode/deepseek-moe-16b-f32.gguf` | `8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27` |
| Signed binary (never rebuilt) | `build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| Engine binary (this build) | `build-deepseek/strata` | `8b84f55a8332be1340decb94f85fcc49ad6f483ceb9e1889b8d6826b986ae432` |
| Oracle harness | `/tmp/opencode/oracle_s5` (built from `scripts/oracle_s5.cpp`, parent hash recorded, llama.cpp pin `78e05298f0d68abff41d08d79fa7469264b2aff0`) | `a9575ffd3ae6bde3126b39c1e17b72264dff3169b23c8a1070976d57f691d169` |
| HO-014 exact-f32 oracle dump (intact) | `workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin` | `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49` |
| HO-007 Qwen IDs (comparison basis) | `workflow/evidence/HO-STRATA-007/artifacts/generated-token-ids.txt` | listed in `hashes.txt` |
| HO-010 P1 reference | `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt` | listed in `hashes.txt` |

**Logits dumps — size decision (§5 of the handoff, A16-class):** the 12 raw
full-logits dumps (3 prompts × {engine, engine-run2, Q4_K, f32}, each
6,553,600 bytes ≈ 6.25 MiB, total ≈ 78.6 MiB) exceed the bundle's practical
scale, so they are **not committed**. They are kept external at
`/tmp/opencode/HO-STRATA-016-dumps/`, their SHA-256 digests are recorded in
`hashes-notes.txt`, and they are regenerable byte-for-byte from this bundle
with the committed generator (`scripts/oracle_s5.cpp` + the pinned oracle
binary; engine dumps regenerate from the pinned Strata commit) using the
exact commands in `commands.log` §AC-2/AC-3/AC-5 — re-verified this session:
fresh re-runs `cmp` byte-identical to the stored digests (6/6 oracle, 6/6
engine including run2).

## 4. Failures, skips, limits

- **No AC failed.** Raw outputs are in `test-output.txt` and `artifacts/`.
- **Profile (one profile per claim):** gfx1150 / Radeon 890M / Ryzen AI 9 HX 370 /
  ROCm 10.1 / DeepSeek-MoE-16B Q4_K_M / greedy / 16 tokens / 3 prompts. Every
  number above is from this profile only.
- **A6 (carried):** this parity run validates the **f32 GEMV path** of the
  engine and, newly, greedy sampling (argmax; ties → lowest id,
  `ds_engine.cu:548`); the production **quantized GEMM path is not exercised**
  by any S5 claim, and none is made about it.
- **A18 (gap sign convention, carried from HO-015):** the S4b artifact
  `−1.3845e-4` is the `40 − 33` order and the prose `+1.385e-4` is the
  `33 − 40` order — one and the same physical event, equal magnitude, opposite
  subtraction order. Both are correct; the convention is stated once here.
- **A14 (block-0 input assertion, closed in S5):** the ≤1e-6 injection
  assertion lives in the engine (recorded deviation from DEC-046 condition 2,
  which literally names `compare_layers.py`); in S5 every free-run position
  additionally asserts the block-0 input (`b.residual`) against a direct,
  independent dequant of that token's row from the GGUF payload
  (second `GgufModel` reader; `ds_engine.cu` at Strata commit `3c2f89555`),
  required bit-exact: 21/26/20 positions ok across P1/P2/P3 (visible in
  `artifacts/flip.txt` and every `artifacts/runs/engine_p*_tokens.txt`).
  **Read-only proof:** all six engine logits dumps re-captured after the
  change are byte-identical (`cmp` exit 0) to the pre-change dumps — the
  assertion changed no arithmetic (guard rail honoured).
- **Oracle env:** the oracle harness needs `LD_LIBRARY_PATH=/tmp/opencode/llama-ref/build/bin`
  (missing it exits 127); engine commands need `/opt/rocm/core-10.1/lib`.
  Both were re-recorded in `commands.log` this session.
- **Fixed point (AC-11, DEC-041 §2):** `artifacts/check_bundle.txt` was
  produced after the final capture and the hashes; the loop was iterated until
  a fresh `--strict` run on the committed tree was byte-identical (`cmp` exit 0)
  to the stored file. Raw proof lines live in `commands.log` / this file's
  history; QAQC reproduces by simply re-running cmd 9.
- **KL context curves** (engine‖Q4_K, Q4_K‖f32) are reported per DEC-047 §3
  and are **not** gates; the step-3/step-2 peaks (3.20e-01 / 3.32e-01) sit on
  the *shipment* comparison and the quantization gap, not on the gated curve.
- **No perf claim** is made or implied anywhere in this bundle; throughput
  lines in the Qwen transcript are incidental output, not claims (S6 owns perf).
- Not tested here (out of scope per §2 of the handoff): tokenizer behaviour,
  other quantizations, batching, MTP, serving.

## 5. Environment notes

- `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` for all Strata binary runs;
  `LD_LIBRARY_PATH=/tmp/opencode/llama-ref/build/bin` for `oracle_s5` only.
- No `GFX1150_SKIP_CMAKE` / `HSA_OVERRIDE_GFX_VERSION` in play: native gfx1150.
- `build-hip/` was **not** rebuilt (guard rail); `d58ee239…` verified identical
  before and after all captures (`artifacts/ac1-build.txt`).
- Host caveats: 47.0 GiB device memory total; engine load + buffers measured
  23.821 GiB used (`artifacts/flip.txt`), reported by the engine, not claimed.

## 6. Statement

- [x] Commands are reproducible (`commands.log`, copy-paste with cwd + env).
- [x] Outputs are raw; failures/skips would be kept verbatim — none occurred in AC runs.
- [x] No secrets (B7 clean by `check_bundle --strict`).
- [x] Every claim cites a command (`commands.log`) and a file containing it (AC-13).
- [x] One profile per claim (§4 profile line).
