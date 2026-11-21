# HO-STRATA-011-QAQC — OLMoE oracle extension (S0b) review

| Field | Value |
|---|---|
| **ID** | HO-STRATA-011-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-20 |
| **From → To** | Primary Coder (`coder-primary`) → QAQC (`qaqc`) |
| **Work package** | `strata-011-olmoe-oracle` |
| **Branch / base commit** | `wp/strata-011-olmoe-oracle` / `8ce28c4e2e33904b824d8541d69f1ea770548424` |
| **Priority / timebox** | P1 · 4 working hours |

## 1. Scope (in)

- Independently verify the evidence bundle in `workflow/evidence/HO-STRATA-011/`.
- Re-run the acceptance commands from `manifest.md` §1.
- Confirm the pack identity, harness build provenance, tokenizer parity table,
  reference-run reproducibility, dump shapes, hash integrity, and no engine change.
- Record the tokenizer parity finding: the engine tokenizer at the Strata pin
  raises `UnknownPreTokenizer('olmo')`. Verify this is reported truthfully and
  not hidden.

## 2. Out of scope

- Any engine change or new model download.
- Mixtral / DeepSeek / `qwen4exp` re-runs.
- Tolerance values or KL bounds (S4/S5).
- Performance or support claims.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Original handoff | `workflow/handoffs/HO-STRATA-011.md` | CODER_DONE |
| Evidence bundle | `workflow/evidence/HO-STRATA-011/` | attached |
| Model pack | `/home/kupipi/Documents/models/gguf/olmoe-1b-7b/olmoe-1b-7b-0924-instruct-q4_k_m.gguf` sha256 `8c310f14…` | present |
| llama.cpp pin | `/tmp/opencode/llama.cpp` @ `b12527` (`78e05298…`) | present |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | Pack identity matches §2 of HO-011 | `stat` + `sha256sum` + architecture read | size 4,213,512,672; sha `8c310f14…`; arch `olmoe` |
| 2 | Harness builds from committed source | `g++ … oracle_harness.cpp …` | exit 0 (warnings acceptable) |
| 3 | Tokenizer parity table reproduced | `python3 artifacts/generate_parity_table.py --gguf <olmoe> --harness /tmp/opencode/oracle_harness` | table present; engine `UnknownPreTokenizer('olmo')` finding visible; BOS convention stated |
| 4 | Reference run reproducible | commands 4, 5, 6a, 6b, 6c | `raw_diff_exit=1`; `normalized_diff_exit=0`; `gen:` lines identical; logits binaries identical |
| 5 | Layer dump shape and non-degeneracy | commands 3 + 7 | shape `[4][16][2048]`; all layers non-zero; no nan/inf |
| 6 | Top-2 logits dump shape | command 4 | shape `[16][2][2]`, 256 bytes, layout documented |
| 7 | Evidence hashes verify | `sha256sum -c workflow/evidence/HO-STRATA-011/hashes.txt` | all OK |
| 8 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain` + HEAD + binary hash | empty; HEAD `baf16363…`; binary `d58ee239…` |
| 9 | No unsupported claim | review | no perf/support claim |

## 5. Evidence required

- `workflow/reports/qaqc/HO-STRATA-011-qaqc.md` using `templates/QAQC_REPORT.md`.
- Re-run outputs saved under `workflow/evidence/HO-STRATA-011/artifacts/qaqc/` (do not overwrite coder artifacts).
- PASS or FAIL verdict; if FAIL, issue `RW-HO-STRATA-011-1` referencing the failed criterion and the raw output.

## 6. Guard rails

- Do not modify code, tests, docs, or configuration.
- Do not merge or push to `main`.
- Do not add dependencies.
- Do not change acceptance criteria.
- No secrets in the report or evidence.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| llama.cpp build at `/tmp/opencode/llama.cpp` | Coder | present | re-run |
| Strata engine at `/home/kupipi/Documents/git/strata` | Coder | present | no-change check |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branch and base commit named
- [x] Scope and out-of-scope explicit
- [x] Inputs linked and available
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable
- [x] Guard rails explicit
- [x] Dependencies resolved or owned
- [x] Priority/timebox set
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] QAQC report written and committed on the branch
- [ ] Every acceptance command re-run; raw output preserved
- [ ] Verdict recorded (PASS / FAIL)
- [ ] On FAIL, rework handoff issued
- [ ] Handoff state moved to `QAQC_REVIEW` or `REWORK`

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` | 2026-11-20 | CODER_DONE |
| Receiver (QAQC) | `qaqc` | | |

## 11. Log

- 2026-11-20 coder-primary: created CODER_TO_QAQC handoff; evidence bundle ready at `workflow/evidence/HO-STRATA-011/`.
