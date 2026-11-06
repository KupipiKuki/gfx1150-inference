#!/usr/bin/env python3
"""
AUDITOR probe (G3/7C) — written independently of the coder's tests.

Does NOT import tests/reference_model.py. Fixture *construction* reuses
tests/family_fixtures.py (test-data generation only) and the engine is run as
a black box; the expected logits are computed by a forward pass written here
from the brief/pinned-llama.cpp semantics (vectorized, own rope/attention
implementation), using only gguf_parser's format layer for dequantization.

Checks:
 1. phi3 fused F16 (+biases) engine logits vs this probe's FP32 forward.
 2. phi3 fused quantized (Q4_K proj + Q6_K down) vs probe forward.
 3. phi3 fused vs separate layout: engine logits agree.
 4. gemma F16 + softcap 30 vs probe forward (scale/GeGLU/NeoX/key+value dims).
 5. gemma Q4_K vs probe forward.
 6. fail-fast distinctness: unknown arch, gemma2, missing required (all names
    in ONE error), missing optional (no error), shape mismatch, phi3 rope
    factors, gemma sliding window, key_length != value_length.
 7. static reference-independence: tests/reference_model.py must not import
    layer / inference / model_spec / matmul_module.

Exit 0 iff all pass.
"""

from __future__ import annotations

import ast
import math
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

from gguf_parser import (  # noqa: E402
    GGMLType,
    GGUFParser,
    dequantize_q4_0_cpu,
    dequantize_q4_k_cpu,
    dequantize_q6_k_cpu,
    dequantize_q8_0_cpu,
)
import family_fixtures  # noqa: E402

PROMPT = [1, 7, 10, 11]
TOL = 6e-3
RESULTS = []


def report(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


# ---------------------------------------------------------------- own forward
def load_weights(path):
    with open(path, "rb") as f:
        buf = f.read()
    gguf = GGUFParser(buf)
    md = dict(gguf.metadata)
    w = {}
    for name, info in gguf.tensors.items():
        raw = np.frombuffer(buf, dtype=np.uint8, count=info.n_bytes, offset=info.abs_offset)
        shape = info.shape_row_major
        t = info.ggml_type
        if t == GGMLType.F32:
            arr = raw.view(np.float32).reshape(shape)
        elif t == GGMLType.F16:
            arr = raw.view(np.float16).reshape(shape)
        elif t == GGMLType.Q4_0:
            arr = dequantize_q4_0_cpu(raw, info.n_elements).reshape(shape)
        elif t == GGMLType.Q4_K:
            arr = dequantize_q4_k_cpu(raw, info.n_elements).reshape(shape)
        elif t == GGMLType.Q6_K:
            arr = dequantize_q6_k_cpu(raw, info.n_elements).reshape(shape)
        elif t == GGMLType.Q8_0:
            arr = dequantize_q8_0_cpu(raw, info.n_elements).reshape(shape)
        else:
            raise ValueError(t)
        w[name] = arr.astype(np.float32)
    return md, w


def m(md, arch, key, default=None):
    if f"{arch}.{key}" in md:
        return md[f"{arch}.{key}"]
    if f"llama.{key}" in md:
        return md[f"llama.{key}"]
    if default is not None:
        return default
    raise KeyError(f"{arch}.{key}")


def rmsnorm(x, w, eps):
    x = x.astype(np.float32)
    return x / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps) * w


def rope_neox(x, base):  # x: (seq, heads, hd)
    seq, heads, hd = x.shape
    half = hd // 2
    i = np.arange(half, dtype=np.float32)
    inv = 1.0 / (base ** (2.0 * i / hd))
    ang = np.arange(seq, dtype=np.float32)[:, None] * inv[None, :]  # (seq, half)
    c = np.cos(ang)[:, None, :]
    s = np.sin(ang)[:, None, :]
    a, b = x[:, :, :half], x[:, :, half:]
    return np.concatenate([a * c - b * s, a * s + b * c], axis=-1)


