# Auditor probe — sdist lane red on `baa3e87` (G6 blocker)

**Date:** 2026-11-08
**Candidate:** `wp/7F-evidence-release` @ `baa3e87`
**CI:** CPU-Only Verification & Regression CI run `42549525288`, job
`128941746885` (Sdist Install), step
**"Run the shipped CPU lane in the extracted sdist tree"** — failure.

## Finding

`tests/test_bench_gate.py` is a CPU-lane test that imports
`scripts/bench/aggregate.py`:

```python
_BENCH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "bench"))
...
from aggregate import (...)
```

`MANIFEST.in` ships `CMakeLists.txt`, `LICENSE`, `README.md`, `src/kernels`,
`src/python_bindings`, `tests/*.py`, and `tests/fixtures/*` — it does **not**
ship `scripts/`.

## Reproduction

```
python setup.py sdist --dist-dir /tmp/opencode/dist7f
tar -tzf /tmp/opencode/dist7f/*.tar.gz | grep scripts/      # nothing
# extract, then:
python -m pytest -m "not gpu and not slow" -q
```

```
ERROR collecting tests/test_bench_gate.py
ModuleNotFoundError: No module named 'aggregate'
```

## Fix verified

Add to `MANIFEST.in`:

```
recursive-include scripts/bench *.py *.json
```

Rebuild and run the same sdist lane:

```
521 passed, 49 deselected
```

The CI step is correct to fail; the package is missing a directory its own
shipped tests import.

## Required remediation

1. Ship `scripts/bench` (or move the pure aggregation/gate module into the
   installed package and import it from there).
2. Rebuild the sdist and run the exact CI lane; confirm green.
3. Add a packaging assertion that every module imported by a shipped test is
   present in the sdist (the current "every tests/*.py ships" guard is
   necessary but not sufficient).
