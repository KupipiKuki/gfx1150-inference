# HO-STRATA-010-QAQC — QAQC review of S0 reference oracle

| Field | Value |
|---|---|
| **ID** | HO-STRATA-010-QAQC |
| **Type** | CODER_TO_QAQC |
| **State** | PROPOSED |
| **Created / updated (UTC)** | 2026-11-18 |
| **From → To** | Primary Coder (`coder-primary`) → QAQC (`qaqc`) |
| **Work package** | `strata-010-reference-oracle` |
| **Branch / base commit** | `wp/strata-010-reference-oracle` / `main` `36609255e28da370a35b3a687e9bc351c52981a0` |
| **Priority / timebox** | P1 · 1 working day |

## 1. Scope (in)

Independent review of the S0 reference oracle:

- Verify llama.cpp is pinned and built at the recorded tag/commit with the recorded flags.
- Verify the harness `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` builds and runs from a clean workflow checkout (llama.cpp must be cloned/built separately).
- Verify DeepSeek tokenizer parity for the three fixed prompts (P1, P2, P3) by re-running `tokenize_compare.py` or an equivalent check.
- Verify the DeepSeek reference `gen:` line reproduces on two independent runs.
- Verify the layer dump shape is `[4][28][2048]` and the sanity script shows non-degenerate layers.
- Verify the 16-step top-2 logits dump shape is `[16][2]`.
- Confirm no `strata` source edits and no support/performance claims.

## 2. Out of scope

- Mixtral 8x7B (deferred by DEC-029; the TheBloke pack uses the legacy per-expert layout).
- Any engine changes or family support work (S1+ remains held).
- Choosing tolerances or KL bounds for later stages.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Architect handoff | `workflow/handoffs/HO-STRATA-010.md` | CODER_DONE |
| Harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp` (`fc0a01da…`) | committed |
| Tokenizer parity script | `workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py` (`9ff5a394…`) | committed |
| Layer sanity script | `workflow/evidence/HO-STRATA-010/artifacts/check_layers.py` (`65eca3bd…`) | committed |
| DeepSeek pack | `/home/kupipi/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397cdb560ffb519aa8371d2f9eebae50d34d/deepseek-moe-16b-base-q4_k_m.gguf` (`f00ecd83…`) | present |
| Evidence bundle | `workflow/evidence/HO-STRATA-010/` | complete |

## 4. Acceptance criteria

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| 1 | llama.cpp provenance matches manifest | inspect `manifest.md` §4 and re-run clone/build if needed | tag `b12527`, commit `78e05298…`, lib hashes match |
| 2 | Harness builds and runs | run the build command in `commands.log` | exit 0, harness `--help` works |
| 3 | Tokenizer parity passes for DeepSeek | `python3 artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/oracle_harness` | all 3 prompts `match=True`, no BOS mismatch |
| 4 | Reference `gen:` reproduces | run the P1 16-token command twice and `diff` the `gen:` lines and logits binaries | identical |
| 5 | Layer dump shape + sanity | `python3 artifacts/check_layers.py artifacts/runs/deepseek_p1_4_layers.bin` | shape `(4,28,2048)`, L0 vs L1 differs, no nan/inf |
| 6 | Logits dump shape | `ls -l artifacts/runs/deepseek_p1_logits.bin` | 256 bytes, shape `[16][2]` |
| 7 | No engine change | `git -C /home/kupipi/Documents/git/strata status --porcelain` | empty; HEAD `baf16363…` |
| 8 | No support/performance claims | review `manifest.md` and handoff | none |

## 5. Evidence required

- `workflow/evidence/HO-STRATA-010/manifest.md`
- `workflow/evidence/HO-STRATA-010/commands.log`
- `workflow/evidence/HO-STRATA-010/test-output.txt`
- `workflow/evidence/HO-STRATA-010/hashes.txt`
- `workflow/evidence/HO-STRATA-010/artifacts/`
- QAQC report in `workflow/reports/qaqc/HO-STRATA-010-qaqc.md`

## 6. Guard rails

- Do not modify code, tests, docs, or configuration outside the QAQC report directory.
- Do not merge or push to `main`.
- Do not change acceptance criteria or scope.
- No new dependencies without architect approval.
- No secrets in the report or logs.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| llama.cpp build environment | QAQC host | available recipe in manifest | criterion 1/2 |
| DeepSeek Q4_K_M pack | Owner | present, hash verified | criteria 3–6 |

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

- [ ] QAQC report written and committed to `workflow/reports/qaqc/HO-STRATA-010-qaqc.md`
- [ ] Every acceptance criterion run; raw output preserved
- [ ] Verdict PASS or FAIL with explicit findings
- [ ] If PASS, state transitioned to `QAQC_REVIEW → AUDIT_REVIEW` per DEC-018
- [ ] If FAIL, rework handoff created

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Coder) | `coder-primary` | 2026-11-18 | PROPOSED |
| Receiver (QAQC) | `qaqc` | | |

## 11. Log

- 2026-11-18 Coder: created `CODER_TO_QAQC` after completing S0 evidence bundle and updating `HO-STRATA-010.md` to `CODER_DONE`.
