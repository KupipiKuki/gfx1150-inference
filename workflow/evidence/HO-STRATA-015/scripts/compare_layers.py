#!/usr/bin/env python3
"""Compare a DeepSeek parity engine dump against the HO-014 exact-f32 oracle.

Engine dump layout: [position][slot][hidden] f32, slot 0 = input residual,
slot l+1 = after block l.  Oracle dump layout: [position][block][hidden] f32,
blocks 0..27.  The caller must name the slot count explicitly with --slots;
this script asserts slots == 28 and rejects any dump whose geometry disagrees.
"""

import argparse
import math
import os
import struct
import sys


BOUND = 5e-3
HIDDEN = 2048
ORACLE_BLOCKS = 28


def load(path, what):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) % 4:
        raise ValueError(f"{what}: file size {len(data)} is not a multiple of 4")
    n = len(data) // 4
    floats = struct.unpack(f"<{n}f", data)
    return floats, n


def main():
    parser = argparse.ArgumentParser(description="Compare parity engine dump to exact-f32 oracle")
    parser.add_argument("--oracle", required=True, help="oracle .bin file")
    parser.add_argument("--dump", required=True, help="engine .bin dump")
    parser.add_argument("--slots", type=int, required=True, help="slots per record (input + N layers)")
    parser.add_argument("--shape-only", action="store_true", help="only check size and finiteness")
    parser.add_argument("--floor", action="store_true", help="report max without gating (informative Q4_K floor)")
    args = parser.parse_args()

    print(f"bound = {BOUND:.6e}  (fixed, not caller-supplied)")

    if args.slots != ORACLE_BLOCKS + 1:
        raise ValueError(f"--slots must be {ORACLE_BLOCKS + 1} (input + {ORACLE_BLOCKS} layers), got {args.slots}")

    oracle, oracle_n = load(args.oracle, "oracle")
    if oracle_n != 4 * ORACLE_BLOCKS * HIDDEN:
        raise ValueError(f"oracle: expected {4*ORACLE_BLOCKS*HIDDEN} floats, got {oracle_n}")
    oracle_arr = [oracle[i * ORACLE_BLOCKS * HIDDEN:(i + 1) * ORACLE_BLOCKS * HIDDEN]
                  for i in range(4)]

    dump, dump_n = load(args.dump, "engine dump")
    if dump_n % HIDDEN != 0:
        raise ValueError(f"dump: {dump_n} floats is not a multiple of hidden={HIDDEN}")
    R = dump_n // HIDDEN
    if R % args.slots != 0:
        raise ValueError(f"dump: {R} slots total is not divisible by --slots={args.slots}")
    records = R // args.slots
    if records < 4:
        raise ValueError(f"dump: expected at least 4 records, got {records}")

    print(f"engine dump: {records} records, {args.slots} slots/record, N={args.slots-1} blocks computed")
    print(f"oracle: 4 records, {ORACLE_BLOCKS} blocks")

    dump_arr = []
    for r in range(4):
        base = r * args.slots * HIDDEN
        record = [dump[base + s * HIDDEN:base + (s + 1) * HIDDEN] for s in range(args.slots)]
        dump_arr.append(record)

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

    def compare_cells(layers):
        errors = []
        for p in range(4):
            for l in layers:
                e = dump_arr[p][l + 1]
                o = oracle_arr[p][l * HIDDEN:(l + 1) * HIDDEN]
                num2 = sum((a - b) ** 2 for a, b in zip(e, o))
                den2 = sum(b ** 2 for b in o)
                rel = math.sqrt(num2 / den2) if den2 > 0 else (math.sqrt(num2) if num2 > 0 else 0.0)
                errors.append(((l, p), rel))
                print(f"  cell (layer={l}, pos={p}): rel L2 = {rel:.6e}")
        vals = [e for _, e in errors]
        max_err = max(vals)
        worst = max(errors, key=lambda x: x[1])[0]
        first_bad = next((cell for cell, e in errors if e > BOUND), None)
        return errors, max_err, worst, first_bad

    if args.floor:
        _, max_err, worst, _ = compare_cells(range(ORACLE_BLOCKS))
        print(f"max rel L2 = {max_err:.6e} at (layer={worst[0]}, pos={worst[1]})")
        print("RESULT: FLOOR (not gated)")
        return 0

    # Stage 1: layers 1..27 (108 cells)
    print("stage 1: layers 1-27 (108 cells)")
    _, max1, worst1, first_bad1 = compare_cells(range(1, ORACLE_BLOCKS))
    print(f"stage 1 max rel L2 = {max1:.6e} at (layer={worst1[0]}, pos={worst1[1]})")
    if first_bad1:
        print(f"stage 1 first cell above bound {BOUND}: (layer={first_bad1[0]}, pos={first_bad1[1]})")
        print("RESULT: FAIL")
        return 1
    print("stage 1: PASS")

    # Stage 2: layers 0..27 (112 cells)
    print("stage 2: layers 0-27 (112 cells)")
    _, max2, worst2, first_bad2 = compare_cells(range(ORACLE_BLOCKS))
    print(f"stage 2 max rel L2 = {max2:.6e} at (layer={worst2[0]}, pos={worst2[1]})")
    if first_bad2:
        print(f"stage 2 first cell above bound {BOUND}: (layer={first_bad2[0]}, pos={first_bad2[1]})")
        print("RESULT: FAIL")
        return 1
    print("stage 2: PASS")

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
