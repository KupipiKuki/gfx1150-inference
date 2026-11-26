#!/usr/bin/env python3
"""Compare a DeepSeek parity engine dump against the HO-014 exact-f32 oracle.

Two modes:
* Free-running: --dump is an engine dump with layout [position][slot][hidden],
  slot 0 = input residual, slot l+1 = after block l.  --slots must be 28.
* Teacher-forced: --teacher-outputs is a [layer][position][hidden] f32 dump of
  single-block runs starting from the reference residual/KV.  This is the gate.

Oracle layout in both modes: [position][block][hidden], blocks 0..27.
The bound is fixed at 5e-3 and is printed on every run.
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


def rel_l2(a, b):
    num2 = sum((x - y) ** 2 for x, y in zip(a, b))
    den2 = sum(y ** 2 for y in b)
    return math.sqrt(num2 / den2) if den2 > 0 else (math.sqrt(num2) if num2 > 0 else 0.0)


def compare_cells(dump_cells, oracle_arr):
    """dump_cells[(l,p)] -> vector; oracle_arr[p] is a flat [layer*hidden] array."""
    errors = []
    for (l, p) in sorted(dump_cells):
        e = dump_cells[(l, p)]
        o = oracle_arr[p][l * HIDDEN:(l + 1) * HIDDEN]
        rel = rel_l2(e, o)
        errors.append(((l, p), rel))
        print(f"  cell (layer={l}, pos={p}): rel L2 = {rel:.6e}")
    vals = [e for _, e in errors]
    max_err = max(vals)
    worst = max(errors, key=lambda x: x[1])[0]
    median = sorted(vals)[len(vals) // 2] if len(vals) % 2 else (
        sorted(vals)[len(vals) // 2 - 1] + sorted(vals)[len(vals) // 2]) / 2
    first_bad = next((cell for cell, e in errors if e > BOUND), None)
    return errors, max_err, worst, median, first_bad


def stage_report(name, layers, dump_cells, oracle_arr):
    print(f"{name}: layers {layers[0]}-{layers[-1]} ({len(layers) * 4} cells)")
    _, max_err, worst, median, first_bad = compare_cells(
        {(l, p): dump_cells[(l, p)] for l in layers for p in range(4)}, oracle_arr)
    print(f"{name} median rel L2 = {median:.6e}")
    print(f"{name} max rel L2    = {max_err:.6e} at (layer={worst[0]}, pos={worst[1]})")
    if first_bad:
        print(f"{name} first cell above bound {BOUND}: (layer={first_bad[0]}, pos={first_bad[1]})")
        return False
    print(f"{name}: PASS")
    return True


def main():
    parser = argparse.ArgumentParser(description="Compare parity engine dump to exact-f32 oracle")
    parser.add_argument("--oracle", required=True, help="oracle .bin file")
    parser.add_argument("--dump", help="free-running engine .bin dump")
    parser.add_argument("--slots", type=int, help="number of layers computed (input + N layers total)")
    parser.add_argument("--teacher-outputs", help="teacher-forced outputs .bin file [layer][pos][hidden]")
    parser.add_argument("--shape-only", action="store_true", help="only check size and finiteness")
    parser.add_argument("--floor", action="store_true", help="report max without gating (informative Q4_K floor)")
    args = parser.parse_args()

    print(f"bound = {BOUND:.6e}  (fixed, not caller-supplied)")

    if not args.dump and not args.teacher_outputs:
        raise ValueError("need either --dump (free-running) or --teacher-outputs (teacher-forced)")
    if args.dump and args.teacher_outputs:
        raise ValueError("--dump and --teacher-outputs are mutually exclusive")

    oracle, oracle_n = load(args.oracle, "oracle")
    if oracle_n != 4 * ORACLE_BLOCKS * HIDDEN:
        raise ValueError(f"oracle: expected {4*ORACLE_BLOCKS*HIDDEN} floats, got {oracle_n}")
    oracle_arr = [oracle[i * ORACLE_BLOCKS * HIDDEN:(i + 1) * ORACLE_BLOCKS * HIDDEN]
                  for i in range(4)]

    dump_cells = {}  # (layer, pos) -> vector

    if args.teacher_outputs:
        data, data_n = load(args.teacher_outputs, "teacher outputs")
        want = ORACLE_BLOCKS * 4 * HIDDEN
        if data_n != want:
            raise ValueError(f"teacher outputs: expected {want} floats, got {data_n}")
        for l in range(ORACLE_BLOCKS):
            for p in range(4):
                dump_cells[(l, p)] = data[((l * 4) + p) * HIDDEN:((l * 4) + p + 1) * HIDDEN]
        print(f"teacher outputs: {ORACLE_BLOCKS} layers x 4 positions x {HIDDEN}")
    else:
        if args.slots is None:
            raise ValueError("--slots is required with --dump")
        if args.slots != ORACLE_BLOCKS:
            raise ValueError(f"--slots must be {ORACLE_BLOCKS} layers, got {args.slots}")
        slots_per_record = ORACLE_BLOCKS + 1

        dump, dump_n = load(args.dump, "engine dump")
        if dump_n % HIDDEN != 0:
            raise ValueError(f"dump: {dump_n} floats is not a multiple of hidden={HIDDEN}")
        R = dump_n // HIDDEN
        if R % slots_per_record != 0:
            raise ValueError(f"dump: {R} slots total is not divisible by {slots_per_record}")
        records = R // slots_per_record
        if records < 4:
            raise ValueError(f"dump: expected at least 4 records, got {records}")
        print(f"engine dump: {records} records, {slots_per_record} slots/record, N={ORACLE_BLOCKS} blocks computed")
        for p in range(4):
            base = p * slots_per_record * HIDDEN
            for l in range(ORACLE_BLOCKS):
                dump_cells[(l, p)] = dump[base + (l + 1) * HIDDEN:base + (l + 2) * HIDDEN]

    print(f"oracle: 4 records, {ORACLE_BLOCKS} blocks")

    bad = 0
    for v in dump_cells.values():
        for x in v:
            if not math.isfinite(x):
                bad += 1
    print(f"non-finite values in kept dump: {bad}")
    if bad:
        print("RESULT: FAIL")
        return 1

    if args.shape_only:
        print("RESULT: PASS (shape only)")
        return 0

    if args.floor:
        _, max_err, worst, median, _ = compare_cells(dump_cells, oracle_arr)
        print(f"median rel L2 = {median:.6e}")
        print(f"max rel L2    = {max_err:.6e} at (layer={worst[0]}, pos={worst[1]})")
        print("RESULT: FLOOR (not gated)")
        return 0

    # Stage 1: layers 1..27 (108 cells)
    ok1 = stage_report("stage 1", list(range(1, ORACLE_BLOCKS)), dump_cells, oracle_arr)
    if not ok1:
        print("RESULT: FAIL")
        return 1

    # Stage 2: layers 0..27 (112 cells)
    ok2 = stage_report("stage 2", list(range(ORACLE_BLOCKS)), dump_cells, oracle_arr)
    if not ok2:
        print("RESULT: FAIL")
        return 1

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
