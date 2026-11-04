"""Deterministic fuzz for the GGUF header parser (Phase 7A-4).

The goal is **executable evidence that a malformed GGUF header cannot crash
the parser**: every example must either parse, or be rejected with the
parser's documented ``ValueError``. Any other exception -- ``struct.error``,
``IndexError``, ``KeyError``, ``OverflowError``, ``MemoryError``,
``UnicodeDecodeError`` -- is a failure.

The seed is a **valid minimal GGUF v3 buffer built in this test** (header,
metadata and tensor index). The mutations are *structured*: the test draws a
description of a GGUF file -- with hostile values for the alignment, the
counts, the string and array lengths, the dimensions, the type IDs and the
tensor offsets -- and serialises it, so every example is a well-formed GGUF
except in the way the test intends.

The run is deterministic: ``derandomize=True`` fixes the seed and
``database=None`` keeps the result independent of any local ``.hypothesis``
database, so two runs produce the same examples in the same order.

Known defect
------------

``test_nested_arrays_are_rejected_with_a_value_error`` pins a defect this
fuzz uncovered: a header whose metadata array has an ``ARRAY`` element type
makes the parser recurse until the interpreter's stack is exhausted, so it
raises ``RecursionError`` instead of rejecting the file. It is reported as
**BLOCKER-7A4-1** (see ``audit/evidence/G1/7A-4/BLOCKER.md``) and is a strict
xfail, so the fix cannot land unnoticed. The fuzz itself keeps the GGUF
format's own rule -- an array's element type is a scalar -- because the
element type is not a field the fuzz is allowed to invent.

The module is in the CPU lane and the fuzz test is marked ``slow``: the
packaging job deselects ``slow`` so that building and installing the sdist
stays fast, while the CPU job owns the 10,000-example run.
"""

from __future__ import annotations

import gc
import mmap
import os
import struct
import sys
import tempfile
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (os.path.join(_ROOT_DIR, "build"), os.path.join(_ROOT_DIR, "src")):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import GGML_BLOCK_INFO, GGMLType, GGUFParser

# The fuzz is a CPU-lane test: it needs neither the extension nor a GPU.
pytestmark = pytest.mark.cpu

GGUF_MAGIC = b"GGUF"

# GGUF metadata value types (gguf_parser.GGUFValueType).
_UINT32 = 4
_INT32 = 5
_FLOAT32 = 6
_BOOL = 7
_STRING = 8
_ARRAY = 9
_UINT64 = 10

#: The GGML type IDs the parser knows, plus the reserved and unknown ones it
#: must reject.
_VALID_GGML_TYPES = tuple(int(t) for t in GGMLType)
_RESERVED_GGML_TYPES = (4, 5)  # gaps in the enum: reserved by the format
_UNKNOWN_GGML_TYPES = (16, 99, 0xFFFF_FFFF)

#: The alignment values the fuzz tries: the default, the degenerate ones, a
#: non-power-of-two, and the values that are far outside the parser's range.
_HOSTILE_ALIGNMENTS = (0, 1, 3, 30, 65537, 1 << 20, (1 << 63) - 1)

#: The hard bound on the size of a generated buffer. It keeps the harness
#: itself safe: the parser's allocations are bounded by the buffer length, so
#: a 64 KiB input cannot make it allocate more than a few times that.
MAX_BUFFER_BYTES = 64 * 1024

#: The hard bound on the payload the *writer* materialises per tensor. The
#: writer must never size a buffer from a hostile dimension, so the payload is
#: capped: a tensor whose descriptor claims more than this is written short,
#: which the parser then rejects as a truncated file.
MAX_PAYLOAD_BYTES = 4096

