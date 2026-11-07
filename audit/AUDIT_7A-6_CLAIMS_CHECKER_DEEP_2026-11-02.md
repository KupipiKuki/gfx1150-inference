# Independent 7A-6 Audit — Claims Checker

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-6-claims-checker` @ `f0a73a18cbfdc661f878d645f0fdae34a4fe1e2c`
**Content candidate:** `994d62922af7ed9f5b9546d787d8c05606cdb8f1`
**Parent:** `4bcffeb35862c3d0b12fa54aac2f2d27bdc9ec60`
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`; Gemini preliminary report reviewed in its §5)
**Scope:** 7A-6 only. **G1 remains unsigned.** 7A-1 and its follow-up are already merged.

---

## 1. Verdict

**PASS WITH CONDITIONS — the checker is substantively correct and all core acceptance
criteria reproduce, but it is not merge-approved until C-7A6-1/2/3/4 land.**

The ledger is now genuinely enforceable. Default mode passes on the seeded baseline,
`--strict` fails on the 17 inventoried sites, the JSON output is correct, all 10 canaries
pass, the canary mutation-test fails exactly 8/10 when the checker is neutered, and the
adversarial line-precision attacks (a second unqualified `qwen2`, a deleted baseline entry,
a qualifier deletion) fail as designed.

Two defects are additional to the QAQC report:

- **`--strict` prints `RESULT: FAIL` even when it exits 0 on a clean ledger.** The exit
  code is correct, but the release-gate text is wrong. At G6 this would produce a
  misleading artifact.
- **The QAQC probe log is internally inconsistent and is not the transcript it claims to
  be.** It records `--strict` as `exit: 0` (the real exit is 1), references a
  `final-probe-commands.log` that does not exist, and says A10 removed 0 lines while the
  probe found stale scopes.

The QAQC report's three hygiene findings (f6924ff provenance, diffstat, env) are confirmed
and should be closed in the same narrow follow-up. The Gemini preliminary report is
directionally right but factually unreliable; the final QAQC report's §5 correction is
accurate and should be treated as the record.

---

## 2. Reproduction

Fresh clone of the branch at `f0a73a1`, fresh out-of-repo CMake build, checker probes in
`audit/evidence/G1/7A-6/audit-probes/`.

