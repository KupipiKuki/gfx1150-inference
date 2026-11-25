# Audit report — HO-STRATA-014

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-014 (DeepSeek S4a: forward skeleton + block-0 layer parity), with DR-HO-STRATA-014-1 (DEC-043) and the reference amendment DEC-044 |
| **Auditor** | Auditor (`opencode-go/deepseek-v4.1-flash`, **WAIVER-001** — same family as the architect, disclosed) |
| **Date (UTC)** | 2026-11-24 |
| **Verdict** | **PASS** — no blocker, no scope expansion, no unsupported claim |
| **Reviewed** | Workflow `wp/strata-014-deepseek-s4` @ `db4974e`; Strata `strata-014-deepseek-s4` @ `db087d511`; evidence `workflow/evidence/HO-STRATA-014/` |

> **Materialisation note (architect, 2026-11-24).** The auditor completed every
> check and reported its verdict in session, but hit its step budget before it
> could write this file. This document is the auditor's report **transcribed
> unedited** by the architect (the write boundary of DEC-018/041 is unchanged —
> the auditor authored the content; the architect materialised it, as with the
> QAQC report). Everything under §7 is architect-supplied and is labelled so.

---

## 1. The claim, and nothing more — PASS

- `--native <pack> --tokens 1,2,3 --max-new 32 --max-context 1024` → exit 2, and
  `diff` against `workflow/evidence/HO-STRATA-012/artifacts/native-deepseek-refusal.txt`
  is **byte-identical** (`REFUSAL_VERBATIM_MATCH exit=0`).
- `--families` → `qwen4exp qwen35moe`, exit 0.
- `include/strata/artifact/model_family.hpp:60` still
  `return f == ModelFamily::Qwen4Exp;`; `git diff bac859ef9..db087d511 --
  include/strata/artifact/model_family.hpp` is **empty** (the enum is S1–S3's,
  from `0001`).
- Grep for perf/support wording over manifest, `commands.log` and the `.txt`
  artifacts: the only hits are the Qwen regression's own engine log lines
  (`55.3 tok/s`, `19.5 tok/s`) — the supported family's raw output, not a
  DeepSeek claim. No DeepSeek perf/support claim anywhere.
- Commit messages on both repos: no support/perf wording. The strongest
  statement is "engine is more accurate than oracle" in `diagnosis.md`, an
  arithmetic statement about the reference. **No claim smuggled into a commit
  message.**

## 2. DEC-044 is load-bearing — audited the reasoning — PASS (justified by evidence, not by the wish to pass)

- **(a) Same weights, verified far beyond the two-tensor claim.** An independent
  checker (`/tmp/opencode/audit014/check_weights.cpp`, using llama.cpp's `gguf`
  reader and `ggml_get_type_traits(...)->to_float`) compared **15 tensors** —
  `token_embd` (Q4_K, 209,715,200 elements), `blk.0.{attn_norm F32, attn_q Q4_K,
  attn_k Q4_K, attn_v Q6_K, attn_output Q4_K, ffn_norm F32, ffn_gate Q4_K,
  ffn_up Q4_K, ffn_down Q8_0}`, `blk.1.{attn_q Q4_K, attn_v Q6_K,
  ffn_down_exps Q8_0, ffn_gate_exps Q4_K}`, `output_norm` (F32) —
  result **`RESULT: all listed tensors byte-identical`**, `diff_elems=0`,
  `max_abs_diff=0.000e+00` for every one. This covers every tensor block 0 uses,
  all three quant types and a MoE block. DEC-044 changes the arithmetic, not the
  model.
- **(b) The q8_K numbers are present and runnable.** `artifacts/diagnosis.md`
  gives `quantize_row_q8_K_ref` + `ggml_vec_dot_q4_K_q8_K_generic` /
  `ggml_vec_dot_q6_K_q8_K_generic` copied verbatim from `78e05298…`, the `gcc`
  line and both `OFFSET/ROW_BYTES/N_OUT/N_IN/QTYPE` invocations, plus the table:
  q8_K-dot vs oracle **1.24e-07** (Q4_K) / **3.30e-07** (Q6_K) versus exact-f32
  vs oracle **4.44e-03** / **5.78e-02** — matching the handoff.
- **(c) The bound did not move.** `git show 4c29e94 -- workflow/handoffs/HO-STRATA-014.md`
  touches only §3, §4 AC-5a, the log and the §12 *amendment paragraph*; the §12
  gate rows still read ≤ 5e-3, unchanged from pre-registration (`0df301a`)
  through DEC-043 (`672beee`) to HEAD. The failing run used the same 5e-3
  (`1.2275e-01`).
