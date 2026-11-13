#!/usr/bin/env python3
"""
Phase 7C ModelSpec resolution / fail-fast tests (CPU lane).

Pure parser/spec code: no HIP extension, no GPU. The tested behaviors:

- `llama`/`phi3`/`gemma` hparam resolution, including the real header-dump
  values (gemma explicit `key_length`/`value_length; Phi-3 rope dims);
- fail-fast errors: unknown architecture (naming the supported set),
  gemma2/gemma3 variants, missing required tensors listed *all at once*,
  per-tensor actionable shape mismatches, Phi-3 rope factors, gemma2-style
  softcap/SWA features, `key_length != value_length`, missing block_count;
- optional tensors never error; qwen2 resolves through the llama-family
  layout as a metadata/bias regression target only (NOT YET as a claim).
"""

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from model_spec import SUPPORTED_ARCHS, ModelSpec, resolve_model_spec  # noqa: E402
import model_spec_helpers as helpers  # noqa: E402

pytestmark = [pytest.mark.cpu]


def test_model_spec_resolves_real_gemma_header_dims():
    """Exact metadata from the recorded gemma-2b-it header dump."""
    spec = ModelSpec.from_gguf_metadata({
        "general.architecture": "gemma",
        "gemma.block_count": 18,
        "gemma.attention.head_count": 8,
        "gemma.attention.head_count_kv": 1,
        "gemma.attention.key_length": 256,
        "gemma.attention.value_length": 256,
        "gemma.embedding_length": 2048,
        "gemma.feed_forward_length": 16384,
        "gemma.attention.layer_norm_rms_epsilon": 1e-6,
    })
    assert spec.q_dim == 8 * 256
    assert spec.kv_dim == 1 * 256
    assert spec.head_dim == 256
    assert spec.rope_neox is True          # llama.cpp rope_type NEOX for gemma
    assert spec.ffn_act == "geglu"
    assert spec.embedding_scale != 1.0     # sqrt(hidden)
    assert spec.final_logit_softcapping is None  # gemma v1 has no softcap


def test_model_spec_gemma7b_style_dims_reshape_correctly():
    """hidden//heads (192) != key_length (256): the explicit dim must win."""
    spec = ModelSpec.from_gguf_metadata({
        "general.architecture": "gemma",
        "gemma.attention.head_count": 16,
        "gemma.attention.head_count_kv": 16,
        "gemma.attention.key_length": 256,
        "gemma.attention.value_length": 256,
        "gemma.embedding_length": 3072,
        "gemma.feed_forward_length": 24576,
    })
    assert spec.q_dim == 16 * 256 == 4096  # != hidden (3072)
    assert spec.head_dim == 256            # not 3072 // 16 == 192


def test_model_spec_resolves_real_phi3_header_dims():
    """Exact metadata from the recorded Phi-3-mini-4k header dump."""
    spec = ModelSpec.from_gguf_metadata({
        "general.architecture": "phi3",
        "phi3.block_count": 32,
        "phi3.attention.head_count": 32,
        "phi3.attention.head_count_kv": 32,
        "phi3.rope.dimension_count": 96,
        "phi3.embedding_length": 3072,
        "phi3.feed_forward_length": 8192,
    })
    assert spec.head_dim == 96
    assert spec.q_dim == 3072
    assert spec.rope_neox is True
    assert spec.ffn_act == "swiglu"
    assert spec.embedding_scale == 1.0


def test_model_spec_unknown_architecture_fails_fast():
    with pytest.raises(ValueError) as exc:
        resolve_model_spec({"general.architecture": "falcon"}, tensors={})
    msg = str(exc.value)
    assert "falcon" in msg
    for a in SUPPORTED_ARCHS:
        assert a in msg
    assert "qwen2" in msg  # the alias is named in the supported-set message


def test_model_spec_gemma2_gemma3_variants_fail_fast():
    for variant in ("gemma2", "gemma3", "gemma3n"):
        with pytest.raises(ValueError) as exc:
            resolve_model_spec({"general.architecture": variant}, tensors={})
        assert variant in str(exc.value)
        assert "gemma" in str(exc.value)


def test_model_spec_missing_required_tensors_listed_once():
    tensors = helpers.phi3_tensors()
    del tensors["blk.0.attn_norm.weight"]
    del tensors["blk.1.ffn_down.weight"]
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(helpers.phi3_metadata(), tensors)
    msg = str(exc.value)
    assert "blk.0.attn_norm.weight" in msg
    assert "blk.1.ffn_down.weight" in msg
    assert "missing required" in msg


