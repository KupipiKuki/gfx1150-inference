"""Shared pytest fixtures and collection policy for the gfx1150-inference test suite.

Phase 7A-1 (audit AUD-2 / QAQC-2). Two invariants are enforced here:

1. **Collection never imports the HIP extension.** Every test module must import
   cleanly on a CPU-only host, so ``pytest -m "not gpu"`` collects and runs the
   CPU suite on a machine with no built ``matmul_module``. Before this package the
   GPU modules imported the extension at module scope and a clean clone exited 2
   with four collection errors.
2. **The ``gpu`` lane is all-or-nothing.** Tests marked ``gpu`` are *skipped*
   with an actionable reason when the extension is not importable, never failed
   and never silently passed.

The extension itself is exposed to test bodies through the session-scoped
``matmul_module`` fixture; GPU test functions request it by name, and script-mode
callers (``python3 tests/test_layer.py``) import it directly.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
_BUILD_DIR = os.path.join(_ROOT_DIR, "build")

# Make the pure-Python package modules importable from the tests, and the
# compiled HIP extension importable from a default in-tree ``build/`` directory.
for _p in (_SRC_DIR, _BUILD_DIR):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def _extension_is_available() -> bool:
    """Return True when the compiled HIP extension can be located.

    Uses ``find_spec`` so that a *broken* extension (present but unimportable)
    is still reported as available here and is handled by the fixture's
    ``importorskip`` instead, which turns an ``ImportError`` into a skip.
    """
    try:
        return importlib.util.find_spec("matmul_module") is not None
    except (ImportError, ValueError):
        return False


@pytest.fixture(scope="session")
def matmul_module():
    """The compiled HIP extension module (``matmul_module``).

    Skips — never fails — the requesting test when the extension has not been
    built, so that a CPU-only host reports skips instead of collection errors.
    """
    return pytest.importorskip("matmul_module")


def pytest_collection_modifyitems(config, items):
    """Skip the whole ``gpu`` lane when the HIP extension is unavailable.

    A GPU-marked test that cannot run must be *visible as skipped*, per the
    Phase 7 handoff: "a skip is visible in the report, never a silent pass".
    """
    if _extension_is_available():
        return
    skip_gpu = pytest.mark.skip(
        reason=(
            "the compiled HIP extension 'matmul_module' is not importable; the 'gpu' "
            "lane is skipped. Build it with: cmake -B build -DCMAKE_BUILD_TYPE=Release "
            "&& cmake --build build -j"
        )
    )
    for item in items:
        if "gpu" in item.keywords:
            item.add_marker(skip_gpu)
