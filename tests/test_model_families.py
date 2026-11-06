#!/usr/bin/env python3
"""
Phase 7C model-family engine tests (GPU lane): Phi-3, Gemma, and the
llama-family regression.

Every test imports the engine (which needs the HIP extension) inside the test
body so the module still collects on a CPU-only host; the module-level
`pytestmark` puts it in the `gpu` lane per the harness contract
(`tests/test_harness_contract.py::EXPECTED_LANES`).

Expected values come from the *independent* FP32 NumPy reference
(`tests/reference_model.py` — it resolves family parameters from the GGUF
metadata itself and never calls the engine) and, for the llama regression,
from the goldens captured on the parent commit 8426ec6 by
`audit/evidence/G3/7C/qaqc-probes/probe_llama_regression.py`.
"""

import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (os.path.join(_ROOT, "src"), _HERE, os.path.join(_ROOT, "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import family_fixtures  # noqa: E402
import reference_model  # noqa: E402

pytestmark = [pytest.mark.gpu]

_LLM_TOL = 6e-3  # engine runs FP16 activations vs the FP32 reference


def _engine_logits(gguf_path, prompt_ids):
    from inference import LlamaInferenceEngine

    with LlamaInferenceEngine(gguf_path, max_seq_len=64) as engine:
        return engine.forward_tokens(prompt_ids, pos_offset=0)


def _ref_logits(gguf_path, token_ids):
    metadata, weights = reference_model.load_gguf_weights(gguf_path)
    params = reference_model.resolve_ref_params(metadata)
    return reference_model.ref_forward(weights, params, token_ids)


# ===========================================================================
# 7C-2 -- Phi-3: fused attn_qkv + fused gate/up ffn_up (+ optional biases)
# ===========================================================================


@pytest.mark.gpu
def test_phi3_fused_logits_match_independent_reference(tmp_path):
    """Fused attn_qkv + fused gate/up ffn_up + biases + NeoX, F16 weights."""
    path = str(tmp_path / "phi3-fused-f16.gguf")
    family_fixtures.build_phi3_gguf(
        path, np.random.default_rng(71155), layout="fused", quant="f16",
        biases=True, ffn_biases=True,
    )
    prompt = [1, 7, 10, 11]
    from inference import LlamaInferenceEngine

    metadata, weights = reference_model.load_gguf_weights(path)
    params = reference_model.resolve_ref_params(metadata)
    assert params["neox"] is True and params["ffn_act"] == "swiglu"

    with LlamaInferenceEngine(path, max_seq_len=64) as engine:
        assert engine.spec.arch == "phi3"
        assert engine.spec.fused_qkv is True
        assert engine.spec.ffn_fused_gate_up is True
        logits_pre = engine.forward_tokens(prompt, pos_offset=0)
        probe = int(np.argmax(logits_pre))
        logits_dec = engine.forward_tokens([probe], pos_offset=len(prompt))
    ref_pre = reference_model.ref_forward(weights, params, prompt)
    ref_dec = reference_model.ref_forward(weights, params, list(prompt) + [probe])

    err_pre = float(np.max(np.abs(logits_pre.astype(np.float32) - ref_pre)))
    err_dec = float(np.max(np.abs(logits_dec.astype(np.float32) - ref_dec)))
    assert err_pre < _LLM_TOL, f"phi3 prefill max err {err_pre}"
    assert err_dec < _LLM_TOL, f"phi3 decode max err {err_dec}"
    assert int(np.argmax(logits_pre)) == int(np.argmax(ref_pre))


@pytest.mark.gpu
def test_phi3_quantized_fused_matches_reference(tmp_path):
    """A mixed Q4_K/Q6_K fused Phi-3 fixture exercises the quantized fused paths.

    Dims are 256-aligned because the Q4_K/Q6_K matmul kernels require K to be
    a multiple of 256 (the real 3072-hidden files satisfy this naturally).
    """
    path = str(tmp_path / "phi3-fused-q4km.gguf")
    family_fixtures.build_phi3_gguf(
        path, np.random.default_rng(71156), layout="fused", quant="q4km",
        biases=False, ffn_biases=False,
        hidden=256, inter=256, num_heads=4, num_kv_heads=2, head_dim=64,
    )
    prompt = [1, 7, 10, 11]
    logits = _engine_logits(path, prompt)
    ref = _ref_logits(path, prompt)
    err = float(np.max(np.abs(logits.astype(np.float32) - ref)))
    assert err < _LLM_TOL, f"phi3 q4 fused max err {err}"
    assert int(np.argmax(logits)) == int(np.argmax(ref))


@pytest.mark.gpu
def test_phi3_fused_and_separate_equivalence(tmp_path):
    """Fused attn_qkv/ffn_up and legacy separate layouts agree on logits."""
    fused_path = str(tmp_path / "phi3-fused.gguf")
    separate_path = str(tmp_path / "phi3-separate.gguf")
    # Identical seed => identical weights; only the tensor layout differs.
    family_fixtures.build_phi3_gguf(
        fused_path, np.random.default_rng(71157), layout="fused", quant="f16",
        biases=True, ffn_biases=True,
    )
    family_fixtures.build_phi3_gguf(
        separate_path, np.random.default_rng(71157), layout="separate",
        quant="f16", biases=True, ffn_biases=True,
    )
    prompt = [1, 4, 9]
    l_fused = _engine_logits(fused_path, prompt)
    l_separate = _engine_logits(separate_path, prompt)
    err = float(np.max(np.abs(l_fused.astype(np.float32) - l_separate.astype(np.float32))))
    assert err < 1e-3, f"fused vs separate max err {err}"


@pytest.mark.gpu
def test_phi3_zero_bias_equals_no_bias(tmp_path):
    """Zero-valued fused biases reproduce the no-bias logits exactly."""
    no_bias = str(tmp_path / "phi3-nobias.gguf")
    zero_bias = str(tmp_path / "phi3-zerobias.gguf")
    family_fixtures.build_phi3_gguf(
        no_bias, np.random.default_rng(71158), layout="fused", quant="f16",
        biases=False, ffn_biases=False,
    )
    family_fixtures.build_phi3_gguf(
        zero_bias, np.random.default_rng(71158), layout="fused", quant="f16",
        biases=True, ffn_biases=True, bias_scale=0.0,
    )
    prompt = [1, 7, 10, 11]
    l0 = _engine_logits(no_bias, prompt)
    l1 = _engine_logits(zero_bias, prompt)
    err = float(np.max(np.abs(l0.astype(np.float32) - l1.astype(np.float32))))
    assert err < 1e-6, f"zero-bias vs no-bias max err {err}"


@pytest.mark.gpu
def test_phi3_generation_smoke(tmp_path):
    """Greedy generation is deterministic and matches the reference argmax chain."""
    path = str(tmp_path / "phi3-gen.gguf")
    family_fixtures.build_phi3_gguf(
        path, np.random.default_rng(71159), layout="fused", quant="f16",
        biases=True, ffn_biases=True,
    )
    from inference import LlamaInferenceEngine

    prompt = [1, 7]
    with LlamaInferenceEngine(path, max_seq_len=64) as engine:
        new_ids, _metrics = engine.generate_ids(
            prompt, max_new_tokens=4, temperature=0.0
        )
    metadata, weights = reference_model.load_gguf_weights(path)
    params = reference_model.resolve_ref_params(metadata)
    ref_ids = list(prompt)
    for _ in range(4):
        nxt = int(np.argmax(reference_model.ref_forward(weights, params, ref_ids)))
        ref_ids.append(nxt)
    assert new_ids == ref_ids[2:], f"phi3 generated {new_ids}, reference {ref_ids[2:]}"


# ===========================================================================
# 7C-3 -- Gemma: embedding scale + GeGLU + NeoX + key/value dims + softcap + tied
# ===========================================================================


@pytest.mark.gpu
def test_gemma_logits_match_independent_reference(tmp_path):
    """Embedding scale + GeGLU + NeoX + key/value dims + softcap + tied output."""
    path = str(tmp_path / "gemma-f16-softcap.gguf")
    family_fixtures.build_gemma_gguf(
        path, np.random.default_rng(71160), quant="f16", final_logit_softcapping=30.0
    )
    prompt = [1, 7, 10, 11]
    from inference import LlamaInferenceEngine

    metadata, weights = reference_model.load_gguf_weights(path)
    params = reference_model.resolve_ref_params(metadata)
    assert params["embedding_scale"] != 1.0
    assert params["ffn_act"] == "geglu"
    assert params["neox"] is True
    assert params["final_logit_softcapping"] == 30.0
    assert "output.weight" not in weights  # tied output

    with LlamaInferenceEngine(path, max_seq_len=64) as engine:
        assert engine.spec.arch == "gemma"
        assert engine.spec.head_dim == 32  # not hidden // heads (24)
        assert engine.spec.tied_output is True
        logits_pre = engine.forward_tokens(prompt, pos_offset=0)
        probe = int(np.argmax(logits_pre))
        logits_dec = engine.forward_tokens([probe], pos_offset=len(prompt))
    ref_pre = reference_model.ref_forward(weights, params, prompt)
    ref_dec = reference_model.ref_forward(weights, params, list(prompt) + [probe])

    err_pre = float(np.max(np.abs(logits_pre.astype(np.float32) - ref_pre)))
    err_dec = float(np.max(np.abs(logits_dec.astype(np.float32) - ref_dec)))
    assert err_pre < _LLM_TOL, f"gemma prefill max err {err_pre}"
    assert err_dec < _LLM_TOL, f"gemma decode max err {err_dec}"
    assert int(np.argmax(logits_pre)) == int(np.argmax(ref_pre))


@pytest.mark.gpu
def test_gemma_absent_softcap_is_no_cap(tmp_path):
    """Without `gemma.final_logit_softcapping` the logits are uncapped."""
    softcap = str(tmp_path / "gemma-softcap.gguf")
    nocap = str(tmp_path / "gemma-nocap.gguf")
    family_fixtures.build_gemma_gguf(
        softcap, np.random.default_rng(71161), quant="f16", final_logit_softcapping=30.0
    )
    family_fixtures.build_gemma_gguf(
        nocap, np.random.default_rng(71161), quant="f16", final_logit_softcapping=None
    )
    prompt = [1, 7]
    l_cap = _engine_logits(softcap, prompt)
    l_nocap = _engine_logits(nocap, prompt)
    ref_nocap = _ref_logits(nocap, prompt)

    # The capped logits are bounded in absolute value by the cap; the uncapped
    # variant matches the (uncapped) reference so no softcap was applied to it.
    assert float(np.max(np.abs(l_cap))) <= 30.0 + 1e-3
    err_nocap = float(np.max(np.abs(l_nocap.astype(np.float32) - ref_nocap)))
    assert err_nocap < _LLM_TOL, f"gemma no-softcap max err {err_nocap}"
    # The uncapped logits must differ from the capped ones.
    assert not np.array_equal(l_cap, l_nocap)


@pytest.mark.gpu
def test_gemma_quantized_matches_reference(tmp_path):
    """Q4_K gemma fixture exercises separate attention + GeGLU, quantized.

    Dims are 256-aligned for the Q4_K kernels' K-block requirement.
    """
    path = str(tmp_path / "gemma-q4k.gguf")
    family_fixtures.build_gemma_gguf(
        path, np.random.default_rng(71162), quant="q4k", final_logit_softcapping=30.0,
        hidden=256, inter=256, num_heads=4, num_kv_heads=2, key_dim=64, value_dim=64,
    )
    prompt = [1, 7, 10]
    logits = _engine_logits(path, prompt)
    ref = _ref_logits(path, prompt)
    err = float(np.max(np.abs(logits.astype(np.float32) - ref)))
    assert err < _LLM_TOL, f"gemma q4 max err {err}"
    assert int(np.argmax(logits)) == int(np.argmax(ref))


@pytest.mark.gpu
def test_gemma_geglu_differs_from_swiglu(tmp_path):
    """A SwiGLU misimplementation for gemma would not match the reference."""
    path = str(tmp_path / "gemma-geglu.gguf")
    family_fixtures.build_gemma_gguf(
        path, np.random.default_rng(71163), quant="f16", final_logit_softcapping=None
    )
    logits = _engine_logits(path, [1, 7, 10])
    ref = _ref_logits(path, [1, 7, 10])
    err = float(np.max(np.abs(logits.astype(np.float32) - ref)))
    assert err < _LLM_TOL, err

    # Direct adversarial check: GeGLU (gelu_tanh) is measurably different from
    # the SiLU-SwiGLU the llama path uses, so a fake-SwiGLU gemma FFN would
    # fail the reference comparison above by construction.
    rng = np.random.default_rng(9)
    gate = (rng.standard_normal((64, 96)) * 2.0).astype(np.float16)
    up = (rng.standard_normal((64, 96)) * 2.0).astype(np.float16)
    from layer import geglu_host

    geglu = geglu_host(gate, up)
    silu_swiglu = ((
        gate.astype(np.float32) / (1.0 + np.exp(-gate.astype(np.float32)))
    ) * up.astype(np.float32)).astype(np.float16)
    assert float(np.max(np.abs(geglu.astype(np.float32) - silu_swiglu))) > 1e-2


# ===========================================================================
# Llama-family regression (7C-1 exit condition)
# ===========================================================================

# Goldens captured from the parent commit 8426ec6 (llama path must be unchanged
# by 7C). `audit/evidence/G3/7C/qaqc-probes/probe_llama_regression.py` produced
# byte-identical output (logits sha256, greedy token ids) on parent and
# candidate — see `audit/evidence/G3/7C/llama-regression.log`.
_LLAMA_GOLDEN_LOGITS_SHA = "a31dfc6f224d495966da14f2d06161ae2b18bf93ed7a6d5cbe8009c56f32441b"
_LLAMA_GOLDEN_IDS = [9, 15, 9, 0, 3, 9, 14, 9]


@pytest.mark.gpu
def test_llama_regression_fixed_prompt(tmp_path):
    """Llama-family logits and token IDs are unchanged on the fixed prompt/seed.

    The fixture below is the same deterministic two-layer llama GGUF that the
    QAQC probe runs on the parent and the candidate; the goldens above were
    recorded from the parent 8426ec6 run.
    """
    import hashlib
    import math

    from gguf_parser import GGMLType, GGUFValueType, quantize_q4_0_cpu, write_synthetic_gguf

    rng = np.random.default_rng(20261107)  # exact same stream / order as the probe
    intern = 256
    num_layers = 2
    hidden = 128
    num_heads = 4
    head_dim = 32
    q_dim = num_heads * head_dim
    kv_dim = 2 * head_dim
    vocab_size = 16

    def q4(rows, cols):
        w = rng.standard_normal((rows, cols), dtype=np.float32) * (1.0 / math.sqrt(cols))
        return quantize_q4_0_cpu(w)

    vocab = [
        "<unk>", "<s>", "</s>", "▁", "A", "M", "D", "▁AMD",
        "▁gfx", "1150", "▁gfx1150", "▁is", "▁fast", ".", "!", "?",
    ]
    metadata = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, num_layers),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden),
        "llama.feed_forward_length": (GGUFValueType.UINT32, intern),
        "llama.attention.head_count": (GGUFValueType.UINT32, num_heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, 2),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, head_dim),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-5),
        "llama.rope.freq_base": (GGUFValueType.FLOAT32, 10000.0),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, vocab)),
        "tokenizer.ggml.scores": (
            GGUFValueType.ARRAY,
            (GGUFValueType.FLOAT32, [float(-i) for i in range(vocab_size)]),
        ),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
        "tokenizer.ggml.add_bos_token": (GGUFValueType.BOOL, False),
    }
    tensors = [
        ("token_embd.weight", (hidden, vocab_size), GGMLType.Q4_0, q4(vocab_size, hidden).tobytes()),
        ("output_norm.weight", (hidden,), GGMLType.F16,
         (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
        ("output.weight", (hidden, vocab_size), GGMLType.Q4_0, q4(vocab_size, hidden).tobytes()),
    ]
    for il in range(num_layers):
        p = f"blk.{il}."
        tensors.extend([
            (p + "attn_norm.weight", (hidden,), GGMLType.F16,
             (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
            (p + "attn_q.weight", (hidden, q_dim), GGMLType.Q4_0, q4(q_dim, hidden).tobytes()),
            (p + "attn_k.weight", (hidden, kv_dim), GGMLType.Q4_0, q4(kv_dim, hidden).tobytes()),
            (p + "attn_v.weight", (hidden, kv_dim), GGMLType.Q4_0, q4(kv_dim, hidden).tobytes()),
            (p + "attn_output.weight", (q_dim, hidden), GGMLType.Q4_0, q4(hidden, q_dim).tobytes()),
            (p + "ffn_norm.weight", (hidden,), GGMLType.F16,
             (1.0 + 0.05 * rng.standard_normal(hidden, dtype=np.float32)).astype(np.float16).tobytes()),
            (p + "ffn_gate.weight", (hidden, intern), GGMLType.Q4_0, q4(intern, hidden).tobytes()),
            (p + "ffn_up.weight", (hidden, intern), GGMLType.Q4_0, q4(intern, hidden).tobytes()),
            (p + "ffn_down.weight", (intern, hidden), GGMLType.Q4_0, q4(hidden, intern).tobytes()),
        ])

    path = str(tmp_path / "llama-regression.gguf")
    with open(path, "wb") as f:
        write_synthetic_gguf(f, metadata, tensors)

    from inference import LlamaInferenceEngine, sample_next_token

    prompt = [1, 7, 10, 11]
    with LlamaInferenceEngine(path, max_seq_len=64) as engine:
        logits = engine.forward_tokens(prompt, pos_offset=0)
        got_sha = hashlib.sha256(
            np.ascontiguousarray(logits.astype(np.float32)).tobytes()
        ).hexdigest()
        new_ids, _metrics = engine.generate_ids(
            prompt, max_new_tokens=8, temperature=0.0, seed=42
        )

    assert got_sha == _LLAMA_GOLDEN_LOGITS_SHA, (
        f"llama logits hash drifted from parent 8426ec6: {got_sha}"
    )
    assert new_ids == _LLAMA_GOLDEN_IDS, f"llama token ids drifted from parent: {new_ids}"
    # The KV-cache decode steps must produce the same greedy chain as generate.
    with LlamaInferenceEngine(path, max_seq_len=64) as engine:
        logits = engine.forward_tokens(prompt, pos_offset=0)
        next_id = sample_next_token(logits, temperature=0.0)
        chain = [next_id]
        for i in range(7):
            step = engine.forward_tokens([chain[-1]], pos_offset=len(prompt) + i)
            chain.append(sample_next_token(step, temperature=0.0))
    assert chain == _LLAMA_GOLDEN_IDS
