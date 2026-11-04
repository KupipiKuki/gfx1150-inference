"""Golden quantized blocks on the GPU (Phase 7A-3).

The HIP dequantization kernels must reproduce the same golden values as the
CPU path: the expected values come from llama.cpp's own NumPy reference
implementation (see ``tests/fixtures/PROVENANCE.md``), so this compares the
kernel against an external reference and not against this repository's own CPU
dequantizer.

The module is marked ``gpu``: it needs the compiled HIP extension, and it is
skipped (never failed) when the extension is not importable.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, Dict

import numpy as np
import pytest

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_ROOT_DIR, "build"), os.path.join(_ROOT_DIR, "src")):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

# Every test in this module needs the HIP extension.
pytestmark = pytest.mark.gpu

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

_GOLDEN: Dict[str, Any] = json.loads(
    (_FIXTURES / "quant_golden.json").read_text(encoding="utf-8")
)
_ENTRIES = {entry["quant_type"]: entry for entry in _GOLDEN["entries"]}

_QUANT_TYPES = ["Q4_0", "Q4_K", "Q6_K"]


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_gpu_dequantization_matches_the_golden(matmul_module, quant_type: str) -> None:
    """The HIP kernel must produce the reference values.

    The comparison is exact: both sides are FP16 values of the same FP32
    reference, so no tolerance is needed.
    """
    entry = _ENTRIES[quant_type]
    raw = (_FIXTURES / entry["fixture"]).read_bytes()
    blocks = np.frombuffer(raw, dtype=np.uint8)
    n_elements = entry["n_blocks"] * entry["weights_per_block"]

    expected = np.asarray(entry["expected_fp32"], dtype=np.float32).astype(np.float16)
    actual = np.zeros(n_elements, dtype=np.float16)

    kernel = getattr(matmul_module, f"dequantize_{quant_type.lower()}")
    kernel(blocks, actual, n_elements)

    assert np.array_equal(actual, expected), (
        f"{quant_type}: the GPU dequantization differs from llama.cpp's reference "
        f"(max |diff| = {float(np.max(np.abs(actual.astype(np.float32) - expected.astype(np.float32)))):.6g})"
    )


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_gpu_dequantization_matches_the_cpu_path(matmul_module, quant_type: str) -> None:
    """The GPU and the CPU dequantizers must agree on the golden blocks."""
    from gguf_parser import (
        dequantize_q4_0_cpu,
        dequantize_q4_k_cpu,
        dequantize_q6_k_cpu,
    )

    dequantizers = {
        "Q4_0": dequantize_q4_0_cpu,
        "Q4_K": dequantize_q4_k_cpu,
        "Q6_K": dequantize_q6_k_cpu,
    }
    entry = _ENTRIES[quant_type]
    raw = (_FIXTURES / entry["fixture"]).read_bytes()
    blocks = np.frombuffer(raw, dtype=np.uint8)
    n_elements = entry["n_blocks"] * entry["weights_per_block"]

    cpu = dequantizers[quant_type](blocks, n_elements)
    gpu = np.zeros(n_elements, dtype=np.float16)
    getattr(matmul_module, f"dequantize_{quant_type.lower()}")(blocks, gpu, n_elements)

    max_err = float(np.max(np.abs(cpu.astype(np.float32) - gpu.astype(np.float32))))
    assert max_err == 0.0, (
        f"{quant_type}: the GPU and CPU dequantizations differ (max |diff| = {max_err:.6g})"
    )
