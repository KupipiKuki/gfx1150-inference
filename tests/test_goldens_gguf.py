"""Golden GGUF header from an upstream model (Phase 7A-3).

``tests/fixtures/tiny_gguf.gguf`` is the upstream TinyLlama ``stories260K``
GGUF model, committed verbatim. The expectations in
``tests/fixtures/tiny_gguf_expectations.json`` were derived from it by
**llama.cpp's own GGUF reader** (``gguf-py``) -- not by this repository's
parser, which is the code under test.

The parser test therefore checks two independent readings of the same file:
this repository's zero-copy parser must agree with llama.cpp's reader on the
metadata, the tensor descriptors, the alignment and the offsets, and the
``WeightStreamer`` must hand out the tensor values llama.cpp recorded.

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

from gguf_parser import GGMLType, GGUFParser
from weight_loader import WeightStreamer

# The GGUF header golden is pure CPU: no extension, no GPU.
pytestmark = pytest.mark.cpu

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
_GGUF_PATH = _FIXTURES / "tiny_gguf.gguf"
_EXPECTATIONS: Dict[str, Any] = json.loads(
    (_FIXTURES / "tiny_gguf_expectations.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def parsed() -> GGUFParser:
    """The parsed upstream GGUF, read once for the whole module."""
    with open(_GGUF_PATH, "rb") as handle:
        return GGUFParser(handle.read())


def test_the_fixture_is_the_upstream_file() -> None:
    """The committed GGUF must be the upstream file the expectations describe."""
    digest = hashlib.sha256(_GGUF_PATH.read_bytes()).hexdigest()
    assert digest == _EXPECTATIONS["source_gguf_sha256"], (
        "tests/fixtures/tiny_gguf.gguf does not match the hash recorded in the "
        "expectations"
    )


def test_metadata_matches_the_reference_reader(parsed: GGUFParser) -> None:
    """Every metadata value must equal llama.cpp's reading of the file."""
    expected = _EXPECTATIONS["metadata"]
    for key, value in expected.items():
        assert key in parsed.metadata, f"the parser did not read the metadata key {key!r}"
        if isinstance(value, dict) and value.get("type") == "array":
            actual = parsed.metadata[key]
            assert len(actual) == value["length"], (
                f"{key}: the parser read {len(actual)} entries, "
                f"expected {value['length']}"
            )
            for index, item in enumerate(value["first"]):
                assert actual[index] == item, f"{key}[{index}] differs from the reference"
        else:
            assert parsed.metadata[key] == value, f"{key} differs from the reference"


def test_tensor_descriptors_match_the_reference_reader(parsed: GGUFParser) -> None:
    """Names, shapes, types and sizes must equal llama.cpp's reading."""
    expected = _EXPECTATIONS["tensors"]
    assert len(parsed.tensors) == len(expected), (
        f"the parser read {len(parsed.tensors)} tensors, expected {len(expected)}"
    )
    for entry in expected:
        name = entry["name"]
        assert name in parsed.tensors, f"the parser did not read the tensor {name!r}"
        info = parsed.tensors[name]
        assert list(info.dims) == entry["ne"], f"{name}: the shape differs"
        assert info.ggml_type.name == entry["type"], f"{name}: the type differs"
        assert info.n_bytes == entry["n_bytes"], f"{name}: the byte size differs"
        assert info.n_elements == entry["n_elements"], f"{name}: the element count differs"
        assert info.abs_offset == entry["offset"], f"{name}: the offset differs"


def test_the_tensor_offsets_are_aligned(parsed: GGUFParser) -> None:
    """Every tensor must start on the file's alignment boundary."""
    alignment = parsed.alignment
    assert alignment > 0
    for name, info in parsed.tensors.items():
        assert info.abs_offset % alignment == 0, (
            f"{name}: the offset {info.abs_offset} is not a multiple of {alignment}"
        )


def test_the_data_section_starts_after_the_header(parsed: GGUFParser) -> None:
    """The data section must follow the header and be aligned."""
    assert parsed.data_offset % parsed.alignment == 0
    assert parsed.data_offset > 0
    assert parsed.version in (2, 3)
    assert parsed.tensor_count == len(_EXPECTATIONS["tensors"])
    assert parsed.kv_count == len(_EXPECTATIONS["metadata"])


def test_the_zero_copy_values_match_the_reference() -> None:
    """The values ``WeightStreamer`` hands out must equal llama.cpp's.

    The values are read through the zero-copy ``mmap`` view, so this also
    checks that the offsets the parser computes address the right bytes.
    """
    checked = 0
    streamer = WeightStreamer(str(_GGUF_PATH))
    try:
        for entry in _EXPECTATIONS["tensors"]:
            if "first_values" not in entry:
                continue
            view = streamer.get_tensor_view(entry["name"])
            try:
                # A copy for the comparison; the view itself must stay a view
                # into the mapping (a copy would have ``base is None``).
                assert view.base is not None, (
                    f"{entry['name']}: the tensor view is a copy, not a view "
                    "into the mapping"
                )
                expected = np.asarray(entry["first_values"], dtype=np.float32)
                actual = np.array(view, dtype=np.float32).reshape(-1)[: expected.size]
                assert np.array_equal(actual, expected), (
                    f"{entry['name']}: the values differ from llama.cpp's reading"
                )
                checked += 1
            finally:
                # Release the view's export of the mmap buffer. Without this,
                # ``mmap.close()`` raises BufferError -- the behaviour the R-1
                # regression test in tests/test_cpu_only.py pins.
                del view
    finally:
        try:
            streamer.close()
        except BufferError:
            pass
    assert checked > 0, "no tensor values were checked"


def test_the_tensor_shapes_are_transposed_by_the_parser(parsed: GGUFParser) -> None:
    """``ne`` is innermost-first; the row-major shape is its reverse."""
    for entry in _EXPECTATIONS["tensors"]:
        info = parsed.tensors[entry["name"]]
        assert list(info.shape_row_major) == list(reversed(entry["ne"]))


def test_the_model_type_is_the_expected_ggml_type(parsed: GGUFParser) -> None:
    """The fixture's tensors are F32, which is what the reference recorded."""
    types = {info.ggml_type for info in parsed.tensors.values()}
    assert types == {GGMLType.F32}
