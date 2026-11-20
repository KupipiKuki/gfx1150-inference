# HO-STRATA-010 — reference oracle and parity harness (stage S0)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **DONE** (SIGNED 2026-11-19) — READY → CODER_DONE → QAQC PASS → AUDIT FAIL → RW-010-1 → QAQC PASS → AUDIT PASS → **DONE** (DEC-030) |
| **Created / updated (UTC)** | 2026-11-18 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / base commit** | `wp/strata-010-reference-oracle` / `main` `8ce28c4` |
| **Priority / timebox** | P1 · 1 working day |
| **Owner task** | OT-STRATA-001 (S0 authorized 2026-11-18, DEC-028) |
| **Plan** | `planning/strata-engine/13-family-support-test-plan.md` §4 (S0) |

## 1. Purpose

Build the **oracle** that every later family-parity gate compares against, and
prove it reproduces. This stage changes **no engine code**: it produces reference
outputs for Mixtral and DeepSeek-MoE from an independent implementation
(llama.cpp) plus a harness that both sides can be driven with.

Without this, "the engine agrees with the reference" is unverifiable. With it, S4
and S5 have a fixed target and an exact-token gate.

## 2. Scope (in)

1. **Pin and build llama.cpp** (CPU) at a recorded commit/tag.
   Record: tag, commit SHA, build flags, compiler, date, binary SHA256.
   Include the example/tooling needed for evaluation callbacks.
2. **A harness tool** that, given a GGUF and a token-ID list:
   - decodes **N tokens greedily** and prints the generated IDs on one line
     (`gen: id id …`), the shape `strata-q36ref` already uses;
   - optionally **dumps per-layer hidden states** for every processed position as
     raw `f32` (`[pos][layer][hidden]`) and prints the shape;
   - optionally **dumps logits** per step (`f32`, `[step][vocab]`) or the top-2 per
     step, for the later KL check.
   Prefer a small C++ tool against `libllama` (the repo builds one for `q36ref`
   already) over parsing CLI text; a Python wrapper is acceptable only for
   orchestration, not for the numbers.
3. **Three fixed prompts**, tokenized per family (each family has its own
   tokenizer):
   | # | Kind | Text |
   |---|---|---|
   | P1 | prose | `The capital of France is` |
   | P2 | code | `def add(a, b):\n    return` |
   | P3 | list | `Three primary colors are` |
   No chat template, no system prompt — raw text.
