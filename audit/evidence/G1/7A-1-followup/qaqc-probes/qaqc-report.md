# QAQC Report — Work package 7A-1 follow-up (close auditor conditions C-7A1-1/2/3)

**Role:** QAQC (independent session, per handoff §1 and follow-up brief §5)
**Date:** 2026-11-02
**Tree tested:** candidate `ea8e84a1e708ee114ae611f2b257b81eaa57c12a` via a fresh
`git clone` to `/tmp/opencode/qaqc-7a1fu/clone` (no `build/`, `PYTHONPATH` unset for the
no-extension probes). Branch tip `2af8369` verified identical to the candidate for
`tests/**` and `pyproject.toml`. Base `408fcab`; parent `4e87e12`.
**Probes:** `probe-commands.log` (this directory) — full transcript with exit codes.

---

## Verdict

**PASS.** All three auditor conditions are closed and independently verified; every
acceptance criterion in the follow-up brief (§3) reproduces exactly; both canaries fail
the strengthened meta-tests and the suite returns to green after removal; and QAQC's
additional adversarial probes — the two rejection paths the committed canary did not
exercise, a nested-**assert** canary, and eight direct drive-tests of the lane machinery —
all pass. The diff is exactly the brief's allowed file set. No stop condition triggered.

## Condition closure

| Condition | Brief requirement | QAQC verification | Status |
|---|---|---|---|
| **C-7A1-1** | Exact lane check: `EXPECTED_LANES` membership, exact marker match, no cpu-lane hard dependency on the extension | Meta-test passes by name (1 item, exit 0). The brief's canary (`cpu`-marked module requesting `matmul_module`) is **rejected** — exit 1 — and the suite is green (37 passed) after removal. QAQC additionally fired the two rejection paths the committed canary did not reach — *"pytestmark is 'cpu', expected 'gpu'"* (wrong marker for a classified module) and *"uses the matmul_module extension but is in the 'cpu' lane"* (classified cpu module requesting the fixture) — with the contract file restored byte-for-byte. Eight direct drive-tests of `_module_lane`/`_uses_matmul_module` all pass (module-scope vs function-scope vs `if`-guarded marks; conflicting marks; fixture request = hard; unguarded body import = hard; guarded `except ImportError` import = optional; `try/finally` without handler = still hard). | **CLOSED** |
| **C-7A1-2** | Nested raises/asserts must not satisfy the contract | The brief's canary (only `raise` inside a nested, never-called helper) is **rejected** — exit 1 — with the exact expected message. QAQC's extra canary (only **assert** inside a nested helper) is **also rejected**, confirming the pruning covers all four failure mechanisms, not just `raise`. All 7 parametrized items pass on the real suite. | **CLOSED** |
| **C-7A1-3** | Record corrections QF-1/QF-2/QF-3 in the 7A-1 notes/coder-report; no captured log edited | **QF-1** re-verified at this commit: sdist contains `tests/test_harness_contract.py`, does **not** contain `tests/conftest.py` — the corrected record is accurate (and the C-7A1-5 → 7A-5 `MANIFEST.in` fix stands). **QF-2** wording now "a content commit plus follow-up commits". **QF-3** independently recounted by AST against `2659e6c`: **13 bool-returners; 4 with asserts; 9 with no failure mechanism; 1 tuple-returner** — exactly matching the corrected record, and correcting an arithmetic error in QAQC's own 7A-1 report ("5 with asserts"; 5+9≠13). A dated erratum has been appended to `7A-1-pytest-harness/qaqc-probes/qaqc-report.md`. Captured logs were not edited (verified: the corrections live only in `notes.md`/`coder-report.md`). | **CLOSED** |

## Acceptance criteria (brief §3) — all reproduced

