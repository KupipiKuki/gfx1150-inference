# HO-STRATA-015 — DeepSeek S4b: the MoE blocks, layers 1–27

| Field | Value |
|---|---|
| **ID** | HO-STRATA-015 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **CODER_DONE** (2026-11-26) — evidence bundle complete, `check_bundle.py --strict` PASS |
| **Created / updated (UTC)** | 2026-11-25 / 2026-11-25 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `deepseek-s4b` |
| **Branch (workflow)** | `wp/strata-015-deepseek-s4b` / base `main` @ `b791242e0330b2ae5c560c5e937f51e0372e7014` |
| **Branch (Strata checkout)** | `strata-015-deepseek-s4b`, cut from `strata-014-deepseek-s4` @ `db087d5117abd6596fe0609605344bc4cc0ad318` (S1–S3 + S4a included; never `main`) |
| **Priority / timebox** | P1 · 2 working days coder time + 1 day per gate cycle |
| **Predecessor** | `HO-STRATA-014` (**DONE, SIGNED, MERGED #29**) · `HO-STRATA-014-APPROVAL.md` §4 (the carried criteria) |
| **Plan** | `planning/strata-engine/13-family-support-test-plan.md` §4 **S4** |
| **Evidence gate** | `workflow/tools/check_bundle.py … --strict` (DEC-041), PASS before `CODER_DONE` |

## 0. What this handoff is

S4a proved **block 0** — embedding → RMSNorm → MHA(16/16) → NORM-style RoPE →
dense SwiGLU FFN → residual — to **9.76e-05** against an arithmetic-exact
reference (DEC-044). S4b adds the **27 MoE blocks** and gates them on the same
reference, at the same **5e-3**, over **108 then 112 cells**.

When S4b passes, the engine computes the whole DeepSeek-MoE-16B forward pass and
dumps every layer. It still **does not run the family**: `model_family_runs()`
stays `false`, the named refusal and `--families` are unchanged, and the parity
path stays behind `--parity-run`. That is S5 (HO-STRATA-016), which needs exact
**token** parity.

## 1. Scope (in)

### 1.1 The MoE block

Per block `l = 1…27`, after the same attention path S4a proved:

| Component | Value | Source |
|---|---|---|
| router | `ffn_gate_inp.weight` `[2048, 64]`, softmax over all 64, **top-6** | §1.2 |
| expert weights | **not renormalised** over the selected set (`norm_w = false`) | §1.2 |
| shared experts | 2, **always active**, `ffn_gate_shexp` / `ffn_up_shexp` / `ffn_down_shexp`, FF 1408 | §1.2 |
| routed experts | 64 × (`ffn_gate_exps`, `ffn_up_exps`, `ffn_down_exps`), FF 1408 | layout |
| placement | shared branch is **inside** the FFN branch, summed with the routed experts, then the residual | §1.2 |
| FFN activation | SwiGLU, as block 0 | `llama-ref-graph.md` |

Tensor names and shapes are already declared by S1–S3 in
`include/strata/core/family_layout.hpp` (`layer_tensors`, the DeepSeek branch) —
use them; a mismatch there is a **finding**, not a place to improvise.

**HO-012 F2 (carried):** `check_architecture_deepseek` checks presence and
numerics only; the *ranges* live in `geometry_from_gguf`. Verify at least
`expert_count == 64`, `expert_used_count == 6`, `expert_shared_count == 2`,
`expert_feed_forward_length == 1408` are read from metadata and asserted before
the forward starts, and record the assertion output.

### 1.2 Arithmetic source of truth

Still the llama.cpp tree at `78e05298f0d68abff41d08d79fa7469264b2aff0`, cited
file:line in the evidence. `artifacts/llama-ref-graph.md` from HO-014 already
carries the MoE lines (`src/models/deepseek.cpp:47-65`, `:138-164`; top-k at
`src/llama-graph.cpp:2411-2412`, `:2426`; `norm_w=false` at
`src/models/deepseek.cpp:145`; shared placement `:152-166`). Re-verify each
citation against the tree before implementing from it, and add a
`llama-ref-moe.md` with the router/expert pseudocode and the exact citation per
step. Do not port from memory or from `docs/DEEPSEEK41.md`.

### 1.3 Arithmetic precision — **exact f32, no q8_K emulation**

DEC-044 §5 stands: the parity path dequantises weights to f32 and does an f32
dot. **Do not** reproduce llama.cpp's q8_K-quantised-activation matmul; the
reference is the f32 conversion of the same pack and its whole point is to be
arithmetic-clean.

### 1.4 Memory (QAQC F3, now a criterion)

S4a's `upload_weight()` keeps the quantised payload **and** an f32 copy, and its
`q8_1_scratch` is unused. At 27 MoE blocks that is ~76 GB against 92 GB unified
memory — tight on gfx1150's GTT aperture and unnecessary. Required approach:

- keep the **quantised** bytes as the resident copy (that is the pack's size,
  10.10 GiB total);
- dequantise **per matmul or per block** into a scratch buffer using the existing
  `ds_f32_matvec` path, so the f32 materialisation is bounded and reused;
- **assert the dequantised values are identical** to a direct dequant of the same
  tensor (one spot-check per quant type in the evidence), so the memory change
  cannot alter the arithmetic;
- record peak device and peak host allocation, and keep it under the profile's
  GTT budget.

### 1.5 Gate the tool first (audit A3, A4 — **A4 is blocking**)

`workflow/evidence/HO-STRATA-015/scripts/compare_layers.py` is a **new copy** in
this bundle (the S4a bundle is merged and immutable). It must:

1. take the block count **explicitly** — `--slots N` (or read the engine's
   `N layers + the input` line) — and **assert `N == 28`** before comparing;
   the current smallest-divisor inference would read an S4b dump (`4 records ×
   29 slots`, `R = 116`) as `N = 1` and **print PASS having compared block 0
   only**. That is the trap this criterion exists to close;
2. **not** accept a caller-supplied bound: fixed at **5e-3**, and the bound used
   is printed on every run, PASS included (audit A3);
3. reject a dump whose slot count or oracle block count disagrees, rather than
   reshaping it.

### 1.6 F2 — `--parity-run` gating (QAQC F2)

`if (dump_path.empty())` is nested inside the `deepseek` branch in
`src/program/generate.cpp`, so `--parity-run` on a **supported** model without
`--dump-layers` is silently ignored. Hoist it so the flag is either honoured or
refused for every family, and add a unit test for the supported-model case.

## 2. Out of scope

- **Token parity, logits, lm_head, sampling, KL** — S5 (HO-STRATA-016).
- `model_family_runs()`, `--families`, the refusal text — unchanged. No support
  claim of any kind.
- Any qwen4exp / qwen35moe behaviour change; the tokenizer; OLMoE.
- `src/core/**`, shared kernels, `src/qwen35/**` — if the MoE path genuinely
  needs them, **stop and raise a deviation** (DEC-043's re-review trigger).
- Performance work: no pooling, expert cache/streaming, batching, MTP, or new
  fast-path kernels. Correctness only.
- Widening 5e-3. A failed cell is a finding; widening is a deviation.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Pack, DeepSeek-MoE-16B-base Q4_K_M | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` | available |
| **Exact-arithmetic layer reference (the gate)** | `workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin`, `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49`, `[4][28][2048]` — **already covers layers 1–27** | merged (#29) |
| f32 pack (regenerate the dump only if the hash disagrees) | `/tmp/opencode/deepseek-moe-16b-f32.gguf`, `8cd778a7fd6a077fe2d64aa7a7d47fe628c044f9e6439e53a258fd4d9e591f27` | on disk |
| Q4_K dump (**informative floor only**) | `workflow/evidence/HO-STRATA-010/…/deepseek_p1_4_layers.bin`, `db6eccb3…` | signed |
| Harness for regenerating either dump | `workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp` + the command in `HO-STRATA-014-APPROVAL.md` §4 (A1) | merged |
| S4a engine + patches | Strata `db087d511`; `HO-STRATA-014/patches/0002-s4-forward.patch` | merged |
| MoE graph citations | `HO-STRATA-014/artifacts/llama-ref-graph.md`, re-verified per §1.2 | merged |
| Prompt / positions | tokens `549,6077,280,7239`, 4 positions, greedy | fixed |
| Strata pin / llama.cpp pin | `baf16363…` / `78e05298…` | pinned |

**The oracle already has all 28 layers**, so S4b adds no new reference work. Do
not regenerate it unless the hash check in AC-1 fails.

## 4. Acceptance criteria

Run from the Strata checkout with `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`.
`<pack>` = §3 row 1; `<f32-dump>` = §3 row 2.

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| **AC-1** | Builds; signed binary untouched; reference hash intact | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)`; `sha256sum build-hip/strata`; `sha256sum <f32-dump>` | exit 0; `d58ee239…` unchanged; `a4c56b9d…` unchanged |
| **AC-2** | Normal runs still refuse, verbatim; `--families` unchanged | the HO-012 C6 command; `--families` | exit 2, refusal line byte-identical; `qwen4exp qwen35moe` |
| **AC-3** | `--parity-run` gating incl. the F2 fix | no `--dump-layers` (**on the DeepSeek pack and on a supported qwen pack**); unknown arch; accepted run | first two exit ≠ 0 (the supported-model case now also refuses); third exit 0 + the one-line warning |
| **AC-4** | Dump layout, **N = 28** | `stat -c%s`; the run's `layers dumped` line; `compare_layers.py --slots 28 --shape-only` | `5 × 29 × 2048 × 4 = 1,187,840` B; line reads `28 layers + the input`; tool asserts N=28; zero non-finite |
| **AC-5b** | **MoE layer parity — the gate, TEACHER-FORCED** (DEC-046) | `compare_layers.py --slots 28 --oracle <f32-dump> --dump <engine dump>` | each cell `(l,p)` runs block `l` alone from the **reference's** residual at that slot (and its K/V for positions `<p`), asserted to match the reference (≤1e-6); stage 1 **layers 1–27, 108 cells**, stage 2 **all 112**, max rel L2 **≤ 5e-3** in both; worst cell named, every cell printed, bound printed; `RESULT: PASS`. **The free-running trajectory is still produced and reported as informational** with the first divergent cell and the 6th/7th margin (DEC-046) |
| **AC-6** | Deterministic | two runs; `cmp` | byte-identical |
| **AC-7** | Qwen regression + tests green | HO-012 C8 command; `model_family_test`; `gguf_geometry_test` | the 32 HO-007 IDs in order; both exit 0, including the new F2 test |
| **AC-8** | Memory + precision accounting | peak device/host allocation recorded; the per-quant-type dequant spot-check | peak under the GTT budget; dequantised values identical to a direct dequant (`max abs diff` recorded) |
| **AC-9** | Geometry assertions (HO-012 F2 carried) | the startup assertion output | 28 / 2048 / 16 / 16 / 64 / 6 / 2 / 1408 / 1 / 1e4 / 1e-6 read from metadata and asserted |
| **AC-10** | Patch measured, exported, applies | `git diff --stat db087d511..HEAD`; cumulative vs `baf16363`; `format-patch` → `patches/0003-s4b-moe.patch`; `git apply --check` in a clean `baf16363` worktree with `0001` + `0002` applied | both stats recorded; applies cleanly; cumulative T2 stated |
| **AC-11** | Evidence gate | `check_bundle.py workflow/evidence/HO-STRATA-015 --strict` | `RESULT: PASS`, before `CODER_DONE` |
| **AC-12** | **Carried audit/QAQC criteria are implemented, not annotated** | A1 the oracle's generating command is in `commands.log`; A2 `hashes-notes.txt` uses the `## Commit pins` table with **every** digest inlined and `B6-pins` actually runs; A3 no caller-supplied bound, bound printed; A4 `--slots` + `N == 28` assertion; **A6** the manifest states this parity validates dequant→f32 GEMV, not the production quantized GEMM; **A7** the extra `strata-deepseek` target is recorded; **A8** the manifest's commit labels are unambiguous | each demonstrable from the bundle; quote the `B6-pins` PASS lines (they must be present, not skipped) and the `--slots`/bound output |

## 5. Evidence required

`workflow/evidence/HO-STRATA-015/`: `manifest.md` (with the A6 statement and the
A8 labels), `commands.log` (**including the oracle line, A1**), `test-output.txt`
(raw, AC-1…AC-12), `artifacts/` (`llama-ref-moe.md`, engine dump ×2, the
comparison output, the dequant spot-check, the geometry assertions, the memory
accounting, the Qwen regression, both test outputs, the patch stats),
`scripts/compare_layers.py` (the fixed copy), `patches/0003-s4b-moe.patch` +
`apply-check.txt`, `hashes.txt` (immutable only), `hashes-notes.txt` (**`## Commit
pins` table, full 64-hex digests, DEC-024/A2**).

DEC-041 §2 capture ordering governs: captures to `/tmp/opencode/…`, moved with
`;`; `;` never `&&` after a command that may exit non-zero; rebuild
`test-output.txt` after the final capture; rehash last.

**One profile per claim:** gfx1150 / Radeon 890M / Ryzen AI 9 HX 370 / ROCm 10.1 /
DeepSeek-MoE-16B Q4_K_M / 4-token prompt / greedy.

## 6. Guard rails

- Strata edits authorised for **this handoff only**, on `strata-015-deepseek-s4b`
  cut from `db087d511`, never `main`, patch exported. Otherwise the checkout is
  read-only (DEC-008, extended per handoff since DEC-033).
- **Never rebuild `build-hip/`** (`d58ee239…`); all family work in
  `build-deepseek/`.
- **Do not touch:** `src/core/**`, shared kernels, `src/qwen35/**`, the tokenizer,
  `model_family_runs()` / refusal text / `--families`, any merged
  `workflow/evidence/HO-STRATA-0xx/` bundle, `workflow/DECISIONS.md`,
  `workflow/STATUS.md`, `.opencode/**`, `.github/**`.
- **DEC-043's re-review trigger:** if the MoE path needs shared-code edits rather
  than new `src/deepseek/**` files, **stop** and raise
  `DR-HO-STRATA-015-1`; do not proceed.
- Do not add dependencies; no network at runtime.
- **Do not widen 5e-3, do not switch the reference, do not change the prompt,
  the positions or the cell count.** Those are the four ways the S4a gate could
  have been faked, and each is a deviation now.
- No perf/support claim. No merge, no push to `main`, nothing pushed in the
  Strata tree.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Oracle covering layers 1–27 | Architect | **available** (S4a's f32 dump) | AC-5b |
| S4a merged (`db087d511`) | Architect | merged #29 | base |
| ROCm 10.1, `build-deepseek/` | environment | available | AC-1 |
| GTT headroom for 27 MoE blocks | environment | 45.97 GiB aperture; §1.4 keeps residency at pack size | AC-8 |
| Actions billing | — | **resolved** (DEC-045: repo public, free hosted minutes) | merge |

## 8. Definition of Ready — MET

- [x] ID/type/from/to/title/work package
- [x] Branches and bases named (`wp/strata-015-deepseek-s4b` @ `b791242`; Strata `strata-015-deepseek-s4b` @ `db087d511`)
- [x] Scope and out-of-scope explicit (including the MoE semantics)
- [x] Inputs linked with hashes; **the oracle already covers the layers in scope**
- [x] Every criterion has a command/check; the carried criteria are ACs (AC-12)
- [x] Evidence requirements runnable, capture rules and the evidence gate stated
- [x] Guard rails explicit (incl. DEC-043's re-review trigger and the four ways a gate can be faked)
- [x] Dependencies resolved
- [x] Priority/timebox set
- [x] Tolerance pre-registered: **5e-3, unchanged**, cells = layers 1–27 × 4 (108), then 112
- [x] Owner authorization: S4b is part of the S4 authorisation (DEC-042 §8)
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [x] AC-1…AC-12 run; raw output in `test-output.txt`
- [x] AC-5b PASS in both stages (108 cells, then 112); worst cell named `(layer=4, pos=3)` max `1.569942e-04`
- [x] Refusal, `--families` and the Qwen regression unchanged
- [x] Signed binary unchanged (`build-hip/strata` = `d58ee239…`); peak allocation recorded (23.124 GiB / 45.970 GiB)
- [x] Patch exported, measured, applies on `0001`+`0002`
- [x] `check_bundle.py … --strict` PASS, including **`B6-pins` actually running** (9 pin rows PASS)
- [x] No secrets, no out-of-scope edits, no new dependencies
- [x] `CODER_DONE`; `CODER_TO_QAQC` record attached

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | `architect` (`opencode-go/deepseek-v4-pro#max`) | 2026-11-25 | **READY** |
| Receiver (Coder) | `coder-primary` (`opencode-go/kimi-k2.7-code`) | 2026-11-25 | **IN_PROGRESS** |
| Coder sign-off | `coder-primary` | 2026-11-26 | **CODER_DONE** |

## 11. Log

- 2026-11-25 Architect: created `READY`. Scope is the 27 MoE blocks on the S4a
  skeleton; the gate and the reference are **unchanged** from S4a (5e-3, exact-f32
  reference, same prompt), and the nine carried audit/QAQC items are acceptance
  criteria (AC-3, AC-8, AC-12) so they cannot be deferred again.
- 2026-11-25 Coder-primary: accepted; switched Strata checkout to
  `strata-015-deepseek-s4b` @ `db087d511`. Starting with the tool fix and memory
  refactor before adding MoE blocks.
- 2026-11-25 Coder-primary: AC-5b fails at layer 19, position 1 (rel L2 2.67e-2).
  Layers 0–18 stay flat at <2.3e-4, then jump at layer 19.  Router diagnostics
  show the 6th/7th expert margin is 2.80e-4 probability (6.62e-3 logit); the
  engine selects expert 33 while the f32 oracle selects expert 40.  Teacher-forcing
  block 19 with the oracle's pre-block residual and KV cache produces output
  matching the oracle to 2.37e-5.  Verdict: layer 19 is arithmetically correct;
  the gate failure is inherited drift amplified by a router near-tie, not an
  implementation bug.  No code change or bound widening pursued.
- 2026-11-26 Coder-primary: DEC-046 implemented. Teacher-forced gate **PASS**
  (stage 1: 108 cells, max 1.569942e-04 at layer 4 pos 3; stage 2: 112 cells,
  same max/worst). Free-running profile reported informationally: first cell above
  5e-3 is layer 19 pos 1. Normal build explicitly rejects `--parity-teacher-force`.
  AC-1…AC-12 complete; `check_bundle.py --strict` PASS (42 checks, 0 warnings);
  `CODER_TO_QAQC` attached.

## 12. Tolerance (inherited, unchanged — HO-014 §12)

Same definition and the same binding value: per-cell relative L2,
`err = ||engine[l+1][p] - oracle[l][p]|| / ||oracle[l][p]||`, **max over the cells
in scope ≤ 5e-3**, all cells finite, worst cell `(l,p)` named, no averaging.
Stage 1 = `l = 1…27`, `p = 0…3` (**108 cells**); stage 2 = `l = 0…27`, `p = 0…3`
(**112 cells**, layer 0 must not regress from S4a's 9.76e-05).

A failure is a **finding**: name the first divergent layer. If it is structural
(router weights, expert layout, shared-expert placement), that is a deviation, not
a tolerance change. DEC-044's reasoning — why the reference is exact and why the
engine must not emulate q8_K — applies unchanged.

## 13. Task map after this handoff

| Stage | Handoff | Gate | State |
|---|---|---|---|
| **S4b** MoE 1–27 | **this file** | 108 cells, then 112, ≤ 5e-3 | READY |
| **S5** token parity + KL + the support flip | **HO-STRATA-016** (on AC-5b PASS) | 3 prompts × 16 greedy tokens **zero** mismatches against the Q4_K oracle; KL ≤ 1.5× the CPU/HIP floor; then `model_family_runs()` → true, `--families` gains `deepseek` | not written |
| S6/S7 baseline, envelope, regression, signoff | HO-STRATA-017 | GTT/`dmesg` envelope, HO-007 32 IDs bit-identical, QAQC → audit → sign | not written |

## 14. CODER_TO_QAQC

Branch: `wp/strata-015-deepseek-s4b` (workflow)  
Strata branch: `strata-015-deepseek-s4b`  
Workflow commit: `12995e1…` (tip after bundle fixes)  
Strata commit: `e2e7e1b347b4ac39cf51e7bf3eecaaf771a933f4`  
Evidence: `workflow/evidence/HO-STRATA-015/`  

### What QAQC must re-run

1. `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-015 --strict` → `RESULT: PASS`.
2. Verify the nine `B6-pins` rows in `hashes-notes.txt` report `PASS`.
3. Re-run the acceptance commands in `commands.log` and confirm the observed values:
   - AC-1: build exit 0; `build-hip/strata` hash `d58ee239…`; oracle hash `a4c56b9d…`.
   - AC-2: `--native <pack>` exit 2 with named refusal; `--families` prints `qwen4exp qwen35moe`.
   - AC-3: `--parity-run` without `--dump-layers` refused on DeepSeek and Qwen packs; with `--dump-layers` accepted.
   - AC-4: dump size `1,187,840` B; `compare_layers.py --slots 28 --shape-only` PASS with N=28.
   - AC-5b teacher-forced: the command in `commands.log` requires temporarily defining `STRATA_DEEPSEEK_DIAG`; expected `RESULT: PASS`, stage 1/2 max `1.569942e-04` at `(layer=4, pos=3)`.
   - AC-5b free-running informational: normal build; expected first cell above bound `(layer=19, pos=1)`.
   - AC-6: two normal dumps byte-identical.
   - AC-7: `model_family_test` and `gguf_geometry_test` both exit 0; Qwen regression token IDs match HO-007.
   - AC-8: device memory 23.124 GiB used / 45.970 GiB total; dequant spot-check max abs diff 0.0.
   - AC-9: geometry assertions all `ok`.
   - AC-10: `0003-s4b-moe.patch` applies cleanly on `baf16363 + 0001 + 0002`.
4. Confirm the normal binary rejects `--parity-teacher-force` (`artifacts/diag_unreachable.log`).
5. Check the diff is in scope (no `src/core/**`, shared kernels, `src/qwen35/**`, tokenizer, support-surface or `--families` changes).
