import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.getcwd(), 'build'))
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
import matmul_module
hidden, inter, heads, kvh, hd = 32, 64, 4, 2, 8
q_dim, kv_dim = heads*hd, kvh*hd
seq=3
x_in=np.zeros((seq,hidden),dtype=np.float16); x_out=np.zeros((seq,hidden),dtype=np.float16)
norm=np.ones(hidden,dtype=np.float16)
def w(n,k): return np.zeros((n,k),dtype=np.float16).reshape(-1)
matmul_module.kv_cache_init(2,64,kvh,hd)
matmul_module.forward_layer_cached(x_in,x_out,norm,
  w(q_dim,hidden),1,w(kv_dim,hidden),1,w(kv_dim,hidden),1,w(hidden,q_dim),1,
  norm,w(inter,hidden),1,w(inter,hidden),1,w(hidden,inter),1,
  0,seq,0,hidden,inter,heads,kvh,hd,1e-5,10000.0,False,0.0442)
pass
matmul_module.forward_layer_cached(x_in,x_out,norm,
  w(q_dim,hidden),1,w(kv_dim,hidden),1,w(kv_dim,hidden),1,w(hidden,q_dim),1,
  norm,w(inter,hidden),1,w(inter,hidden),1,w(hidden,inter),1,
  0,seq,0,hidden,inter,heads,kvh,hd,1e-5,10000.0,False,0.0442)
print('done')