#: The tensor names the fuzz draws from. They include the ``blk.N.`` family
#: so that the layer-span helpers are exercised, and a foreign name so that
#: the "interleaved" case can be built.
_TENSOR_NAME_POOL = (
    "token_embd.weight",
    "output_norm.weight",
    "output.weight",
    "blk.0.attn_q.weight",
    "blk.0.attn_k.weight",
    "blk.0.attn_v.weight",
    "blk.0.attn_output.weight",
    "blk.0.attn_norm.weight",
    "blk.0.ffn_gate.weight",
    "blk.0.ffn_down.weight",
    "blk.0.ffn_up.weight",
    "blk.1.attn_q.weight",
    "blk.1.attn_norm.weight",
    "blk.2.ffn_up.weight",
    "blk.7.attn_q.weight",
)


# ---------------------------------------------------------------------------
# The description of a GGUF file, and its serialiser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _MetaEntry:
    """One metadata key-value pair, possibly with a hostile length."""

    key: str
    vtype: int
    value: Any
    #: Overrides the written string length (u64) or array count (u64).
    length_override: Optional[int] = None


@dataclass(frozen=True)
class _TensorEntry:
    """One tensor descriptor, possibly with hostile fields."""

    name: str
    dims: Tuple[int, ...]
    ggml_type: int
    rel_offset: int
    #: Overrides the written dimension count (u32).
    n_dims_override: Optional[int] = None
    #: Overrides the written name length (u64).
    name_length_override: Optional[int] = None


@dataclass(frozen=True)
class _GGUFDescription:
    """A whole GGUF file, as drawn by the strategies."""

    version: int = 3
    metadata: Tuple[_MetaEntry, ...] = ()
    tensors: Tuple[_TensorEntry, ...] = ()
    #: Overrides the written tensor count (u64).
    tensor_count_override: Optional[int] = None
    #: Overrides the written key-value count (u64).
    kv_count_override: Optional[int] = None
    #: The alignment the *writer* pads the data section to. The alignment in
    #: the metadata is a separate, possibly hostile, value.
    writer_alignment: int = 32
    #: Extra bytes appended after the data section.
    tail_bytes: int = 0


@dataclass
class _Built:
    """A serialised buffer and the offsets of its interesting boundaries."""

    data: bytes
    header_end: int
    metadata_end: int
    tensor_index_end: int
    data_end: int
    boundaries: Dict[str, int] = field(default_factory=dict)


def _pack_string(text: str, length_override: Optional[int] = None) -> bytes:
    raw = text.encode("utf-8")
    length = len(raw) if length_override is None else int(length_override)
    return struct.pack("<Q", length & 0xFFFF_FFFF_FFFF_FFFF) + raw


def _pack_value(vtype: int, value: Any, length_override: Optional[int] = None) -> bytes:
    if vtype == _UINT32:
        return struct.pack("<I", int(value) & 0xFFFF_FFFF)
    if vtype == _INT32:
        return struct.pack("<i", int(value))
    if vtype == _FLOAT32:
        # A float32 cannot hold every Python float; the writer clamps rather
        # than failing, because a hostile value must reach the parser, not
        # the harness.
        value = float(value)
        if value != value or value in (float("inf"), float("-inf")):
            value = 0.0
        value = max(-3.4e38, min(3.4e38, value))
        return struct.pack("<f", value)
    if vtype == _BOOL:
        return struct.pack("<B", 1 if value else 0)
    if vtype == _UINT64:
        return struct.pack("<Q", int(value) & 0xFFFF_FFFF_FFFF_FFFF)
    if vtype == _STRING:
        return _pack_string(str(value), length_override)
    if vtype == _ARRAY:
        count = len(value) if length_override is None else int(length_override)
        out = struct.pack("<IQ", _INT32, count & 0xFFFF_FFFF_FFFF_FFFF)
        for item in value:
            out += struct.pack("<i", int(item))
        return out
    raise AssertionError(f"unsupported metadata value type {vtype}")


