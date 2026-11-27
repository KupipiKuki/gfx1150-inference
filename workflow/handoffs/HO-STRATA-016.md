# HO-STRATA-016 — DeepSeek S5: exact token parity, KL, and the support claim

| Field | Value |
|---|---|
| **ID** | HO-STRATA-016 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **READY** (2026-11-27) — part of the owner-authorised S4/S5 chain (DEC-042 §8) |
| **Created / updated (UTC)** | 2026-11-27 / 2026-11-27 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `deepseek-s5` |
| **Branch (workflow)** | `wp/strata-016-deepseek-s5` / base `main` @ `8abcb3bd0e85c52788a09742f8081e17e9cda2c5` |
| **Branch (Strata)** | `strata-016-deepseek-s5`, cut from `strata-015-deepseek-s4b` @ `e2e7e1b` |
| **Priority / timebox** | P1 · 3 working days + 1 day per gate cycle |
| **Predecessors** | HO-STRATA-014 (S4a), HO-STRATA-015 (S4b) — both DONE/SIGNED/merged (#29, #31) |
| **Decisions** | DEC-037 (**S4 not authorised** — superseded), DEC-042, DEC-044, DEC-046, **DEC-047**, **DEC-048** |

## 0. What this handoff decides

S4a and S4b proved the arithmetic: every block within **1.569942e-04** of the
exact-f32 reference, given the reference's own state. What neither proved is the
engine's **own** trajectory over 16 steps — its K/V, its residual accumulation,
its sampling. Teacher forcing deliberately cannot see that (audit A15), and
**this handoff's token gate is the only thing that can**.

If it passes, DeepSeek-MoE-16B becomes a **supported family**: `--native` runs it
without a diagnostic flag, `--families` lists it, and the named refusal stops
applying. That is a product claim, and it is the last thing in the chain that can
still fail on numerics.

## 1. Scope (in)

### 1.1 The gate: exact tokens, shipped pack, 3 prompts

Three fixed prompts (token IDs from HO-010's parity table — **no tokenizer work**,
so a tokenizer bug cannot masquerade as a model bug):

| Prompt | Tokens |
|---|---|
| P1 prose | `549,6077,280,7239,317` |
| P2 code | `1558,962,7,64,11,270,1780,185,300,972` |
| P3 list | `21477,6663,8247,418` |

Each prompt generates **16 greedy tokens**. The engine's 16 IDs must equal the
**Q4_K oracle's** 16 IDs exactly (plan A3; DEC-038 makes the CLI oracle the
authority). P1's reference is committed (`HO-STRATA-010` `run1.txt`:
`8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280`); **P2 and
P3 must be generated** with the committed harness on the Q4_K pack (§1.2).

**A mismatch is a finding, not a rework instruction**: report the step, both
tokens, the top-2 margins at that step for both models, and what the **exact-f32
oracle** produces at the same step. The architect decides. Do not "fix" a token by
nudging arithmetic, and do not accept a mismatch because the margin was small.

### 1.2 The reference, extended

The committed harness (`HO-STRATA-014/scripts/oracle_nodes.cpp`) dumps per-layer
nodes and **top-2** logits. This handoff needs, for each of the 3 prompts:

- the 16 generated IDs (greedy, `--tokens`, `n_predict 16`);
- **full logits** for each of the 16 steps (`[16][n_vocab]` f32 ≈ 6.4 MB/prompt),
  so KL can be computed;
- the same full logits from the **exact-f32 pack**, for the KL comparison and for
  adjudicating any token mismatch.

Add a `--dump-logits-full` mode **in a copy under this bundle**
(`scripts/oracle_s5.cpp`), derived from the committed harness, with the parent's
hash recorded. Do not edit `HO-STRATA-010`'s or `HO-STRATA-014`'s scripts.

### 1.3 Engine side

- **Full-logits dump** per step (`--dump-logits-full PATH`, `[steps][n_vocab]` f32)
  on the same token sequence, greedy.
- `--dump-layers` becomes **optional** (DEC-048 §5) — normal runs must not require
  a parity dump.
- Greedy sampling must be deterministic and documented (argmax; ties → lowest ID).

### 1.4 The support flip (DEC-048)

Only after AC-1…AC-5 pass:

1. `--native <deepseek pack> --tokens … --max-new 16` runs **without**
   `--parity-run` and produces the tokens.
2. `--families` lists `deepseek` **in a build that compiles the engine**, and does
   **not** list it otherwise.
3. `model_family_runs(DeepseekMoe)` is **true only when the engine is compiled**.
4. In a build **without** the engine, the named refusal still fires — prove it.

`--parity-run`, the teacher-forced diagnostics and `--inspect` stay (regression
value); they stop being required.

## 2. Out of scope