- **(d) The Q4_K comparison is informative only** — handoff §3/§4/§12, manifest
  §5, `test-output.txt` (`floor_exit=1`), and `compare-layers.txt` (f32 gate
  only). Labelled correctly everywhere.

## 3. The fix is real and is what passed — PASS

- `bac859ef9..db087d511 -- src/deepseek/`: commit `c94accbab` replaces
  `K::rope_neox_apply` with `D::k_rope_norm` (pairs `(2i, 2i+1)`, `a*c-b*s`,
  `a*s+b*c`) and switches Q and K to it. Nothing else in that commit.
- Reference semantics confirmed in the pinned tree: `/tmp/opencode/llama-ref` at
  `78e05298…`; `src/llama-model.cpp:3700+` lists **`LLM_ARCH_DEEPSEEK` under
  "normal RoPE, operating on pairs of consecutive head values"**;
  `src/models/deepseek.cpp:109-110` builds rope for Q and K;
  `GGML_ROPE_TYPE_NORMAL = 0`.
- The passing number is not produced by moving the prompt, cell count or bound:
  same 4 tokens, `N` derived = 1, 4 cells, no `--bound` (default 5e-3 = §12).
- Decisive: with the **NEOX** kernel the same f32 oracle gives
  `p0 = 9.757537e-05` but `p1..p3 = 5.25e-2 / 5.81e-2 / 1.26e-1`; with **NORM**
  `p0` is **unchanged** at `9.757537e-05` and `p1..p3` become
  `5.94e-5 / 6.39e-5 / 5.65e-5`. The improvement is exactly where RoPE is
  non-trivial and zero at `p0` where rotation is the identity — the signature of
  a correct pairing fix, not of tuning.

## 4. The gate, reproduced independently end to end — PASS

- Stored comparison → `9.757537e-05 / 5.944078e-05 / 6.385591e-05 /
  5.652541e-05`, median `6.164835e-05`, max `9.757537e-05 at (layer=0, pos=0)`,
  `RESULT: PASS`, exit 0.
- **Regenerated the oracle** from the committed `scripts/oracle_nodes.cpp`
  compiled against `/tmp/opencode/llama-ref` @ `78e05298…` from
  `/tmp/opencode/deepseek-moe-16b-f32.gguf` (`--tokens 549,6077,280,7239 --n 0
  --dump-layers`) → `a4c56b9d9189468aeaf1b89637ed4f14f9107b5aaaf75cd4b0e324b6d1c3fc49`,
  **`cmp` identical** to the committed dump. The Q4_K oracle regenerates to
  `db6eccb3…`, identical to HO-010's signed dump. **QAQC's regeneration claim is
  true on the auditor's own reproduction.**
- Two fresh engine runs from the clean tree reproduce
  `d534fdcb44026b2d244942ed7a23a163fcae8c89d3182516c1ba7bf30e998a0d`
  byte-for-byte, equal to `dump-run-1.bin`/`dump-run-2.bin`; size `81,920` B;
  stdout `(1 layer + the input x 1 streams x 2048)`.
- Q4_K floor: `1.939394e-02 / 1.257641e-02 / 2.054810e-02 / 1.333939e-02`,
  `RESULT: FAIL`, exit 1 — as recorded, informative.
- `compare_layers.py` soft-spot review: slot mapping (`engine slot l+1 ↔ oracle
  block l`), `den2=0` fallback, strict `>` on the bound, NaN checked on kept
  records (allowed by §12), first-4-records handling — all correct. Two hazards
  found, see **A3** and **A4**.

## 5. Guard rails (DEC-043) — PASS

- S4a delta `bac859ef9..db087d511`: **10 files, 839 insertions** — exactly
  `cmake/strata_gpu_engine.cmake` +12, `include/strata/deepseek/engine.hpp` +10,
  `src/deepseek/{ds_engine.cu +474, ds_f32_matvec.cu +129, ds_f32_matvec.cuh +28,
  ds_kernels.cu +81, ds_kernels.cuh +24, ds_main.cpp +4}`,
  `src/program/generate.cpp` +37, `tests/core/model_family_test.cpp` +40.
  Cumulative `14 files, +1,073 / −31`.
- **No edits under `src/core/**`, shared kernels, `src/qwen35/**`, the tokenizer,
  `model_family_runs()`, the refusal text or `--families`.** DEC-043's re-review
  trigger has **not** fired.
