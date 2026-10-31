"""
GGUF v2/v3 file format parser and Q4_0 quantization utilities for gfx1150-inference.

Parses GGUF headers, metadata key-value pairs, and 32-byte aligned tensor descriptors
directly from a memory-mapped file (`mmap`) or buffer without loading weights into RAM.
"""

from __future__ import annotations

import enum
import math
import struct
from dataclasses import dataclass
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
import numpy as np


GGUF_MAGIC = b"GGUF"
GGUF_DEFAULT_ALIGNMENT = 32


class GGMLType(enum.IntEnum):
    F32 = 0
    F16 = 1
    Q4_0 = 2
    Q4_1 = 3
    Q5_0 = 6
    Q5_1 = 7
    Q8_0 = 8
    Q8_1 = 9
    Q2_K = 10
    Q3_K = 11
    Q4_K = 12
    Q5_K = 13
    Q6_K = 14
    Q8_K = 15


# Map GGMLType -> (block_elements, block_bytes)
GGML_BLOCK_INFO: Dict[int, Tuple[int, int]] = {
    GGMLType.F32: (1, 4),
    GGMLType.F16: (1, 2),
    GGMLType.Q4_0: (32, 18),
    GGMLType.Q4_1: (32, 20),
    GGMLType.Q5_0: (32, 22),
    GGMLType.Q5_1: (32, 24),
    GGMLType.Q8_0: (32, 34),
    GGMLType.Q8_1: (32, 36),
    GGMLType.Q2_K: (256, 84),
    GGMLType.Q3_K: (256, 110),
    GGMLType.Q4_K: (256, 144),
    GGMLType.Q5_K: (256, 176),
    GGMLType.Q6_K: (256, 210),
    GGMLType.Q8_K: (256, 292),
}


class GGUFValueType(enum.IntEnum):
    UINT8 = 0
    INT8 = 1
    UINT16 = 2
    INT16 = 3
    UINT32 = 4
    INT32 = 5
    FLOAT32 = 6
    BOOL = 7
    STRING = 8
    ARRAY = 9
    UINT64 = 10
    INT64 = 11
    FLOAT64 = 12


_SCALAR_FORMATS: Dict[int, str] = {
    GGUFValueType.UINT8: "<B",
    GGUFValueType.INT8: "<b",
    GGUFValueType.UINT16: "<H",
    GGUFValueType.INT16: "<h",
    GGUFValueType.UINT32: "<I",
    GGUFValueType.INT32: "<i",
    GGUFValueType.FLOAT32: "<f",
    GGUFValueType.UINT64: "<Q",
    GGUFValueType.INT64: "<q",
    GGUFValueType.FLOAT64: "<d",
}


@dataclass(frozen=True)
class GGUFTensorInfo:
    name: str
    dims: Tuple[int, ...]  # GGUF dimensions (ne[0] is innermost/contiguous)
    ggml_type: GGMLType
    rel_offset: int        # Offset relative to start of data section
    abs_offset: int        # Absolute byte offset in the GGUF file
    n_elements: int        # Total number of logical elements
    n_bytes: int           # Total quantized byte size in file

    @property
    def shape_row_major(self) -> Tuple[int, ...]:
        """Return NumPy/PyTorch row-major shape (reversing GGUF ne[0..n-1])."""
        return tuple(reversed(self.dims))


def align_offset(offset: int, alignment: int = GGUF_DEFAULT_ALIGNMENT) -> int:
    return (offset + alignment - 1) // alignment * alignment


