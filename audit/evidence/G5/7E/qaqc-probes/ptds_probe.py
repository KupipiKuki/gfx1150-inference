#!/usr/bin/env python3
"""7E per-thread-default-stream probe: imports the PTDS build FIRST, then runs
deterministic correctness plus a non-main-thread stress of the layer path."""
import hashlib
import os
import sys
import tempfile
import threading

ROOT = "/home/kupipi/Documents/git/gfx1150-inference"
ptds = os.environ.get("GFX1150_7E_MODULE_DIR", os.path.join(ROOT, "build-ptds"))
sys.path.insert(0, ptds)  # MUST be imported before tests helpers prepend ./build
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import numpy as np
import matmul_module

print(f"module: {matmul_module.__file__}")
with open(matmul_module.__file__, "rb") as fh:
    print(f"module sha256[:12]: {hashlib.sha256(fh.read()).hexdigest()[:12]}")

from test_phase5_scale import _build_synthetic_q4km_model
import inference as inference_mod

with tempfile.TemporaryDirectory() as tmpdir:
    model = os.path.join(tmpdir, "q4km.gguf")
    _build_synthetic_q4km_model(model, num_layers=2)
    prompt = [1, 15, 20, 23, 4, 5]
    with inference_mod.LlamaInferenceEngine(model, max_seq_len=128) as eng:
        logits = eng.prefill_tokens(prompt)
        d = hashlib.sha256(np.ascontiguousarray(logits, dtype=np.float16).tobytes()).hexdigest()
        ids, _ = eng.generate_ids(prompt, max_new_tokens=8, temperature=0.0, stop_on_eos=False)
    print(f"prefill_logits_sha256={d}")
    print(f"greedy_ids={ids}")

    # Non-main-thread stress: one thread at a time (the GPU workspaces are
    # process-global and mutex-guarded); exercises per-thread default-stream
    # semantics since the PTDS build routes every implicit stream-0 call
    # through the CALLING THREAD's default stream.
    errors = []

    def run_engine_loop(n, seed):
        try:
            rng = np.random.default_rng(seed)
            with inference_mod.LlamaInferenceEngine(model, max_seq_len=192) as eng2:
                for i in range(n):
                    k = 2 + (i % 5)
                    p = list(rng.integers(0, 28, size=k))
                    _ = eng2.forward_tokens(p, pos_offset=0, compute_logits=False)
                    _ = eng2.forward_tokens([int(p[0])], pos_offset=1, compute_logits=False)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=run_engine_loop, args=(6, s)) for s in (1, 2, 3, 4)]
    for t in threads:
        t.start()
        t.join()  # sequential: single GPU workspace set, no concurrent use
    if errors:
        print(f"THREAD-STRESS FAIL: {errors}")
        sys.exit(3)
    print("non-main-thread (sequential) stress: OK, no errors")
print("PTDS PROBE OK")
