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

    MAX_TENSOR_DIMS = 8
    MAX_ALIGNMENT = 65536
    MIN_KV_ENTRY_BYTES = 13
    MIN_TENSOR_ENTRY_BYTES = 24

    def __init__(self, buf: Union[bytes, bytearray, memoryview, Any]):
        # Create a private memoryview wrapper so releasing `view` in `finally`
        # drops our export on `mmap` without invalidating a caller-owned memoryview.
        view = memoryview(buf).cast("B")
        self._buf: Optional[memoryview] = view
        self._pos = 0
        self.version: int = 0
        self.tensor_count: int = 0
        self.kv_count: int = 0
        self.metadata: Dict[str, Any] = {}
        self.tensors: Dict[str, GGUFTensorInfo] = {}
        self.alignment: int = GGUF_DEFAULT_ALIGNMENT
        self.data_offset: int = 0

        try:
            self._parse()
        finally:
            self._buf = None
            view.release()

    def _read_fmt(self, fmt: str) -> Tuple[Any, ...]:
        if self._buf is None:
            raise RuntimeError("Parser buffer already released")
        size = struct.calcsize(fmt)
        if self._pos + size > len(self._buf):
            raise ValueError(f"Unexpected EOF at offset {self._pos} while reading {fmt}")
        vals = struct.unpack_from(fmt, self._buf, self._pos)
        self._pos += size
        return vals

    def _read_string(self) -> str:
        if self._buf is None:
            raise RuntimeError("Parser buffer already released")
        (length,) = self._read_fmt("<Q")
        if self._pos + length > len(self._buf):
            raise ValueError(f"Unexpected EOF while reading string of length {length}")
        raw = bytes(self._buf[self._pos : self._pos + length])
        self._pos += length
        return raw.decode("utf-8")

    def _read_value(self, vtype: int) -> Any:
        if self._buf is None:
            raise RuntimeError("Parser buffer already released")
        if vtype in _SCALAR_FORMATS:
            return self._read_fmt(_SCALAR_FORMATS[vtype])[0]
        if vtype == GGUFValueType.BOOL:
            return bool(self._read_fmt("<B")[0])
        if vtype == GGUFValueType.STRING:
            return self._read_string()
        if vtype == GGUFValueType.ARRAY:
            elem_type, count = self._read_fmt("<IQ")
            if elem_type == GGUFValueType.ARRAY:
                raise ValueError("GGUF array element type must not be an array")
            remaining = len(self._buf) - self._pos
            if count > remaining:
                raise ValueError(
                    f"GGUF array count {count} exceeds remaining buffer bytes ({remaining})"
                )
            return [self._read_value(elem_type) for _ in range(count)]
        raise ValueError(f"Unsupported GGUF metadata value type: {vtype}")

    def _parse(self) -> None:
        if self._buf is None:
            raise RuntimeError("Parser buffer already released")
        buf_len = len(self._buf)
        if buf_len < 4:
            raise ValueError(f"Buffer too small for GGUF header ({buf_len} bytes)")
        magic = bytes(self._buf[0:4])
        if magic != GGUF_MAGIC:
            raise ValueError(f"Invalid GGUF magic: {magic!r} (expected b'GGUF')")
        self._pos = 4

        self.version, self.tensor_count, self.kv_count = self._read_fmt("<IQQ")
        if self.version not in (2, 3):
            raise ValueError(f"Unsupported GGUF version: {self.version} (expected 2 or 3)")

        remaining_after_header = buf_len - self._pos
        if self.kv_count * self.MIN_KV_ENTRY_BYTES > remaining_after_header:
            raise ValueError(
                f"Corrupt GGUF header: kv_count={self.kv_count} requires at least "
                f"{self.kv_count * self.MIN_KV_ENTRY_BYTES} bytes, but only {remaining_after_header} remain"
            )
        if self.tensor_count * self.MIN_TENSOR_ENTRY_BYTES > remaining_after_header:
            raise ValueError(
                f"Corrupt GGUF header: tensor_count={self.tensor_count} requires at least "
                f"{self.tensor_count * self.MIN_TENSOR_ENTRY_BYTES} bytes, but only {remaining_after_header} remain"
            )

        for _ in range(self.kv_count):
            key = self._read_string()
            (vtype,) = self._read_fmt("<I")
            self.metadata[key] = self._read_value(vtype)

        raw_align = self.metadata.get("general.alignment", GGUF_DEFAULT_ALIGNMENT)
        if isinstance(raw_align, bool) or not isinstance(raw_align, int):
            raise ValueError(f"Invalid general.alignment value: {raw_align!r}")
        if (
            raw_align < 1
            or raw_align > self.MAX_ALIGNMENT
            or (raw_align & (raw_align - 1)) != 0
        ):
            raise ValueError(
                f"Invalid general.alignment={raw_align}: must be a power of 2 in [1, {self.MAX_ALIGNMENT}]"
            )
        self.alignment = raw_align

        remaining_for_tensors = buf_len - self._pos
        if self.tensor_count * self.MIN_TENSOR_ENTRY_BYTES > remaining_for_tensors:
            raise ValueError(
                f"Corrupt GGUF tensor table: tensor_count={self.tensor_count} exceeds remaining bytes ({remaining_for_tensors})"
            )

        raw_tensors = []
        seen_names = set()
        for _ in range(self.tensor_count):
            name = self._read_string()
            if name in seen_names:
                raise ValueError(f"Duplicate tensor name in GGUF tensor table: {name!r}")
            seen_names.add(name)
            (n_dims,) = self._read_fmt("<I")
            if n_dims == 0 or n_dims > self.MAX_TENSOR_DIMS:
                raise ValueError(
                    f"Tensor '{name}' has invalid n_dims={n_dims} (must be in [1, {self.MAX_TENSOR_DIMS}])"
                )
            dims = tuple(self._read_fmt(f"<{n_dims}Q"))
            if any(d == 0 for d in dims):
                raise ValueError(f"Tensor '{name}' has a zero dimension in {dims}")
            ggml_type_id, rel_offset = self._read_fmt("<IQ")
            try:
                ggml_type = GGMLType(ggml_type_id)
            except ValueError as exc:
                raise ValueError(
                    f"Tensor '{name}' has unknown GGMLType id {ggml_type_id}"
                ) from exc
            if ggml_type not in GGML_BLOCK_INFO:
                raise ValueError(
                    f"Tensor '{name}' has unsupported GGMLType {ggml_type!r} (no block size info)"
                )

            n_elements = math.prod(dims)
            block_elems, block_bytes = GGML_BLOCK_INFO[ggml_type]
            if n_elements % block_elems != 0:
                raise ValueError(
                    f"Tensor '{name}' element count {n_elements} is not divisible by block size {block_elems}"
                )
            n_bytes = (n_elements // block_elems) * block_bytes
            raw_tensors.append((name, dims, ggml_type, rel_offset, n_elements, n_bytes))

        self.data_offset = align_offset(self._pos, self.alignment)
        if self.data_offset > buf_len and self.tensor_count > 0:
            raise ValueError(
                f"Truncated GGUF file: data_offset {self.data_offset} exceeds buffer size {buf_len}"
            )

        for name, dims, ggml_type, rel_offset, n_elements, n_bytes in raw_tensors:
            abs_offset = self.data_offset + rel_offset
            if abs_offset < self.data_offset or abs_offset + n_bytes > buf_len:
                raise ValueError(
                    f"Truncated GGUF file: tensor '{name}' requires byte range "
                    f"[{abs_offset}, {abs_offset + n_bytes}), but file size is {buf_len} bytes"
                )
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

    def get_layer_byte_spans(self, layer_idx: int) -> List[Tuple[int, int]]:
        """
        Return a list of `(start_offset, byte_length)` spans for `layer_idx`, merging
        adjacent layer tensors that have no foreign (non-layer) tensor interleaved between them.
        """
        layer_tensors = self.get_layer_tensors(layer_idx)
        if not layer_tensors:
            raise KeyError(f"No tensors found for layer {layer_idx}")

        sorted_layer = sorted(layer_tensors.values(), key=lambda t: t.abs_offset)
        layer_names = set(layer_tensors.keys())
        foreign_intervals = sorted(
            (t.abs_offset, t.abs_offset + t.n_bytes)
            for name, t in self.tensors.items()
            if name not in layer_names
        )

        def _has_foreign_between(end_prev: int, start_next: int) -> bool:
            if start_next <= end_prev:
                return False
            for f_start, f_end in foreign_intervals:
                if f_start >= start_next:
                    break
                if f_end > end_prev and f_start < start_next:
                    return True
            return False

        spans: List[Tuple[int, int]] = []
        cur_start = sorted_layer[0].abs_offset
        cur_end = cur_start + sorted_layer[0].n_bytes

        for t in sorted_layer[1:]:
            t_start = t.abs_offset
            t_end = t_start + t.n_bytes
            gap = t_start - cur_end
            if gap <= self.alignment and not _has_foreign_between(cur_end, t_start):
                cur_end = max(cur_end, t_end)
            else:
                spans.append((cur_start, cur_end - cur_start))
                cur_start, cur_end = t_start, t_end

        spans.append((cur_start, cur_end - cur_start))
        return spans

    def get_layer_byte_span(self, layer_idx: int) -> Tuple[int, int]:
        """Return hull `(start_offset, byte_length)` covering all tensors in `layer_idx`."""
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


def quantize_q8_0_cpu(weights_fp32: np.ndarray) -> np.ndarray:
    """
    Reference CPU quantizer: converts a float32/float16 array (multiple of 32 elements)
    into GGML Q8_0 packed bytes (`uint8` array of length `n_elements // 32 * 34`).
    """
    flat = np.asarray(weights_fp32, dtype=np.float32).reshape(-1, 32)
    num_blocks = flat.shape[0]

    max_abs = np.max(np.abs(flat), axis=1)
    d_fp16 = (max_abs / 127.0).astype(np.float16)
    d_fp32 = d_fp16.astype(np.float32)

    inv_d = np.where(d_fp32 > 0.0, 1.0 / d_fp32, 0.0)[:, None]
    qs = np.clip(np.round(flat * inv_d), -127, 127).astype(np.int8)

    out = np.empty((num_blocks, 34), dtype=np.uint8)
    out[:, :2] = d_fp16.view(np.uint8).reshape(num_blocks, 2)
    out[:, 2:] = qs.view(np.uint8)
    return out.reshape(-1)


def dequantize_q8_0_cpu(q8_bytes: np.ndarray, num_elements: int) -> np.ndarray:
    """Reference CPU dequantizer for GGML Q8_0 blocks into `np.float16`."""
    num_blocks = num_elements // 32
    raw = np.frombuffer(q8_bytes, dtype=np.uint8, count=num_blocks * 34).reshape(num_blocks, 34)
    d = raw[:, :2].copy().view(np.float16).astype(np.float32)  # (num_blocks, 1)
    qs = raw[:, 2:].view(np.int8).astype(np.float32)           # (num_blocks, 32)
    weights = qs * d
    return weights.reshape(-1).astype(np.float16)


def quantize_q4_k_cpu(weights_fp32: np.ndarray) -> np.ndarray:
    """
    Reference CPU quantizer: converts a float32/float16 array (multiple of 256 elements)
    into GGML Q4_K (Q4_K_M / Q4_K_S) super-block bytes (`n_elements // 256 * 144` bytes).
    """
    flat = np.asarray(weights_fp32, dtype=np.float32).reshape(-1, 256)
    num_sb = flat.shape[0]
    sub = flat.reshape(num_sb, 8, 32)

    # Sub-block mins (non-negative offset so x + m >= 0)
    m_val = np.maximum(0.0, -np.min(sub, axis=2))  # (num_sb, 8)
    shifted = sub + m_val[:, :, None]
    sc_val = np.max(shifted, axis=2) / 15.0        # (num_sb, 8)

    d_fp16 = (np.max(sc_val, axis=1) / 63.0).astype(np.float16)
    dmin_fp16 = (np.max(m_val, axis=1) / 63.0).astype(np.float16)
    d_fp32 = d_fp16.astype(np.float32)[:, None]
    dmin_fp32 = dmin_fp16.astype(np.float32)[:, None]

    inv_d = np.where(d_fp32 > 0.0, 1.0 / d_fp32, 0.0)
    inv_dmin = np.where(dmin_fp32 > 0.0, 1.0 / dmin_fp32, 0.0)

    sc_q = np.clip(np.round(sc_val * inv_d), 0, 63).astype(np.uint8)   # (num_sb, 8)
    m_q = np.clip(np.round(m_val * inv_dmin), 0, 63).astype(np.uint8)  # (num_sb, 8)

    eff_d = (d_fp32 * sc_q.astype(np.float32))[:, :, None]
    eff_m = (dmin_fp32 * m_q.astype(np.float32))[:, :, None]
    inv_eff_d = np.where(eff_d > 0.0, 1.0 / eff_d, 0.0)

    q_sub = np.clip(np.round((sub + eff_m) * inv_eff_d), 0, 15).astype(np.uint8)  # (num_sb, 8, 32)

    # Pack 6-bit scales[8] and mins[8] into 12 bytes per GGML get_scale_min_k4 layout
    scales_packed = np.empty((num_sb, 12), dtype=np.uint8)
    for j in range(4):
        scales_packed[:, j]     = (sc_q[:, j] & 63) | ((sc_q[:, j + 4] >> 4) << 6)
        scales_packed[:, j + 4] = (m_q[:, j]  & 63) | ((m_q[:, j + 4]  >> 4) << 6)
        scales_packed[:, j + 8] = (sc_q[:, j + 4] & 0x0F) | ((m_q[:, j + 4] & 0x0F) << 4)

    # Pack 256 nibbles into 128 bytes (4 chunks of 32 bytes; low nibble = sub 2*c, high = sub 2*c+1)
    qs_packed = np.empty((num_sb, 128), dtype=np.uint8)
    for chunk in range(4):
        lo = q_sub[:, 2 * chunk, :]
        hi = q_sub[:, 2 * chunk + 1, :]
        qs_packed[:, chunk * 32 : (chunk + 1) * 32] = lo | (hi << 4)

    out = np.empty((num_sb, 144), dtype=np.uint8)
    out[:, 0:2] = d_fp16.view(np.uint8).reshape(num_sb, 2)
    out[:, 2:4] = dmin_fp16.view(np.uint8).reshape(num_sb, 2)
    out[:, 4:16] = scales_packed
    out[:, 16:144] = qs_packed
    return out.reshape(-1)


def dequantize_q4_k_cpu(q4k_bytes: np.ndarray, num_elements: int) -> np.ndarray:
    """Reference CPU dequantizer for GGML Q4_K super-blocks into `np.float16`."""
    num_sb = num_elements // 256
    raw = np.frombuffer(q4k_bytes, dtype=np.uint8, count=num_sb * 144).reshape(num_sb, 144)
    d = raw[:, 0:2].copy().view(np.float16).astype(np.float32)     # (num_sb, 1)
    dmin = raw[:, 2:4].copy().view(np.float16).astype(np.float32)  # (num_sb, 1)
    scales = raw[:, 4:16]                                          # (num_sb, 12)
    qs = raw[:, 16:144]                                            # (num_sb, 128)

    sc_q = np.empty((num_sb, 8), dtype=np.float32)
    m_q = np.empty((num_sb, 8), dtype=np.float32)
    for j in range(4):
        sc_q[:, j]     = (scales[:, j] & 63).astype(np.float32)
        m_q[:, j]      = (scales[:, j + 4] & 63).astype(np.float32)
        sc_q[:, j + 4] = ((scales[:, j + 8] & 0x0F) | ((scales[:, j] >> 6) << 4)).astype(np.float32)
        m_q[:, j + 4]  = ((scales[:, j + 8] >> 4)   | ((scales[:, j + 4] >> 6) << 4)).astype(np.float32)

    out = np.empty((num_sb, 256), dtype=np.float32)
    for chunk in range(4):
        q_chunk = qs[:, chunk * 32 : (chunk + 1) * 32]
        q0 = (q_chunk & 0x0F).astype(np.float32)
        q1 = (q_chunk >> 4).astype(np.float32)

        d0 = (d[:, 0] * sc_q[:, 2 * chunk])[:, None]
        dm0 = (dmin[:, 0] * m_q[:, 2 * chunk])[:, None]
        d1 = (d[:, 0] * sc_q[:, 2 * chunk + 1])[:, None]
        dm1 = (dmin[:, 0] * m_q[:, 2 * chunk + 1])[:, None]

        out[:, chunk * 64 : chunk * 64 + 32] = d0 * q0 - dm0
        out[:, chunk * 64 + 32 : (chunk + 1) * 64] = d1 * q1 - dm1

    return out.reshape(-1).astype(np.float16)


def quantize_q6_k_cpu(weights_fp32: np.ndarray) -> np.ndarray:
    """
    Reference CPU quantizer: converts a float32/float16 array (multiple of 256 elements)
    into GGML Q6_K super-block bytes (`n_elements // 256 * 210` bytes).

    Layout of `block_q6_K` (210 bytes per 256 elements):
    - `ql[128]` (bytes 0..128): lower 4 bits of the 256 6-bit unsigned quants (offset by -32)
    - `qh[64]`  (bytes 128..192): upper 2 bits of the 256 6-bit unsigned quants
    - `scales[16]` (bytes 192..208): 16 signed `int8` sub-block scales (16 elements per sub-block)
    - `d` (bytes 208..210): 2-byte FP16 super-block scale
    """
    flat = np.asarray(weights_fp32, dtype=np.float32).reshape(-1, 256)
    num_sb = flat.shape[0]
    sub = flat.reshape(num_sb, 16, 16)

    # Sub-block scales for symmetric 6-bit signed range [-32, 31]
    sub_max = np.max(np.abs(sub), axis=2)  # (num_sb, 16)
    sc_float = sub_max / 31.0              # (num_sb, 16)
    d_fp16 = (np.max(sc_float, axis=1) / 127.0).astype(np.float16)
    d_fp32 = d_fp16.astype(np.float32)[:, None]

    inv_d = np.where(d_fp32 > 0.0, 1.0 / d_fp32, 0.0)
    sc_i8 = np.clip(np.round(sc_float * inv_d), -127, 127).astype(np.int8)  # (num_sb, 16)

    eff_scale = (d_fp32 * sc_i8.astype(np.float32))[:, :, None]  # (num_sb, 16, 1)
    inv_eff = np.where(np.abs(eff_scale) > 0.0, 1.0 / eff_scale, 0.0)
    q_u6 = np.clip(np.round(sub * inv_eff) + 32.0, 0, 63).astype(np.uint8).reshape(num_sb, 256)

    ql = np.empty((num_sb, 128), dtype=np.uint8)
    qh = np.empty((num_sb, 64), dtype=np.uint8)

    for n in range(2):
        half_q = q_u6[:, n * 128 : (n + 1) * 128]
        q1 = half_q[:, 0:32]
        q2 = half_q[:, 32:64]
        q3 = half_q[:, 64:96]
        q4 = half_q[:, 96:128]

        ql[:, n * 64 : n * 64 + 32] = (q1 & 0x0F) | ((q3 & 0x0F) << 4)
        ql[:, n * 64 + 32 : (n + 1) * 64] = (q2 & 0x0F) | ((q4 & 0x0F) << 4)
        qh[:, n * 32 : (n + 1) * 32] = (
            ((q1 >> 4) & 0x03)
            | (((q2 >> 4) & 0x03) << 2)
            | (((q3 >> 4) & 0x03) << 4)
            | (((q4 >> 4) & 0x03) << 6)
        )

    out = np.empty((num_sb, 210), dtype=np.uint8)
    out[:, 0:128] = ql
    out[:, 128:192] = qh
    out[:, 192:208] = sc_i8.view(np.uint8)
    out[:, 208:210] = d_fp16.view(np.uint8).reshape(num_sb, 2)
    return out.reshape(-1)


def dequantize_q6_k_cpu(q6k_bytes: np.ndarray, num_elements: int) -> np.ndarray:
    """Reference CPU dequantizer for GGML Q6_K super-blocks into `np.float16`."""
    num_sb = num_elements // 256
    raw = np.frombuffer(q6k_bytes, dtype=np.uint8, count=num_sb * 210).reshape(num_sb, 210)
    ql = raw[:, 0:128]
    qh = raw[:, 128:192]
    scales = raw[:, 192:208].view(np.int8).astype(np.float32)          # (num_sb, 16)
    d = raw[:, 208:210].copy().view(np.float16).astype(np.float32)     # (num_sb, 1)

    out = np.empty((num_sb, 256), dtype=np.float32)
    for n in range(2):
        ql_n = ql[:, n * 64 : (n + 1) * 64]
        qh_n = qh[:, n * 32 : (n + 1) * 32]
        sc_n = scales[:, n * 8 : (n + 1) * 8]

        q1 = (((ql_n[:, 0:32]  & 0x0F) | (((qh_n >> 0) & 0x03) << 4)).astype(np.int8) - 32).astype(np.float32)
        q2 = (((ql_n[:, 32:64] & 0x0F) | (((qh_n >> 2) & 0x03) << 4)).astype(np.int8) - 32).astype(np.float32)
        q3 = (((ql_n[:, 0:32]  >> 4)   | (((qh_n >> 4) & 0x03) << 4)).astype(np.int8) - 32).astype(np.float32)
        q4 = (((ql_n[:, 32:64] >> 4)   | (((qh_n >> 6) & 0x03) << 4)).astype(np.int8) - 32).astype(np.float32)

        out[:, n * 128 + 0  : n * 128 + 16]  = d * sc_n[:, 0:1] * q1[:, 0:16]
        out[:, n * 128 + 16 : n * 128 + 32]  = d * sc_n[:, 1:2] * q1[:, 16:32]
        out[:, n * 128 + 32 : n * 128 + 48]  = d * sc_n[:, 2:3] * q2[:, 0:16]
        out[:, n * 128 + 48 : n * 128 + 64]  = d * sc_n[:, 3:4] * q2[:, 16:32]
        out[:, n * 128 + 64 : n * 128 + 80]  = d * sc_n[:, 4:5] * q3[:, 0:16]
        out[:, n * 128 + 80 : n * 128 + 96]  = d * sc_n[:, 5:6] * q3[:, 16:32]
        out[:, n * 128 + 96 : n * 128 + 112] = d * sc_n[:, 6:7] * q4[:, 0:16]
        out[:, n * 128 + 112: n * 128 + 128] = d * sc_n[:, 7:8] * q4[:, 16:32]

    return out.reshape(-1).astype(np.float16)


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
