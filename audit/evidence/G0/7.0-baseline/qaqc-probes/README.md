# QAQC probes — G0

**Reserved for the QAQC reviewer.**

The G0 package was executed and signed by the role that owns gate decisions, so it is
**self-tested**, not independently tested (handoff §1, independence rule). The QAQC must
reproduce the gate from a clean checkout and place its probes here.

## Required re-runs

Per the handoff §1, QAQC must at minimum re-run from a clean clone and write new probes.
For G0 the minimum set is:

1. `python3 tests/test_cpu_only.py` — expect 12/12
2. `python3 -O tests/test_cpu_only.py` — expect 12/12
3. All five GPU suites — expect exit 0 each:
   - `python3 tests/test_matmul.py`
   - `python3 tests/test_gguf_and_q4.py`
   - `python3 tests/test_layer.py`
   - `python3 tests/test_full_model.py`
   - `python3 tests/test_phase5_scale.py`
4. `python3 setup.py sdist` then a **full** clean-venv install
   (`pip install --no-build-isolation dist/*.tar.gz`) — expect all 7 modules to import and
   `gfx1150-infer --help` to work
5. `GFX1150_SKIP_CMAKE=1` clean-venv install — expect `gguf_parser`, `tokenizer`, and
   `weight_loader` to import, and `kv_cache` / `layer` / `inference` to raise the
   actionable `ImportError`
6. The claims ledger review — spot-check that each `VERIFIED` row's evidence path exists
   and that each `UNVERIFIED` / `NOT YET` row's literal still resolves in a public document

## Suggested independent probes

- Verify the build defect independently: run the README's documented
  `cmake -S . -B <fresh-dir> -DCMAKE_BUILD_TYPE=Release` and confirm it fails at
  `CMakeLists.txt:17` with the pybind11 error (condition C-1).
- Confirm the CPU-only install surface: import each of the six `src/*.py` modules
  individually in the `GFX1150_SKIP_CMAKE=1` venv and record which three import and
  which three raise.
- Spot-check ledger qualification flags against the live prose — in particular IDs 8–12,
  whose flags were corrected at G0, and ID 13 (the `983` literal appears unqualified at
  `IMPLEMENTATION_PLAN.md` L209 and qualified at L266).
- Check that the measured G0 performance figures in `gpu-suite.log` match the reference
  values in `baseline-report.md`.
- Confirm the G0 package contains no source, test, workflow, or packaging change:
  `git diff --stat <parent>..<candidate> -- src/ tests/ .github/ setup.py pyproject.toml CMakeLists.txt MANIFEST.in`
  must be empty.

## Result

**Executed 2026-11-01 — PASS WITH CONDITIONS.** All required re-runs reproduce from a clean
clone at the candidate `04e47dc`: CPU suite 12/12 (normal and `-O`), pytest 30 passed,
all five GPU suites exit 0, the README's `cmake -B build` command fails exactly as C-1
records, the full clean-venv sdist install succeeds with all 7 modules and a working CLI,
the CPU-only install exposes exactly 3 importable modules with 3 actionable ImportErrors,
and the claims ledger's literals and evidence paths all verify. See `qaqc-report.md`.

Conditions raised by QAQC (details in `qaqc-report.md`):

- **QAQC-1 (before 7A-1 merges):** correct the corrupted parent SHA in
  `baseline-report.md` / `notes.md` / `diffstat.txt` (`…db99…` → `…db29…`), resolve the
  contradictory sdist sha256 records, fix the notes' commit-chain diagram, the
  "nine rows/ten IDs" list, and the "two commits" wording — a documentation-only commit
  inside the 7.0 allowed file set. **Status: landed — the erratum commit that added these
  probes applies it (see the report's Erratum section); pending auditor acceptance.**
- **QAQC-2 (7A-1, G1):** the G0 pytest record relied on the untracked in-tree
  `build/matmul_module.so`; a clean clone fails collection without it. The harness must
  collect without a pre-built extension.
- **QAQC-3 (7F-3, G6):** throughput figures vary run-to-run on the same host (matmul
  0.89/1.02/1.12 TFLOPS; E2E 818.6/849.3/852.0 tok/s); correctness is stable. Confirms
  C-2's disposition: delete or re-record with a median/p95 harness, baseline neither.

G0's status is upgraded per handoff §1 from *self-tested* to **self-tested, independently
re-run**. QAQC-1's erratum landed in the same commit as these probes (pending auditor
acceptance); 7A-1 / 7A-6 / 7A-7 may then proceed; 7B remains gated by G1.