| Criterion | Claimed | QAQC result |
|---|---|---|
| `pytest -m "not gpu"` | 37 passed, 18 deselected | ✅ exact, exit 0 |
| `pytest -m gpu` on gfx1150 | 18 passed, 37 deselected | ✅ exact (G0 baseline `.so` per env.txt), exit 0 |
| `pytest -m gpu` without the extension | 18 skipped, exit 0 | ✅ exact (clean clone, `PYTHONPATH` unset), exit 0 |
| `python tests/test_cpu_only.py` and `-O` | 12/12 | ✅ 12/12 both, exit 0 |
| C-7A1-1 canary fails the updated meta-test | exit 1 → removed → green | ✅ reproduced: exit 1, then 37 passed, exit 0 |
| C-7A1-2 canary fails the updated meta-test | exit 1 → removed → green | ✅ reproduced |
| No `src/`, `pyproject.toml`, build, packaging, CI, README, ledger, `CMakeLists.txt` change | empty diff | ✅ verified — only `tests/test_harness_contract.py` + the two 7A-1 evidence markdowns + this bundle |
| Scientific assertions and tolerances unchanged | unchanged | ✅ the five GPU test files and `test_cpu_only.py` have an **empty** diff; tolerance literals per file identical (`1e-2`, `1e-3`, `1e-5`, `2e-3`, `5e-3`, `2e-2`, `5e-2`) |
| CPU lane count unchanged (no new meta-test items) | 37 | ✅ 37 passed, 37 collected under `-m cpu` — the lane test replaced the old one 1-for-1 |

## Findings

None against the follow-up package. Three items recorded for the auditor:

1. **Confirmed — the auditor's dangling evidence (flagged by the coder, verified here).**
   `audit/evidence/G1/7A-1-pytest-harness/audit-probes/probe-commands.log` is referenced
   by both `AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md` and the audit-probes README,
   but it is **not committed** — `.gitignore`'s global `*.log` excluded it and, unlike the
   sibling `qaqc-probes/*.log`, it was never force-added (`git status` shows it as
   ignored, `!!`). It exists only in the working tree. The coder correctly did not touch
   it (outside the follow-up's allowed set); **the auditor should `git add -f` it** so
   the audit's P-AUD-1/P-AUD-2 transcript is actually part of the record.
2. **Forward flag (restating notes §6.4).** `EXPECTED_LANES` deliberately forces every
   new test module to be classified. 7A-3 (goldens) and 7A-4 (fuzz) will add test files
   and **must** add their `EXPECTED_LANES` entries or the CPU lane fails. Prominently
   documented already; repeated here so it is on the G1 checklist.
3. **QAQC erratum (own record).** QAQC's 7A-1 report stated "5 of the 13 also had
   asserts"; the correct figure is **4**. Corrected with a dated erratum in
   `7A-1-pytest-harness/qaqc-probes/qaqc-report.md`; the coder's C-7A1-3 record
   correction is the accurate one.

## QAQC checklist (handoff §7.1)

- Candidate SHA frozen; tree clean — ✅ (clean clone; no force-push; linear commits).
- Diff limited to allowed files — ✅ (3 files, verified per-path).
- Every claim has a command and artifact — ✅ (bundle complete per brief §4: env,
  SHAs, diffstat, cpu-suite, gpu-suite, gate-commands, both canary logs, notes,
  coder-report; `red/green` per brief §4 = the canary pairs, recorded against a real
  worktree of the old code at `408fcab`).
- CPU suite normal and `-O` — ✅ 12/12 both.
- GPU lane on gfx1150 — ✅ 18 passed, 0 skipped; without extension: 18 skipped, 0 passed.
- No test deleted, skipped, or weakened — ✅ (meta-tests strictly stronger; counts
  unchanged 37/18/55; scientific files untouched).
- No new runtime dependency — ✅.
- Docs/ledger — ✅ untouched.
- Rollback — ✅ plausible (one test file + two evidence markdowns).
- Commit messages reference the package — ✅ (`G1/7A-1 follow-up` prefix).

## Disposition

The **7A-1 follow-up passes QAQC**; conditions C-7A1-1/2/3 are closed. 7A-1 plus this
follow-up are recommended to the auditor for acceptance. Per the brief: 7A-6 continues on
`wp/7A-6-claims-checker`; 7A-7/7A-8 may be branched from `408fcab` when authorized;
**G1 remains unsigned** (7A-2..7A-5 outstanding), and 7B remains blocked.

**QAQC sign-off:** 2026-11-02. Probe transcript: `probe-commands.log` (this directory).
Clone and scratch retained at `/tmp/opencode/qaqc-7a1fu/` for inspection.
