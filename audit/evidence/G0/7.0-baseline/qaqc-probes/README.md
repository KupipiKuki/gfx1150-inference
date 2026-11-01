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

_(to be filled by QAQC)_
