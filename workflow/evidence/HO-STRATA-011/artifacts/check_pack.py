#!/usr/bin/env python3
"""Verify a GGUF pack: print size, SHA256, and general.architecture."""
import argparse
import hashlib
import os
import struct
import sys


def read_architecture(path: str) -> str:
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            raise ValueError(f"not a GGUF file: magic={magic!r}")
        version = struct.unpack("<I", f.read(4))[0]
        n_tensors, n_kv = struct.unpack("<QQ", f.read(16))
        slen_t = "<Q" if version == 3 else "<I"
        slen_sz = struct.calcsize(slen_t)

        def read_val(ty: int):
            if ty == 0:
                return struct.unpack("<B", f.read(1))[0]
            if ty == 1:
                return struct.unpack("<b", f.read(1))[0]
            if ty == 2:
                return struct.unpack("<H", f.read(2))[0]
            if ty == 3:
                return struct.unpack("<h", f.read(2))[0]
            if ty == 4:
                return struct.unpack("<I", f.read(4))[0]
            if ty == 5:
                return struct.unpack("<i", f.read(4))[0]
            if ty == 6:
                return struct.unpack("<f", f.read(4))[0]
            if ty == 7:
                return struct.unpack("<B", f.read(1))[0] != 0
            if ty == 8:
                sl = struct.unpack(slen_t, f.read(slen_sz))[0]
                return f.read(sl).decode("utf-8")
            if ty == 9:
                at = struct.unpack("<I", f.read(4))[0]
                al = struct.unpack("<Q", f.read(8))[0]
                return [read_val(at) for _ in range(al)]
            if ty == 10:
                return struct.unpack("<Q", f.read(8))[0]
            if ty == 11:
                return struct.unpack("<q", f.read(8))[0]
            raise ValueError(f"unknown GGUF value type {ty}")

        for _ in range(n_kv):
            klen = struct.unpack(slen_t, f.read(slen_sz))[0]
            key = f.read(klen).decode("utf-8")
            vtype = struct.unpack("<I", f.read(4))[0]
            val = read_val(vtype)
            if key == "general.architecture":
                return val
    return None


def main():
    ap = argparse.ArgumentParser(description="Verify GGUF pack identity")
    ap.add_argument("path", help="path to the .gguf file")
    args = ap.parse_args()

    size = os.path.getsize(args.path)
    with open(args.path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    arch = read_architecture(args.path)

    print(f"size: {size}")
    print(f"sha256: {sha}")
    print(f"general.architecture: {arch}")


if __name__ == "__main__":
    main()