def attend(q, k, v, scale):  # (seq, h, hd) causal, vectorized
    seq, h, hd = q.shape
    kvh = k.shape[1]
    g = h // kvh
    q = q * scale
    scores = np.zeros((h, seq, seq), dtype=np.float32)
    for hh in range(h):
        scores[hh] = q[:, hh, :] @ k[:, hh // g, :].T
    mask = np.triu(np.ones((seq, seq), dtype=bool), k=1)
    scores = np.where(mask[None], -np.inf, scores)
    scores -= scores.max(axis=-1, keepdims=True)
    p = np.exp(scores)
    p /= p.sum(axis=-1, keepdims=True)
    out = np.zeros((seq, h, hd), dtype=np.float32)
    for hh in range(h):
        out[:, hh, :] = p[hh] @ v[:, hh // g, :]
    return out


def silu(x):
    x = x.astype(np.float32)
    return x / (1.0 + np.exp(-x))


def gelu_tanh(x):
    x = x.astype(np.float32)
    return 0.5 * x * (1.0 + np.tanh(0.7978845608028654 * x * (1.0 + 0.044715 * x * x)))


def my_forward(md, w, tokens):
    arch = str(md.get("general.architecture", "llama")).lower()
    H = int(m(md, arch, "embedding_length"))
    I = int(m(md, arch, "feed_forward_length"))
    nh = int(m(md, arch, "attention.head_count"))
    nkv = int(m(md, arch, "attention.head_count_kv", nh))
    rd = int(m(md, arch, "rope.dimension_count", H // nh))
    kd = int(m(md, arch, "attention.key_length", rd))
    vd = int(m(md, arch, "attention.value_length", kd))
    eps = float(m(md, arch, "attention.layer_norm_rms_epsilon", 1e-5))
    base = float(m(md, arch, "rope.freq_base", 10000.0))
    L = int(md.get(f"{arch}.block_count", 0))
    qd, kvd = nh * kd, nkv * vd
    scale = 1.0 / math.sqrt(kd)

    h = w["token_embd.weight"][tokens].astype(np.float32)
    if arch == "gemma":
        h = h * math.sqrt(H)
    seq = h.shape[0]
    for il in range(L):
        p = f"blk.{il}."
        x = h
        nx = rmsnorm(x, w[p + "attn_norm.weight"], eps)
        if p + "attn_qkv.weight" in w:
            qkv = nx @ w[p + "attn_qkv.weight"].T
            if p + "attn_qkv.bias" in w:
                qkv = qkv + w[p + "attn_qkv.bias"]
            q = qkv[:, :qd].reshape(seq, nh, kd)
            k = qkv[:, qd:qd + kvd].reshape(seq, nkv, kd)
            v = qkv[:, qd + kvd:].reshape(seq, nkv, vd)
        else:
            q = (nx @ w[p + "attn_q.weight"].T).reshape(seq, nh, kd)
            k = (nx @ w[p + "attn_k.weight"].T).reshape(seq, nkv, kd)
            v = (nx @ w[p + "attn_v.weight"].T).reshape(seq, nkv, vd)
            for nm, tgt in (("attn_q.bias", q), ("attn_k.bias", k), ("attn_v.bias", v)):
                if p + nm in w:
                    tgt += w[p + nm].reshape(1, *tgt.shape[1:])
        q = rope_neox(q, base)
        k = rope_neox(k, base)
        a = attend(q, k, v, scale).reshape(seq, qd)
        sa = x + a @ w[p + "attn_output.weight"].T
        if p + "attn_output.bias" in w:
            sa = sa + w[p + "attn_output.bias"]
        fn = rmsnorm(sa, w[p + "ffn_norm.weight"], eps)
        if arch == "gemma":
            act = gelu_tanh(fn @ w[p + "ffn_gate.weight"].T) * (fn @ w[p + "ffn_up.weight"].T)
        elif p + "ffn_gate.weight" in w:
            act = silu(fn @ w[p + "ffn_gate.weight"].T) * (fn @ w[p + "ffn_up.weight"].T)
        else:  # phi3 fused gate+up, contiguous halves
            gu = fn @ w[p + "ffn_up.weight"].T
            if p + "ffn_up.bias" in w:
                gu = gu + w[p + "ffn_up.bias"]
            act = silu(gu[:, :I]) * gu[:, I:]
        ff = act @ w[p + "ffn_down.weight"].T
        if p + "ffn_down.bias" in w:
            ff = ff + w[p + "ffn_down.bias"]
        h = sa + ff
    last = rmsnorm(h[-1:], w["output_norm.weight"], eps)
    head = "output.weight" if "output.weight" in w else "token_embd.weight"
    logits = (last @ w[head].T).reshape(-1)
    cap = md.get(f"{arch}.final_logit_softcapping")
    if cap is not None:
        logits = float(cap) * np.tanh(logits / float(cap))
    return logits.astype(np.float32)


def engine_logits(path):
    from inference import LlamaInferenceEngine

    engine = LlamaInferenceEngine(path, max_seq_len=64)
    try:
        return engine.forward_tokens(PROMPT, pos_offset=0).astype(np.float32)
    finally:
        try:
            engine.close()
        except BufferError:
            pass  # a mid-forward failure can leave live views; probe already failed


def check_engine_vs_probe(tag, path):
    md, w = load_weights(path)
    ref = my_forward(md, w, PROMPT)
    eng = engine_logits(path)
    err = float(np.max(np.abs(eng - ref)))
    report(tag, err < TOL, f"max_err={err:.6f} tol={TOL}")


# ---------------------------------------------------------------- fail-fast
def failfast_checks():
    from model_spec import resolve_model_spec

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "phi3.gguf")
        family_fixtures.build_phi3_gguf(
            path, np.random.default_rng(99), layout="fused", quant="f16",
            biases=True, ffn_biases=True,
        )
        with open(path, "rb") as f:
            gguf = GGUFParser(f.read())
        md = dict(gguf.metadata)
        tensors = dict(gguf.tensors)

        # unknown arch names the supported set
        md2 = dict(md)
        md2["general.architecture"] = "bert"
        try:
            resolve_model_spec(md2, tensors)
            report("unknown-arch", False, "no error raised")
        except ValueError as e:
            ok = "bert" in str(e) and "llama" in str(e) and "phi3" in str(e) and "gemma" in str(e)
            report("unknown-arch", ok, str(e)[:120])

        # gemma2 variant
        md3 = dict(md)
        md3["general.architecture"] = "gemma2"
        try:
            resolve_model_spec(md3, tensors)
            report("gemma2-fail-fast", False, "no error")
        except ValueError as e:
            report("gemma2-fail-fast", "gemma" in str(e), str(e)[:100])

        # missing required: drop several required tensors -> ONE error listing all
        t2 = dict(tensors)
        del t2["blk.0.ffn_down.weight"]
        del t2["blk.1.attn_output.weight"]
        del t2["output_norm.weight"]
        try:
            resolve_model_spec(md, t2)
            report("missing-required-all-listed", False, "no error")
        except ValueError as e:
            s = str(e)
            ok = all(n in s for n in ("blk.0.ffn_down.weight", "blk.1.attn_output.weight", "output_norm.weight"))
            report("missing-required-all-listed", ok, s[:200])

        # missing optional: drop biases -> no error
        t3 = {k: v for k, v in tensors.items() if not k.endswith(".bias")}
        try:
            resolve_model_spec(md, t3)
            report("missing-optional-ok", True)
        except ValueError as e:
            report("missing-optional-ok", False, str(e)[:120])

        # shape mismatch names tensor/expected/actual
        import dataclasses
        t4 = dict(tensors)
        info = tensors["blk.0.attn_output.weight"]
        assert dataclasses.is_dataclass(info)
        t4["blk.0.attn_output.weight"] = dataclasses.replace(
            info, dims=(info.dims[0], info.dims[1] + 1)
        )
        try:
            resolve_model_spec(md, t4)
            report("shape-mismatch-actionable", False, "no error")
        except ValueError as e:
            s = str(e)
            ok = "attn_output.weight" in s and "expected" in s
            report("shape-mismatch-actionable", ok, s[:160])

        # phi3 rope factors fail fast
        import dataclasses as dc
        t5 = dict(tensors)
        fake = dc.replace(tensors["blk.0.attn_norm.weight"], name="blk.0.rope_factors_long.weight")
        t5["blk.0.rope_factors_long.weight"] = fake
        try:
            resolve_model_spec(md, t5)
            report("phi3-rope-factors-fail-fast", False, "no error")
        except ValueError as e:
            report("phi3-rope-factors-fail-fast", "rope" in str(e), str(e)[:100])

        # key_length != value_length (on a real gemma fixture's metadata)
        gpath = os.path.join(td, "gemma.gguf")
        family_fixtures.build_gemma_gguf(gpath, np.random.default_rng(5), quant="f16")
        with open(gpath, "rb") as f:
            gmd = dict(GGUFParser(f.read()).metadata)
        try:
            resolve_model_spec({**gmd, "gemma.attention.key_length": 32,
                                "gemma.attention.value_length": 24}, t3)
            report("keyvalue-mismatch-fail-fast", False, "no error")
        except ValueError as e:
            report("keyvalue-mismatch-fail-fast", "key_length" in str(e), str(e)[:110])

        # sliding window fail fast
        try:
            resolve_model_spec({**md, "phi3.attention.sliding_window": 4096}, t3)
            report("sliding-window-fail-fast", False, "no error")
        except ValueError as e:
            report("sliding-window-fail-fast", "sliding" in str(e), str(e)[:100])


def reference_independence_check():
    path = os.path.join(_TESTS, "reference_model.py")
    tree = ast.parse(open(path).read())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    bad = mods & {"layer", "inference", "model_spec", "matmul_module"}
    report("reference-model-independence", not bad, f"imports={sorted(mods)}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        p_fused = os.path.join(td, "phi3-fused-f16.gguf")
        family_fixtures.build_phi3_gguf(
            p_fused, np.random.default_rng(4242), layout="fused", quant="f16",
            biases=True, ffn_biases=True,
        )
        check_engine_vs_probe("phi3-fused-f16-vs-auditor-forward", p_fused)

        p_q = os.path.join(td, "phi3-fused-q4km.gguf")
        family_fixtures.build_phi3_gguf(
            p_q, np.random.default_rng(4242), layout="fused", quant="q4km",
            biases=True, ffn_biases=True, hidden=256, inter=256,
            num_heads=4, num_kv_heads=2, head_dim=64,  # q_dim=256: Q4_K K-alignment
        )
        check_engine_vs_probe("phi3-fused-q4km-vs-auditor-forward", p_q)

        p_sep = os.path.join(td, "phi3-separate-f16.gguf")
        family_fixtures.build_phi3_gguf(
            p_sep, np.random.default_rng(4242), layout="separate", quant="f16",
            biases=True, ffn_biases=True,
        )
        e_fused = engine_logits(p_fused)
        e_sep = engine_logits(p_sep)
        err = float(np.max(np.abs(e_fused - e_sep)))
        report("phi3-fused-vs-separate-engine", err < 1e-3, f"max_err={err:.6f}")

        g_f16 = os.path.join(td, "gemma-f16-softcap.gguf")
        family_fixtures.build_gemma_gguf(
            g_f16, np.random.default_rng(777), quant="f16", final_logit_softcapping=30.0,
        )
        check_engine_vs_probe("gemma-f16-softcap-vs-auditor-forward", g_f16)

        g_q = os.path.join(td, "gemma-q4k.gguf")
        family_fixtures.build_gemma_gguf(
            g_q, np.random.default_rng(777), quant="q4k", final_logit_softcapping=30.0,
            hidden=256, inter=256, num_heads=4, num_kv_heads=2, key_dim=64, value_dim=64,
        )
        check_engine_vs_probe("gemma-q4k-vs-auditor-forward", g_q)

    failfast_checks()
    reference_independence_check()
    print(f"AUDITOR PROBE: {'ALL GREEN' if all(RESULTS) else 'FAILURES PRESENT'} ({sum(RESULTS)}/{len(RESULTS)})")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
