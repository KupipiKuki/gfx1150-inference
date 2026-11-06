#!/usr/bin/env python3
"""
Dump the header (metadata + tensor table) of a GGUF file *slice* for 7C evidence.

The production `GGUFParser` validates that every tensor's byte range fits inside
the buffer, which a partial-range slice cannot satisfy. This dumper therefore
stops at `data_offset` and only *records* tensor extents. It asserts that the
slice covers the complete header so the dump is a full header dump, not a
truncated one.

Usage: python dump_gguf_header.py <slice-file>
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys

GGUF_MAGIC = b"GGUF"

GGML_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1",
    8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K",
    14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "Q2_K_S",
    19: "IQ3_XS", 20: "IQ3_XXS", 21: "IQ1_S", 22: "IQ4_NL", 23: "IQ3_S",
    24: "IQ2_S", 25: "IQ4_XS", 26: "IQ1_M", 27: "BF16",
    30: "TQ1_0", 31: "TQ2_0",
}

VALUE_TYPE_NAMES = {
    0: "UINT8", 1: "INT8", 2: "UINT16", 3: "INT16", 4: "UINT32", 5: "INT32",
    6: "FLOAT32", 7: "BOOL", 8: "STRING", 9: "ARRAY", 10: "UINT64",
    11: "INT64", 12: "FLOAT64",
}

SCALAR_FORMATS = {
    0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
    10: "<Q", 11: "<q", 12: "<d",
}


def _read(buf: memoryview, pos: int, fmt: str):
    size = struct.calcsize(fmt)
    vals = struct.unpack_from(fmt, buf, pos)
    return vals, pos + size


def _read_string(buf: memoryview, pos: int) -> str:
    (length,), pos = _read(buf, pos, "<Q")
    s = bytes(buf[pos:pos + length]).decode("utf-8")
    return s, pos + length


def _read_value(buf: memoryview, pos: int, vtype: int):
    if vtype in SCALAR_FORMATS:
        (v,), pos = _read(buf, pos, SCALAR_FORMATS[vtype])
        return v, pos
    if vtype == 7:  # BOOL
        (v,), pos = _read(buf, pos, "<B")
        return bool(v), pos
    if vtype == 8:  # STRING
        return _read_string(buf, pos)
    if vtype == 9:  # ARRAY
        (elem_type, count), pos = _read(buf, pos, "<IQ")
        if elem_type == 9:
            raise ValueError("GGUF array element type must not be an array")
        items = []
        for _ in range(count):
            item, pos = _read_value(buf, pos, elem_type)
            items.append(item)
        return items, pos
    raise ValueError(f"unsupported value type {vtype}")


def parse_header(buf: memoryview):
    """Return (version, alignment, metadata, tensors, data_offset)."""
    if bytes(buf[0:4]) != GGUF_MAGIC:
        raise ValueError("not a GGUF file")
    pos = 4
    (version, tensor_count, kv_count), pos = _read(buf, pos, "<IQQ")
    if version not in (2, 3):
        raise ValueError(f"unsupported GGUF version {version}")

    metadata = {}
    for _ in range(kv_count):
        key, pos = _read_string(buf, pos)
        (vtype,), pos = _read(buf, pos, "<I")
        val, pos = _read_value(buf, pos, vtype)
        metadata[key] = (vtype, val)

    raw_align = metadata.get("general.alignment", (4, 32))[1]
    tensors = []
    for _ in range(tensor_count):
        name, pos = _read_string(buf, pos)
        (n_dims,), pos = _read(buf, pos, "<I")
        dims, pos = _read(buf, pos, f"<{n_dims}Q")
        (ggml_type, rel_offset), pos = _read(buf, pos, "<IQ")
        tensors.append((name, tuple(dims), ggml_type, rel_offset))

    def align(x):
        a = raw_align if isinstance(raw_align, int) else 32
        return (x + a - 1) // a * a

    return version, raw_align, metadata, tensors, align(pos)


def _fmt_array(val, max_items=6):
    if not val:
        return "[]"
    if len(val) <= max_items:
        return "[" + ", ".join(repr(x) for x in val) + "]"
    return f"[{len(val)} items; first: {val[0]!r}, ...]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slice_file")
    args = ap.parse_args()

    with open(args.slice_file, "rb") as f:
        raw = f.read()
    mv = memoryview(raw)
    version, alignment, metadata, tensors, data_offset = parse_header(mv)

    print(f"# slice: {args.slice_file}")
    print(f"sha256(slice) = {hashlib.sha256(raw).hexdigest()}")
    print(f"# gguf version: {version}; alignment: {alignment}; slice bytes: {len(raw)}")
    if data_offset > len(raw):
        print(f"ERROR: data_offset {data_offset} exceeds slice size {len(raw)}; dump is truncated")
        return 1
    print(f"data_offset = {data_offset} (slice covers the complete header: yes)")
    print(f"kv_count = {len(metadata)}; tensor_count = {len(tensors)}")
    print()
    print("## Metadata")
    for key in sorted(metadata):
        vtype, val = metadata[key]
        tn = VALUE_TYPE_NAMES.get(vtype, str(vtype))
        if vtype == 9:
            print(f"{key} = ARRAY<{tn}>({_fmt_array(val)})")
        else:
            print(f"{key} = {tn}({val!r})")
    print()
    print("## Tensors (ne dims in GGUF order: ne[0] is innermost/contiguous)")
    print("### Global tensors")
    for name, dims, ggml_type, rel_offset in tensors:
        if not name.startswith("blk."):
            print(f"{name}: dims={dims} type={GGML_TYPE_NAMES.get(ggml_type, ggml_type)}")
    print("### blk.0 tensors")
    for name, dims, ggml_type, rel_offset in tensors:
        if name.startswith("blk.0."):
            print(f"{name}: dims={dims} type={GGML_TYPE_NAMES.get(ggml_type, ggml_type)}")
    print("### blk.1 tensors")
    for name, dims, ggml_type, rel_offset in tensors:
        if name.startswith("blk.1."):
            print(f"{name}: dims={dims} type={GGML_TYPE_NAMES.get(ggml_type, ggml_type)}")
    print("### Unique tensor suffix histogram (blk.* -> suffix)")
    suffixes = {}
    for name, dims, ggml_type, rel_offset in tensors:
        suffix = name.split(".", 2)[-1] if name.startswith("blk.") else name
        suffixes[suffix] = suffixes.get(suffix, 0) + 1
    for suffix in sorted(suffixes):
        print(f"{suffix}: count={suffixes[suffix]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