- Any change to the arithmetic that produced S4a/S4b's 1.57e-04 (no q8_K
  emulation, no "tuning" toward the oracle). If parity needs an arithmetic change,
  that is a finding.
- Performance work of any kind (no pooling, expert cache/streaming, batching, MTP);
  no throughput/tok-s claim, no GTT envelope claim (that is S6).
- OLMoE, `qwen4exp`/`qwen35moe` behaviour, MTP/draft models, serving/API.
- Any new family in `--families` other than `deepseek`.
- Changing the 5e-3 layer bound, the reference, the prompts or the cell counts from
  S4 (they are historical); this handoff's own numbers are DEC-047's.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Pack | Q4_K_M, `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` | available |
| f32 pack (exact reference) | `/tmp/opencode/deepseek-moe-16b-f32.gguf`, `8cd778a7…` (regenerate with the committed command if absent) | on disk |
| llama.cpp pin | `78e05298f0d68abff41d08d79fa7469264b2aff0` (`/tmp/opencode/llama-ref`) | available |
| P1 reference (16 IDs) | `HO-STRATA-010/artifacts/runs/run1.txt` + logits `5334baef…` | signed |
| Prompt token IDs | `HO-STRATA-010/artifacts/tokenizer_parity_table.md` | signed |
| Engine (S4b) | Strata `e2e7e1b`; patch `HO-STRATA-015/patches/0003-s4b-moe.patch` | merged |
| KL rationale | DEC-047; `tools/qwen35/kl.py` (practice), `docs/GDN_CONTRACT.md:78` | in tree |
| Support semantics | DEC-048 | recorded |

## 4. Acceptance criteria

`<pack>` = Q4_K_M; `<f32>` = the exact pack. Engine runs from the Strata checkout
with `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib`.

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| **AC-1** | Builds; signed binary + both oracles untouched | build; `sha256sum build-hip/strata`; re-hash the f32 dump | `d58ee239…`; `a4c56b9d…` |
| **AC-2** | The reference set exists for all 3 prompts | harness on `<pack>` for P1/P2/P3, 16 greedy tokens + full logits | P1 **must** reproduce `8913 13 185 40619 317 …`; P2/P3 recorded; the f32 pack gives the same 3 sets (or the difference is reported) |
| **AC-3** | **Token parity — the gate** | engine, 3 prompts × 16 greedy tokens | **zero mismatches** vs the Q4_K oracle. Any mismatch: report step, both tokens, top-2 margins, and the f32 oracle's token at that step (see §1.1) |
| **AC-4** | **KL — absolute ceiling** (DEC-047) | KL over the 16 steps on the oracle's token sequence | mean KL(engine‖f32) **≤ 1e-2 nats** per prompt and **no step > 1e-1**; KL(engine‖Q4_K) and KL(Q4_K‖f32) reported as context (not gated) |
| **AC-5** | Sampler determinism | two runs per prompt; `cmp` the token lines and the logits dumps | identical |
| **AC-6** | **The support flip** (DEC-048) | `--native <pack> --tokens … --max-new 16` **without** `--parity-run`; `--families`; a build **without** the engine | runs and emits AC-3's tokens; `--families` lists `deepseek` **with** the engine and not without; the refusal fires without the engine |
| **AC-7** | `--dump-layers` optional | a normal run with no dump flags | exit 0, no dump file written |
| **AC-8** | Qwen regression + tests | HO-012 C8 command; `model_family_test`; `gguf_geometry_test` | the 32 HO-007 IDs; both exit 0 (including the `--families` and refusal tests, updated) |
| **AC-9** | Geometry/route assertions unchanged | the startup assertion output | the 11 fields still asserted |
| **AC-10** | Patch measured, exported, applies | `git diff --stat e2e7e1b..HEAD`; cumulative vs `baf16363`; `patches/0004-s5-tokens.patch`; `git apply --check` on `baf16363`+`0001`+`0002`+`0003` | applies; cumulative stated |
| **AC-11** | Evidence gate | `check_bundle.py … --strict` | PASS before `CODER_DONE` |
| **AC-12** | **Carried audit criteria (A12, A14, A18, A10/11/13/16)** | verdict-consistency must cover **every** PASS-cited artifact; the block-0 input assertion uses `token_embd`; the gap convention stated; manifest env row correct; AC-8 wording; no stale labels; generators committed and runnable | each demonstrable |
| **AC-13** | No claim without an artifact | every numeric claim in the manifest cites a command and a file that contains it | grep-checked |

## 5. Evidence required

`workflow/evidence/HO-STRATA-016/`: `manifest.md`, `commands.log` (every command,
including the three oracle generations and the KL runs), `test-output.txt` (raw,
rebuilt after the final capture), `artifacts/` (per-prompt token lines for
engine/Q4_K/f32, full-logits dumps for the 16 steps × 3 prompts — or their hashes
if too large, with the generator committed — KL tables, margin tables, the
`--families` outputs from both builds, the no-engine refusal, the Qwen regression,
the tests, the patch stats, the geometry assertions), `scripts/oracle_s5.cpp` +
the KL script, `patches/0004-s5-tokens.patch` + `apply-check.txt`, `hashes.txt`
(immutable only), `hashes-notes.txt` (`## Commit pins` table, full digests).

