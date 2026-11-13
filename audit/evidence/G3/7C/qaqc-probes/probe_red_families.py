#!/usr/bin/env python3
"""
QAQC probe (7C): red/green family evidence on the engine paths.

Runs on both the parent 8426ec6 and the 7C candidate without importing
`model_spec` (which does not exist on the parent):

- builds the synthetic *fused* Phi-3 fixture and runs `LlamaInferenceEngine`
  forward. Expected on the parent: hard failure (missing separate
  `attn_q.weight` / fused `attn_qkv` unsupported -> KeyError), because the
  pre-7C layer had only the hardcoded llama tensor map.
- builds the synthetic Gemma fixture (embedding scale, GeGLU, NeoX,
  key_length/value_length, softcap, tied output) and runs the engine forward,
  comparing the logits with the independent FP32 NumPy reference
  (`tests/reference_model.py`). Expected on the parent: either a hard shape
  failure or wrong logits (head_dim defaults to hidden//heads == 24 instead of
  the explicit 32, no sqrt(hidden) embedding scale, SwiGLU instead of GeGLU,
  adjacent-pair instead of NeoX rope); on the candidate: max_err < 6e-3.

Exit code 0 iff every family probe passes (green); non-zero on the parent.
"""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
_BUILD = os.path.join(_ROOT, "build")
for _p in (_SRC, _TESTS, _BUILD):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import family_fixtures  # noqa: E402
import reference_model  # noqa: E402

PROMPT = [1, 7, 10, 11]
TOL = 6e-3


def probe_phi3(tag: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "phi3-fused-f16.gguf")
        family_fixtures.build_phi3_gguf(
            path, np.random.default_rng(71155), layout="fused", quant="f16",
            biases=True, ffn_biases=True,
        )
        from inference import LlamaInferenceEngine

        try:
            with LlamaInferenceEngine(path, max_seq_len=64) as engine:
                logits = engine.forward_tokens(PROMPT, pos_offset=0)
        except Exception as exc:  # noqa: BLE001 - the red log records the reason
            print(f"[phi3] {tag}: FAIL (engine refused/raised) -> {type(exc).__name__}: {exc}")
            return False
        metadata, weights = reference_model.load_gguf_weights(path)
        params = reference_model.resolve_ref_params(metadata)
        ref = reference_model.ref_forward(weights, params, PROMPT)
        err = float(np.max(np.abs(logits.astype(np.float32) - ref)))
        ok = err < TOL
        print(
            f"[phi3] {tag}: {'PASS' if ok else 'FAIL'} "
            f"(fused QKV + fused gate/up + biases vs independent FP32 reference, "
            f"max_err={err:.6f}, tol={TOL})"
        )
        return ok


def probe_gemma(tag: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "gemma-f16-softcap.gguf")
        family_fixtures.build_gemma_gguf(
            path, np.random.default_rng(71160), quant="f16",
            final_logit_softcapping=30.0,
        )
        from inference import LlamaInferenceEngine

        try:
            with LlamaInferenceEngine(path, max_seq_len=64) as engine:
                logits = engine.forward_tokens(PROMPT, pos_offset=0)
        except Exception as exc:  # noqa: BLE001
            print(f"[gemma] {tag}: FAIL (engine refused/raised) -> {type(exc).__name__}: {exc}")
            return False
        metadata, weights = reference_model.load_gguf_weights(path)
        params = reference_model.resolve_ref_params(metadata)
        ref = reference_model.ref_forward(weights, params, PROMPT)
        err = float(np.max(np.abs(logits.astype(np.float32) - ref)))
        ok = err < TOL
        print(
            f"[gemma] {tag}: {'PASS' if ok else 'FAIL'} "
            f"(embed scale + GeGLU + NeoX + key/value dims + softcap + tied output "
            f"vs independent FP32 reference, max_err={err:.6f}, tol={TOL})"
        )
        return ok


def main() -> int:
    results = [probe_phi3("engine-forward"), probe_gemma("engine-forward")]
    print(f"probe families: {'ALL GREEN' if all(results) else 'RED'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
