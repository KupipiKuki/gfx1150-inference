#!/usr/bin/env python3
"""7E correctness probe: deterministic greedy generation + logits digest.

Runs the synthetic Q4_K_M model from tests/test_phase5_scale.py through the
full engine (CPU-independent GPU forward path incl. forward_layer_cached),
prints the greedy token IDs and a digest of prefill logits. Parent-vs-candidate
outputs must match identically (or within documented FP16 tolerance, aim: identical).
"""
import os
import sys

ROOT = "/home/kupipi/Documents/git/gfx1150-inference"
sys.path.insert(0, os.path.join(ROOT, "build"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np
import matmul_module  # noqa: F401  (must import cleanly)
from test_phase5_scale import _build_synthetic_q4km_model  # noqa: E402
import tempfile
import hashlib
import inference as inference_mod


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        model = os.path.join(tmpdir, "q4km.gguf")
        _build_synthetic_q4km_model(model, num_layers=2)
        prompt_ids = [1, 15, 20, 23, 4, 5]
        with inference_mod.LlamaInferenceEngine(model, max_seq_len=128) as eng:
            logits = eng.prefill_tokens(prompt_ids)
            digest = hashlib.sha256(
                np.ascontiguousarray(logits, dtype=np.float16).tobytes()
            ).hexdigest()
            print(f"logits_shape={logits.shape}")
            print(f"prefill_logits_sha256={digest}")
            ids_full, m = eng.generate_ids(prompt_ids, max_new_tokens=8, temperature=0.0, stop_on_eos=False)
            print(f"greedy_ids={ids_full}")
            # decode step with cached path (pos>0) also deterministic
            step_logits = eng.forward_tokens([ids_full[-1]], pos_offset=len(prompt_ids) + len(ids_full) - 1)
            print(f"decode_logits_sha256={hashlib.sha256(np.ascontiguousarray(step_logits, dtype=np.float16).tobytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
