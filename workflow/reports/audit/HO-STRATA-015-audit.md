# Audit report — HO-STRATA-015

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-015 (DeepSeek S4b: MoE blocks 1–27) + DR-HO-STRATA-015-1 (APPROVED, DEC-046) + RW-HO-STRATA-015-1 (CLOSED) |
| **Reviewer** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) |
| **Date (UTC)** | 2026-11-26 |
| **Verdict** | **REWORK** — evidence-only (A9). The **gate itself PASSes** and is justified by independent measurement; the bundle must not merge carrying a wrong figure for the very near-tie the deviation rests on. |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-015/` (bundle unchanged after `f80d775`: `git diff --stat f80d775..HEAD -- workflow/evidence/HO-STRATA-015/` is empty) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-015-qaqc.md` (§§1–6 + §7 delta re-check) |
| **Workflow branch** | `wp/strata-015-deepseek-s4b` @ `65f8ef4` (evidence tip `f80d775`; base `main` @ `b791242e0330b2ae5c560c5e937f51e0372e7014`) |
| **Strata branch** | `strata-015-deepseek-s4b` @ `e2e7e1b347b4ac39cf51e7bf3eecaaf771a933f4` (base `db087d511`, pin `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`); working tree clean |
| **Profile (one profile per claim)** | AMD Ryzen AI 9 HX 370 / Radeon 890M `gfx1150`, Linux Mint 22.3, kernel `7.0.0-42-generic`, ROCm `core-10.1` (`LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`), HIP `7.16.26385`, GCC `13.3.0`, Python `3.14.10`; DeepSeek-MoE-16B-base Q4_K_M `f00ecd83…`, f32 pack `8cd778a7…`; 4-token prompt `549,6077,280,7239`, greedy |

