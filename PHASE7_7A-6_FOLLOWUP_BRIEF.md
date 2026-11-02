# 7A-6 Follow-up Brief — Close the Auditor Conditions

**To:** GLM5.3 (coder) and QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-02
**Branch:** `wp/7A-6-followup`
**Base:** `wp/7A-6-claims-checker` @ `b626c94` (audit commit; candidate `994d629`)
**Gate:** 7A-6 follow-up only. G1 remains unsigned; 7B remains blocked.

This closes the conditions in
`audit/AUDIT_7A-6_CLAIMS_CHECKER_DEEP_2026-11-02.md` §4. It is a narrow follow-up; the
checker is accepted in substance.

---

## 1. Allowed files

- `scripts/qa/check_claims.py` (C-7A6-1; C-7A6-4 if the ledger literal changes)
- `scripts/qa/canary_claims.py` (new `strict_clean` canary; removal test if needed)
- `audit/CLAIMS_LEDGER.md` (ID 3 literal; no status/flag changes)
- `audit/evidence/G1/7A-6/**` (provenance erratum; QAQC probe-log correction)
- `audit/evidence/G1/7A-6-followup/**` (new evidence)
- docs

**No `src/`, `tests/`, `pyproject.toml`, build, packaging, CI, README, or
`IMPLEMENTATION_PLAN.md` changes.** If a fix seems to require one, stop and write a blocker
report.

---

## 2. Required changes

### C-7A6-1 (Medium) — strict-clean output must say PASS

`check_claims.py` `_render()` currently prints, in strict mode:

```
RESULT: FAIL - {len(report.violations)} unqualified occurrence(s)
```

unconditionally. On a clean ledger the exit code is 0 but the text says FAIL. At G6 the
human-readable `--strict` output is a release artifact.

**Fix:** compute the strict result from `_failed(report, strict)` (or
`report.violations`/`report.findings`) and print `RESULT: PASS` when the run passes, e.g.:

```python
failed = _failed(report, strict)
out.append(
    f"RESULT: {'FAIL' if failed else 'PASS'} - "
    f"{len(report.violations)} unqualified occurrence(s) "
    f"(strict mode ignores the baseline)"
)
```

**Canary:** add `strict_clean` to `scripts/qa/canary_claims.py`. It builds a minimal clean
tree (one VERIFIED claim, empty baseline, literal in README/PLAN with existing evidence)
and asserts:
- `--strict` exits **0**;
- stdout contains `RESULT: PASS`;
- `--strict --json` has `ok: true`.

Keep the existing `strict_detects_baseline` canary (real tree still exits 1).

### C-7A6-2 (Medium) — QAQC probe log must match the run

The QAQC report says `**Probes: final-probe-commands.log (this directory)`; the file is
`probe-commands.log`. The log also records `--strict` as `exit: 0` (actual exit **1**) and
A10 as `lines removed: 0` while reporting stale scopes. A2–A10 say “see earlier run”.

**Fix (QAQC):**
- Rename the file or correct the report reference to `probe-commands.log`; the sign-off
  and header must agree.
- Correct B2 to `exit: 1`.
- Correct A10 to the actual removed-line count (1) and the actual finding count
  (5 stale-scope + 1 unresolved-literal = 6 findings; “5 stale-scope” is fine if stated).
- Either include the full probe transcript or label the file explicitly as a **summary**
  and point to the retained full logs. Do not present a summary as a transcript.

### C-7A6-3 (Minor) — Evidence provenance erratum

- `f6924ff` is a pre-amend commit; `candidate-sha.txt` is `994d629`. The restricted
  code/ledger/CI delta is **empty**; `git diff f6924ff..994d629` changes only evidence
  files (9 files, +11/−10). Document this in `audit/evidence/G1/7A-6/notes.md` (or a new
  erratum file). Do not edit captured logs.
- `diffstat.txt` says 2661 insertions / 23 deletions; the true
  `4bcffeb..994d629` figure is **2691 / 24**. Correct it.
- `env.txt` repeats the `candidate:` line three times; add a note that
  `candidate-sha.txt` is authoritative and the repetition is a capture artifact. Do not
  edit the captured log.

### C-7A6-4 (Minor) — ID 3 literal

ID 3 (“GPU kernel/layer/E2E suites pass”) uses `PYTHONPATH=build`, a command token, not a
claim-specific phrase. Choose one:
1. replace it with a claim-specific phrase (e.g. the specific GPU test-suite command/file
   that would disappear if the claim were removed); or
2. document in the ledger that VERIFIED-row literals are **locators** (the evidence path is
   the proof), and add a removal test that deletes the actual claim line and expects
   failure.

Do not leave a command token labelled “claim-specific.”

---

## 3. Acceptance

- `check_claims.py` default: exit 0, 0 new / 17 baselined / 0 expired / 0 findings.
- `check_claims.py --strict` on the real tree: exit 1, `RESULT: FAIL`.
- `check_claims.py --strict` on the clean canary tree: exit 0, `RESULT: PASS`.
- `check_claims.py --strict --json` on the clean tree: `ok: true`.
- `canary_claims.py`: 11/11 pass (10 existing + `strict_clean`).
- Canary mutation: the new `strict_clean` also fails when the checker is neutered.
- QAQC log corrections are present and internally consistent.
- Evidence erratum present; `diffstat.txt` 2691/24.
- ID 3 literal/rule resolved.
- CPU/GPU suites unchanged (37/18, 12/12).
- No `src/`, tests, packaging, CI, README, or PLAN change.

---

## 4. Evidence

`audit/evidence/G1/7A-6-followup/` with:

```
env.txt  parent-sha.txt  candidate-sha.txt  diffstat.txt
strict-clean.log  canary.log  cpu-suite.log  gpu-suite.log
gate-commands.log  notes.md
```

`red/green` for C-7A6-1: the clean tree prints `RESULT: FAIL` on the parent (red) and
`RESULT: PASS` on the candidate (green), with exit 0 in both cases. Record both.

---

## 5. Stop

After the follow-up commit, stop for QAQC. Do not start 7A-7/7A-8 on this branch. G1
remains unsigned; 7A-8 may start in parallel from `4bcffeb`.