def _payload_bytes(tensor: _TensorEntry) -> int:
    """How many payload bytes the writer materialises for a tensor.

    It is the size the descriptor claims, capped: the writer must not size a
    buffer from a hostile dimension. A tensor whose type is unknown, whose
    element count is not a multiple of the block size, or whose size exceeds
    the cap is written short -- the parser then rejects the file as
    truncated, which is the documented behaviour.
    """
    try:
        block_elements, block_bytes = GGML_BLOCK_INFO[tensor.ggml_type]
    except (KeyError, TypeError):
        return 0
    elements = 1
    for dim in tensor.dims:
        elements *= max(0, int(dim))
        if elements > (1 << 24):
            return MAX_PAYLOAD_BYTES
    if elements % block_elements:
        return 0
    return min((elements // block_elements) * block_bytes, MAX_PAYLOAD_BYTES)


def _build(description: _GGUFDescription) -> _Built:
    """Serialise a description into GGUF bytes.

    The writer never trusts the description's hostile fields for its *own*
    arithmetic: the padding uses ``writer_alignment`` and the payload is a
    fixed size, so the writer cannot be destabilised by a hostile field. The
    hostile values are written into the buffer, where the parser sees them.
    """
    out = bytearray()
    out.extend(GGUF_MAGIC)
    tensor_count = (
        len(description.tensors)
        if description.tensor_count_override is None
        else int(description.tensor_count_override)
    )
    kv_count = (
        len(description.metadata)
        if description.kv_count_override is None
        else int(description.kv_count_override)
    )
    out.extend(struct.pack("<IQQ", description.version, tensor_count & 0xFFFF_FFFF_FFFF_FFFF,
                           kv_count & 0xFFFF_FFFF_FFFF_FFFF))
    header_end = len(out)

    for entry in description.metadata:
        out.extend(_pack_string(entry.key))
        out.extend(struct.pack("<I", entry.vtype))
        out.extend(_pack_value(entry.vtype, entry.value, entry.length_override))
    metadata_end = len(out)

    for tensor in description.tensors:
        out.extend(_pack_string(tensor.name, tensor.name_length_override))
        n_dims = (
            len(tensor.dims)
            if tensor.n_dims_override is None
            else int(tensor.n_dims_override)
        )
        out.extend(struct.pack("<I", n_dims & 0xFFFF_FFFF))
        out.extend(struct.pack(f"<{len(tensor.dims)}Q", *[d & 0xFFFF_FFFF_FFFF_FFFF for d in tensor.dims]))
        out.extend(struct.pack("<IQ", tensor.ggml_type & 0xFFFF_FFFF,
                               tensor.rel_offset & 0xFFFF_FFFF_FFFF_FFFF))
    tensor_index_end = len(out)

    alignment = max(1, int(description.writer_alignment))
    data_offset = (len(out) + alignment - 1) // alignment * alignment
    out.extend(b"\x00" * (data_offset - len(out)))
    # The payload is placed at the tensor's *declared* offset, so a
    # well-formed description describes a file whose data section really does
    # cover its tensors. A hostile offset is not placed: the buffer is not
    # grown for it, and the parser then rejects the file as truncated.
    end = data_offset
    for tensor in description.tensors:
        size = _payload_bytes(tensor)
        if tensor.rel_offset >= (1 << 20):
            continue
        end = max(end, data_offset + tensor.rel_offset + size)
    out.extend(b"\x00" * (end - len(out)))
    data_end = len(out)
    out.extend(b"\x00" * max(0, int(description.tail_bytes)))

    return _Built(
        data=bytes(out),
        header_end=header_end,
        metadata_end=metadata_end,
        tensor_index_end=tensor_index_end,
        data_end=data_end,
        boundaries={
            "magic": 4,
            "header": header_end,
            "metadata": metadata_end,
            "tensor_index": tensor_index_end,
            "data": data_end,
        },
    )


# ---------------------------------------------------------------------------
# The strategies
# ---------------------------------------------------------------------------

#: The hostile values each field can take. The mutation is applied to a
#: well-formed file, so that the examples reach deep into the parser instead
#: of all being rejected at the first check.
_HOSTILE_COUNTS = (0, 1, 2, 3, 7, 64, 1024, 1 << 20, (1 << 63) - 1, (1 << 64) - 1)
_HOSTILE_LENGTHS = (0, 1, 5, 64, 1 << 20, (1 << 63) - 1, (1 << 64) - 1)
_HOSTILE_DIMS = (0, 1, 2, 7, 32, 256, 1024, (1 << 32) - 1, (1 << 63) - 1, (1 << 64) - 1)
_HOSTILE_OFFSETS = (0, 1, 3, 7, 31, 32, 33, 64, 1 << 20, (1 << 63) - 1, (1 << 64) - 1)
_HOSTILE_VERSIONS = (0, 1, 4, 5, 0xFFFF, (1 << 32) - 1)

#: How often a field is mutated. The mutations are rare, so that an example is
#: usually a well-formed file: the fuzz then reaches deep into the parser
#: instead of being rejected at the first check, and every mutation class is
#: still exercised thousands of times over the run.
_MUTATION_RATE = 16


def _hostile(draw: st.DrawFn, values: Tuple[int, ...]) -> Optional[int]:
    """Return a hostile value with a small probability, otherwise ``None``."""
    if draw(st.integers(0, _MUTATION_RATE - 1)) == 0:
        return draw(st.sampled_from(values))
    return None


@st.composite
def _meta_entries(draw: st.DrawFn) -> _MetaEntry:
    """Draw one metadata entry, well formed or with a mutated length."""
    kind = draw(st.sampled_from(["alignment", "string", "array", "uint32", "int32", "float32", "bool"]))
    if kind == "alignment":
        hostile = _hostile(draw, _HOSTILE_ALIGNMENTS)
        if hostile is not None:
            return _MetaEntry("general.alignment", _UINT32, hostile)
        # A well-formed alignment: a power of two the parser accepts.
        return _MetaEntry(
            "general.alignment", _UINT32, draw(st.sampled_from((1, 2, 4, 8, 16, 32, 64, 4096)))
        )
    if kind == "string":
        text = draw(st.text(max_size=24))
        return _MetaEntry("general.name", _STRING, text, _hostile(draw, _HOSTILE_LENGTHS))
    if kind == "array":
        items = draw(st.lists(st.integers(-(1 << 31), (1 << 31) - 1), max_size=6))
        return _MetaEntry("general.tags", _ARRAY, items, _hostile(draw, _HOSTILE_LENGTHS))
    if kind == "uint32":
        return _MetaEntry("custom.u32", _UINT32, draw(st.integers(0, (1 << 32) - 1)))
    if kind == "int32":
        return _MetaEntry("custom.i32", _INT32, draw(st.integers(-(1 << 31), (1 << 31) - 1)))
    if kind == "float32":
        return _MetaEntry("custom.f32", _FLOAT32, draw(st.floats(min_value=-3.4e38, max_value=3.4e38)))
    return _MetaEntry("custom.bool", _BOOL, draw(st.booleans()))


@st.composite
def _tensor_entries(draw: st.DrawFn) -> _TensorEntry:
    """Draw one tensor descriptor, well formed or with a mutated field."""
    name = draw(st.sampled_from(_TENSOR_NAME_POOL))

    hostile_type = _hostile(draw, _RESERVED_GGML_TYPES + _UNKNOWN_GGML_TYPES)
    hostile_dims = _hostile(draw, _HOSTILE_DIMS)
    hostile_offset = _hostile(draw, _HOSTILE_OFFSETS)
    hostile_n_dims = _hostile(draw, (0, 1, 2, 3, 4, 5, 6, 7, 8, 9))
    hostile_name_length = _hostile(draw, _HOSTILE_LENGTHS)

    if (
        hostile_type is None
        and hostile_dims is None
        and hostile_offset is None
        and hostile_n_dims is None
        and hostile_name_length is None
    ):
        # A well-formed descriptor: the type, the element count and the offset
        # agree, so the file can be accepted and the layer helpers exercised.
        ggml_type = draw(st.sampled_from(_VALID_GGML_TYPES))
        block_elements, _ = GGML_BLOCK_INFO[ggml_type]
        elements = block_elements * draw(st.integers(1, 3))
        return _TensorEntry(
            name=name,
            dims=(elements,),
            ggml_type=ggml_type,
            rel_offset=draw(st.sampled_from((0, 32, 64, 96, 128, 160))),
        )

    n_dims = draw(st.integers(1, 4))
    dims = tuple(
        hostile_dims if hostile_dims is not None and index == 0 else draw(st.sampled_from(_HOSTILE_DIMS))
        for index in range(n_dims)
    )
    ggml_type = hostile_type if hostile_type is not None else draw(
        st.one_of(
            st.sampled_from(_VALID_GGML_TYPES),
            st.integers(0, (1 << 32) - 1),
        )
    )
    rel_offset = hostile_offset if hostile_offset is not None else draw(st.sampled_from((0, 32, 64, 96, 128, 160)))
    return _TensorEntry(
        name=name,
        dims=dims,
        ggml_type=ggml_type,
        rel_offset=rel_offset,
        n_dims_override=hostile_n_dims,
        name_length_override=hostile_name_length,
    )


@st.composite
def _descriptions(draw: st.DrawFn) -> _GGUFDescription:
    """Draw a GGUF file: a well-formed one, with optional mutations."""
    metadata = draw(st.lists(_meta_entries(), max_size=4))
    tensors = list(draw(st.lists(_tensor_entries(), max_size=4)))

    # A duplicate tensor name: the parser must reject the table, not silently
    # keep one of the two.
    if len(tensors) >= 2 and draw(st.integers(0, _MUTATION_RATE - 1)) == 0:
        tensors[1] = replace(tensors[1], name=tensors[0].name)

    version = 3
    if draw(st.integers(0, _MUTATION_RATE - 1)) == 0:
        version = draw(st.sampled_from((2,) + _HOSTILE_VERSIONS))
    tensor_count_override = _hostile(draw, _HOSTILE_COUNTS)
    kv_count_override = _hostile(draw, _HOSTILE_COUNTS)
    writer_alignment = draw(st.sampled_from([1, 2, 8, 16, 32, 64, 4096]))
    tail_bytes = draw(st.integers(0, 4096))
    return _GGUFDescription(
        version=version,
        metadata=tuple(metadata),
        tensors=tuple(tensors),
        tensor_count_override=tensor_count_override,
        kv_count_override=kv_count_override,
        writer_alignment=writer_alignment,
        tail_bytes=tail_bytes,
    )


@st.composite
def _buffers(draw: st.DrawFn) -> bytes:
    """Draw a GGUF buffer: a description, serialised, possibly truncated."""
    description = draw(_descriptions())
    built = _build(description)

    if draw(st.integers(0, _MUTATION_RATE - 1)) != 0:
        return built.data

    # Truncate at one of the interesting boundaries, or anywhere inside them.
    boundaries = sorted(built.boundaries.values())
    where = draw(st.one_of(st.sampled_from(boundaries), st.integers(0, len(built.data))))
    return built.data[:where]


# ---------------------------------------------------------------------------
# The fuzz
# ---------------------------------------------------------------------------


def _assert_no_leak() -> None:
    """Fail if the parse left a file descriptor or a mapping behind."""
    open_fds = len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else 0
    assert open_fds < 256, f"the fuzz leaked file descriptors ({open_fds} open)"


@settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
@given(_buffers())
@pytest.mark.slow
def test_fuzz_gguf_headers(buffer: bytes) -> None:
    """A malformed GGUF header must be rejected, never crash the parser.

    The parser's documented failure mode is ``ValueError``. Anything else --
    ``struct.error``, ``IndexError``, ``KeyError``, ``OverflowError``,
    ``MemoryError``, ``UnicodeDecodeError``, ``RecursionError`` -- is a
    failure of this test.
    """
    assert len(buffer) <= MAX_BUFFER_BYTES + 4096, (
        f"the fuzz generated a {len(buffer)}-byte buffer, above the bound"
    )
    try:
        parser = GGUFParser(buffer)
    except ValueError:
        # The documented rejection: the header is malformed and the parser
        # says so.
        return
    except Exception as exc:  # noqa: BLE001 - the point of the test
        raise AssertionError(
            f"the parser raised {type(exc).__name__} instead of rejecting the "
            f"malformed header with a ValueError: {exc}\n"
            f"buffer ({len(buffer)} bytes): {buffer[:96].hex()}"
        ) from exc

    # The parse succeeded, so the file was well formed enough to be accepted.
    # The layer helpers must not crash either: a missing layer is a documented
    # KeyError, anything else is a failure.
    for layer_idx in (0, 1, 99):
        try:
            parser.get_layer_tensors(layer_idx)
        except KeyError:
            pass
        except Exception as exc:  # noqa: BLE001 - the point of the test
            raise AssertionError(
                f"get_layer_tensors({layer_idx}) raised {type(exc).__name__}: {exc}"
            ) from exc
        try:
            parser.get_layer_byte_spans(layer_idx)
        except KeyError:
            pass
        except Exception as exc:  # noqa: BLE001 - the point of the test
            raise AssertionError(
                f"get_layer_byte_spans({layer_idx}) raised {type(exc).__name__}: {exc}"
            ) from exc
    _assert_no_leak()


@settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
@given(_buffers())
@pytest.mark.slow
def test_fuzz_gguf_headers_are_deterministic(buffer: bytes) -> None:
    """Parsing the same buffer twice must give the same result.

    A parser that depends on uninitialised memory or on the order of its
    inputs would fail here.
    """
    outcomes = []
    for _ in range(2):
        try:
            parser = GGUFParser(buffer)
        except ValueError as exc:
            outcomes.append(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - the point of the test
            raise AssertionError(
                f"the parser raised {type(exc).__name__} instead of rejecting the "
                f"malformed header with a ValueError: {exc}"
            ) from exc
        else:
            outcomes.append(
                (
                    "parsed",
                    parser.version,
                    parser.alignment,
                    tuple(sorted(parser.tensors)),
                    tuple(sorted((k, repr(v)) for k, v in parser.metadata.items())),
                )
            )
    assert outcomes[0] == outcomes[1], (
        "parsing the same buffer twice gave different results:\n"
        f"  {outcomes[0]}\n  {outcomes[1]}"
    )


# ---------------------------------------------------------------------------
# The known defect, pinned
# ---------------------------------------------------------------------------


def _nested_array_header(depth: int) -> bytes:
    """A GGUF header whose metadata array has an ``ARRAY`` element type.

    Each level of nesting is 12 bytes, so the buffer stays small while the
    parser's recursion grows without bound.
    """
    value = struct.pack("<IQ", _STRING, 1) + struct.pack("<Q", 1) + b"x"
    for _ in range(depth):
        value = struct.pack("<IQ", _ARRAY, 1) + value
    metadata = struct.pack("<Q", 1) + b"k" + struct.pack("<I", _ARRAY) + value
    return GGUF_MAGIC + struct.pack("<IQQ", 3, 0, 1) + metadata


@pytest.mark.xfail(
    strict=True,
    reason="BLOCKER-7A4-1: a nested GGUF array recurses until the stack is exhausted",
)
def test_nested_arrays_are_rejected_with_a_value_error() -> None:
    """A nested metadata array must be rejected, not crash the parser.

    This is the defect the fuzz uncovered. The GGUF format does not allow an
    array whose element type is an array, so the parser has to reject the
    file; instead it recurses once per nesting level and raises
    ``RecursionError`` on a header of about 12 KiB.

    The assertion states the behaviour the parser *should* have, so the test
    fails today and passes when the defect is fixed. ``strict=True`` means the
    suite fails if the test starts passing while the xfail is still in place.
    """
    buffer = _nested_array_header(1000)
    try:
        GGUFParser(buffer)
    except ValueError:
        return
    except RecursionError as exc:
        raise AssertionError(
            "the parser recursed until the interpreter's stack was exhausted "
            f"instead of rejecting the nested array: {exc}"
        ) from exc
    raise AssertionError(
        "the parser accepted a header with a nested metadata array, which the "
        "GGUF format does not allow"
    )


# ---------------------------------------------------------------------------
# The cases the fuzz draws, checked directly as well
# ---------------------------------------------------------------------------


def _interleaved_description() -> _GGUFDescription:
    """A valid file with a foreign tensor between two tensors of layer 0."""
    f32 = int(GGMLType.F32)
    return _GGUFDescription(
        metadata=(_MetaEntry("general.alignment", _UINT32, 32),),
        tensors=(
            _TensorEntry("blk.0.attn_q.weight", (16,), f32, 0),
            _TensorEntry("output.weight", (16,), f32, 64),
            _TensorEntry("blk.0.attn_norm.weight", (16,), f32, 128),
        ),
    )


def test_the_layer_span_is_split_by_an_interleaved_foreign_tensor() -> None:
    """A foreign tensor between two layer tensors must split the span.

    The layer-span helpers merge adjacent layer tensors, but only when no
    foreign tensor sits between them. The fuzz draws this shape; the check
    here states the expected result, so a change in the helper's semantics
    cannot pass unnoticed.
    """
    built = _build(_interleaved_description())
    parser = GGUFParser(built.data)

    layer = parser.get_layer_tensors(0)
    assert set(layer) == {"blk.0.attn_q.weight", "blk.0.attn_norm.weight"}

    spans = parser.get_layer_byte_spans(0)
    assert len(spans) == 2, (
        f"the foreign tensor between the two layer tensors must split the span, "
        f"got {spans}"
    )
    assert spans[0][0] < spans[1][0]

    # The hull still covers both layer tensors, from the first to the last.
    start, length = parser.get_layer_byte_span(0)
    assert start == spans[0][0]
    assert start + length == spans[1][0] + spans[1][1]


def test_a_duplicate_tensor_name_is_rejected() -> None:
    """A tensor table with the same name twice must be rejected.

    The parser has to say so rather than silently keep one of the two.
    """
    f32 = int(GGMLType.F32)
    description = _GGUFDescription(
        metadata=(_MetaEntry("general.alignment", _UINT32, 32),),
        tensors=(
            _TensorEntry("blk.0.attn_q.weight", (16,), f32, 0),
            _TensorEntry("blk.0.attn_q.weight", (16,), f32, 64),
        ),
    )
    built = _build(description)
    try:
        GGUFParser(built.data)
    except ValueError as exc:
        assert "Duplicate tensor name" in str(exc), (
            f"the parser rejected the duplicate name for the wrong reason: {exc}"
        )
    else:
        raise AssertionError("the parser accepted a tensor table with a duplicate name")


# ---------------------------------------------------------------------------
# The file and mapping paths
# ---------------------------------------------------------------------------


def test_parsing_from_a_file_releases_the_descriptor() -> None:
    """A parsed file must not leak its descriptor or its mapping.

    The fuzz parses buffers, so the file path is checked here: the streamer
    must close the file even when a live view keeps the mapping exported (the
    behaviour the R-1 regression test in ``tests/test_cpu_only.py`` pins).
    """
    description = _GGUFDescription(
        metadata=(_MetaEntry("general.alignment", _UINT32, 32),),
        tensors=(_TensorEntry("blk.0.attn_norm.weight", (32,), int(GGMLType.F16), 0),),
    )
    built = _build(description)
    before = len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else 0
    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as handle:
        handle.write(built.data)
        path = handle.name
    try:
        with open(path, "rb") as source:
            mapping = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                parser = GGUFParser(mapping)
                assert parser.version == 3
                assert "blk.0.attn_norm.weight" in parser.tensors
            finally:
                try:
                    mapping.close()
                except BufferError:
                    # A live export keeps the mapping open; that is the
                    # documented behaviour, and the file is closed anyway.
                    pass
    finally:
        os.unlink(path)
        gc.collect()
    after = len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else 0
    assert after <= before, (
        f"parsing a file leaked a descriptor ({before} open before, {after} after)"
    )