- `build-hip/strata` = `d58ee239…`, verified before and after the auditor's build.
- No signed bundle edited: the workflow diff touches only `HO-STRATA-014/**`,
  `HO-STRATA-014.md`, `DR-HO-STRATA-014-1.md`, `DECISIONS.md`, `STATUS.md`,
  `reports/qaqc/HO-STRATA-014-qaqc.md`.
- No new dependency: `compare_layers.py` imports `argparse, math, os, struct,
  sys` (stdlib only); cmake adds only in-tree targets.
- Qwen regression reproduced: 32/32 IDs identical; `model_family_test` ALL PASSED
  (39 checks); `gguf_geometry_test` passed.
- Patch `0002-s4-forward.patch` is byte-identical to the live diff (`cmp` exit
  0) and applies to a clean `baf16363` worktree after `0001` (exit 0 for both
  check and apply).

## 6. Evidence integrity — PASS with two carried defects

- `check_bundle.py workflow/evidence/HO-STRATA-014 --strict` → `RESULT: PASS (31
  checks, 0 warnings)`, exit 0. The count reconciles (2·B1 + 23·B2 + B3 + 2·B4 +
  B5 + B7 + B8) — and contains **no B6 rows**.
- Fresh `git archive HEAD` + `sha256sum -c hashes.txt` → **23/23 OK**, exit 0;
  no absolute paths; no secrets (B7).
- Pins verified by hand: `DECISIONS.md` → `a717e14341ab…` ✓;
  `HO-010 deepseek_p1_4_layers.bin` → `db6eccb3e8a9…` ✓;
  `0001-deepseek-family.patch` → `9a7b280f5d8c…` resolves and matches QAQC's
  quote but is **not inlined** in the file (line 12 says "see HO-STRATA-012
  hashes.txt"). All three resolve.
- **`B6-pins` did not run.** `check_bundle.py:528-539` emits nothing when the
  `## Commit pins` table yields no rows; HO-014's `hashes-notes.txt` regressed to
  flat lines where HO-012/013 use that table. So "PASS (31 checks)" silently
  omits the pin check (**A2**).
- **The generating command for the gate reference is missing.** `commands.log`
  and `manifest.md` carry the f32 *conversion* command but no
  `oracle_nodes --model … --tokens 549,6077,280,7239 --n 0 --dump-layers …` line
  — for the most load-bearing artifact of DEC-044 (**A1**).
- Manifest §1 labels `4c29e94` as "workflow commit / branch" while the bundle was
  committed at `d0418bb` (defensible as a pin, ambiguous label — **A8**).
- `test-output.txt` is verbatim engine output with `=== AC-n ===` markers and
  `*_exit=` captures — acceptable. `commands.log` abbreviates one path with `...`
  (line 24) but is a redundant index with the full text in `test-output.txt`.

## 7. The three QAQC Minors — each decided

- **F1 (pins)** — upheld; **rework not required**, carry to HO-015. All three pins
  resolve and match; the defect is documentation and gate coverage, not any
  content hash or the gate value. A rework would force re-hashing a verified
  fixed point for no evidential gain. Conditions: HO-015 uses the `## Commit
  pins` table with all digests inlined, and the architect decides whether
  `check_bundle.py` should **warn** when `hashes-notes.txt` yields no table rows.
- **F2 (`--parity-run` silently ignored on a supported model without
  `--dump-layers`)** — upheld, carry. Confirmed in the diff (`generate.cpp`
  nested refusal, `o.parity_run` never read afterwards). It can mislead mildly
  (a diagnostic flag appears honoured), cannot corrupt a result or fake parity,
  and AC-3 as written does not cover it. Three-line fix; HO-015 AC.
- **F3 (`upload_weight` dual allocation)** — upheld, carry; **tight, not
  infeasible**. `w.d` is never read (`matvec` uses only `w.f32`),
  `q8_1_scratch` is unused. At 28 blocks ≈ 64 GB f32 + 10.8 GB quantized + ~1 GB
  ≈ 76 GB against 92 GB unified — the real risk is the GTT aperture (S6), not a
  hard wall. Trivial fix; HO-015 AC.

## 8. Findings

| # | Severity | Finding | Action |
|---|---|---|---|
| **A1** | **Major (carried)** | The gate reference's generating command is absent from `commands.log`/`manifest.md`; §5 "every command, verbatim" is not met for `artifacts/runs/deepseek_f32_p1_4_layers.bin`. Independently reproduced by the auditor, so the claim is sound, but the bundle is not self-contained for its most load-bearing artifact. | Carry into HO-015 (record the `oracle_nodes … --n 0 --dump-layers` line). A one-line append + rehash is the minimal rework if the architect prefers. |
| **A2** | Major (process, carried) | `B6-pins` silently skipped; one pin digest not inlined; format regressed from HO-012/013. "PASS (31 checks)" overstates coverage. | Carry + architect decision on a tool-side warning. |
| **A3** | Minor | `compare_layers.py` accepts `--bound` (outside the §1.5 CLI); `--bound 1.0` turns the Q4_K floor into `RESULT: PASS`; the PASS path does not print the bound used. | HO-015: remove the flag or reject values ≠ 5e-3 and always echo the bound. |
| **A4** | Minor | Slot/`N` derivation picks the smallest divisor of `R` in 2..29 and is not unique; the auditor's 29-slot probe returned `29 records, 5 slots, N=4` and it could not finish explaining it. | HO-015: pass the slot count explicitly (or read it from the engine's stdout line) and re-probe. **See §9 — confirmed by the architect and it is worse than "fragile".** |
| **A5** | Minor | Handoff §10 receiver signature row was blank; acceptance lived only in the log (contract field 15 not formally met). | Fixed by the architect at signoff (§9). |
| **A6** | Observation | The engine bypasses the quantized MMVQ path (`ds_f32_matvec.cu`), so this parity validates dequant→f32 GEMV, not the production quantized GEMM. Correct per DEC-044; the manifest §7 does not state it. | HO-015 manifest: state it. |
| **A7** | Observation | An extra `strata-deepseek` executable was added in cmake; harmless, not asked for. | None. |
| **A8** | Observation | Manifest §1 "workflow commit / branch: `4c29e94`" vs bundle commit `d0418bb` — ambiguous label. | Clarify in HO-015. |

