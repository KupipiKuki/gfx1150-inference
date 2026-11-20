# RW-HO-STRATA-010-1 — rework request

| Field | Value |
|---|---|
| **Rework ID** | RW-HO-STRATA-010-1 |
| **Original handoff** | HO-STRATA-010 (`ARCHITECT_TO_CODER`), branch `wp/strata-010-reference-oracle`, base `36609255e28da370a35b3a687e9bc351c52981a0`, audited tip `02bc3c2` |
| **From → To** | Auditor (`auditor`) → Primary Coder (`coder-primary`) |
| **State** | REWORK |
| **Created (UTC)** | 2026-11-18 |
| **Reviewer** | Auditor (`auditor`) — after QAQC re-pass (A-3) |
| **Audit report** | `workflow/reports/audit/HO-STRATA-010-audit.md` |

## 1. Failed criterion/criteria

| # | Criterion | Evidence (command + output/line) |
|---|---|---|
| 1 | **AC-3 evidence integrity** — the tokenizer parity artifact must show the full multi-line decode comparison with no false mismatch (QAQC M1 / closure C4) | `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md:1` = `  harness decode mismatch: 'def add(a, b):'`. Re-running `commands.log` step 2 with the fixed `tokenize_compare.py` (`9903bc16…`) writes a table **without** that line: `diff /tmp/…/parity.out artifacts/tokenizer_parity_table.md` → `0a1`, exit `1`. The file was last changed in `d5d4800`, not in the closure commit `02bc3c2`. `manifest.md:34` claims "P2 multi-line decode now parsed in full"; `test-output.txt:2-6` agrees with the fix, so the table contradicts the rest of the bundle. |
| 2 | **Raw-output fidelity (AC-2 evidence)** — the reproducibility transcript must record the exit codes it actually observed | `workflow/evidence/HO-STRATA-010/test-output.txt:37` = `stdout_diff_exit=0`, while lines 29–36 print a non-empty `diff` and `diff run1.txt run2.txt` exits **1**. The real reproducibility evidence is the normalized diff (`normalized_diff_exit=0`), whose producing command appears in neither `commands.log` nor `manifest.md`. QAQC repeated the false claim ("`diff` exit `0`", QAQC report §1 row 2). |

Nothing else is at issue. I independently reproduced the oracle from the committed source (harness binary `40cf635f…`, build exit 0): `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280`, logits dump `5334baef…` (bit-identical, both runs), layer dump `db6eccb3…` with `[(0,28),(1,28),(2,28),(3,28)]` and 0 zero rows of 112, parity P1/P2/P3 exact, 15/15 `hashes.txt` `OK`, Strata clean at `baf16363` with `build-hip/strata` unchanged. `tokenize_compare.py`, `oracle_harness.cpp`, `check_layers.py` and `hashes.txt` stay as they are.

## 2. Required fix

- **F1 (A-1).** Regenerate `workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` with the current script and the recorded command:
  `python3 workflow/evidence/HO-STRATA-010/artifacts/tokenize_compare.py --gguf <deepseek> --harness /tmp/opencode/oracle_harness`
  Confirm the file starts with the `| prompt | …` header, contains no `harness decode mismatch` line, and that re-running the command reproduces the file byte-for-byte. Update its digest in `hashes.txt` and in `manifest.md` §3.
- **F2 (A-2).** Fix the reproducibility transcript. Either record the true `diff` exit (`1`) and the reason (only `wall_s` and the output filename differ), or drop that diff from the gate and record the normalized comparison instead. Prefer both: add the normalization command (the one that produced `run{1,2}.norm.txt`) to `commands.log`, record `normalized_diff_exit=0`, and record `stdout_diff_exit=1` truthfully. Do not present a non-empty diff as exit 0.
- **F3 (A-3, hands off to QAQC).** After the commit, QAQC re-runs AC-1…9 and C1–C5 against the new commit and refreshes `workflow/reports/qaqc/HO-STRATA-010-qaqc.md` (fingerprint: commit SHA, `hashes.txt` entry count and the two dump digests). The auditor then re-audits.
- **Permitted in the same commit (minor, inside the evidence bundle only; not required to pass):** A-4 (record the normalization command — also needed by F2), A-5 (manifest §1 rows 3/4/7 paths), A-6 (manifest commit field = the new evidence commit), A-7 (record `GGML_NATIVE=ON`, `cmake --version`, host CPU, `nproc`; state that lib digests are this-host only), A-8 (state `add_special=false` / `parse_special` on both sides), A-9 (one line: the C1 fix changes the last block's GEMM from M=1 to M=4; `l_out-27` pos 3 moved by ≤3.81e-6 abs, rel L2 8.07e-8 vs the pre-fix dump; layers 0–26 and the generation logits are bit-identical).
- Do **not** regenerate the dumps or the gen reference unless re-running the full set changes them; if a re-run produces a different digest, stop and report it as a deviation instead of overwriting.
- Do not touch `tokenize_compare.py`'s logic, `oracle_harness.cpp`'s logic, `check_layers.py`, `workflow/MODELS.md`, `DECISIONS.md`, `STATUS.md`, or the handoffs (DEC-018: the architect mirrors states).

## 3. Evidence required to prove the fix

- `sha256sum -c workflow/evidence/HO-STRATA-010/hashes.txt` → all entries `OK`, exit 0, with the new count.
- `head -2 workflow/evidence/HO-STRATA-010/artifacts/tokenizer_parity_table.md` → `| prompt | text | …` and `|---…`, no mismatch line.
- `diff` between a fresh run of `commands.log` step 2 and the committed table → empty, exit 0.
- `grep -n "stdout_diff_exit\|normalized_diff_exit" workflow/evidence/HO-STRATA-010/test-output.txt` → the true values.
- Raw output of the normalization command, and its presence in `commands.log`.
- New `manifest.md` and `hashes.txt` digests for every file changed in this rework.
- `git -C /home/kupipi/Documents/git/strata status --porcelain` empty and `sha256sum /home/kupipi/Documents/git/strata/build-hip/strata` = `d58ee239…` (unchanged guard rail).

## 4. Guard rails

- Fix only F1 and F2 plus the permitted minor items; no unrelated changes, no scope expansion.
- No engine change, no Strata rebuild, no model download or conversion, no prompt tuning.
- No new dependency; keep the llama.cpp pin at `78e05298…` / tag `b12527`.
- Re-run the full acceptance set, not only the failed items.
- Update `workflow/evidence/HO-STRATA-010/` on the same branch `wp/strata-010-reference-oracle`; state stays `CODER_DONE` until QAQC re-passes.
- No secrets in any file; commit subject `HO-STRATA-010: close RW-HO-STRATA-010-1 (parity artifact + diff exit)`.

## 5. Acknowledgment

| Role | Date | Note |
|---|---|---|
| Coder | | |
| QAQC (re-pass) | | |
| Auditor (re-audit) | | |

**Escalation:** a second failure on the same criterion goes to the architect.