| Check | Result |
|---|---|
| Default `check_claims.py` | exit 0 — 0 new, 17 baselined, 0 expired, 0 findings, 1 warning (claim 21) |
| `--strict` | exit 1 — 17 unqualified occurrences |
| `--json` | valid JSON; `ok=true`, 30 claims, 17 baselined violations, 0 findings |
| Canaries | 10/10 pass, exit 0 |
| Canary mutation (force checker exit 0) | exactly 8/10 canaries fail |
| `pytest -m "not gpu"` | 37 passed, 18 deselected |
| `pytest -m gpu` (gfx1150) | 18 passed, 37 deselected |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Baseline | byte-identical to the parent (15 exact entries) |
| Ledger | 30 rows; statuses and flags unchanged vs parent; only literals + scope annotations added |
| Allowed files | `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, `.github/workflows/**`, evidence; no `src/`, tests, packaging, README/PLAN |

Adversarial probes reproduced:

| Probe | Result |
|---|---|
| A2 second unqualified `qwen2` in a baselined path | **fails** — `README.md:115` NEW VIOLATION (not inventoried) |
| A3 delete baseline `10 README.md qwen2` | **fails** — `README.md:109` NEW VIOLATION, 16 baselined |
| A4 wildcard baseline | exit 2 |
| A5 malformed baseline | exit 2 |
| A6 invalid status | exit 1, `invalid-status` |
| A7 duplicate claim ID | exit 2 |
| A9 line inserted at README top | exit 0, exactly 13 drift warnings |
| A10 qualifier bullet deleted | exit 1, 5 stale-scope + 1 unresolved-literal finding |

---

## 3. Findings

### AUD-7A6-1 (Medium) — `--strict` prints FAIL when it passes

`check_claims.py` `_render()` unconditionally appends, in strict mode:

```
RESULT: FAIL - {len(report.violations)} unqualified occurrence(s)
```

On a clean ledger (no violations, no findings) the exit code is **0** but the text says
`RESULT: FAIL`. I reproduced this with a minimal one-VERIFIED-claim tree and an empty
baseline:

```
$ check_claims.py --strict
RESULT: FAIL - 0 unqualified occurrence(s) (strict mode ignores the baseline)
exit: 0
$ check_claims.py --strict --json
{ "ok": true, "violations": [], "findings": [] }   # exit 0
```

At G6 the human-readable `--strict` output is a release artifact; a `FAIL` line with a
zero exit will mislead the release checklist or any reader.

**Required:** compute the strict result from `_failed(report, strict)` and print
`RESULT: PASS` when there are no violations/findings. Add a `strict_clean` canary that
builds a clean tree and asserts both exit 0 and `RESULT: PASS`.

### AUD-7A6-2 (Medium) — QAQC probe log is inconsistent and not a full transcript

`audit/evidence/G1/7A-6/qaqc-probes/qaqc-report.md` says `**Probes:**
final-probe-commands.log (this directory)`, but the directory contains only
`probe-commands.log`. That file is a summary, not a transcript: A2–A10 say "see earlier
run", and two entries are wrong:

- **B2 strict mode** is recorded as `exit: 0`; the actual checker returns **exit 1** on
  the current tree (reproduced independently). The QAQC report itself says exit 1, so the
  log contradicts the report.
- **A10** says `lines removed: 0` while reporting 5 stale scopes; a mutation that removed
  no lines cannot produce stale scopes. My run removed the qualifier bullet (1 line) and
  produced 5 stale + 1 unresolved finding.
- The report/sign-off names `final-probe-commands.log`; the file is `probe-commands.log`.

**Required:** rename the file or correct the reference, fix the B2/A10 entries, and either
include the full probe transcript or label the file explicitly as a summary and point to
the retained full logs. The QAQC verdict is substantively right; the artifact must be
accurate.

### AUD-7A6-3 (Minor) — Evidence provenance/diffstat/env (QAQC findings 1–3 confirmed)

- `f6924ff` is a pre-amend commit; `candidate-sha.txt` says `994d629`. I verified
  `git diff f6924ff..994d629` changes only evidence files (9 files, +11/−10) and that the
  restricted code/ledger/CI delta is **empty**. The evidence is valid, but the bundle never
  documents the relationship.
- `diffstat.txt` says 2661 insertions / 23 deletions; the true `4bcffeb..994d629` figure
  is **2691 / 24**.
- `env.txt` repeats the `candidate:` line three times with different spacing.

**Required:** add an erratum to `notes.md` (do not edit captured logs) documenting the
`f6924ff`↔`994d629` equivalence and the zero substantive delta; correct `diffstat.txt` to
2691/24; note that `candidate-sha.txt` is authoritative for the repeated env lines.

### AUD-7A6-4 (Minor) — ID 3’s replacement literal is still not claim-specific

The four original generic literals were replaced, but ID 3 (“GPU kernel/layer/E2E suites
pass”) now uses `PYTHONPATH=build` — a command token from the README test block, not a
phrase that disappears when the claim does. It survives removal of the claim and is not in
`GENERIC_LITERALS`, so the anti-generic guard cannot catch it. ID 1 (`sdist`) and ID 4
(`Q4_0`/`Q4_K`/`Q8_0`) are broad but are evidence-backed locators; ID 3 is the weakest.

**Required (choose one):** replace ID 3’s literal with a claim-specific phrase (e.g. the
specific GPU test-suite command/file), or document in the ledger that VERIFIED-row
literals are locators and the evidence path is the proof, and add a negative test that
removes the actual claim line and expects failure. Do not silently leave a command token
labelled “claim-specific.”

### AUD-7A6-5 (Observation) — design boundary is acceptable

The checker enforces geometry (occurrence inventory, line drift, baseline exactness), not
in-place rewording at a qualified site. That is disclosed by the coder and QAQC. G6 should
cite 7F-5 (ledger-vs-docs diff) as the wording backstop. No action for 7A-6.

---

## 4. Conditions and gate impact

| ID | Condition | Owner | Target | Blocks |
|---|---|---|---|---|
| **C-7A6-1** | Fix the strict clean-result text; add a `strict_clean` canary asserting exit 0 + `RESULT: PASS`. | 7A-6 coder | before 7A-6 merge | 7A-6 merge / G1 |
| **C-7A6-2** | Correct the QAQC probe log (name, B2 exit, A10 removal, full transcript or summary label). | QAQC | before 7A-6 merge | 7A-6 merge / G1 |
| **C-7A6-3** | Add the `f6924ff`↔`994d629` erratum, correct `diffstat.txt` to 2691/24, clarify env candidate lines. | 7A-6 coder | before 7A-6 merge | 7A-6 merge / G1 |
| **C-7A6-4** | Fix ID 3’s literal or document the VERIFIED-locator rule with a removal test. | 7A-6 coder | before 7A-6 merge | 7A-6 merge / G1 |
| **C-7A6-5** | Commit the QAQC artifacts (done in this audit commit). | auditor | done | — |
| **C-7A1-5** | `conftest.py` still absent from sdist; add `recursive-include tests *.py` and assert installed-tree collection. | 7A-5 | G1 | G1 |
| **C-7A1-6** | GPU CI must fail on a skip; 18 passed / 0 skipped on gfx1150. | 7A-7/G5/G6 | G5/G6 | G5/G6 |

**Gate impact:**
- 7A-6 is accepted in substance; a narrow follow-up closes the conditions.
- 7A-8 may start in parallel from `4bcffeb` (it does not depend on 7A-6).
- **G1 remains unsigned**: 7A-2..7A-5, 7A-7, 7A-8 and these conditions are outstanding.
- **7B remains blocked** until G1 and the 7A-3 goldens.

---

## 5. Sign-off

**7A-6 decision: PASS WITH CONDITIONS.** The checker does the job; the strict-mode output
and the QAQC evidence log need correction before merge, and the two minor record/literal
items should be closed in the same follow-up. No runtime or scientific surface is involved.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