**No blocker. No scope expansion requested. No false claim found.** The reference
change is justified by evidence — byte-identical weights across 15 tensors, a
runnable q8_K explanation, an unchanged bound — and was vindicated by catching a
real NEOX/NORM RoPE bug that the old reference masked.

## 9. Architect addendum (not the auditor's text)

**A4 confirmed, and it is a silent false-PASS trap for S4b.** By inspection of
`compare_layers.py:47-58`: `slots` is the smallest divisor of `R = dump_floats /
2048` in 2..29. For S4a's dump (`5 records × 2 slots`) `R = 10` → `slots = 2`,
correct. For an **S4b** dump (`4 records × 29 slots`) `R = 116` → the smallest
divisor ≥ 2 is **2**, so the tool would report `58 records, 2 slots, N = 1` and
compare **only block 0** — printing `RESULT: PASS`. The auditor's 29-slot probe
output is consistent with this (it saw a divisor of `R/2048` chosen out of
order). This is therefore not a Minor for S4b: HO-STRATA-015 **must** make the
slot count explicit (`--slots`, or read the `N layers + the input` line) and
**must** assert `N == 28` before comparing, or the S4b gate can pass on one block.

The auditor's A1 was accepted as a carry rather than a rework on this reasoning:
two independent reviewers (QAQC and auditor) regenerated the reference from the
committed harness and the on-disk f32 pack, so the claim does not depend on the
missing command line; editing `commands.log` now would invalidate 23 verified
digests and force a second review cycle for documentation. The cost is carried
forward and bound into HO-015's acceptance criteria.

### AUDITOR_TO_ARCHITECT (embedded)

| Field | Value |
|---|---|
| **Type** | AUDITOR_TO_ARCHITECT |
| **From → To** | Auditor → Architect |
| **Handoff** | HO-STRATA-014 |
| **Verdict** | **PASS** |
| **Evidence** | `workflow/evidence/HO-STRATA-014/`; QAQC `reports/qaqc/HO-STRATA-014-qaqc.md`; Strata `db087d511`; workflow `db4974e` |
| **Blockers** | none |
| **Carried** | A1 (gate-reference command), A2 (`B6-pins` not exercised, digest not inlined), A3 (`--bound` softens the gate), A4 (slot derivation — silent 1-block PASS for S4b), A5 (signature row — fixed at signoff), A6–A8 (observations) |
| **Conditions on signoff** | A1–A4 become **acceptance criteria** in HO-STRATA-015; A2 includes an architect decision on a `check_bundle.py` warning when `hashes-notes.txt` has no pin table. |
