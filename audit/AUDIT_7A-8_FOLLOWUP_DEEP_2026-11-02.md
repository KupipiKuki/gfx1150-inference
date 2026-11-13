# Independent 7A-8 Follow-up Audit — C-7A8-1 / C-7A8-2

**Auditor:** DeepSeek V4.1 Flash (independent of the coder and QAQC)
**Date:** 2026-11-02
**Target:** `wp/7A-8-followup` @ `86cdd32`
**Fix commit:** `683a0f70` · **Evidence commit:** `b69b9f4`
**Base:** `cb4655c` (7A-8 audit commit; work candidate `9c04912`)
**Coder:** GLM5.3 · **QAQC:** independent session
**Scope:** 7A-8 follow-up only. **G1 remains unsigned.**

---

## 1. Verdict

**PASS — C-7A8-1 is closed; C-7A8-2 is recorded and will be executed at merge.**

I verified the CI evidence through GitHub's public API, not just the committed excerpt:

- **RED run 41544981963** (head `33fc5f98`, no pytest): conclusion **failure**; the
  failing step is *Run the configure smoke test*; build/configure/ROCm steps were green.
- **GREEN run 41545742018** (head `683a0f7`, pytest added): conclusion **success**, every
  step green including configure, build, smoke test, sdist, and full sdist install.
- **Tip `86cdd32`:** both *Clean-clone documented build (G0 C-1)* and *CPU Parser,
  Tokenizer, Sampler & Packaging Suite* checks are **success**.

The workflow change is minimal and correctly scoped: `pytest` added to the prerequisites,
`set -o pipefail` around the tee'd configure, and an `if: always()` summary step that
publishes the pybind11 discovery line. The pipefail detail is a real silent-failure
prevention, not decoration. No build-fix, CMake, README, test, source, packaging, ledger,
or 7A-6 change.

---

## 2. Reproduction

| Check | Result |
|---|---|
| Public API run 41545742018 | `conclusion: success`, head `683a0f7` |
| Public API run 41544981963 | `conclusion: failure`, failing step 9 smoke test |
| Public API check-runs for `86cdd32` | both workflows `success` |
| Job steps (GREEN) | prerequisites, ROCm, configure, summary, build, smoke test, sdist, install: all success |
| Job steps (RED) | configure/build green; smoke test failure; sdist steps skipped |
| `ci-build.yml` prerequisites | includes `pytest` |
| Configure step | `set -o pipefail`; `cmake ... 2>&1 | tee configure.log` |
| Summary step | `if: always()`; publishes `pybind11 CMake package` / `Configuring done` / `Could not find` |
| Local smoke test | `pytest tests/test_build_configure.py` → 3 passed (QAQC + coder) |
| Scope | only `ci-build.yml`, follow-up evidence, one-line 7A-8 notes erratum |
| QF-2 table | recorded; merge-time recompute required |
| ROCm cost | RED 6:46 / GREEN 4:49 ROCm install; 83–87% of job; G1 ruling open |

The raw-run-log limitation is legitimate: the logs endpoint needs an API token, and the
public API step table + annotations + `capture-run.py` are an honest substitute. The
recorded conclusions match GitHub's own API exactly.

---

## 3. Conditions and gate impact

- **C-7A8-1:** closed. The CI reproduces the fix on a clean runner, with a green run and
  a green branch tip.
- **C-7A8-2:** recorded. At merge, refresh the 7A-6 ledger's README scope references
  (+19: 110/111 → 129/130, 104 → 123, ID-3 L85–L89 → L98–L102), re-run
  `check_claims.py`, and require zero drift warnings. The auditor will perform this in
  the merge commit.
- **ROCm cost:** open G1 decision. The acceptance-critical steps cost under a minute; the
  ROCm install dominates. Accept for now, or narrow the hosted job to configure-only and
  move the full build/GPU tests to the self-hosted runner.
- **7A-8:** PASS; merge-approved after the QF-2 refresh.
- **G1:** still unsigned (7A-2..7A-5, 7A-7 outstanding). **7B:** blocked.

---

## 4. Sign-off

**7A-8 follow-up decision: PASS.** C-7A8-1 is closed with API-verifiable evidence; C-7A8-2
is executed at merge.

**Sign-off:** DeepSeek V4.1 Flash, 2026-11-02.