**Method note.** I rebuilt the diagnostic binary myself from the committed source
(`clang++ … -DSTRATA_DEEPSEEK_DIAG -c src/deepseek/ds_engine.cu` into
`/tmp/opencode/audit-015/ds_engine_diag.o`, linked against the existing
`build-deepseek/` archives). No tracked file in either repository was modified;
both trees were clean before and after (`git status --porcelain` empty,
`build-hip/strata` = `d58ee239…`). All probes ran in `/tmp/opencode/audit-015/`.

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-015 --strict` → `RESULT: PASS (49 checks, 0 warnings)`, including **10 `B6-pins` rows**. `commands.log` has cwd, env, and the oracle line (A1). I re-ran every gate command from the manifest, not from the coder's log.
- [x] **Outputs raw; failures/skips kept verbatim.** The free-running `RESULT: FAIL` is present as `artifacts/ac5b_free.log`; the stale capture is preserved as `artifacts/ac5-stale-attempt.log` under its own header in `test-output.txt`; no skips.
- [x] **Artifacts/hashes match.** `git archive HEAD | tar -x` → `sha256sum -c workflow/evidence/HO-STRATA-015/hashes.txt` → **30/30 OK**.
- [x] **Environment recorded.** Present, but the manifest's §"Environment" row is factually wrong (A10): "Linux 6.x / Python 3.12" vs kernel `7.0.0-42-generic` / Python `3.14.10`; compiler and HIP versions absent. The QAQC report records the correct values.
- [x] **No secrets.** `PASS B7-secrets`; spot-grep found no token/PAT shapes.
- [ ] **Near-tie justification faithful.** **FAILS (A9).** `manifest.md:76` and `artifacts/llama-ref-moe.md:69-70` still state the router margin as **2.80e-4 probability / 6.62e-3 logit** — the Q4_K-oracle figure, not the exact-f32 trajectory this gate uses. DEC-046's erratum (`9fb3866`) says in terms: *"The same correction applies to … the manifest, which cite it."* It was not applied. The correct measurement (mine, §3.1) is **3.357e-6 / 7.948e-5**.

## 2. Claim and scope audit

Every claim in the handoff/manifest was checked against an artifact I produced or
reproduced myself:

| # | Claim | Artifact | Independent check | Verdict |
|---|---|---|---|---|
| 1 | Teacher-forced gate: 112 cells ≤ 5e-3, max **1.569942e-04 at (4,3)**, `RESULT: PASS` | `artifacts/ac5.log` (`94e52860…`) | Rebuilt diag binary; ran from **regenerated** inputs → `teacher_outputs.bin` = `e0b6aa02…` (byte-identical); `compare_layers.py --teacher-outputs` output **byte-identical to `ac5.log`** (`cmp` = 0); stage 1 108 cells, stage 2 112 cells, same max/worst, `RESULT: PASS` | **PASS** |
| 2 | Gate inputs reproduce from the bundle | `scripts/gen_teacher_inputs.py`, `artifacts/runs/teacher_{inputs,kv}.bin` | Ran the committed script from a clean tree into a fresh dir: `d386c2d4…` / `62ca264d…`; `cmp` = 0 for both | **PASS** |
| 3 | Free-running first divergence **(19,1) = 2.668110e-02**, informational | `artifacts/ac5b_free.log`, `artifacts/runs/s4b-free-normal.bin` (`4214269e…`) | Re-ran normal build: dump byte-identical; comparison reproduces `(19,1) = 2.668110e-02`, stage-1 max `6.317236e-02 at (25,1)`, `RESULT: FAIL` | **PASS (informational)** |
| 4 | The failure is a router near-tie on the exact-f32 trajectory | DEC-046 + erratum; QAQC §2.1 | Recomputed from `oracle_nodes` on the f32 pack + my own router implementation (§3.1): 3.357e-6 / 7.948e-5; drift 7.123e-5; induced gap shift **1.385e-4 > 7.948e-5** | **PASS** (justification); **A9** (bundle still cites the old number) |
| 5 | Teacher-forced mode unreachable in a normal/shipped build | `artifacts/diag_unreachable.log`; committed source | No `#define STRATA_DEEPSEEK_DIAG` in the tree; `build-deepseek/strata` (normal) → exit 2, `--parity-teacher-force is a diagnostic option…`; `strings build-hip/strata \| grep -c parity-teacher-force` = **0** | **PASS** |
| 6 | The macro changes no arithmetic | QAQC §1 | Free dump from normal build **and** from my diag build: both `4214269e…`, `cmp` = 0, byte-identical to the committed dump | **PASS** |
| 7 | Reference unchanged; gate value unchanged | `HO-STRATA-014/…deepseek_f32_p1_4_layers.bin` (`a4c56b9d…`) | Regenerated from the f32 pack with `oracle_nodes` at llama.cpp `78e05298…`: **byte-identical** (`cmp` = 0); f32 pack hash `8cd778a7…`; HO-014 bundle untouched since `b791242e` | **PASS** |
| 8 | No support claim; refusal/`--families` unchanged | AC-2 | `--families` → `qwen4exp qwen35moe`; `--native <pack>` → exit 2, refusal byte-identical to HO-012; `model_family_runs()` returns only `Qwen4Exp` | **PASS** |
| 9 | Qwen regression + tests | `artifacts/ac7.log` | `model_family_test` 41/41 `ok` incl. both `--parity-run without --dump-layers` cases; `gguf_geometry_test` all passed; Qwen 32 greedy IDs **exactly** the HO-007 list | **PASS** |
| 10 | Memory + dequant accounting | `artifacts/ac8.log` | My run: `used=24829116416 (23.124 GiB)`, `total=49359982592 (45.970 GiB)`; Q4_K/Q6_K/Q8_0/Q5_0 spot-check `0.000000e+00` | **PASS** (host-half wording: A11) |
| 11 | Geometry assertions (HO-012 F2 carried) | `artifacts/ac9.log` | 11 metadata assertions `ok` on my run (`28/2048/16/16/64/6/2/1408/1/1e4/1e-6`) | **PASS** |
| 12 | Patch measured, exported, applies on `baf16363 + 0001 + 0002` | `patches/0003-s4b-moe.patch` (`e14271eb…`), `apply-check.txt` | Live `git format-patch db087d511..e2e7e1b34 --stdout` = committed patch (`cmp` = 0); applied `0001`,`0002`,`0003` to a clean `git archive baf16363b` tree → `diff -r` vs `e2e7e1b34` archive = **0** | **PASS** |
| 13 | Memory refactor removed the dual allocation | code + `ac8.log` | `upload_weight` keeps the quantised payload resident (F32/F16/BF16 only converted once); matvec dequantises rows into one reused scratch; 23.1 GiB used vs S4a's ~76 GB projection | **PASS** |
| 14 | `check_bundle --strict` + fresh archive | — | 49 checks, 0 warnings; 30/30 hashes from a fresh `git archive` | **PASS** |
| 15 | Carried A1–A8 implemented | AC-12 | A1 oracle command present (`commands.log:16-28`); A2 `## Commit pins` 10 rows, all `PASS B6-pins`; A3 `--bound` rejected (exit 2), bound printed; A4 `--slots` required, `N==28`, R=116 trap closed; A6 §6 statement present; A7 §7; A8 §8 | **PASS** |
| 16 | F2 (QAQC): supported-model `--parity-run` refuses | AC-3b | `--parity-run` on the Qwen pack without `--dump-layers` → exit 2 | **PASS** |

