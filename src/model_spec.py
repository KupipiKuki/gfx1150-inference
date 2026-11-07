"""
Model-spec / tensor-map resolution for the supported GGUF model families
(Phase 7C: `llama`, `phi3`, `gemma`; `qwen2` resolves through the llama-family
layout as a metadata/bias regression target only).

`ModelSpec` resolves, for a loaded GGUF:

- architecture (`general.architecture`) and `{arch}.block_count`;
- `hidden`, `intermediate`, `num_heads`, `num_kv_heads`;
- separate `key_dim` / `value_dim` per head (`{arch}.attention.key_length`
  / `{arch}.attention.value_length`, falling back to `rope.dimension_count`,
  then to `hidden // num_heads` only where correct);
- `rms_norm_eps`, `rope_freq_base`, and the rope pattern (NeoX per family default);
- FFN activation family (`swiglu` for llama/qwen2/phi3, `geglu` for gemma) and
  the Phi-3 fused gate+up `ffn_up` layout;
- embedding scale (`1.0` or `sqrt(hidden)` for gemma);
- final-logit softcap (`{arch}.final_logit_softcapping`, `c * tanh(logits / c)`);
- tied output (`output.weight` absent -> `token_embd.weight`);
- the fused-QKV / separate-QKV tensor layout actually present in the file.

Validation is fail-fast and actionable: an unknown architecture names the
supported set; a missing required tensor lists *every* missing name; a shape
mismatch names the tensor, the expected shape, and the actual shape; optional
tensors never error, they simply mark the feature absent. Unsupported
family-specific features (Phi-3 long-rope factors, Gemma 2/3 softcaps,
sliding-window attention, `key_length != value_length`, partial rotary dims)
are rejected with explicit messages instead of silently degrading.

Real-name authority: the tensor names and shapes validated here are taken from
`audit/evidence/G3/7C/header-dumps/` (recorded GGUF header dumps for
`microsoft/Phi-3-mini-4k-instruct-q4.gguf` and `gemma-2b-it.Q4_K_M.gguf`) and
cross-checked against the pinned llama.cpp source
(`149f5641b931aaf33697d70f9abc90c3e5300247`: `src/models/phi3.cpp`,
`src/models/gemma.cpp`, `src/llama-model.cpp::create_tensor_qkv`,
`src/llama-arch.cpp`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

try:
    from .gguf_parser import GGUFTensorInfo
except ImportError:  # pragma: no cover - script-mode import
    import os
    import sys

    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SRC_DIR not in sys.path:
        sys.path.append(_SRC_DIR)
    from gguf_parser import GGUFTensorInfo


# Architectures whose default rope pattern is NeoX half-dim rotation
# (cf. llama.cpp `llama_model_rope_type`, pinned revision). `gemma` is NeoX.
_NEOX_ROPE_ARCHS = frozenset(
    {"qwen2", "stablelm", "falcon", "gptneox", "phi2", "phi3", "starcoder2", "gemma"}
)

# Architectures with a fully supported forward path (synthetic-fixture verified
# for phi3/gemma; real-GGUF goldens are 7F-2).
SUPPORTED_ARCHS = frozenset({"llama", "phi3", "gemma"})

# Architectures accepted via the llama-family tensor layout only for
# metadata/bias regression (no support claim; ledger row 10 stays NOT YET).
LLAMA_LAYOUT_ALIAS_ARCHS = frozenset({"qwen2"})

# Gemma variants that are out of scope for 7C (softcaps / SWA / other extras).
UNSUPPORTED_GEMMA_VARIANTS = frozenset({"gemma2", "gemma3", "gemma3n"})


def get_arch_meta(
    metadata: Mapping[str, object], arch: str, suffix: str, default: object = None
) -> object:
    """Resolve `{arch}.{suffix}`, falling back to `llama.{suffix}` then `default`."""
    arch_key = f"{arch}.{suffix}"
    if arch_key in metadata:
        return metadata[arch_key]
    llama_key = f"llama.{suffix}"
    if llama_key in metadata:
        return metadata[llama_key]
    if default is not None:
        return default
    raise KeyError(f"Missing required GGUF metadata key '{arch_key}' (or '{llama_key}')")


@dataclass(frozen=True)
class ModelSpec:
    """Resolved per-file model specification (hparams + tensor layout)."""

    arch: str
    hidden_size: int
    intermediate_size: int
    num_heads: int
    num_kv_heads: int
    head_dim: int                 # attention head dim (== key_dim == value_dim)
    key_dim: int                  # per-head Q/K dimension
    value_dim: int                # per-head V dimension
    rms_norm_eps: float = 1e-5
    rope_freq_base: float = 10000.0
    rope_neox: bool = False
    num_layers: int = 0           # 0 = unresolved by metadata-only resolution
    ffn_act: str = "swiglu"       # "swiglu" (llama/qwen2/phi3) | "geglu" (gemma)
    ffn_fused_gate_up: bool = False  # Phi-3 fused gate+up ffn_up (rows = 2*inter)
    embedding_scale: float = 1.0  # gemma multiplies embeddings by sqrt(hidden)
    final_logit_softcapping: Optional[float] = None  # c * tanh(logits / c)
    fused_qkv: bool = False        # file carries blk.N.attn_qkv.weight
    tied_output: bool = False      # output.weight absent -> tied token_embd.weight

    # Backward-compatible aliases for the former `LlamaLayerConfig` field names.
    @property
    def q_dim(self) -> int:
        return self.num_heads * self.key_dim

    @property
    def kv_dim(self) -> int:
        return self.num_kv_heads * self.value_dim

    @classmethod
    def from_gguf_metadata(
        cls,
        metadata: Mapping[str, object],
        rope_neox: Optional[bool] = None,
    ) -> "ModelSpec":
        """Resolve hyperparameters from GGUF metadata (no tensor validation).

        Kept for compatibility with the former `LlamaLayerConfig.from_gguf_metadata`.
        Same value semantics as before for llama/qwen2; phi3/gemma add the
        explicit `key_length`/`value_length` resolution.
        """
        arch = str(metadata.get("general.architecture", "llama")).lower()
        hidden_size = int(get_arch_meta(metadata, arch, "embedding_length"))
        intermediate_size = int(get_arch_meta(metadata, arch, "feed_forward_length"))
        num_heads = int(get_arch_meta(metadata, arch, "attention.head_count"))
        num_kv_heads = int(
            get_arch_meta(metadata, arch, "attention.head_count_kv", num_heads)
        )
        rope_dimension_count = int(
            get_arch_meta(metadata, arch, "rope.dimension_count", hidden_size // num_heads)
        )
        key_dim = int(
            get_arch_meta(metadata, arch, "attention.key_length", rope_dimension_count)
        )
        value_dim = int(
            get_arch_meta(metadata, arch, "attention.value_length", key_dim)
        )
        rms_norm_eps = float(
            get_arch_meta(metadata, arch, "attention.layer_norm_rms_epsilon", 1e-5)
        )
        rope_freq_base = float(get_arch_meta(metadata, arch, "rope.freq_base", 10000.0))
        num_layers = int(
            metadata.get(f"{arch}.block_count", metadata.get("llama.block_count", 0)) or 0
        )

        if rope_neox is None:
            neox_key = f"{arch}.rope.neox"
            if neox_key in metadata:
                rope_neox = bool(metadata[neox_key])
            elif "llama.rope.neox" in metadata:
                rope_neox = bool(metadata["llama.rope.neox"])
            else:
                rope_neox = arch in _NEOX_ROPE_ARCHS

        if key_dim != value_dim:
            raise ValueError(
                f"Unsupported model configuration for '{arch}': "
                f"attention.key_length ({key_dim}) != attention.value_length "
                f"({value_dim}); the attention kernels and the unified KV cache "
                "require equal per-head key/value dimensions"
            )

        ffn_act = "geglu" if arch == "gemma" else "swiglu"
        embedding_scale = math.sqrt(hidden_size) if arch == "gemma" else 1.0
        final_logit_softcapping = metadata.get(f"{arch}.final_logit_softcapping")
        spec = cls(
            arch=arch,
            hidden_size=hidden_size,
            intermediate_size=intermediate_size,
            num_heads=num_heads,
            num_kv_heads=num_kv_heads,
            head_dim=key_dim,
            key_dim=key_dim,
            value_dim=value_dim,
            rms_norm_eps=rms_norm_eps,
            rope_freq_base=rope_freq_base,
            rope_neox=bool(rope_neox),
            num_layers=num_layers,
            ffn_act=ffn_act,
            ffn_fused_gate_up=False,
            embedding_scale=embedding_scale,
            final_logit_softcapping=(
                float(final_logit_softcapping) if final_logit_softcapping is not None else None
            ),
        )
        return spec


def _validate_arch(arch: str) -> None:
    if arch in SUPPORTED_ARCHS:
        return
    if arch in LLAMA_LAYOUT_ALIAS_ARCHS:
        return
    if arch in UNSUPPORTED_GEMMA_VARIANTS:
        raise ValueError(
            f"Unsupported gemma variant: '{arch}'. Only architecture 'gemma' is "
            "supported (synthetic-fixture verified); gemma2/gemma3 attention "
            "softcaps, sliding-window attention, and other variant features are "
            "not implemented"
        )
    raise ValueError(
        f"Unsupported GGUF architecture '{arch}'. Supported architectures: "
        f"{', '.join(sorted(SUPPORTED_ARCHS))} (qwen2 resolves through the "
        "llama-family tensor layout as a metadata/bias regression target only). "
        f"Known-unsupported set includes: gemma2, gemma3, gemma3n."
    )


def _reject_unsupported_features(
    arch: str, metadata: Mapping[str, object], tensors: Mapping[str, GGUFTensorInfo]
) -> None:
    """Fail fast on family features this engine does not implement."""
    if arch == "phi3":
        for name in sorted(tensors):
            if name.startswith("blk.") and (
                name.endswith(".rope_factors_long.weight")
                or name.endswith(".rope_factors_short.weight")
            ):
                raise ValueError(
                    f"Unsupported Phi-3 feature: tensor '{name}' "
                    "(per-layer rope factors for long/short context) is present; "
                    "rope factors are not implemented - refusing to run the file "
                    "without them"
                )
    if arch == "gemma":
        attention_softcap = metadata.get(f"{arch}.attention.logit_softcapping")
        sliding_window = metadata.get(f"{arch}.attention.sliding_window")
        if attention_softcap is not None:
            raise ValueError(
                f"Unsupported gemma feature: '{arch}.attention.logit_softcapping' "
                f"is present ({attention_softcap}); attention soft-capping is a "
                "gemma2 feature and is not implemented - refusing to run the file"
            )
        if f"{arch}.final_logit_softcapping" not in metadata and any(
            k.endswith(".attn_logit_softcapping") for k in metadata
        ):
            raise ValueError(
                "Unsupported gemma feature: attention soft-capping metadata is "
                "present; gemma2 attention soft-caps are not implemented"
            )
        if sliding_window is not None and int(sliding_window) > 0:
            raise ValueError(
                f"Unsupported gemma feature: '{arch}.attention.sliding_window' = "
                f"{sliding_window}; sliding-window attention is not implemented - "
                "refusing to run the file"
            )
    for any_arch in ("llama", "phi3", "gemma", "qwen2"):
        sliding_window = metadata.get(f"{any_arch}.attention.sliding_window")
        if sliding_window is not None and int(sliding_window) > 0:
            raise ValueError(
                f"Unsupported feature: '{any_arch}.attention.sliding_window' = "
                f"{sliding_window}; sliding-window attention is not implemented"
            )


def _expected_layer_shapes(
    spec: "ModelSpec",
    tensors: Mapping[str, GGUFTensorInfo],
    layer_idx: int,
) -> Tuple[Dict[str, Tuple[int, ...]], Dict[str, Tuple[int, ...]], bool]:
    """Build the (required, optional) expected tensor shape maps for one layer.

    `required` holds the tensors that must exist with exact shapes; `optional`
    holds bias tensors that are validated only when present; the third value
    reports whether this layer carries a fused `attn_qkv.weight`.
    """
    p = f"blk.{layer_idx}."
    hidden = spec.hidden_size
    inter = spec.intermediate_size
    q_dim = spec.q_dim
    kv_dim = spec.kv_dim

    fused_qkv_here = f"{p}attn_qkv.weight" in tensors
    separate_qkv_here = (
        f"{p}attn_q.weight" in tensors
        and f"{p}attn_k.weight" in tensors
        and f"{p}attn_v.weight" in tensors
    )
    if not fused_qkv_here and not separate_qkv_here:
        raise ValueError(
            f"ModelSpec validation failed (layer {layer_idx}): neither fused "
            f"tensor '{p}attn_qkv.weight' nor the separate set "
            f"('{p}attn_q.weight', '{p}attn_k.weight', '{p}attn_v.weight') is present; "
            "at least one QKV layout is required"
        )

    required: Dict[str, Tuple[int, ...]] = {
        f"{p}attn_norm.weight": (hidden,),
        f"{p}attn_output.weight": (q_dim, hidden),
        f"{p}ffn_norm.weight": (hidden,),
    }
    optional: Dict[str, Tuple[int, ...]] = {f"{p}attn_output.bias": (hidden,)}
    if fused_qkv_here:
        required[f"{p}attn_qkv.weight"] = (hidden, q_dim + 2 * kv_dim)
        optional[f"{p}attn_qkv.bias"] = (q_dim + 2 * kv_dim,)
    if separate_qkv_here:
        required[f"{p}attn_q.weight"] = (hidden, q_dim)
        required[f"{p}attn_k.weight"] = (hidden, kv_dim)
        required[f"{p}attn_v.weight"] = (hidden, kv_dim)
        optional[f"{p}attn_q.bias"] = (q_dim,)
        optional[f"{p}attn_k.bias"] = (kv_dim,)
        optional[f"{p}attn_v.bias"] = (kv_dim,)

    if spec.arch == "phi3":
        # Phi-3 fused gate+up `ffn_up` (rows = 2*inter; llama.cpp phi3.cpp).
        required[f"{p}ffn_up.weight"] = (hidden, 2 * inter)
        required[f"{p}ffn_down.weight"] = (inter, hidden)
        optional[f"{p}ffn_up.bias"] = (2 * inter,)
        optional[f"{p}ffn_down.bias"] = (hidden,)
    else:
        required[f"{p}ffn_gate.weight"] = (hidden, inter)
        required[f"{p}ffn_up.weight"] = (hidden, inter)
        required[f"{p}ffn_down.weight"] = (inter, hidden)

    return required, optional, fused_qkv_here


def _validate_file(
    spec: "ModelSpec",
    tensors: Mapping[str, GGUFTensorInfo],
) -> bool:
    """Validate every layer at once; raise one error listing all problems.

    Missing required tensors are all listed in a single error (never the first
    `KeyError` and never layer-by-layer); shape mismatches are all reported with
    the tensor name, the expected shape, and the actual shape. Returns whether
    any layer carries a fused `attn_qkv.weight`.
    """
    per_layer = [
        (i, _expected_layer_shapes(spec, tensors, i)) for i in range(spec.num_layers)
    ]

    missing: List[Tuple[str, str]] = []
    if "output_norm.weight" not in tensors:
        missing.append(("global", "output_norm.weight"))
    checked: List[Tuple[str, Tuple[int, ...]]] = [
        ("output_norm.weight", (spec.hidden_size,))
    ]
    optional_checked: List[Tuple[str, Tuple[int, ...]]] = []
    for layer_idx, (exp_required, exp_optional, _fused) in per_layer:
        for name, exp in exp_required.items():
            if name in tensors:
                checked.append((name, exp))
            else:
                missing.append((f"layer {layer_idx}", name))
        for name, exp in exp_optional.items():
            if name in tensors:
                optional_checked.append((name, exp))

    if missing:
        raise ValueError(
            "ModelSpec validation failed: missing required tensor(s): "
            f"{', '.join(sorted(n for _c, n in missing))}. Expected required "
            f"tensors for every block + globals: "
            f"output_norm.weight, token_embd.weight + one full "
            f"'{_expected_layer_summary(spec)}' set per layer. "
            f"(architecture '{spec.arch}', {spec.num_layers} layers)"
        )

    mismatches: List[str] = []
    for name, exp in checked:
        actual = tensors[name].dims
        if actual != exp:
            mismatches.append(
                f"tensor '{name}' has dims {actual}, expected {exp}"
            )
    for name, exp in optional_checked:
        actual = tensors[name].dims
        if actual != exp:
            mismatches.append(
                f"tensor '{name}' has dims {actual}, expected {exp} (optional tensor)"
            )
    if mismatches:
        raise ValueError(
            "ModelSpec shape mismatch: " + "; ".join(mismatches)
        )

    return any(f"blk.{i}.attn_qkv.weight" in tensors for i in range(spec.num_layers))


def _expected_layer_summary(spec: "ModelSpec") -> str:
    """Human-readable summary of one layer's required tensor name set."""
    if spec.arch == "phi3":
        return (
            "attn_norm.weight, attn_qkv.weight-or-attn_{q,k,v}.weight, "
            "attn_output.weight, ffn_norm.weight, ffn_up.weight (fused gate+up), "
            "ffn_down.weight"
        )
    if spec.arch == "gemma":
        return (
            "attn_norm.weight, attn_qkv.weight-or-attn_{q,k,v}.weight, "
            "attn_output.weight, ffn_norm.weight, ffn_gate.weight, "
            "ffn_up.weight, ffn_down.weight"
        )
    return (
        "attn_norm.weight, attn_{q,k,v}.weight, attn_output.weight, "
        "ffn_norm.weight, ffn_gate.weight, ffn_up.weight, ffn_down.weight"
    )


