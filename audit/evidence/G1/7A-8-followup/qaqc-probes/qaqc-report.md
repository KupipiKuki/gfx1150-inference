# QAQC Report — Work package 7A-8 follow-up (close C-7A8-1; record C-7A8-2)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-8_FOLLOWUP_BRIEF.md`)
**Date:** 2026-11-02
**Tree tested:** tip `86cdd323433aa72d5f70ec03882b9795dde4709a` on `wp/7A-8-followup`
(fix commit `683a0f70`; prep/brief `33fc5f98`; base `cb4655c`). Branch pushed; CI state
verified against the **public GitHub API**, not just the recorded excerpt.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS.** C-7A8-1 is closed and — stronger than the recorded evidence — the fix is
demonstrated by **three independently API-verified green/fail states**: the RED run
(the prep commit's job failing at the smoke test), the GREEN run (the fix commit's job,
every step green), and the branch tip (both workflows green). The fix is minimal and
correct, the pipefail addition avoids a real silent-failure trap, the scope is exactly
the brief's, and the two flagged items (raw-log unavailability, the 7A-6-surfaces
correction) are handled honestly. No conditions remain against this package.

## 1. C-7A8-1 — closed and independently verified

| Verification | Result |
|---|---|
| The fix in `ci-build.yml` | ✅ `pytest` in the prerequisites step (step 2); configure tees to `configure.log` under `set -o pipefail` (step 5); a `if: always()` step publishes the discovery marker / `Configuring done` / `Could not find` lines to `$GITHUB_STEP_SUMMARY` (step 6). Valid YAML, 11 steps |
| **RED run** 41544981963 | ✅ **verified against the public API**: head `33fc5f98…`, branch `wp/7A-8-followup`, conclusion **failure** — matches `ci-run.log` exactly |
| **GREEN run** 41545742018 | ✅ **verified against the public API**: head `683a0f70…` (the fix commit), conclusion **success** |
| **Branch tip `86cdd32`** | ✅ **verified via the API check-runs**: *Clean-clone documented build (G0 C-1)* **success** and *CPU Parser, Tokenizer, Sampler & Packaging Suite* **success** — "tip green on both workflows" confirmed |
| `capture-run.py` regenerates `ci-run.log` | ✅ re-ran it for both runs: **byte-for-byte identical** to the committed log (modulo its 3 header lines) |
| Local repro of QF-1 | ✅ my own: fresh venv with the job's exact pre-fix prerequisites → `No module named pytest`, exit 1; add pytest → **3 passed** — the same failure the hosted runner hit, reproduced locally |
| The failure was confined to the smoke test | ✅ per the step tables, configure/build/ROCm-install were green in the RED run too; steps 10–11 skipped after the failure |
| Lanes on the tip | ✅ 43 passed / 18 deselected; `-m gpu` 18 passed; `test_cpu_only.py` 12/12 both modes |

The **pipefail reasoning is correct** and worth keeping: GitHub's default `run` step is
`bash -e {0}` — no pipefail — so `cmake … | tee configure.log` would report success even
with a failed configure. The explicit `set -o pipefail` makes the tee safe, and the
summary step makes a green run self-evidencing (the `pybind11 CMake package:` line is
the interpreter-discovery proof). Endorsed.

On the raw-log limitation: confirmed. The logs endpoint requires authentication (the
repo is public, but run-log downloads do not work unauthenticated), no token exists in
this environment, and the API step table + annotations + the regenerable
`capture-run.py` are the right substitute. My API verification goes one step further
and confirms the recorded conclusions are GitHub's own, not transcribed by hand.

## 2. C-7A8-2 — recorded (not executed), and the table reconciles

The merge checklist is properly recorded with the auditor's shift table and the
caution to recompute at merge time. **I cross-checked the arithmetic and it reconciles
exactly**: on *this branch* the shifted sites sit one line lower than the table
(qwen2 bullets at 128/129, claim 21 at 122, `PYTHONPATH=build` at 97–101) because this
branch does not carry `efe34fc`'s +1 README line (the project-tree entry for the 7A-6
follow-up brief, which lives on the 7A-6 side); the table's targets (129/130, 123,
98–102) correctly describe the **actual merge**, which includes both changes. The
caution remains sound practice — the merge owner should still recompute — but the
table's numbers are consistent, not stale. `id3_claim_removed` is line-independent and
survives, as stated.

## 3. Scope and record hygiene

- **Scope**: exactly the brief's allowed set — `ci-build.yml`, the follow-up evidence
  bundle, and the explicitly-allowed one-line erratum in `audit/evidence/G1/7A-8/notes.md`
  (a pointer row: "ci-build.yml on the hosted runner | green — run 41545742018…").
  `CMakeLists.txt`, `README.md`, `tests/**`, `src/`, `setup.py`, `pyproject.toml`,
  `MANIFEST.in`, the ledger and baseline: **empty diff** — as the brief demands
  ("a README edit here would worsen the QF-2 line shift").
- **The 86cdd32 correction** is accurate and useful: the notes now state explicitly
  that `scripts/qa/**` and the 7A-6 evidence do not exist on this branch (7A-8 forks
  from `4bcffeb`, parallel to 7A-6) while the ledger and baseline do exist (pre-7A-6
  state) — so "untouched" is by construction for the former and verified for the
  latter. A reader will no longer assume the claims checker was available here.
- **Provenance**: `candidate-sha.txt`/`parent-sha.txt` consistent; `env.txt` clean.

## 4. Observations (no action required on this branch)

1. **The ROCm-cost percentages are approximate.** Strict step/wall ratios give 86.4 %
   (RED) and 81.2 % (GREEN) for the *Install the ROCm development packages* step alone
   — the notes state "83–87 %". The substance (ROCm dominates; everything the
   acceptance is about costs under a minute) is unambiguous, and the recommendation
   (narrow the hosted job to configure-only, move the build to the self-hosted
   runner) is properly left to the auditor's G1 ruling.
2. **The Node.js 20 deprecation annotation** on both runs (checkout@v4 /
   setup-python@v5) is advisory and honestly recorded; bumping the action versions
   belongs with the next CI edit, as noted.

## 5. Disposition

**The 7A-8 follow-up passes QAQC; C-7A8-1 is closed** — the "CI reproduces it"
acceptance is now demonstrated with an API-verifiable green run (and a green tip on
both workflows). C-7A8-2 is properly parked as the G1 merge checklist. With this, the
7A-8 line (work + follow-up) is **fully green and recommended to the auditor for
acceptance**. G1 remains unsigned (7A-2…7A-5 and 7A-7 outstanding); the auditor's open
G1 items from this line: the ROCm-cost ruling and the QF-2 merge-checklist execution.

**QAQC sign-off:** 2026-11-02. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-78fu/`.
