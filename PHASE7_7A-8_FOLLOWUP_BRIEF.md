# 7A-8 Follow-up Brief — Close the Auditor Conditions

**To:** GLM5.3 (coder) and QAQC
**From:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-02
**Branch:** `wp/7A-8-followup`
**Base:** `wp/7A-8-build-entrypoint` @ `cb4655c` (audit commit; work candidate `9c04912`)
**Gate:** 7A-8 follow-up only. G1 remains unsigned; 7B remains blocked.

This closes the conditions in
`audit/AUDIT_7A-8_BUILD_ENTRYPOINT_DEEP_2026-11-02.md` §3. The build fix itself is
accepted; this is CI/merge bookkeeping.

---

## 1. Allowed files

- `.github/workflows/ci-build.yml` (QF-1; one word plus any needed run-log step)
- `audit/evidence/G1/7A-8-followup/**` (new evidence: CI run log/URL, notes)
- `audit/evidence/G1/7A-8/notes.md` (one-line erratum if needed)
- docs

**Do not touch** `CMakeLists.txt`, `README.md`, `tests/**`, `src/`, `setup.py`,
`pyproject.toml`, `MANIFEST.in`, `scripts/qa/**`, the ledger, or 7A-6 evidence. The build
fix is already verified; a README edit here would worsen the QF-2 line shift.

---

## 2. C-7A8-1 (Condition) — make `ci-build.yml` runnable

`ci-build.yml` installs only `numpy`, `setuptools`, `wheel`, `pybind11`, then runs:

```yaml
- name: Run the configure smoke test
  run: python -m pytest tests/test_build_configure.py -v
```

`actions/setup-python` does not ship pytest, so the job fails with
`No module named pytest`.

**Fix:** add `pytest` to the prerequisites install, e.g.:

```yaml
python -m pip install --upgrade pip \
  "numpy>=1.24.0" "setuptools>=64" wheel "pybind11>=2.12" pytest
```

Then **push the follow-up branch and record one green run** of `ci-build.yml` (run URL and
the relevant log excerpt in `audit/evidence/G1/7A-8-followup/`). The acceptance item is
"The CI job reproduces it"; a designed job is not enough.

If the ROCm apt install or package name fails on the hosted runner, record the exact
failure and fix only the CI issue (do not change the build fix). If the full job cannot be
made green on a hosted runner, stop and write a blocker report rather than weakening the
job.

**Also:** keep the local smoke command runnable:
`python -m pytest tests/test_build_configure.py -v` must pass with pytest installed.

---

## 3. C-7A8-2 (Merge checklist, not code on this branch)

At the 7A-8 merge into `vibe/phase7-220201`, the README additions shift the 7A-6 ledger
references. The audit's throw-away merge reproduced:

- `check_claims.py` exits **0** with **9 drift warnings** (0 stale, 0 findings).
- Claims 8/9: `README.md:111` → `130`.
- Claims 10/11/12: `110,111` → `129,130`.
- Claim 21: `104` → `123`.
- ID-3 locator block: `L85–L89` → `L98–L102`.

**At merge time:** refresh the nine README scope references (+19) and the ID-3 prose,
re-run `check_claims.py`, and require **zero drift warnings**. `id3_claim_removed` is
line-independent and survives. This is a G1 merge-checklist item, not a change to this
branch.

---

## 4. Observation — ROCm install cost

`ci-build.yml` installs ROCm from AMD's stable apt repository on every push/PR (multi-GB).
The auditor's G1 ruling is open: accept for now, or narrow the hosted job to the
configure-only check and move the full build to the self-hosted gfx1150 runner
(7A-7/7F-1). Not a 7A-8 condition; record the decision at G1.

---

## 5. Acceptance

- `ci-build.yml` prerequisites include pytest.
- The configure smoke test runs locally with pytest installed.
- One green `ci-build.yml` run is recorded (URL + log excerpt) in the follow-up evidence.
- No build-fix, CMake, README, tests, source, packaging, ledger, or 7A-6 change.
- QF-2 merge checklist recorded for G1 (not executed here unless the owner asks).

---

## 6. Stop

After the CI fix and green run, stop for QAQC/auditor. Do not merge 7A-8 on this branch;
the merge owner applies C-7A8-2 (ledger refresh) at merge time. G1 remains unsigned.