4. **Tokenizer parity:** for each family, `tools/strata_tokenizer.py` (or the
   engine's tokenizer) must encode/decode the three prompts to the **same IDs** as
   the reference. Record the table. A mismatch here invalidates every later token
   comparison, so it is a hard gate.
5. **Reference runs**, greedy, 16 tokens, from the P1 token IDs:
   - **DeepSeek-MoE-16B Q4_K_M** — in scope;
   - **Mixtral 8x7B Q3_K_M — deferred** (2026-11-18): the TheBloke pack is the
     2023 per-expert layout and current llama.cpp refuses it
     (`check_tensor_dims: tensor 'blk.0.ffn_down_exps.weight' not found`).
     Proving the harness on one family is sufficient for S0; Mixtral's oracle
     waits for a stacked-format pack (DEC-029).
   Save: token IDs, per-layer dumps for a 4-token prompt, logits for the 16 steps
   (or top-2 per step), and the wall time as an observation only.

## 3. Out of scope

- Any change to the `strata` engine, its CMake, or the family enum.
- Building or running Strata for Mixtral/DeepSeek (that is S1+).
- Choosing tolerance values for S4; choosing the KL bound for S5. S0 records the
  dumps; the bounds are fixed in those handoffs **before** comparison.
- Performance measurement or claims. CPU wall time is recorded as an observation.
- New model downloads; only the packs in `workflow/MODELS.md` are used.
- 780M, MI25, gfx1100.

## 4. Acceptance criteria

| # | Criterion | Check |
|---|---|---|
| 1 | llama.cpp pinned and built; provenance recorded | tag + commit + flags + binary SHA256 in `manifest.md` |
| 2 | Harness reproduces the same IDs on two consecutive runs of the same input | run twice, `diff` empty |
| 3 | Tokenizer parity: all 3 prompts, DeepSeek, zero ID differences vs the reference | parity table with the ID lists side by side |
| 4 | Reference token IDs for DeepSeek, P1, 16 tokens (Mixtral deferred, DEC-029) | `gen:` line saved |
| 5 | Per-layer dumps exist with the documented shape and are non-degenerate | shape line + `sha256` + a sanity check that consecutive layers differ |
| 6 | Logits/top-2 dumps exist for the 16 steps | files present, shapes printed |
| 7 | Harness script committed and runnable from a clean checkout of the workflow repo | command in `commands.log`, exit 0 |
| 8 | No engine change | `git -C strata status --porcelain` empty, HEAD `baf16363…` |
| 9 | No perf/support claim | report review |

## 5. Evidence required

`workflow/evidence/HO-STRATA-010/`: `manifest.md`, `commands.log`,
`test-output.txt`, `artifacts/` (llama.cpp provenance, harness source path +
hash, tokenizer parity table, `gen:` outputs, dump files or their hashes + shapes),
`hashes.txt` (immutable; pin `workflow/MODELS.md` by commit per DEC-024).

Dumps may be large: if a dump exceeds ~50 MB, store its **shape, a SHA256, and a
regeneration command** instead of the file, and say so in the manifest.

## 6. Guard rails

- No `strata` source edits, no rebuild of `build-hip/strata`.
- No model conversion; read the GGUFs as they are.
- No prompt tuning to get a nicer answer; the prompts are fixed in §2.3.
- No secret in logs; no weights in git.
- If llama.cpp cannot load a pack (arch, quant), record the exact error and stop —
  do not switch packs or rebuild with hacks.

## 7. Dependencies / blockers

| Dependency | Owner | Status |
|---|---|---|
| Mixtral Q3_K_M, DeepSeek Q4_K_M packs | Owner | present, hashes verified |
| llama.cpp source | Coder | fetch + pin (network allowed for this stage) |
| gfx1150 host | — | not required (CPU build) |

## 8. Definition of Ready — MET

- [x] ID/type/from/to/title/work package
- [x] Branch/base named (record the SHA)
- [x] Scope/out-of-scope explicit
- [x] Inputs available
- [x] Every criterion has a check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved
- [x] Priority/timebox set
- [x] No `NEEDS_INFO`
- [x] Authorized (DEC-028: S0 only; S1+ stays held)

## 9. Definition of Done

- [x] Oracle built, pinned, reproducible (DeepSeek only; Mixtral deferred, DEC-029)
- [x] Tokenizer parity proven for DeepSeek
- [x] Reference IDs + dumps for DeepSeek
- [x] Harness committed and rerunnable
- [x] No engine change; no claim
- [x] Manifest complete; `CODER_DONE`; QAQC handoff created

## 10. Why the tokenizer gate comes first

A tokenizer difference changes every token, so a later token mismatch would look
like a model bug and burn days in S4. Proving encode/decode parity before any
inference is the cheapest possible insurance, and it is why this stage is worth a
day on its own.

## 11. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-18 | READY |
| Receiver (Coder) | `coder-primary` | 2026-11-18 | CODER_DONE |

## 12. Log

- 2026-11-18 Architect: created READY after the owner chose S0 (DEC-028). Scope is
  the oracle and harness only; no engine change, no family support.
- 2026-11-18 Coder: built llama.cpp `b12527`, wrote `oracle_harness.cpp`, proved
  DeepSeek tokenizer parity for P1/P2/P3, produced reference `gen:` IDs, layer dump
  `[4][28][2048]`, and 16-step top-2 logits. Mixtral deferred per DEC-029. State
  `CODER_DONE`; QAQC handoff created.
- 2026-11-18 Coder: closed all five QAQC findings (C1–C5). DoD re-verified:
  layer dump regenerated with all 28 layers non-zero at all 4 positions
  (`db6eccb3…`), logits shape label corrected to `[16][2][2]` with layout note,
  `workflow/MODELS.md` removed from `hashes.txt` and four helper stdout files
  added, `tokenize_compare.py` now compares the full multi-line decode payload,
  and `commands.log` now includes the `git clone`/`checkout` and CMake build
  steps. `sha256sum -c` clean. State remains `CODER_DONE`.
- 2026-11-19 Coder: closed RW-HO-STRATA-010-1 (A-1/A-2). Rebased branch onto
  `main` `8ce28c4`; regenerated `tokenizer_parity_table.md` with no false P2
  mismatch; recorded true `stdout_diff_exit=1` and the normalization command as
  the reproducibility gate; updated `manifest.md` with runnable paths, host
  provenance, tokenizer convention, and C1 last-block note; pinned
  `workflow/MODELS.md` and the family test plan at `8ce28c4` in
  `hashes-notes.txt`. Full acceptance set re-run: layer dump `db6eccb3…`, logits
  `5334baef…`, gen line bit-identical. `sha256sum -c` clean. State remains
  `CODER_DONE`; bundle commit is the tip of `wp/strata-010-reference-oracle`.
- 2026-11-19 Architect: **SIGNED** → `DONE` after the second audit PASS. Residual
  minors B-1 (curated transcript labelled raw), B-2 (build-scoped lib digests),
  B-4 (pins recorded without digests) are carried to the next bundle touch; B-3
  closed here. See `HO-STRATA-010-APPROVAL.md`.
