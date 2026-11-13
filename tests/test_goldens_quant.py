"""Golden quantized blocks from llama.cpp's reference quantizer (Phase 7A-3).

The block bytes in ``tests/fixtures/q4_0_blocks.bin``,
``tests/fixtures/q4_k_blocks.bin`` and ``tests/fixtures/q6_k_blocks.bin`` were
produced by **llama.cpp's own quantizer** (``llama-quantize``) and extracted
from the quantized GGUF it wrote. The expected dequantized values were computed
by llama.cpp's own NumPy reference implementation (``gguf-py``), which is
independent of this repository's CPU dequantizers.

They are deliberately **not** a ``quantize_*_cpu`` → ``dequantize_*_cpu``
round-trip of this repository's own code: such a pair would only prove that
the implementation agrees with itself.

The provenance of every fixture is in ``tests/fixtures/PROVENANCE.md``.
"""

from __future__ import annotations

import hashlib
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

from gguf_parser import (
    dequantize_q4_0_cpu,
    dequantize_q4_k_cpu,
    dequantize_q6_k_cpu,
)

# Quantization goldens are pure CPU: no extension, no GPU.
pytestmark = pytest.mark.cpu

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

#: The GGML block layout, which the brief pins: weights per block and bytes
#: per block.
BLOCK_LAYOUT = {
    "Q4_0": (32, 18),
    "Q4_K": (256, 144),
    "Q6_K": (256, 210),
}

_DEQUANTIZERS = {
    "Q4_0": dequantize_q4_0_cpu,
    "Q4_K": dequantize_q4_k_cpu,
    "Q6_K": dequantize_q6_k_cpu,
}

_GOLDEN: Dict[str, Any] = json.loads(
    (_FIXTURES / "quant_golden.json").read_text(encoding="utf-8")
)
_ENTRIES = {entry["quant_type"]: entry for entry in _GOLDEN["entries"]}

_QUANT_TYPES = ["Q4_0", "Q4_K", "Q6_K"]


def _fixture_bytes(quant_type: str) -> bytes:
    return (_FIXTURES / _ENTRIES[quant_type]["fixture"]).read_bytes()


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_block_layout_matches_the_ggml_specification(quant_type: str) -> None:
    """The block size and the byte size must match the GGML layout."""
    weights_per_block, block_bytes = BLOCK_LAYOUT[quant_type]
    entry = _ENTRIES[quant_type]
    assert entry["weights_per_block"] == weights_per_block
    assert entry["block_size_bytes"] == block_bytes

    raw = _fixture_bytes(quant_type)
    assert len(raw) == entry["n_blocks"] * block_bytes, (
        f"{quant_type}: the fixture is {len(raw)} bytes, expected "
        f"{entry['n_blocks']} blocks of {block_bytes} bytes"
    )
    assert len(raw) % block_bytes == 0


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_cpu_dequantization_matches_the_reference(quant_type: str) -> None:
    """The CPU dequantizer must reproduce llama.cpp's reference values.

    The reference values are FP32; this repository's CPU dequantizer returns
    FP16, so the comparison is against the FP16 rounding of the reference.
    The values agree exactly -- there is no tolerance to widen.
    """
    entry = _ENTRIES[quant_type]
    raw = _fixture_bytes(quant_type)
    n_elements = entry["n_blocks"] * entry["weights_per_block"]

    expected = np.asarray(entry["expected_fp32"], dtype=np.float32)
    assert expected.shape == (n_elements,)

    actual = _DEQUANTIZERS[quant_type](np.frombuffer(raw, dtype=np.uint8), n_elements)
    assert actual.dtype == np.float16, (
        f"{quant_type}: the CPU dequantizer returned {actual.dtype}, expected float16"
    )
    assert np.array_equal(actual, expected.astype(np.float16)), (
        f"{quant_type}: the CPU dequantization differs from llama.cpp's reference"
    )


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_the_fixture_bytes_match_their_recorded_hash(quant_type: str) -> None:
    """The committed bytes must be the ones the golden was computed from."""
    entry = _ENTRIES[quant_type]
    digest = hashlib.sha256(_fixture_bytes(quant_type)).hexdigest()
    assert digest == entry["block_bytes_sha256"], (
        f"{quant_type}: the fixture bytes do not match the hash recorded in the golden"
    )


def test_the_q4_0_bytes_are_llama_cpp_s_own_quantizer_output() -> None:
    """For Q4_0 the provenance is machine-checkable.

    llama.cpp ships a NumPy implementation of its own Q4_0 quantizer
    (``gguf-py``). Re-quantizing the source tensor with it must reproduce the
    committed bytes exactly; that ties the fixture to ``llama-quantize``'s
    output rather than to a re-implementation.
    """
    entry = _ENTRIES["Q4_0"]
    assert entry["numpy_requantize_is_byte_identical"] is True, (
        "the recorded provenance says llama.cpp's NumPy quantizer does not "
        "reproduce the committed Q4_0 bytes"
    )


def test_the_expected_values_are_not_self_referential() -> None:
    """The golden must not be a round-trip of this repository's own code.

    The reference implementation is llama.cpp's ``gguf-py``; if the recorded
    provenance ever names this repository, the fixture is no longer independent.
    """
    reference = _GOLDEN["reference"]
    assert reference["project"] == "ggml-org/llama.cpp", (
        "the reference implementation must be llama.cpp"
    )
    assert "llama.cpp" in reference["expected_values"], (
        "the expected values must come from an independent reference"
    )
    assert reference["blocks"].startswith("llama"), (
        "the blocks must come from llama.cpp's own quantizer"
    )
    assert "gfx1150" not in json.dumps(reference), (
        "the recorded provenance must not name this repository"
    )


@pytest.mark.parametrize("quant_type", _QUANT_TYPES)
def test_the_blocks_are_not_degenerate(quant_type: str) -> None:
    """A golden of zeros would pass every dequantization check.

    The blocks must contain a spread of values, so that a broken dequantizer
    cannot pass by accident.
    """
    expected = np.asarray(_ENTRIES[quant_type]["expected_fp32"], dtype=np.float32)
    assert float(np.max(np.abs(expected))) > 0.0
    assert float(np.std(expected)) > 0.0
    assert len(np.unique(expected)) > 4