def resolve_model_spec(
    metadata: Mapping[str, object],
    tensors: Mapping[str, GGUFTensorInfo],
    rope_neox: Optional[bool] = None,
) -> ModelSpec:
    """Resolve and fully validate a `ModelSpec` against a loaded GGUF.

    This is the entry point the inference engine uses: metadata plus the parsed
    tensor table. Unknown architectures, unsupported family features, missing
    required tensors (one error listing every missing name), and shape
    mismatches each fail fast with a distinct, actionable message.
    """
    arch = str(metadata.get("general.architecture", "llama")).lower()
    _validate_arch(arch)
    _reject_unsupported_features(arch, metadata, tensors)

    spec = ModelSpec.from_gguf_metadata(metadata, rope_neox=rope_neox)
    if spec.num_layers <= 0:
        raise ValueError(
            f"Missing required GGUF metadata key '{arch}.block_count' "
            "(or 'llama.block_count')"
        )
    # qwen2 et al. resolve through the llama-family tensor layout below; no
    # support claim is implied (ledger row 10 stays NOT YET).

    # Global tensors.
    vocab_meta = metadata.get(f"{arch}.vocab_size", metadata.get("llama.vocab_size"))
    has_output = "output.weight" in tensors
    emb = tensors.get("token_embd.weight")
    if emb is None:
        raise ValueError(
            "ModelSpec validation failed (global): missing required tensor(s): "
            "token_embd.weight. Expected required tensors: token_embd.weight, "
            "output_norm.weight"
        )
    if len(emb.dims) != 2 or emb.dims[0] != spec.hidden_size:
        actual = emb.dims
        raise ValueError(
            f"ModelSpec shape mismatch (global): tensor 'token_embd.weight' has "
            f"dims {actual}, expected ({spec.hidden_size}, vocab)"
        )
    vocab_size = int(vocab_meta) if vocab_meta is not None else emb.dims[1]
    if emb.dims[1] != vocab_size:
        raise ValueError(
            f"ModelSpec shape mismatch (global): tensor 'token_embd.weight' dims "
            f"{emb.dims} disagree with the declared vocabulary size {vocab_size}"
        )
    if has_output:
        out = tensors["output.weight"]
        if out.dims != (spec.hidden_size, vocab_size):
            raise ValueError(
                f"ModelSpec shape mismatch (global): tensor 'output.weight' dims "
                f"{out.dims}, expected ({spec.hidden_size}, {vocab_size})"
            )

    for layer_idx in range(spec.num_layers):
        for other in (
            f"blk.{layer_idx}.rope_factors_long.weight",
            f"blk.{layer_idx}.rope_factors_short.weight",
        ):
            if other in tensors:
                raise ValueError(
                    f"Unsupported feature: tensor '{other}' (rope factors) is "
                    "present; extended/long-context rope factors are not "
                    "implemented - refusing to run the file"
                )

    fused_qkv_any = _validate_file(spec, tensors)

    return ModelSpec(
        arch=spec.arch,
        hidden_size=spec.hidden_size,
        intermediate_size=spec.intermediate_size,
        num_heads=spec.num_heads,
        num_kv_heads=spec.num_kv_heads,
        head_dim=spec.head_dim,
        key_dim=spec.key_dim,
        value_dim=spec.value_dim,
        rms_norm_eps=spec.rms_norm_eps,
        rope_freq_base=spec.rope_freq_base,
        rope_neox=spec.rope_neox,
        num_layers=spec.num_layers,
        ffn_act=spec.ffn_act,
        ffn_fused_gate_up=(arch == "phi3"),
        embedding_scale=spec.embedding_scale,
        final_logit_softcapping=spec.final_logit_softcapping,
        fused_qkv=fused_qkv_any,
        tied_output=not has_output,
    )