class GGUFParser:
    """Zero-copy parser for GGUF v2/v3 headers and tensor descriptors."""

    def __init__(self, buf: Union[bytes, bytearray, memoryview, Any]):
        self._buf = memoryview(buf)
        self._pos = 0
        self.version: int = 0
        self.tensor_count: int = 0
        self.kv_count: int = 0
        self.metadata: Dict[str, Any] = {}
        self.tensors: Dict[str, GGUFTensorInfo] = {}
        self.alignment: int = GGUF_DEFAULT_ALIGNMENT
        self.data_offset: int = 0

        self._parse()
        if isinstance(self._buf, memoryview):
            self._buf.release()
        self._buf = None

    def _read_fmt(self, fmt: str) -> Tuple[Any, ...]:
        size = struct.calcsize(fmt)
        if self._pos + size > len(self._buf):
            raise ValueError(f"Unexpected EOF at offset {self._pos} while reading {fmt}")
        vals = struct.unpack_from(fmt, self._buf, self._pos)
        self._pos += size
        return vals

    def _read_string(self) -> str:
        (length,) = self._read_fmt("<Q")
        if self._pos + length > len(self._buf):
            raise ValueError(f"Unexpected EOF while reading string of length {length}")
        raw = bytes(self._buf[self._pos : self._pos + length])
        self._pos += length
        return raw.decode("utf-8")

    def _read_value(self, vtype: int) -> Any:
        if vtype in _SCALAR_FORMATS:
            return self._read_fmt(_SCALAR_FORMATS[vtype])[0]
        if vtype == GGUFValueType.BOOL:
            return bool(self._read_fmt("<B")[0])
        if vtype == GGUFValueType.STRING:
            return self._read_string()
        if vtype == GGUFValueType.ARRAY:
            elem_type, count = self._read_fmt("<IQ")
            return [self._read_value(elem_type) for _ in range(count)]
        raise ValueError(f"Unsupported GGUF metadata value type: {vtype}")

    def _parse(self) -> None:
        magic = bytes(self._buf[0:4])
        if magic != GGUF_MAGIC:
            raise ValueError(f"Invalid GGUF magic: {magic!r} (expected b'GGUF')")
        self._pos = 4

        self.version, self.tensor_count, self.kv_count = self._read_fmt("<IQQ")
        if self.version not in (2, 3):
            raise ValueError(f"Unsupported GGUF version: {self.version} (expected 2 or 3)")

        for _ in range(self.kv_count):
            key = self._read_string()
            (vtype,) = self._read_fmt("<I")
            self.metadata[key] = self._read_value(vtype)

        self.alignment = int(self.metadata.get("general.alignment", GGUF_DEFAULT_ALIGNMENT))

        raw_tensors = []
        for _ in range(self.tensor_count):
            name = self._read_string()
            (n_dims,) = self._read_fmt("<I")
            dims = tuple(self._read_fmt(f"<{n_dims}Q"))
            ggml_type_id, rel_offset = self._read_fmt("<IQ")
            ggml_type = GGMLType(ggml_type_id)

            n_elements = math.prod(dims) if dims else 0
            block_elems, block_bytes = GGML_BLOCK_INFO[ggml_type]
            if n_elements % block_elems != 0:
                raise ValueError(
                    f"Tensor '{name}' element count {n_elements} is not divisible by block size {block_elems}"
                )
            n_bytes = (n_elements // block_elems) * block_bytes
            raw_tensors.append((name, dims, ggml_type, rel_offset, n_elements, n_bytes))

        self.data_offset = align_offset(self._pos, self.alignment)

        for name, dims, ggml_type, rel_offset, n_elements, n_bytes in raw_tensors:
            abs_offset = self.data_offset + rel_offset
            self.tensors[name] = GGUFTensorInfo(
                name=name,
                dims=dims,
                ggml_type=ggml_type,
                rel_offset=rel_offset,
                abs_offset=abs_offset,
                n_elements=n_elements,
                n_bytes=n_bytes,
            )

    def get_layer_tensors(self, layer_idx: int) -> Dict[str, GGUFTensorInfo]:
        """Return all tensors belonging to transformer block `layer_idx` (`blk.{layer_idx}.*`)."""
        prefix = f"blk.{layer_idx}."
        return {k: v for k, v in self.tensors.items() if k.startswith(prefix)}

    def get_layer_byte_span(self, layer_idx: int) -> Tuple[int, int]:
        """Return `(start_offset, byte_length)` covering all tensors in `layer_idx`."""
        layer_tensors = self.get_layer_tensors(layer_idx)
        if not layer_tensors:
            raise KeyError(f"No tensors found for layer {layer_idx}")
        start = min(t.abs_offset for t in layer_tensors.values())
        end = max(t.abs_offset + t.n_bytes for t in layer_tensors.values())
        return start, end - start


def quantize_q4_0_cpu(weights_fp32: np.ndarray) -> np.ndarray:
    """
    Reference CPU quantizer: converts a float32/float16 array (whose size is a multiple of 32)
    into GGML Q4_0 packed bytes (`uint8` array of length `n_elements // 32 * 18`).

    In GGML Q4_0:
    - Each block of 32 floats has scale `d = max(abs(x)) / -8.0` (or `max_abs / 7.0`)
    - Lower nibble `qs[j] & 0x0F` holds `clamp(round(x[j] / d) + 8, 0, 15)` for `j = 0..15`
    - Upper nibble `qs[j] >> 4` holds `clamp(round(x[j + 16] / d) + 8, 0, 15)` for `j = 0..15`
    """
    flat = np.asarray(weights_fp32, dtype=np.float32).reshape(-1, 32)
    num_blocks = flat.shape[0]

    max_abs = np.max(np.abs(flat), axis=1)
    d_fp16 = (max_abs / 7.0).astype(np.float16)
    d_fp32 = d_fp16.astype(np.float32)

    inv_d = np.where(d_fp32 > 0.0, 1.0 / d_fp32, 0.0)[:, None]
    q = np.clip(np.round(flat * inv_d) + 8.0, 0, 15).astype(np.uint8)

    lo = q[:, :16]
    hi = q[:, 16:]
    packed_qs = (lo | (hi << 4)).astype(np.uint8)

    out = np.empty((num_blocks, 18), dtype=np.uint8)
    out[:, :2] = d_fp16.view(np.uint8).reshape(num_blocks, 2)
    out[:, 2:] = packed_qs
    return out.reshape(-1)


def dequantize_q4_0_cpu(q4_bytes: np.ndarray, num_elements: int) -> np.ndarray:
    """Reference CPU dequantizer for GGML Q4_0 blocks into `np.float16`."""
    num_blocks = num_elements // 32
    raw = np.frombuffer(q4_bytes, dtype=np.uint8, count=num_blocks * 18).reshape(num_blocks, 18)
    d = raw[:, :2].copy().view(np.float16).astype(np.float32)  # (num_blocks, 1)
    qs = raw[:, 2:]  # (num_blocks, 16)

    x0 = (qs & 0x0F).astype(np.int8) - 8
    x1 = (qs >> 4).astype(np.int8) - 8
    weights = np.concatenate([x0, x1], axis=1).astype(np.float32) * d
    return weights.reshape(-1).astype(np.float16)


def write_synthetic_gguf(
    file_obj: BinaryIO,
    metadata: Dict[str, Tuple[GGUFValueType, Any]],
    tensors: List[Tuple[str, Tuple[int, ...], GGMLType, bytes]],
    alignment: int = GGUF_DEFAULT_ALIGNMENT,
) -> None:
    """Write a valid GGUF v3 binary stream for unit testing."""
    buf = bytearray()
    buf.extend(GGUF_MAGIC)
    buf.extend(struct.pack("<IQQ", 3, len(tensors), len(metadata)))

    def _pack_str(s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def _pack_val(vtype: GGUFValueType, val: Any) -> bytes:
        if vtype in _SCALAR_FORMATS:
            return struct.pack(_SCALAR_FORMATS[vtype], val)
        if vtype == GGUFValueType.BOOL:
            return struct.pack("<B", 1 if val else 0)
        if vtype == GGUFValueType.STRING:
            return _pack_str(val)
        if vtype == GGUFValueType.ARRAY:
            elem_type, items = val
            out_arr = bytearray(struct.pack("<IQ", int(elem_type), len(items)))
            for item in items:
                out_arr.extend(_pack_val(elem_type, item))
            return bytes(out_arr)
        raise ValueError(f"Unsupported synthetic metadata type: {vtype}")

    for k, (vtype, val) in metadata.items():
        buf.extend(_pack_str(k))
        buf.extend(struct.pack("<I", int(vtype)))
        buf.extend(_pack_val(vtype, val))

    rel_offset = 0
    tensor_payloads = []
    for name, dims, ggml_type, raw_bytes in tensors:
        rel_offset = align_offset(rel_offset, alignment)
        buf.extend(_pack_str(name))
        buf.extend(struct.pack("<I", len(dims)))
        buf.extend(struct.pack(f"<{len(dims)}Q", *dims))
        buf.extend(struct.pack("<IQ", int(ggml_type), rel_offset))
        tensor_payloads.append((rel_offset, raw_bytes))
        rel_offset += len(raw_bytes)

    data_offset = align_offset(len(buf), alignment)
    buf.extend(b"\x00" * (data_offset - len(buf)))

    for offset, payload in tensor_payloads:
        target_pos = data_offset + offset
        if len(buf) < target_pos:
            buf.extend(b"\x00" * (target_pos - len(buf)))
        buf.extend(payload)

    file_obj.write(buf)
    file_obj.flush()
