#!/usr/bin/env python3
"""Top-2 margin per generation step from a full-logits dump.

Reads a flat [steps][n_vocab] f32 dump and prints, for each step, the
sampled token id (argmax; ties -> lowest id, the engine's greedy rule), the
runner-up id, and the logit gap top1 - top2.  Used to show the token gate was
not a near-tie at any step (HO-STRATA-016; the margins the handoff requires to
be on record per §1.1).

Usage: python3 top2_margin.py DUMP.bin [--steps 16] [--label NAME]
"""
import argparse
import struct
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--steps", type=int, default=16)
    ap.add_argument("--label", default="")
    ap.add_argument("--vocab", type=int, default=102400)
    args = ap.parse_args()

    data = Path(args.dump).read_bytes()
    n = len(data) // 4
    if n % args.vocab != 0:
        print(f"size {len(data)} is not a whole number of vocab rows", file=sys.stderr)
        sys.exit(1)
    steps = n // args.vocab
    vals = struct.unpack(f"<{n}f", data)

    print(f"# top-2 margins — {args.label or args.dump} — steps={steps}, vocab={args.vocab}")
    print("| step | sampled id | top1 logit | runner-up id | top2 logit | margin (top1-top2) |")
    print("|---|---|---|---|---|---|")
    for s in range(steps):
        row = vals[s * args.vocab:(s + 1) * args.vocab]
        best = 0
        for i in range(1, len(row)):
            if row[i] > row[best]:
                best = i
        second = None
        for i in range(len(row)):
            if i == best:
                continue
            if second is None or row[i] > row[second]:
                second = i
        print(f"| {s} | {best} | {row[best]:.6f} | {second} | {row[second]:.6f} | {row[best] - row[second]:.6e} |")


if __name__ == "__main__":
    main()