## 3. The central question — DEC-046: justified, or a loosened gate?

### 3.1 Is the near-tie real and correctly characterised?

Independently recomputed from `oracle_nodes` on the **f32 pack** (`ffn_inp-19`
node, position 1), `blk.19.ffn_norm.weight` and `blk.19.ffn_gate_inp.weight`,
RMSNorm ε = 1e-6, softmax over 64, top-6. The engine's free-running
`ffn_inp(19,1)` came from my own diag build; the teacher-forced logits from my
own teacher run.

| Quantity at `(layer=19, pos=1)` | Exact-f32 oracle | Teacher-forced engine (same input) | Free-running engine |
|---|---|---|---|
| top-6 | `[25, 2, 3, 22, 5, 40]` | `[25, 2, 3, 22, 5, 40]` | `[25, 2, 3, 22, 5, 33]` |
| p(33) / p(40) | 4.223790e-02 / 4.224125e-02 | 4.223800e-02 / 4.223974e-02 | 4.224072e-02 / 4.223823e-02 |
| 6th–7th **probability** margin | **3.357e-06** | 1.74e-06 | 2.491e-06 |
| 6th–7th **logit** margin | **7.948e-05** | 4.100e-05 | 5.897e-05 |

Input drift, free-running vs oracle at that node: **rel L2 = 7.123e-05**, max abs
5.703e-04. What matters is not that scalar but its effect through the router:

- drift-induced logit change: expert 33 **+5.246e-05**, expert 40 **−8.599e-05**;
  the 33↔40 gap moves by **+1.385e-04**, i.e. **1.74× the 7.948e-05 gap** → the
  flip is predicted, not merely possible;
- with **identical** input, the engine's own f32 arithmetic still moves expert
  40's logit by **−3.841e-05** (max over all 64: 4.250e-05), i.e. **0.48× the
  gap** → the top-6 decision at that cell is inside the engine's own rounding
  band for any implementation that is not bit-identical to the reference.

**Verdict: the near-tie is real and the flip is explained.** The erratum's
phrasing ("the margin is tighter than the drift") is loose — it compares a
probability margin (3.36e-6) with a relative-L2 drift (7.12e-5), which are not
commensurable. The precise, measured statement is the logit one above: the
drift moves the competing logits by more than their separation, and the engine's
own arithmetic moves one of them by half the separation. This is a quotation
defect, not a collapse of the justification.

### 3.2 Does teacher forcing measure what S4 must prove?

**Yes, for S4's proposition (per-block arithmetic), and I demonstrated it is
sharp rather than lax.** I compiled two mutated copies of `ds_engine.cu` in
`/tmp` (no repo change), ran the same teacher-forced gate, and both fail
immediately:

| Mutation | Teacher-forced result |
|---|---|
| Re-normalise the top-6 weights (`norm_w = true`; DeepSeek requires `false`) | first cell above bound **(1,0)**, max **6.159e-01** — `RESULT: FAIL` |
| Compute the shared-expert branch but do not add it | first cell above bound **(1,0)**, max **7.523e-01** — `RESULT: FAIL` |

So the gate catches the router-normalisation semantics and shared-expert
placement, not merely "roughly right" output. The 1.57e-04 worst cell is a
31.8× margin, and all 112 cells are compared from the reference's exact input.

**What it cannot catch, by construction.** Each cell re-anchors to the
reference's residual at block `l` and the reference's K/V for positions `< p`, so
the gate is blind to:

1. **Cross-position state**: the engine's *own* K/V values from earlier positions
   and the residual trajectory from block to block. The injection overwrites
   exactly the state the engine would reuse. A cache-offset/layout error that is
   self-consistent within one block, or per-layer cache overlap, would not show.
2. **Accumulated drift and its amplification** — the very phenomenon that failed
   the free-running gate (6.8e-5 entering layer 19 → 2.67e-2 after one routing
   flip; 6.3e-2 by layer 25 at position 1).
3. **Anything outside blocks 0–27 at four positions**: token selection, final
   norm/lm_head, sampling, tokenizer; positions > 3; multi-token generation.
4. **Compensating errors** inside a block that cancel in the residual output at
   these four inputs (sub-nodes are not gated; only `l_out`).

**Are the compensations adequate?** For this increment, yes:

- The free-running profile is in the bundle as **informational**, labelled as
  such in `manifest.md` §2/§4, with the divergence table and the first cell —
  the risk is measured and shown, not excluded. (Its *margin* text must be fixed:
  A9.)
- S5 `HO-STRATA-016` is the end-to-end gate (3 prompts × 16 greedy tokens against
  the Q4_K oracle, zero mismatches, plus KL). **It is not yet written**, so today
  this is a commitment, not evidence. It must be a blocking gate before any
  support flip; the handoff §13 and DEC-046 §4 already say so.
- S6 `HO-STRATA-017` re-runs the HO-007 regression bit-for-bit; the AC-7 check
  already reproduces the 32 Qwen IDs today.
- No support or performance claim is made anywhere: `model_family_runs()` is
  still `false` for DeepSeek, `--families` is still `qwen4exp qwen35moe`, and the
  refusal text is unchanged.

The acknowledged DEC-046 risk is therefore real, correctly identified, and
covered by later gates — provided S5 is written with the same discipline and
nothing is claimed before it passes. That must be carried as an audit condition
(A15).

### 3.3 Was anything else moved to make it pass?

No. Verified from git history:

- **The four ways the gate could be faked are unchanged from READY.** At READY
  (`e045dee`) and at HEAD: bound **5e-3**, reference **`a4c56b9d…`**, prompt
  **`549,6077,280,7239`**, **4 positions**, cells **108 then 112**. The only
  change to AC-5b is its *comparison mode* (`febb501`, after the approved
  DR/DEC-046); the number, reference, prompt, positions and cell count are
  untouched in every revision of the handoff.
- **The comparison tool's bound was never edited**: `BOUND = 5e-3` enters at
  `045e303` and `git log -p` shows no later change to that line; `--bound` is
  rejected (`exit 2`), and the bound prints on every run.
- **The reference is genuinely unchanged**: regenerating it from the f32 pack at
  the pinned llama.cpp (`78e05298…`) reproduces `a4c56b9d…` byte-for-byte, and
  the HO-014 bundle has no commits since `b791242e`.
- **Nothing substantive changed after the failure.** `b68979e`'s own message
  records *"AC-5b still FAIL at layer 19 pos 1; diagnostics follow"*. The four
  commits after it add only: diagnostic hooks/`#ifdef` blocks, option parsing,
  a memory print, and the `#else` rejection. No arithmetic, tolerance or
  special-case on `(19,1)` was introduced — the only `layer_idx == 19 && pos == 1`
  code is diagnostic printing/dumping inside `#ifdef STRATA_DEEPSEEK_DIAG`.
- **Teacher-forced mode is unreachable outside the macro**: no `#define` in the
  tree; the normal dev build refuses with exit 2; the shipped `build-hip/strata`
  (`d58ee239…`, dated 2026-11-15, before this work) has **zero** occurrences of
  `parity-teacher-force` or `parity-run` in its strings.
- **The macro changes no arithmetic**: normal-build and diag-build free dumps are
  byte-identical (`4214269e…`).

## 4. Gate re-run and tool-honesty probes

Commands (cwd `/home/kupipi/Documents/git/gfx1150-inference`; `$ORACLE` =
`workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin`):

```bash
# regenerated inputs, then my diag build
python3 workflow/evidence/HO-STRATA-015/scripts/gen_teacher_inputs.py --output-dir /tmp/opencode/audit-015/regen
/tmp/opencode/audit-015/strata-diag-audit --parity-run --native $PACK \
  --dump-layers /tmp/opencode/audit-015/teacher_dummy.bin \
  --parity-teacher-force /tmp/opencode/audit-015/regen/teacher_inputs.bin,/tmp/opencode/audit-015/regen/teacher_kv.bin,/tmp/opencode/audit-015/teacher_outputs_audit.bin,$ORACLE
python3 workflow/evidence/HO-STRATA-015/scripts/compare_layers.py --oracle $ORACLE \
  --teacher-outputs /tmp/opencode/audit-015/teacher_outputs_audit.bin
```

Observed: 112 lines `input assert ok (max abs diff = 0.000000e+00)`;
`teacher_outputs_audit.bin` = `e0b6aa02…`; stage 1 108 cells max
`1.569942e-04 at (layer=4, pos=3)`, stage 2 112 cells same, `RESULT: PASS`; the
whole output is **byte-identical to `artifacts/ac5.log`**.

Honesty probes:

| Probe | Expected | Observed |
|---|---|---|
| `teacher_inputs` cell (1,0) `+2e-6` | fail > 1e-6 | exit 1, `teacher cell (1,0) input assert FAIL maxd=2.000481e-06` |
| `teacher_inputs` cell (1,0) `+5e-7` | pass | exit 0, `max abs diff = 4.991889e-07` (the zero is computed) |
| `teacher_inputs` cell (0,0) `+2e-6` | (F3(i)) self-comparison → pass | exit 0; block-0 output still within bound → gate PASS |
| `--teacher-outputs` on the **raw** free dump | reject | exit 1, `expected 229376 floats, got 296960` |
| `--teacher-outputs` on the free dump **transposed** to 28×4 | reject | exit 1, `first cell above bound … (19,1)`, `RESULT: FAIL` |
| `--slots 1` / `--slots 29` / no `--slots` / 30-slot dump | reject | exit 1 each (`must be 28`, `must be 28`, `required`, `120 slots not divisible by 29`) |
| R=116 (4 records × 29 slots) with `--slots 28` | compare all 28 layers, no N=1 | `engine dump: 4 records, 29 slots/record, N=28 blocks computed`; fails at `(19,1)` — trap closed |
| `--bound 0.1` | reject | argparse: `unrecognized arguments: --bound 0.1`, exit 2 |
| Free dump, normal build vs my diag build | identical | both `4214269e…`, `cmp` = 0 |

## 5. RW-1 self-containment

- Committed `scripts/gen_teacher_inputs.py` runs from a clean tree (`git status
  --porcelain` empty) and produces **byte-identical** `teacher_inputs.bin`
  (`d386c2d4…`) and `teacher_kv.bin` (`62ca264d…`) — `cmp` = 0. **RW-1's
  objective is met: the gate itself needs nothing outside the repo except the
  f32 pack and `oracle_nodes`.**
- Residual (Minor, A16): the *regeneration script* additionally imports
  `gguf_reader` from `/home/kupipi/Documents/git/strata/tools` and defaults to
  absolute `/tmp/opencode/…` paths. The gate does not need the script (both
  `.bin` inputs are committed, hashed and pinned), so this does not re-open
  RW-1; it is a portability note for S5.

## 6. Carried criteria (A1–A8) and QAQC F1–F3

- **A1** oracle generating command: present and exact (`commands.log:16-28`); I
  re-ran it and reproduced the oracle. **Closed.**
- **A2** `## Commit pins`: 10 rows, full 64-hex digests, and `check_bundle
  --strict` executes all 10 as `PASS B6-pins` (not skipped). **Closed.** (DoD
  prose still says "9 pin rows": A13.)
- **A3** no caller-supplied bound; bound printed on every run. **Closed.**
- **A4** `--slots` mandatory, `N==28` asserted, R=116 reads 28 blocks. **Closed.**
- **A6** manifest §6 states the dequant→f32 GEMV vs production quantized GEMM
  distinction. **Closed.**
- **A7** `strata_deepseek` target recorded (§7). **Closed.**
- **A8** commit labels: Strata/base/DB named, workflow pins per-file. **Closed**,
  except a stale `12995e1…` in the first `CODER_TO_QAQC` block and a stale handoff
  `State` field (A13).
- **QAQC F1** (transcript provenance): closed on the merits — `test-output.txt`
  (861 lines / 43,105 B) contains each of the 14 cited artifacts contiguously,
  with the stale capture under its own "preserved" header; the gate section is
  byte-identical to `ac5.log`. `diag_unreachable.log` and `apply-check.txt` live
  as standalone artifacts rather than in the transcript (Minor, A13).
- **QAQC F2** (margin from the wrong oracle): **not closed in the bundle** — see
  A9. QAQC's own recomputation is correct; it closed F2 on the existence of the
  DEC-046 erratum, but the erratum's instruction to correct the manifest and
  `llama-ref-moe.md` was not carried out.