def test_model_spec_missing_qkv_layout_fails_fast():
    tensors = helpers.phi3_tensors()
    del tensors["blk.0.attn_qkv.weight"]
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(helpers.phi3_metadata(), tensors)
    assert "attn_qkv" in str(exc.value)
    assert "attn_q.weight" in str(exc.value) and "attn_v.weight" in str(exc.value)


def test_model_spec_missing_optional_tensors_do_not_error():
    spec = resolve_model_spec(helpers.phi3_metadata(), helpers.phi3_tensors(fused=True))
    assert spec.arch == "phi3"
    assert spec.fused_qkv is True
    assert spec.ffn_fused_gate_up is True
    assert spec.tied_output is True  # no output.weight -> tied token_embd
    spec_g = resolve_model_spec(helpers.gemma_metadata(), helpers.gemma_tensors())
    assert spec_g.arch == "gemma"
    assert spec_g.fused_qkv is False
    assert spec_g.tied_output is True


def test_model_spec_shape_mismatches_are_actionable():
    tensors = helpers.phi3_tensors()
    tensors["blk.0.attn_qkv.weight"] = helpers.info(
        "blk.0.attn_qkv.weight", (64, 111)
    )
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(helpers.phi3_metadata(), tensors)
    msg = str(exc.value)
    assert "blk.0.attn_qkv.weight" in msg
    assert "(64, 111)" in msg and "(64, 128)" in msg


def test_model_spec_phi3_rope_factors_fail_fast():
    tensors = helpers.phi3_tensors()
    tensors["blk.0.rope_factors_long.weight"] = helpers.info(
        "blk.0.rope_factors_long.weight", (48,)
    )
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(helpers.phi3_metadata(), tensors)
    assert "rope_factors_long" in str(exc.value)
    assert "not implemented" in str(exc.value) or "refusing" in str(exc.value)


def test_model_spec_gemma_unsupported_features_fail_fast():
    # gemma2-style attention softcap
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(
            {**helpers.gemma_metadata(), "gemma.attention.logit_softcapping": 50.0},
            helpers.gemma_tensors(),
        )
    assert "logit_softcapping" in str(exc.value)
    # sliding-window attention
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(
            {**helpers.gemma_metadata(), "gemma.attention.sliding_window": 4096},
            helpers.gemma_tensors(),
        )
    assert "sliding_window" in str(exc.value)


def test_model_spec_key_value_dim_mismatch_fails_fast():
    meta = helpers.gemma_metadata(key_dim=32, value_dim=16)
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(meta, helpers.gemma_tensors(key_dim=32, value_dim=16))
    assert "key_length" in str(exc.value) and "value_length" in str(exc.value)


def test_model_spec_gemma_final_logit_softcap_resolves():
    spec = resolve_model_spec(
        helpers.gemma_metadata(softcap=30.0), helpers.gemma_tensors()
    )
    assert spec.final_logit_softcapping == 30.0


def test_model_spec_qwen2_metadata_regression():
    """qwen2 resolves through the llama-family layout; claim stays NOT YET."""
    meta, tensors = helpers.qwen2_metadata_and_tensors()
    spec = resolve_model_spec(meta, tensors)  # optional q bias: no error
    assert spec.arch == "qwen2"
    assert spec.rope_neox is True
    assert spec.ffn_act == "swiglu"
    assert spec.embedding_scale == 1.0


def test_model_spec_missing_block_count_is_actionable():
    meta = helpers.phi3_metadata()
    del meta["phi3.block_count"]
    with pytest.raises(ValueError) as exc:
        resolve_model_spec(meta, helpers.phi3_tensors())
    assert "block_count" in str(exc.value)


def test_compat_unsupported_architectures_rejected_with_named_set():
    """Every non-supported architecture is rejected by name (compat surface).

    The supported forward set is exactly llama/phi3/gemma (synthetic-fixture
    verified for phi3/gemma); qwen2 resolves through the llama-family layout
    as a metadata/bias regression target only. No other family reaches the
    engine.
    """
    unsupported = ["mistral-nemo", "stablelm", "phi2", "starcoder2", "gpt2"]
    for arch in unsupported:
        meta = {**helpers.phi3_metadata(), "general.architecture": arch}
        with pytest.raises(ValueError) as exc:
            resolve_model_spec(meta, tensors={})
        msg = str(exc.value)
        assert "Unsupported" in msg
        assert arch in msg or "gemma family" in msg
