# Independent 7A-6 Follow-up Audit — C-7A6-1/2/3/4

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-6-followup` @ `330fe70` + auditor evidence erratum
**Content candidate:** `190c9e1ba5d624f70ff362d364ec402dd1a3faad`
**Parent:** `b626c94` (7A-6 audit commit)
**Coder:** GLM5.3 · **QAQC:** independent session
**Scope:** 7A-6 follow-up only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS — C-7A6-1/2/3/4 are closed, and the three QAQC findings QF-1/2/3 are closed by
auditor evidence erratum.**

I reproduced the strict-clean fix, all 12 canaries, the canary mutations, the real-tree
default/strict/JSON behavior, the ID 3 removal canary, the QAQC log corrections, and the
provenance erratum. I also reproduced QF-1 (the committed reproducer crashed at B5 on a
clean clone without an extension), fixed the one-line fallback, and re-ran the reproducer
from a clean clone with no extension: **exit 0**, B5 now prints `18 skipped` instead of
crashing, and B9 reports the true `22 files, 2014/54` follow-up diffstat.

The checker is accepted. No product code, `src/`, tests, packaging, or public document
changed in the follow-up.

---

## 2. Reproduction

Fresh clone of the branch at `330fe70`, no in-tree build for the QF-1 reproducer; GPU
suite run with the repository build artifact.

| Check | Result |
|---|---|
| Default `check_claims.py` | exit 0 — 0 new, 17 baselined, 0 expired, 0 findings, 1 warning (claim 21) |
| `--strict` (real tree) | exit 1 — `RESULT: FAIL - 17 unqualified occurrence(s)` |
| `--strict` (clean tree) | **exit 0 — `RESULT: PASS - 0 unqualified occurrence(s)`** |
| `--strict --json` (clean tree) | `ok: true` |
| `--json` (real tree) | `ok: true`, 30 claims, 17 baselined, 0 findings |
| Canaries | **12/12 pass** |
| Canary mutation — force exit 0 | 9/12 fail |
| Canary mutation — always print FAIL | **`strict_clean` fails** (the C-7A6-1 defect) |
| Canary mutation — checker does nothing | **12/12 fail** |
| CPU lane | 37 passed, 18 deselected |
| GPU lane | 18 passed, 37 deselected |
| `test_cpu_only.py` / `-O` | 12/12 each |
| Baseline | byte-identical to `994d629` |
| Ledger statuses/flags | unchanged; ID 3 rule documented, scope lines refreshed |
| QAQC summary/full transcript | corrections present; full transcript present |
| QF-1 reproducer from clean clone, no extension | **exit 0** (was `TypeError` at B5) |

---

## 3. Condition closure

- **C-7A6-1 (strict-clean):** `_render()` now uses `_failed(report, strict)`; a clean
  `--strict` prints `RESULT: PASS` with exit 0, while the real tree still prints
  `RESULT: FAIL` with exit 1. The `strict_clean` canary covers it.
- **C-7A6-2 (QAQC log):** the summary is labelled as a summary, B2 is exit 1, A10 is
  1 line removed / 5 stale-scope + 1 unresolved-literal, A2–A9 have actual results, the
  dangling `final-probe-commands.log` references are corrected, and the full transcript is
  committed.
- **C-7A6-3 (provenance):** `PROVENANCE-ERRATUM.md` documents `f6924ff`↔`994d629` and the
  empty restricted delta; `diffstat.txt` is 2691/24; the repeated `env.txt` candidate line
  is documented.
- **C-7A6-4 (ID 3):** the VERIFIED-locator rule is documented; ID 3’s literal selects
  exactly the five GPU-suite invocations; the `id3_claim_removed` canary deletes those
  lines and requires `unresolved-literal`.

## 4. QAQC findings QF-1/2/3

| Finding | Disposition |
|---|---|
| **QF-1** — reproducer crashes at B5 on a tree without an extension | **Fixed** in `reproduce-probes.py` (`(out.strip().splitlines() or [""])[-1]`); verified from a clean clone with no extension/PYTHONPATH, exit 0. New transcript: `audit/evidence/G1/7A-6-followup/reproduce-probes-audit.log`. |
| **QF-2** — committed full transcript B9 is stale (`2 files, 141 insertions`) | **Annotated** in the follow-up notes (captured log not edited); the corrected reproducer writes `22 files, 2014/54` at the follow-up tip. |
| **QF-3** — follow-up `env.txt` names pre-amend `bafcd9c`/`88cc19b` with no note | **Annotated** in the same auditor evidence erratum: `candidate-sha.txt` (`190c9e1`) is authoritative; restricted delta empty; same convention as `PROVENANCE-ERRATUM.md`. |

These were applied by the auditor as evidence-only corrections; no checker or product code
changed in the QF pass.

## 5. Gate impact

- **7A-6:** PASS; merge-approved into `vibe/phase7-220201`.
- **7A-8:** in progress independently from `4bcffeb`; no dependency on this follow-up.
- **G1:** unsigned — 7A-2..7A-5, 7A-7, and 7A-8 remain; C-7A1-5/6 carry forward.
- **7B:** blocked until G1 and the 7A-3 goldens.

## 6. Sign-off

**7A-6 follow-up decision: PASS.** Conditions C-7A6-1/2/3/4 and QAQC QF-1/2/3 are closed;
merge approved.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