- **QAQC F3(ii)** (inputs in `/tmp`): closed by RW-1 (verified above).
- **QAQC F3(i)** (block-0 injection is a self-comparison): **acceptable as a
  carry, not a rework.** For `l=0` the assertion is the identity, which I
  confirmed by perturbation; but the *block-0 output* is still gated against
  `l_out-0` (5.65e-5…9.76e-5, matching S4a's signed 9.757537e-05), the block-0
  input is committed and regenerates from `token_embd.weight` byte-for-byte, and
  S4a already signed block 0. A wrong block-0 computation cannot pass; only a
  wrong block-0 *input* below the output bound could, and the input is
  deterministic from the pack. Carry to S5 with a one-line note.

## 7. Guard rails

| Guard rail | Check | Result |
|---|---|---|
| No `src/core/**`, shared kernels, `src/qwen35/**`, tokenizer | `git diff --name-status baf16363b..e2e7e1b34` | none; only new `src/deepseek/**`, `include/strata/deepseek/engine.hpp`, and the S1–S3 metadata headers + dispatch/build/test hunks |
| `model_family_runs()` / refusal / `--families` unchanged | diff grep + live binary | no diff; `--families` = `qwen4exp qwen35moe`; refusal byte-identical; `model_family_runs` = Qwen4Exp only |
| Signed binary untouched | `sha256sum build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |
| No new dependency | diff + scripts | stdlib only (`argparse`, `math`, `os`, `struct`, `sys`, `hashlib`, `subprocess`, `tempfile`) |
| Patch applies on `baf16363`+`0001`+`0002` | clean archive + `git apply` | applies; result `diff -r` vs `e2e7e1b34` = 0 |
| Cumulative overlay within DEC-043 | `git diff --stat baf16363b..e2e7e1b34` | **14 files, +1,656 / −31**; S4b delta **7 files, +760 / −177**; 7 new files. DEC-043 approved exactly this shape (dedicated `src/deepseek` path, dispatch/build/test hunks; estimate 4,800–6,200 lines / 6–7 files). Actual is 7 new files and 26–35% of the line estimate. DEC-043's re-review trigger did **not** fire (no `src/core/**`, no shared kernels, no `src/qwen35/**`). The modified `include/strata/core/{family_layout,geometry}.hpp` and `include/strata/artifact/*` are S1–S3 (HO-STRATA-012), not S4b and not `src/core/**`. |
| No support/perf claim | bundle grep + binary | no support/performance claim; informational FAIL explicitly not the gate |
| Other evidence bundles untouched | `git diff --name-only b791242e..HEAD` | only `workflow/evidence/HO-STRATA-015/**`, the three HO-015 handoffs, `DECISIONS.md`, `STATUS.md`, the QAQC report |

## 8. Evidence integrity

- `check_bundle.py --strict`: **PASS (49 checks, 0 warnings)**, 10 `B6-pins`
  rows, `B4-tracked git status clean`, `B7-secrets` clean.
- Fresh `git archive HEAD` + `sha256sum -c hashes.txt`: **30/30 OK**.
- Verdict consistency: **weak, and partly vacuous.** The committed
  `verdict-consistency.txt` checks only `ac4`, `ac5`, `ac7` and `test-output` —
  4 of the 12 artifacts the manifest calls PASS; its command is not recorded in
  `commands.log`; and "test-output contains expected verdict" is effectively
  vacuous (the stale-transcript F1 passed it). My independent re-run verified the
  missing eight (exit codes/`ok` lines in `ac1`, `ac2`, `ac3`, `ac6`, `ac8`,
  `ac9`, `ac10`, `apply-check`) plus the four it covers. **A12 (Minor).**
- Bundle unchanged after RW-1: `git diff f80d775..HEAD -- workflow/evidence/HO-STRATA-015/` empty.

## 9. Findings

A1–A8 are HO-014's findings; their HO-015 status is in §6 (all closed except the
label nits in A13). New findings continue the numbering.

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| **A9** | **Major** | **The bundle still cites the Q4_K-oracle router margin, not the gate's exact-f32 margin.** `manifest.md:76` and `artifacts/llama-ref-moe.md:69-70` state `2.80e-4` probability / `6.62e-3` logit for the 6th/7th margin at `(19,1)`, against `6.8e-5…7.12e-5` of drift — a reader of the bundle alone would conclude the flip is *not* explained. The correct exact-f32 value is **3.357e-6 / 7.948e-5** (teacher-forced 1.74e-6 / 4.10e-5), and the drift-induced 33↔40 gap shift is **1.385e-4**. DEC-046's erratum ordered this correction in terms and DEC-046 condition 3 requires the margins in the bundle; QAQC closed F2 on the erratum's existence without checking the files. The conclusion is correct; the merged, immutable bundle would freeze the wrong figure. | RW-HO-STRATA-015-2 (below): correct the two files, add the recompute as a bundle artifact + command, re-run `check_bundle --strict`, rehash. Evidence-only; **do not touch code, the gate, 5e-3, the reference, the prompt, the positions or 108/112**. | coder-primary → auditor re-check |
| **A10** | Minor | Manifest environment row is factually wrong/incomplete: "Linux 6.x, Python 3.12" vs kernel `7.0.0-42-generic`, Python `3.14.10`; no GCC/HIP/driver. HANDOFF_CONTRACT §7 requires OS/kernel/driver/compiler/runtime. | Correct in S5; the QAQC report already records the right values. | coder (S5) |
| **A11** | Minor | AC-8 says "peak **device/host** allocation recorded"; only a post-allocation device sample is recorded (23.124 GiB / 45.970 GiB GTT). On this unified-memory profile GTT *is* host memory, so the substance is met; the wording is not. | State the GTT=host equivalence, or record both, in S5. | coder (S5) |
| **A12** | Minor | `verdict-consistency.txt` covers 4 of 12 PASS-cited artifacts; its command is not in `commands.log`; "test-output contains expected verdict" cannot detect a stale transcript (F1 counter-example). | Commit the check script and give each PASS-cited artifact its expected token; S5. | coder (S5) |
| **A13** | Minor | Stale labels: manifest §3 `(computed after commit)` for patch/`compare_layers.py`; manifest §1 row 10 cites "test-output tail" for `check_bundle` (tail is `rw1-regenerate.txt`); DoD §9 "9 pin rows" vs 10; the first `CODER_TO_QAQC` cites `12995e1…` and §11 cites "42 checks"; handoff `State` still `CODER_DONE` while `STATUS.md` says `AUDIT_REVIEW`. | Clean at signoff/S5; none affect the evidence. | architect/coder |
| **A14** | Observation | DEC-046 condition 2 literally places the ≤1e-6 injection assertion in `compare_layers.py`; it lives in the engine (`ds_engine.cu`, `#ifdef`), and for `l=0` it is the identity. It is non-vacuous for `l≥1` (my +2e-6 probe fails). | Record the deviation from the literal condition; S5 can assert block-0 inputs against `token_embd`. | architect |
| **A15** | Observation (carry) | Teacher forcing is blind to cross-position state, drift amplification, positions >3, and sub-node cancellation (§3.2). The compensations (informational profile, S5 token gate, S6 regression) are adequate **only if** S5 is written as a blocking gate and no support/perf claim precedes it. | Carry to HO-STRATA-016 as a hard gate; repeat in the S5 handoff. | architect |
| **A16** | Minor | `scripts/gen_teacher_inputs.py` imports `gguf_reader` from the Strata checkout (`/home/kupipi/Documents/git/strata/tools`) and defaults to absolute `/tmp/opencode/…` paths. The gate is self-contained (inputs committed), so RW-1 stands; the regeneration command is machine-specific. | Vendor a minimal reader or document the dependency; S5. | coder (S5) |

**RW-HO-STRATA-015-2 — precise scope (A9 only).** The RW file is specified here
in full and is issued on the `AUDIT_REVIEW → REWORK` transition. Evidence-only;
no code, no Strata tree, no gate value (`1.569942e-04`), no `5e-3`, no reference,
no prompt, no positions, no cell counts, no DEC-046 record.

1. In `workflow/evidence/HO-STRATA-015/manifest.md` §4 and
   `artifacts/llama-ref-moe.md` ("Why the gate is teacher-forced"): replace the
   `2.80e-4 / 6.62e-3` margin with the exact-f32 values and name the trajectory:
   oracle **3.357e-6 prob / 7.948e-5 logit**; teacher-forced engine **1.74e-6 /
   4.10e-5**; free-running engine **2.49e-6 / 5.90e-5**; inherited `ffn_inp`
   drift **7.12e-5 rel L2** (max abs 5.70e-4); drift-induced 33↔40 logit gap
   shift **+1.385e-4**. Note that the earlier `2.80e-4 / 6.62e-3` came from the
   Q4_K_M oracle and is not the gate trajectory (DEC-046 erratum).
2. Add the recompute as a bundle artifact (e.g. `artifacts/router-margin-19-1.txt`)
   produced by a committed, copy-paste command that reads the f32 pack +
   `oracle_nodes` + the committed free/teacher dumps; record the command in
   `commands.log` and the artifact in `test-output.txt` (rebuild the transcript
   **after** the final capture, DEC-041 §2).
3. Re-run `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-015 --strict`
   → `RESULT: PASS`, `git status --porcelain` clean, rehash `hashes.txt` /
   `hashes-notes.txt`, `sha256sum -c` 100% from a fresh archive.
4. Return to the **auditor** for a delta re-check. A second failure on this
   criterion escalates to the architect.

## 10. Verdict

- **Gate (AC-5b, teacher-forced, DEC-046): PASS on the merits.** Independently
  reproduced: 112 cells, max `1.569942e-04` at `(4,3)`, `RESULT: PASS`,
  byte-identical artifact. The near-tie at `(19,1)` is real and the flip is
  predicted by measurement: 3.357e-6 / 7.948e-5 margin vs a 1.385e-4 drift-induced
  gap shift and a 4.25e-5 engine-arithmetic shift at identical input. The gate is
  sharp (two semantic mutations fail at `(1,0)`), and nothing else was moved: the
  bound, reference, prompt, positions and cell counts are unchanged from READY,
  the reference regenerates byte-for-byte, the macro is unreachable and
  arithmetically inert.
- **Scope, guard rails, RW-1: PASS.**
- **Evidence: FAIL on A9 only.** The bundle's own explanation of the deviation
  cites the wrong-trajectory margin, and the DEC-046 erratum ordered it
  corrected. Because merged bundles are immutable, this must be fixed before
  merge.
- **Verdict: REWORK (evidence-only, A9).** The architect must not sign, and the
  branch must not merge, until RW-HO-STRATA-015-2 is closed and re-checked. The
  gate does not need to be re-run; the fix is two paragraphs, one artifact, and
  a rehash.

### AUDITOR_TO_ARCHITECT (embedded per DEC-018)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-015-AUDIT (embedded in `workflow/reports/audit/HO-STRATA-015-audit.md`) |
| **Type** | AUDITOR_TO_ARCHITECT |
| **State** | REWORK (evidence-only) — the gate is confirmed PASS; A9 blocks audit PASS |
| **Date (UTC)** | 2026-11-26 |
| **From → To** | Auditor (`opencode-go/deepseek-v4.1-flash`, WAIVER-001) → Architect (`opencode-go/deepseek-v4-pro#max`) |
| **Handoff** | `workflow/handoffs/HO-STRATA-015.md` + `DR-HO-STRATA-015-1.md` + `RW-HO-STRATA-015-1.md` (DEC-043, DEC-044, DEC-046 + erratum) |
| **Branches** | Workflow `wp/strata-015-deepseek-s4b` @ `65f8ef4` (bundle `f80d775`); Strata `strata-015-deepseek-s4b` @ `e2e7e1b` |
| **Evidence** | `workflow/evidence/HO-STRATA-015/` (`check_bundle --strict` PASS 49 checks; 30/30 hashes from a fresh archive) |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-015-qaqc.md` |
| **Gate (auditor-reproduced)** | 112 cells, max `1.569942e-04 at (4,3)`, `RESULT: PASS`; free-running `(19,1) = 2.668110e-02` informational; exact-f32 margin 3.357e-6 / 7.948e-5; drift 7.123e-5; induced gap shift 1.385e-4; engine arithmetic at identical input 4.25e-5 |
| **Central question** | **Justified by measurement, not a loosened gate.** Teacher forcing is sharp (two semantic mutations fail at cell (1,0), max 6.16e-1 / 7.52e-1), and the free-running FAIL is reported and labelled informational. Nothing else was moved: 5e-3, `a4c56b9d…`, prompt, positions, 108/112 unchanged since READY; the oracle regenerates byte-for-byte at `78e05298…`; the macro is unreachable in the shipped build and changes zero bits of arithmetic. |
| **Blocking finding** | **A9** — `manifest.md:76` and `artifacts/llama-ref-moe.md:69-70` still cite `2.80e-4 / 6.62e-3` (Q4_K oracle) instead of the exact-f32 `3.357e-6 / 7.948e-5`; the DEC-046 erratum ordered this correction and DEC-046 condition 3 requires the margin in the bundle. |
| **Required next step** | Issue **RW-HO-STRATA-015-2** to `coder-primary` exactly as scoped in §9 (two files + one recompute artifact + command + transcript rehash + `check_bundle --strict`); return to the auditor for a delta re-check. Do not sign or merge before it closes. No code, gate, bound, reference, prompt, positions or cell-count changes. |
| **Carried (no rework)** | A10 (environment row), A11 (AC-8 host/GTT wording), A12 (verdict-consistency coverage/command), A13 (stale labels), A14 (assertion location), A15 (teacher-forcing limits → S5 must be a blocking token gate; no support/perf claim before it), A16 (generator portability). F3(i) carried with the reasoning in §6. |
| **Auditor statement** | I did not modify code, tests, docs, handoffs, or configuration; this report is the only artifact I wrote. |

## 11. Statement

I did not modify code, tests, docs, or configuration. This report
(`workflow/reports/audit/HO-STRATA-015-audit.md`) is the only artifact I wrote.
