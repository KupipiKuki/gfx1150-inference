#!/usr/bin/env python3
"""Check a per-layer hidden-state dump for shape and non-degeneracy.

The file is expected to contain float32 data for n_pos prompt positions,
n_layer transformer layers, and n_embd hidden units.  n_embd is derived from
file size and the supplied --layers count so the helper stays family-agnostic.
"""
import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser(description="Check layer dump shape and non-degeneracy")
    ap.add_argument("path", help="path to the float32 layer dump")
    ap.add_argument("--layers", type=int, required=True, help="number of transformer layers")
    ap.add_argument("--pos", type=int, default=4, help="number of prompt positions (default: 4)")
    args = ap.parse_args()

    data = np.fromfile(args.path, dtype=np.float32)
    n_floats = data.size
    n_pos = args.pos
    n_layer = args.layers
    if n_floats % (n_pos * n_layer) != 0:
        raise ValueError(
            f"cannot reshape {n_floats} floats into ({n_pos},{n_layer},*)"
        )
    n_embd = n_floats // (n_pos * n_layer)
    arr = data.reshape(n_pos, n_layer, n_embd)

    print(f"shape: {arr.shape}")
    print(f"non-zero rows per position: {[(p, int(np.any(arr[p] != 0, axis=1).sum())) for p in range(n_pos)]}")
    print(f"L0 vs L1 L2 norm (last pos): {np.linalg.norm(arr[-1, 0] - arr[-1, 1]):.6f}")
    print(f"L0 vs L1 dot (last pos): {np.dot(arr[-1, 0], arr[-1, 1]):.6f}")
    print(f"any nan/inf: {np.isnan(arr).any() or np.isinf(arr).any()}")


if __name__ == "__main__":
    main()
