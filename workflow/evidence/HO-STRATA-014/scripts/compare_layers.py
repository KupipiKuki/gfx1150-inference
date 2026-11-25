#!/usr/bin/env python3
"""Compare a DeepSeek parity engine dump against the HO-010 oracle.

Engine dump layout: [position][slot][hidden] f32, slot 0 = input residual,
slot l+1 = after block l.  Oracle dump layout: [position][block][hidden] f32,
blocks 0..27.  This script derives N (blocks computed) from the engine dump
size and compares oracle blocks 0..N-1 against engine slots 1..N.
"""

import argparse
import math
import os
import struct
import sys


def load(path, what):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) % 4:
        raise ValueError(f"{what}: file size {len(data)} is not a multiple of 4")
    n = len(data) // 4
    floats = struct.unpack(f"<{n}f", data)
    return floats, n


def main():
    parser = argparse.ArgumentParser(description="Compare parity engine dump to oracle")
    parser.add_argument("--oracle", required=True, help="oracle .bin file")
    parser.add_argument("--dump", required=True, help="engine .bin dump")
    parser.add_argument("--shape-only", action="store_true", help="only check size and finiteness")
    parser.add_argument("--bound", type=float, default=5e-3, help="max relative L2 bound")
    args = parser.parse_args()

    HIDDEN = 2048
    ORACLE_BLOCKS = 28

    oracle, oracle_n = load(args.oracle, "oracle")
    if oracle_n != 4 * ORACLE_BLOCKS * HIDDEN:
        raise ValueError(f"oracle: expected {4*ORACLE_BLOCKS*HIDDEN} floats, got {oracle_n}")
    oracle_arr = [oracle[i * ORACLE_BLOCKS * HIDDEN:(i + 1) * ORACLE_BLOCKS * HIDDEN]
                  for i in range(4)]

    dump, dump_n = load(args.dump, "engine dump")
    if dump_n % HIDDEN != 0:
        raise ValueError(f"dump: {dump_n} floats is not a multiple of hidden={HIDDEN}")
    R = dump_n // HIDDEN  # R = records * slots

    # Derive slots per record (N+1) from the dump: must divide R and give >=4 records.
    slots = None
    for s in range(2, ORACLE_BLOCKS + 2):  # 2..29
        if R % s == 0 and R // s >= 4:
            slots = s
            break
    if slots is None:
        raise ValueError(f"dump: cannot derive slots/record from {dump_n} floats (R={R})")
    N = slots - 1
    records = R // slots

    print(f"engine dump: {records} records, {slots} slots/record, N={N} blocks computed")
    print(f"oracle: 4 records, {ORACLE_BLOCKS} blocks")

    # Reshape dump as [record][slot][hidden], keep first 4 records.
    dump_arr = []
    for r in range(min(4, records)):
        base = r * slots * HIDDEN
        record = [dump[base + s * HIDDEN:base + (s + 1) * HIDDEN] for s in range(slots)]
        dump_arr.append(record)

    # NaN/Inf check over all kept records and slots.
    bad = 0
    for r in dump_arr:
        for s in r:
            for v in s:
                if not math.isfinite(v):
                    bad += 1
    print(f"non-finite values in kept dump: {bad}")
    if bad:
        print("RESULT: FAIL")
        return 1

    if args.shape_only:
        print("RESULT: PASS (shape only)")
        return 0

    errors = []
    for p in range(4):
        for l in range(N):
            e = dump_arr[p][l + 1]
            o = oracle_arr[p][l * HIDDEN:(l + 1) * HIDDEN]
            num2 = sum((a - b) ** 2 for a, b in zip(e, o))
            den2 = sum(b ** 2 for b in o)
            rel = math.sqrt(num2 / den2) if den2 > 0 else (math.sqrt(num2) if num2 > 0 else 0.0)
            errors.append(((l, p), rel))
            print(f"  cell (layer={l}, pos={p}): rel L2 = {rel:.6e}")

    vals = [e for _, e in errors]
    median = sorted(vals)[len(vals) // 2] if len(vals) % 2 else (sorted(vals)[len(vals) // 2 - 1] + sorted(vals)[len(vals) // 2]) / 2
    max_err = max(vals)
    worst = max(errors, key=lambda x: x[1])[0]
    first_bad = next((cell for cell, e in errors if e > args.bound), None)

    print(f"median rel L2 = {median:.6e}")
    print(f"max rel L2    = {max_err:.6e} at (layer={worst[0]}, pos={worst[1]})")
    if first_bad:
        print(f"first cell above bound {args.bound}: (layer={first_bad[0]}, pos={first_bad[1]})")
        print("RESULT: FAIL")
        return 1

    print(f"RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
