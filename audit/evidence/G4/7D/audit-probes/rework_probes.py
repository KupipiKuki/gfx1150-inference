#!/usr/bin/env python3
"""Auditor red probes for the two 7D G4 rework fixes.

Run from the repo root:
    PYTHONPATH=src:build:tests python3 audit/evidence/G4/7D/audit-probes/rework_probes.py

Exit 0 means both fixes are present; exit 1 means at least one is still missing.
"""

from __future__ import annotations

import os
import sys
import tempfile
import warnings

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "tests"))

from gguf_parser import GGUFValueType, write_synthetic_gguf  # noqa: E402
from weight_loader import WeightStreamer  # noqa: E402


def probe_negative_block_count() -> bool:
    print("== probe 1: negative block_count with zero blk tensors ==")
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "negative.gguf")
        with open(path, "wb") as fh:
            write_synthetic_gguf(
                fh,
                {
                    "general.architecture": (GGUFValueType.STRING, "llama"),
                    "llama.block_count": (GGUFValueType.INT32, -1),
                },
                [],
            )
        try:
            ws = WeightStreamer(path)
        except ValueError as exc:
            print(f"PASS: rejected with ValueError: {exc}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: wrong exception {type(exc).__name__}: {exc}")
            return False
        print(f"FAIL: accepted with num_layers={ws.num_layers} (expected ValueError)")
        ws.close()
        return False


def probe_engine_no_source() -> bool:
    print("== probe 2: engine AUTO with no readable budget source ==")
    import inference
    from memory_budget import (
        BudgetSources,
        NoBudgetFallbackWarning,
        ResidencyPolicy,
    )
    from test_memory_residency import _engine_model

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "engine.gguf")
        _engine_model(path)
        original = inference.read_budget_sources
        inference.read_budget_sources = lambda: BudgetSources()
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                engine = inference.LlamaInferenceEngine(
                    path, max_seq_len=8, offload_kv_to_cpu=True, residency="auto"
                )
                decision = engine.residency_decision
                warned = any(
                    issubclass(w.category, NoBudgetFallbackWarning) for w in caught
                )
                print(f"effective={decision.effective} weight_budget={decision.weight_budget}")
                print(f"reason={decision.reason}")
                print(f"warnings={[type(w.message).__name__ for w in caught]}")
                engine.close()
        finally:
            inference.read_budget_sources = original
        ok = (
            warned
            and decision.effective == ResidencyPolicy.STREAM
            and decision.weight_budget is None
        )
        if ok:
            print("PASS: NoBudgetFallbackWarning, STREAM, weight_budget=None")
            return True
        print("FAIL: expected NoBudgetFallbackWarning + STREAM + weight_budget=None")
        return False


def main() -> int:
    results = [probe_negative_block_count(), probe_engine_no_source()]
    print()
    if all(results):
        print("RESULT: PASS - both rework fixes present")
        return 0
    print("RESULT: FAIL - at least one rework fix is missing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
