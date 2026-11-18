# HO-STRATA-010 — reference oracle and parity harness (stage S0)

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **READY** — DoR met (§8) |
| **Created / updated (UTC)** | 2026-11-18 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / base commit** | `wp/strata-010-reference-oracle` / `main` at the branch point (record the SHA) |
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

- [ ] Oracle built, pinned, reproducible
- [ ] Tokenizer parity proven (or the mismatch documented and escalated)
- [ ] Reference IDs + dumps for both families
- [ ] Harness committed and rerunnable
- [ ] No engine change; no claim
- [ ] Manifest complete; `CODER_DONE`; QAQC handoff created

## 10. Why the tokenizer gate comes first

A tokenizer difference changes every token, so a later token mismatch would look
like a model bug and burn days in S4. Proving encode/decode parity before any
inference is the cheapest possible insurance, and it is why this stage is worth a
day on its own.

## 11. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | architect | 2026-11-18 | READY |
| Receiver (Coder) | `coder-primary` | | |

## 12. Log

- 2026-11-18 Architect: created READY after the owner chose S0 (DEC-028). Scope is
  the oracle and harness only; no engine change, no family support.
