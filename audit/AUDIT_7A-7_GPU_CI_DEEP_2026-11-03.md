# Independent 7A-7 Audit — GPU CI Scaffold

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-03
**Target:** `wp/7A-7-gpu-ci` @ `8b38e99` + this audit’s evidence erratum
**Work commit:** `955fa04` · **Base:** `a873a9c`
**Coder:** GLM5.3 · **QAQC:** independent session (`qaqc-probes/qaqc-report.md`)
**Scope:** 7A-7 only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS — QF-1 and QF-2 are closed; the scaffold is accepted as queued-not-green.**

The workflow is correct and its guard is genuinely fail-capable. I re-ran the committed
validator (**20/20**), confirmed the bundle copy is byte-identical to the shipped
workflow, reviewed the four guard cases, and verified the API gate state: only the two
existing workflows are registered; `ci-gpu.yml` has never run; the tip’s two push-triggered
checks are green; and the tracking PR #8 is open and names 7A-7 / C-7A1-6.

The package does **not** claim G1 GPU coverage while the runner is absent, and it must not
be counted as a G1 pass. 7F-1 owns runner registration and removal of
`continue-on-error`.

---

## 2. Reproduction

| Check | Result |
|---|---|
| `validate-workflow.py` | **20/20 checks pass**, exit 0 |
| Bundle `workflow.yml` vs `.github/workflows/ci-gpu.yml` | byte-identical |
| Guard: real lane (gfx1150) | 18 passed / 0 skipped → exit 0 |
| Guard: extension missing | pytest exits 0, guard **exit 1** (“no passing test”) |
| Guard: 3 passed + 1 skipped | **exit 1** (“a skip is not a pass”) |
| Guard: nothing collected | **exit 1** (“collected no tests”) |
| Host lane steps from clean clone | configure marker + build + **18 passed / 0 skipped** |
| API workflow list | only `ci-build.yml` and `ci-cpu.yml`; `ci-gpu.yml` not registered |
| API tip `8b38e99` check-runs | `ci-build` success, `ci-cpu` success; no GPU/workflow-file-error check |
| API PR #8 | open/draft; body names 7A-7 and C-7A1-6 under “Still open for G1” |
| Scope | only `.github/workflows/ci-gpu.yml`, evidence, brief; restricted diff empty |
| Merged-package checks | claims checker PASS (0/17/0/0), canaries 12/12, CPU 43/18 |

The brief’s grep pattern does behave correctly on both real lane outputs (green: no
`skipped` substring; no-extension: no `passed` match). The junit guard is still the better
choice for exact counts and robustness, but the record’s original “phantom grep false
positive” rationale was overstated. I corrected it in the notes to describe the actual
reason.

---

## 3. Condition closure

### QF-1 — missing `actions-state.log`: CLOSED

The README table named `actions-state.log`, but the file was never committed. I added
`audit/evidence/G1/7A-7/actions-state.log` with the API capture: remote workflow blob and
size, the two-workflow registry, the tip’s two successful check-runs, the absence of any
GPU workflow run, and the open PR #8 tracking link. Every fact is verified from the
public API; no secrets are included.

### QF-2 — overstated junit-vs-grep rationale: CLOSED

The notes now state the real reason for the junit guard: exact counts and robustness to
prose/report-format changes. The claim that a bare `grep -q skipped` produces a phantom
false positive was removed; both real lane outputs behave correctly under the brief’s
pattern. The deviation itself is endorsed.

No other 7A-7 condition remains. The minor candidate-SHA correction narrative
(`1986d38` → `99d3802` → `8b38e99`; end state correct) needs no action; `candidate-sha.txt`
points at the work commit `955fa04`.

---

## 4. Gate impact

- **7A-7:** accepted as a scaffold; **queued-not-green**, not a G1 pass.
- **7F-1:** register the self-hosted runner and remove `continue-on-error`; then the lane
  becomes required and must report 18 passed / 0 skipped.
- **7A-2..7A-5:** still outstanding (7A-5 owns C-7A1-5 `conftest.py` in the sdist).
- **G1:** unsigned. **7B:** blocked until G1 and the 7A-3 goldens.
- **ROCm cost:** unchanged; 7A-8’s hosted-job cost decision remains a G1 item.

---

## 5. Sign-off

**7A-7 decision: PASS.** The workflow, guard, validation, host execution, and honest gate
state are accepted; QF-1/QF-2 are closed by the evidence erratum.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-03.
