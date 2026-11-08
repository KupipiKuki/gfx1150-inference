import sys, time
sys.path.insert(0, "/home/kupipi/Documents/git/gfx1150-inference/build")
sys.path.insert(0, "/home/kupipi/Documents/git/gfx1150-inference/src")
import numpy as np
import matmul_module

hidden, inter, heads, kvh, hd = 32, 64, 4, 2, 8
q_dim, kv_dim = heads * hd, kvh * hd
matmul_module.kv_cache_init(2, 64, kvh, hd)
x_in = np.zeros((1, hidden), dtype=np.float16)
x_out = np.zeros((1, hidden), dtype=np.float16)
norm_w = np.ones(hidden, dtype=np.float16)
def w(r, c): return np.zeros((r, c), dtype=np.float16).reshape(-1)
def call():
    matmul_module.forward_layer_cached(
        x_in, x_out, norm_w,
        w(q_dim, hidden), 1, w(kv_dim, hidden), 1, w(kv_dim, hidden), 1,
        w(hidden, q_dim), 1, norm_w, w(inter, hidden), 1, w(inter, hidden), 1,
        w(hidden, inter), 1, 0, 1, 0, hidden, inter, heads, kvh, hd,
        1e-5, 10000.0, False, 0.04)
call()  # cold: workspace growth (drains happen here)
time.sleep(0.3)
call()  # warm call 1
time.sleep(0.3)
call()  # warm call 2
time.sleep(0.3)
print("WARM_TWO_CALLS_DONE")
