# 7E event graph — explicit copy/compute stream topology

`launch_forward_layer_cached_fp16` (`src/kernels/attention.hip`) runs entirely
on two streams owned by `DeviceLayerWorkspace`. No kernel is launched on the
NULL stream; no `hipStreamWaitEvent(0, ...)` exists anywhere in
`src/kernels/**` (enforced by `tests/test_harness_contract.py::test_layer_path_explicit_stream_contract`
and `qaqc-probes/stream_source_scan.py`).

Legend: `--wait-->` = `hipStreamWaitEvent` (stream waits on the event);
`--rec-->` = `hipEventRecord` on the stream.

## Stream setup (per process, created lazily by `ensure()`)

```
copy_stream                     compute_stream
copy_done[2], compute_done[2]   inputs_done, ffn_norm_done,
                                norm_consumed, layer_out_ready
```

## Per layer (entry state: previous layer's boundary sync drained everything)

```
copy_stream:    memcpyAsync(d_x <- h_x_in)
                memcpyAsync(d_norm_w <- h_attn_norm_w)
                --rec--> inputs_done
                     compute_stream: --wait--> inputs_done
                     rmsnorm_kernel(d_x, d_norm_w -> d_normed)
                     --rec--> norm_consumed

projections p in {q=0, k=1, v=2, o=3, gate=4, up=5, down=6}; slot = p%2:

  copy_stream:    --wait--> compute_done[slot]        (slot's previous
                  stage h_w: hipHostRegister (page        consumer done)
                  aligned) or pinned-slab memcpy
                  memcpyAsync(d_w[slot] <- staged)
                  --rec--> copy_done[slot]
                     compute_stream: --wait--> copy_done[slot]
                     matmul_*_device(d_in, d_w[slot] -> d_out, compute_stream)
                     --rec--> compute_done[slot]

  (the copy of projection p+1 overlaps the kernel of projection p on a
   different slot and a different stream)

copy_stream:    --wait--> norm_consumed          (d_norm_w reuse safe)
                memcpyAsync(d_norm_w <- h_ffn_norm_w)
                --rec--> ffn_norm_done
                     compute_stream: --wait--> ffn_norm_done
                     rmsnorm_residual_kernel(...)
                     rope_kernel(q), rope_kernel(k)          [compute stream]
                     gqa attention:                            [compute stream]
                       memcpyAsync D2D K,V into pool; gqa_online_softmax_kernel
                     swiglu_kernel, residual_add_kernel       [compute stream]

                     --rec--> layer_out_ready

D2H boundary sync (the only hipStreamSynchronize in the layer path):
copy_stream:    --wait--> layer_out_ready
                memcpyAsync(h_x_out <- d_x)
                hipStreamSynchronize(copy_stream)      <-- 1 sync per layer
```

## Drains (7E-3)

- `DeviceLayerWorkspace::ensure()` / `ensure_weight_slot()`: on growth, both
  streams are synchronized *before* any `hipFree` (grow-only buffers).
- Layer RAII guard: on any exception after enqueue, `drain()` syncs both
  streams and unregisters all `hipHostRegister` spans before unwinding.
- Destructor: `drain()`, then frees, then destroys events, then streams —
  nothing destroyed with pending work.
- `AttentionWorkspace::ensure` realloc paths sync the NULL stream first;
  `DeviceKVCachePool::release()` performs `hipDeviceSynchronize()` before
  freeing (the D2D writes land on the layer compute stream).
- Normal-path layer end also unregisters registered spans after the boundary
  sync (paired registration; no leak).

## Slot-reuse safety

`copy_done[slot]` is recorded when the slot's staged copy completes;
`compute_done[slot]` after the consuming kernel. The copy stream waits on
`compute_done[slot]` before overwriting a slot, so a weight copy never
overwrites data a kernel is still reading. The pinned-slab fallback waits on
its own previous `copy_done[slot]` before the host `memcpy` reuses the slab.

## Sync count

Exactly one `hipStreamSynchronize` per `launch_forward_layer_cached_fp16`
call (the layer boundary). The Python `forward_layer_cached` API returns
host hidden states per layer, so a token through an N-layer model performs
**N syncs per token** — the brief's documented G5 boundary; no
one-sync/token claim.
