#!/usr/bin/env python3
import numpy as np, sys
path = sys.argv[1]
n_pos, n_layer, n_embd = 4, 28, 2048
arr = np.fromfile(path, dtype=np.float32).reshape(n_pos, n_layer, n_embd)
print(f"shape: {arr.shape}")
print(f"non-zero rows per position: {[(p, np.any(arr[p]!=0, axis=1).sum()) for p in range(n_pos)]}")
print(f"L0 vs L1 L2 norm (last pos): {np.linalg.norm(arr[-1,0]-arr[-1,1]):.6f}")
print(f"L0 vs L1 dot (last pos): {np.dot(arr[-1,0], arr[-1,1]):.6f}")
print(f"any nan/inf: {np.isnan(arr).any() or np.isinf(arr).any()}")