Logits dumps are ~6.4 MB × 3 × 2 packs ≈ 38 MB — **commit the generated token
lines and the KL tables; commit the dumps only if under ~10 MB each, otherwise
commit the generator and their SHA256s** and say so in the manifest (a carried
A16-class decision). Whatever is external must be regenerable from the bundle.

**One profile per claim:** gfx1150 / Radeon 890M / Ryzen AI 9 HX 370 / ROCm 10.1 /
DeepSeek-MoE-16B Q4_K_M / greedy / 16 tokens / 3 prompts.

## 6. Guard rails

- Strata edits authorised for this handoff only, on `strata-016-deepseek-s5` cut
  from `e2e7e1b`; patch exported; never `main`.
- **Do not rebuild `build-hip/`** (`d58ee239…`).
- **Do not touch** the arithmetic that produced S4's 1.57e-04 in a way that changes
  parity numbers; `src/core/**`, shared kernels, `src/qwen35/**`; the tokenizer;
  any merged `workflow/evidence/HO-STRATA-0xx/` bundle; `DECISIONS.md`;
  `STATUS.md`; `.opencode/**`; `.github/**`.
- **The four ways this gate could be faked**: changing the prompt tokens, the
  greedy rule, the reference pack, or the token count. None is permitted.
- DEC-043's re-review trigger stands: shared-code edits → stop, raise a DR.
- No perf/support claim *except* the DEC-048 flip, which is the point.
- DEC-041 §2 capture ordering; `check_bundle --strict` before `CODER_DONE`.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| Signed S4b engine (`e2e7e1b`) | Architect | merged #31 | base |
| f32 pack + `llama-ref` build | environment | present (regenerate per §3 if evicted) | AC-2, AC-4 |
| Reference for P2/P3 | this handoff | **to produce** | AC-3 |
| ROCm 10.1 / `build-deepseek/` | environment | available | AC-1 |
| Actions billing | — | resolved (DEC-045) | merge |

## 8. Definition of Ready — MET

- [x] ID/type/from/to/title/work package; branches and bases named
- [x] Scope/out-of-scope explicit
- [x] Inputs linked with hashes; the gap (P2/P3 reference) is named as work, not assumed
- [x] Every criterion has a command/check; the token gate states what a mismatch means
- [x] Evidence requirements runnable, incl. the logits-size decision
- [x] Guard rails explicit, incl. the four ways the gate could be faked
- [x] Dependencies resolved
- [x] Priority/timebox set
- [x] **Pre-registered numbers**: zero token mismatches (plan A3); KL mean ≤ 1e-2 / step ≤ 1e-1 vs the f32 model (DEC-047)
- [x] Owner authorization (S5 is in the authorised chain, DEC-042 §8)
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] AC-1…AC-13 run; raw output in `test-output.txt`
- [ ] 3 × 16 tokens identical to the Q4_K oracle (or a reported finding, not a pass)
- [ ] KL within the DEC-047 ceilings, with both context curves reported
- [ ] The flip verified in **both** directions (with and without the engine)
- [ ] Qwen regression exact; tests green; signed binary untouched
- [ ] Patch exported, measured, applies on `0001…0003`
- [ ] `check_bundle --strict` PASS, verdict-consistency covering every PASS claim
- [ ] `CODER_DONE`; `CODER_TO_QAQC` record attached

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | `architect` (`opencode-go/deepseek-v4-pro#max`) | 2026-11-27 | **READY** |
| Receiver (Coder) | `coder-primary` (`opencode-go/kimi-k2.7-code`) | | |

## 11. Log

- 2026-11-27 Architect: created `READY`. This is the first handoff that may claim
  **support**, so its gate is the end-to-end token comparison that teacher forcing
  could not perform, and the flip is verified in both directions (DEC-048). KL is
  an absolute ceiling against the exact model rather than a ratio to a floor that
  cannot exist for two different arithmetics (DEC-047).

## 12. Task map after this handoff

| Stage | Handoff | Gate | State |
|---|---|---|---|
| **S5** | **this file** | 3×16 exact tokens; KL ≤ DEC-047; the flip | READY |
| S6/S7 | HO-STRATA-017 (on S5 PASS) | baseline + GTT/`dmesg` envelope + HO-007 regression bit-identical; QAQC → audit → sign | not written |
| OLMoE | HO-STRATA-018 (needs owner scope) | tokenizer pre-tokenizer + family path (DEC-032: two gaps, not one) | held |
