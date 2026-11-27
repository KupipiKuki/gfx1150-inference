#!/usr/bin/env python3
"""Compute KL divergences between full-logits dumps for S5.

Each dump is a flat binary file of f32 values shaped [n_step][n_vocab].
KL is computed over the full vocabulary distribution at each step:
    KL(P||Q) = sum_i P_i * (log P_i - log Q_i)   [nats]

Usage:
    python3 compute_kl.py --engine engine_logits.bin --q4k q4k_logits.bin --f32 f32_logits.bin [--prompt P1]
"""

import argparse
import math
import struct
import sys
from pathlib import Path


def load_logits(path: str):
    p = Path(path)
    data = p.read_bytes()
    n_floats = len(data) // 4
    vals = struct.unpack(f"<{n_floats}f", data)
    # shape [step][vocab]; determine vocab from file size (must be divisible by step count)
    return vals


def softmax(logits):
    m = max(logits)
    exps = [math.exp(v - m) for v in logits]
    s = sum(exps)
    return [e / s for e in exps]


def kl_divergence(p, q):
    """KL(P||Q) in nats. Inputs are probability vectors."""
    s = 0.0
    for pi, qi in zip(p, q):
        if pi > 0.0:
            s += pi * (math.log(pi) - math.log(qi))
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--q4k", required=True)
    parser.add_argument("--f32", required=True)
    parser.add_argument("--prompt", default="P")
    parser.add_argument("--steps", type=int, default=16)
    args = parser.parse_args()

    engine = load_logits(args.engine)
    q4k = load_logits(args.q4k)
    f32 = load_logits(args.f32)

    n = len(engine)
    if n != len(q4k) or n != len(f32):
        print(f"size mismatch: engine={len(engine)} q4k={len(q4k)} f32={len(f32)}", file=sys.stderr)
        sys.exit(1)
    if n % args.steps != 0:
        print(f"cannot infer vocab: {n} floats is not divisible by {args.steps} steps", file=sys.stderr)
        sys.exit(1)
    n_vocab = n // args.steps

    rows = []
    for step in range(args.steps):
        off = step * n_vocab
        e = softmax(engine[off:off + n_vocab])
        q = softmax(q4k[off:off + n_vocab])
        f = softmax(f32[off:off + n_vocab])
        rows.append((
            step,
            kl_divergence(e, f),
            kl_divergence(e, q),
            kl_divergence(q, f),
        ))

    print(f"# KL table — {args.prompt} — vocab={n_vocab}, steps={args.steps}")
    print("| step | KL(engine‖f32) | KL(engine‖Q4_K) | KL(Q4_K‖f32) |")
    print("|---|---|---|---|")
    for step, k_ef, k_eq, k_qf in rows:
        print(f"| {step} | {k_ef:.6e} | {k_eq:.6e} | {k_qf:.6e} |")

    mean_ef = sum(r[1] for r in rows) / len(rows)
    mean_eq = sum(r[2] for r in rows) / len(rows)
    mean_qf = sum(r[3] for r in rows) / len(rows)
    max_ef = max(r[1] for r in rows)
    max_eq = max(r[2] for r in rows)
    max_qf = max(r[3] for r in rows)

    print()
    print(f"{args.prompt} mean KL(engine‖f32) = {mean_ef:.6e}  max step = {max_ef:.6e}")
    print(f"{args.prompt} mean KL(engine‖Q4_K) = {mean_eq:.6e}  max step = {max_eq:.6e}")
    print(f"{args.prompt} mean KL(Q4_K‖f32)   = {mean_qf:.6e}  max step = {max_qf:.6e}")
    print()
    ok = mean_ef <= 1e-2 and max_ef <= 1e-1
    print(f"DEC-047 ceiling: mean <= 1e-2 and no step > 1e-1 -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
