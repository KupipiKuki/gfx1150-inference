"""
End-to-End SSD-Streamed LLM Inference Engine (`LlamaInferenceEngine`) for AMD gfx1150.

Coordinates:
1. GGUF metadata (`llama.*`, `qwen2.*`, `phi3.*`, `gemma.*`), tokenizer (`GGUFTokenizer`),
   and memory-mapped weight streaming (`WeightStreamer`).
2. GQA KV Cache (`KVCacheManager`) supporting GPU-resident offset pools, CPU RAM offload,
   and NVMe `mmap` offload for long-context 70B runs.
3. Layer-wise ping-pong SSD prefetching (`MADV_WILLNEED` on Layer L+1 while GPU computes Layer L),
   followed by best-effort page-cache eviction on Layer L and global embedding/LM-head
   tensors when the effective residency policy is STREAM (`posix_fadvise(POSIX_FADV_DONTNEED)`
   primary, optional `MADV_PAGEOUT`; `MADV_DONTNEED` only as a warned PTE-only fallback).
4. Chunked prompt prefill (`prefill_chunk_size`), multi-prompt batch processing (`generate_batch`),
   and configurable Top-K / Top-P / Temperature / Repetition-Penalty token sampling.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from gguf_parser import GGUFTensorInfo
from weight_loader import WeightStreamer
from kv_cache import KVCacheManager, DEFAULT_MAX_KV_BYTES
from layer import LlamaLayerConfig, TransformerLayer, linear_project, norm_weight_fp16
from model_spec import ModelSpec, resolve_model_spec
from memory_budget import (
    ResidencyPolicy,
    compute_weight_budget,
    decide_residency,
    estimate_activation_bytes,
    read_budget_sources,
)
from tokenizer import GGUFTokenizer, embed_tokens

try:
    import matmul_module
except ImportError:
    if _BUILD_DIR not in sys.path and os.path.isdir(_BUILD_DIR):
        sys.path.append(_BUILD_DIR)
    try:
        import matmul_module
    except ImportError as exc:
        raise ImportError(
            "Failed to import 'matmul_module' HIP extension. Build it first with:\n"
            "  cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j\n"
            "or install the package via 'pip install -e . --no-build-isolation'."
        ) from exc


def sample_next_token(
    logits_fp16: np.ndarray,
    temperature: float = 0.0,
    top_k: int = 40,
    top_p: float = 0.95,
    repetition_penalty: float = 1.0,
    generated_ids: Optional[Sequence[int]] = None,
    rng: Optional[np.random.Generator] = None,
) -> int:
    """
    Sample the next token ID from 1D vocabulary `logits_fp16` (`(vocab_size,)`).
    Uses greedy argmax when `temperature == 0.0` or `top_k == 1`.
    """
    if repetition_penalty <= 0.0 or not np.isfinite(repetition_penalty):
        raise ValueError(f"repetition_penalty must be finite and > 0.0 (got {repetition_penalty})")
    if temperature < 0.0 or not np.isfinite(temperature):
        raise ValueError(f"temperature must be finite and >= 0.0 (got {temperature})")
    if top_p < 0.0 or top_p > 1.0 or not np.isfinite(top_p):
        raise ValueError(f"top_p must be in [0.0, 1.0] (got {top_p})")

    logits = logits_fp16.astype(np.float32).reshape(-1).copy()
    if logits.size == 0:
        raise ValueError("logits_fp16 must not be empty")
    if not np.all(np.isfinite(logits)):
        raise ValueError("logits_fp16 contains NaN or Inf values")

    if repetition_penalty != 1.0 and generated_ids:
        for tid in set(generated_ids):
            if 0 <= tid < logits.size:
                if logits[tid] > 0:
                    logits[tid] /= repetition_penalty
                else:
                    logits[tid] *= repetition_penalty

    if temperature == 0.0 or top_k == 1:
        return int(np.argmax(logits))

    logits /= float(temperature)

    if 0 < top_k < logits.size:
        top_indices = np.argpartition(logits, -top_k)[-top_k:]
        mask = np.full_like(logits, -np.inf)
        mask[top_indices] = logits[top_indices]
        logits = mask

    logits -= np.max(logits)
    probs = np.exp(logits)
    probs_sum = float(np.sum(probs))
    if probs_sum <= 0.0 or not np.isfinite(probs_sum):
        return int(np.argmax(logits_fp16))
    probs /= probs_sum

    if 0.0 < top_p < 1.0:
        sorted_idx = np.argsort(probs)[::-1]
        sorted_probs = probs[sorted_idx]
        cum_probs = np.cumsum(sorted_probs)
        cutoff = cum_probs - sorted_probs > top_p
        sorted_probs[cutoff] = 0.0
        s = float(np.sum(sorted_probs))
        if s <= 0.0 or not np.isfinite(s):
            return int(np.argmax(logits_fp16))
        sorted_probs /= s
        if rng is None:
            rng = np.random.default_rng()
        choice = int(rng.choice(sorted_idx, p=sorted_probs))
        return choice

    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(logits.size, p=probs))


def resolve_residency_policy(
    residency: Optional[str | ResidencyPolicy] = None,
    cache_weights: bool = False,
) -> Tuple[ResidencyPolicy, bool]:
    """Resolve the requested residency policy from the explicit `residency`
    argument and the deprecated `cache_weights` boolean.

    Returns `(policy, used_deprecated)`. Precedence: an explicit policy wins;
    `cache_weights=True` maps to `PIN_ALL`; `cache_weights=False` maps to the
    new default `AUTO`. `used_deprecated` is True when `cache_weights` decided
    the policy (the boolean API is deprecated: True maps to `PIN_ALL`, `False`
    to `AUTO`; the mapping is documented, not silent).
    """
    if residency is not None:
        return ResidencyPolicy.coerce(residency), False
    if cache_weights:
        return ResidencyPolicy.PIN_ALL, True
    return ResidencyPolicy.AUTO, False


class LlamaInferenceEngine:
    """
    Full-model SSD-offloaded LLM inference engine for AMD gfx1150 (7B–70B models).

    Residency policy (7D-2): `residency='auto'` (default) keeps the model's
    pages resident in the host page cache when the model's weight bytes fit
    the computed budget (min of free GTT, MemAvailable, and cgroup headroom,
    minus the KV cache, the activation estimate, and a safety margin) and
    streams otherwise; `'pin_all'` honors the explicit request and warns when
    the model exceeds the budget; `'stream'` streams with best-effort
    page-cache eviction (`posix_fadvise(POSIX_FADV_DONTNEED)` primary,
    optional `MADV_PAGEOUT`). `cache_weights=True` is a deprecated alias for
    `'pin_all'`; `False` maps to the new default `'auto'`.
    """

    def __init__(
        self,
        model_path: str,
        max_seq_len: int = 2048,
        offload_kv_to_cpu: bool = False,
        kv_mmap_dir: Optional[str] = None,
        rope_neox: Optional[bool] = None,
        cache_weights: bool = False,
        residency: Optional[str | ResidencyPolicy] = None,
        residency_budget_mb: Optional[int] = None,
        max_kv_bytes: Optional[int] = None,
    ):
        self.model_path = model_path
        self.streamer: Optional[WeightStreamer] = None
        self.kv_cache: Optional[KVCacheManager] = None
        self._out_norm_w: Optional[np.ndarray] = None

        requested_policy, used_deprecated = resolve_residency_policy(
            residency, cache_weights
        )
        self.residency_requested = requested_policy
        if used_deprecated:
            warnings.warn(
                "cache_weights=True is deprecated and maps to residency='pin_all' "
                "(host page-cache residency, not a device weight cache). Use "
                "--residency pin / residency='pin_all' instead. cache_weights=False "
                "maps to the new default 'auto'.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.streamer = WeightStreamer(model_path)
        try:
            self.metadata = self.streamer.gguf.metadata
            # Model-spec resolution validates the family, feature set, and the
            # full tensor map (fail-fast: unknown arch, unsupported features,
            # missing required tensors listed at once, shape mismatches).
            self.spec: ModelSpec = resolve_model_spec(
                self.metadata, self.streamer.gguf.tensors, rope_neox=rope_neox
            )
            self.num_layers = self.spec.num_layers
            self.layer_cfg = self.spec
            self.layer_runner = TransformerLayer(self.spec)
            self.max_seq_len = int(max_seq_len)

            self.tokenizer: Optional[GGUFTokenizer] = None
            if "tokenizer.ggml.tokens" in self.metadata:
                self.tokenizer = GGUFTokenizer.from_gguf_metadata(self.metadata)
                self.vocab_size = self.tokenizer.vocab_size
            else:
                emb_info = self.streamer.gguf.tensors["token_embd.weight"]
                self.vocab_size = emb_info.shape_row_major[0]

            # 7D-2: resolve AUTO/PIN/STREAM against the budget measured from
            # the real host sources (or the explicit test/user override) and
            # record the decision.
            self.residency_budget_mb = (
                None if residency_budget_mb is None else int(residency_budget_mb)
            )
            self._apply_residency_policy(requested_policy)

            # Cache the small 1D output_norm.weight in host FP16 once and release its mmap view
            out_norm_info, out_norm_view = self._get_global_tensor("output_norm.weight")
            self._out_norm_w = norm_weight_fp16((out_norm_info, out_norm_view)).copy()
            del out_norm_view
            self.streamer.release_tensor("output_norm.weight")

            self._head_name: str = (
                "output.weight"
                if "output.weight" in self.streamer.gguf.tensors
                else "token_embd.weight"
            )

            self.kv_cache = KVCacheManager(
                num_layers=self.num_layers,
                max_seq_len=self.max_seq_len,
                num_kv_heads=self.layer_cfg.num_kv_heads,
                head_dim=self.layer_cfg.head_dim,
                offload_to_cpu=offload_kv_to_cpu,
                mmap_dir=kv_mmap_dir,
                max_kv_bytes=(
                    DEFAULT_MAX_KV_BYTES if max_kv_bytes is None else int(max_kv_bytes)
                ),
            )
        except BaseException:
            self.close()
            raise

    def _apply_residency_policy(self, requested: ResidencyPolicy) -> None:
        """Measure the host budget (unless overridden), decide the effective
        policy, and record the decision (`self.residency_decision`, mirrored
        on the streamer). AUTO never silently pins an over-budget model and
        never invents a budget when no source is readable (it fails safe to
        STREAM)."""
        weight_bytes = self.streamer.weight_bytes
        kv_bytes = (
            2
            * self.spec.num_layers
            * self.max_seq_len
            * self.spec.num_kv_heads
            * self.spec.head_dim
            * 2
        )
        activation_bytes = estimate_activation_bytes(
            self.spec.hidden_size, self.max_seq_len, self.vocab_size
        )
        if self.residency_budget_mb is not None:
            budget_bytes = max(0, int(self.residency_budget_mb) * (1 << 20))
            self.residency_decision_origin = (
                f"budget override residency_budget_mb={self.residency_budget_mb} "
                f"(budget {budget_bytes} bytes)"
            )
            self.residency_decision = decide_residency(
                requested, weight_bytes, budget_bytes
            )
        else:
            sources = read_budget_sources()
            self.weight_budget = compute_weight_budget(
                kv_bytes, activation_bytes, sources
            )
            self.residency_decision_origin = (
                "measured sources: "
                + (", ".join(self.weight_budget.sources.used_sources) or "none")
            )
            self.residency_decision = decide_residency(
                requested, weight_bytes, self.weight_budget.weight_budget, sources
            )
        self.streamer.set_decision(self.residency_decision)

    def _get_global_tensor(self, name: str) -> Tuple[GGUFTensorInfo, np.ndarray]:
        info = self.streamer.gguf.tensors[name]
        view = self.streamer.get_tensor_view(name)
        return info, view

    def forward_tokens(
        self,
        token_ids: Sequence[int],
        pos_offset: int = 0,
        compute_logits: bool = True,
    ) -> Optional[np.ndarray]:
        """
        Run a full-model forward pass for `token_ids` starting at `pos_offset`,
        streaming each transformer layer from SSD with ping-pong prefetch (`MADV_WILLNEED`)
        and best-effort page-cache eviction (fadvise `POSIX_FADV_DONTNEED` / optional
        `MADV_PAGEOUT`) when the effective residency policy is STREAM.

        When `compute_logits=False` (used for intermediate chunks during chunked prefill),
        skips final RMSNorm and LM Head projection to save compute and SSD bandwidth.
        """
        emb_info, emb_view = self._get_global_tensor("token_embd.weight")
        hidden = embed_tokens(token_ids, emb_info, emb_view, self.spec.hidden_size)
        del emb_view
        # Evict touched token_embd pages before streaming transformer layers
        self.streamer.release_tensor("token_embd.weight")

        # Family embedding scale (gemma): embeddings are scaled by sqrt(hidden)
        # before layer 0 (cf. llama.cpp gemma.cpp `ggml_scale(inpL, sqrt(n_embd))`).
        if self.spec.embedding_scale != 1.0:
            hidden = (hidden.astype(np.float32) * self.spec.embedding_scale).astype(
                np.float16
            )

        # Kick off SSD prefetch for Layer 0 before entering the layer loop
        if self.num_layers > 0:
            self.streamer.prefetch_layer(0)

        for layer_idx in range(self.num_layers):
            is_last_layer = (layer_idx + 1 == self.num_layers)
            if is_last_layer and compute_logits:
                self.streamer.prefetch_tensor(self._head_name)
            hidden, _ = self.layer_runner.forward_streamed(
                hidden_states=hidden,
                streamer=self.streamer,
                layer_idx=layer_idx,
                pos_offset=pos_offset,
                kv_cache=self.kv_cache,
                prefetch_next=not is_last_layer,
            )

        if not compute_logits:
            return None

        # Final RMSNorm only on the last token position `(1, hidden_size)` to save compute
        last_hidden = np.ascontiguousarray(hidden[-1:, :], dtype=np.float16)
        normed_last = np.empty_like(last_hidden)
        matmul_module.rmsnorm(
            last_hidden,
            self._out_norm_w,
            normed_last,
            1,
            self.spec.hidden_size,
            self.spec.rms_norm_eps,
        )

        # LM Head projection (`output.weight` or weight-tied `token_embd.weight`) + eviction
        head_entry = self._get_global_tensor(self._head_name)
        logits_2d = linear_project(normed_last, head_entry, self.vocab_size)
        del head_entry
        self.streamer.release_tensor(self._head_name)

        # Family final-logit soft-capping ({arch}.final_logit_softcapping when
        # present): logits = c * tanh(logits / c).
        if self.spec.final_logit_softcapping is not None:
            c = float(self.spec.final_logit_softcapping)
            if c <= 0.0 or not np.isfinite(c):
                raise ValueError(
                    f"Invalid '{self.spec.arch}.final_logit_softcapping' value: {c}"
                )
            logits_fp32 = logits_2d.astype(np.float32)
            logits_2d = (c * np.tanh(logits_fp32 / c)).astype(np.float16)

        return logits_2d.reshape(-1)

    def prefill_tokens(
        self,
        prompt_ids: Sequence[int],
        chunk_size: Optional[int] = None,
    ) -> np.ndarray:
        """
        Prefill `prompt_ids` into the KV cache, optionally splitting long prompts into
        chunks of at most `chunk_size` tokens to bound peak activation memory on 70B models.
        Returns the next-token logits `(vocab_size,)` after the final prompt token.
        """
        total = len(prompt_ids)
        if total == 0:
            raise ValueError("prompt_ids must not be empty")

        if chunk_size is None or chunk_size <= 0 or chunk_size >= total:
            logits = self.forward_tokens(prompt_ids, pos_offset=0, compute_logits=True)
            if logits is None:
                raise RuntimeError("forward_tokens returned None despite compute_logits=True")
            return logits

        logits: Optional[np.ndarray] = None
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            is_last_chunk = (end == total)
            logits = self.forward_tokens(
                prompt_ids[start:end],
                pos_offset=start,
                compute_logits=is_last_chunk,
            )
        if logits is None:
            raise RuntimeError("Chunked prefill completed without computing final chunk logits")
        return logits

    def generate_ids(
        self,
        prompt_ids: Sequence[int],
        max_new_tokens: int = 16,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        stop_on_eos: bool = True,
        seed: Optional[int] = 42,
        prefill_chunk_size: Optional[int] = None,
    ) -> Tuple[List[int], Dict[str, float]]:
        """
        Autoregressively generate up to `max_new_tokens` token IDs from `prompt_ids`.
        Returns `(generated_token_ids, metrics_dict)`.
        """
        if not prompt_ids:
            raise ValueError("prompt_ids must not be empty")
        if max_new_tokens < 0:
            raise ValueError(f"max_new_tokens must be >= 0 (got {max_new_tokens})")
        if len(prompt_ids) + max_new_tokens > self.max_seq_len:
            raise ValueError(
                f"len(prompt_ids) ({len(prompt_ids)}) + max_new_tokens ({max_new_tokens}) "
                f"exceeds max_seq_len ({self.max_seq_len})"
            )

        if max_new_tokens == 0:
            return [], {
                "prefill_time_s": 0.0,
                "decode_time_s": 0.0,
                "total_time_s": 0.0,
                "tokens_generated": 0.0,
                "tokens_per_sec": 0.0,
                "decode_tokens_per_sec": 0.0,
            }

        self.kv_cache.reset()
        rng = np.random.default_rng(seed)
        all_ids: List[int] = [int(t) for t in prompt_ids]
        new_ids: List[int] = []

        t_start = time.perf_counter()
        # 1. Prompt prefill (full or chunked)
        logits = self.prefill_tokens(all_ids, chunk_size=prefill_chunk_size)
        t_prefill = time.perf_counter() - t_start

        next_id = sample_next_token(
            logits,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            generated_ids=all_ids,
            rng=rng,
        )
        new_ids.append(next_id)
        all_ids.append(next_id)

        # 2. Autoregressive single-token decode loop
        t_decode_start = time.perf_counter()
        eos_id = self.tokenizer.eos_token_id if self.tokenizer is not None else -1
        decode_steps = 0

        for _ in range(max_new_tokens - 1):
            if stop_on_eos and next_id == eos_id:
                break
            pos = len(all_ids) - 1
            step_logits = self.forward_tokens([next_id], pos_offset=pos, compute_logits=True)
            if step_logits is None:
                raise RuntimeError("forward_tokens returned None during decode step")
            next_id = sample_next_token(
                step_logits,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                generated_ids=all_ids,
                rng=rng,
            )
            new_ids.append(next_id)
            all_ids.append(next_id)
            decode_steps += 1

        t_decode = time.perf_counter() - t_decode_start
        t_total = time.perf_counter() - t_start

        metrics = {
            "prefill_time_s": t_prefill,
            "decode_time_s": t_decode,
            "total_time_s": t_total,
            "tokens_generated": float(len(new_ids)),
            "tokens_per_sec": len(new_ids) / max(t_total, 1e-9),
            "decode_tokens_per_sec": (
                decode_steps / max(t_decode, 1e-9) if decode_steps > 0 else 0.0
            ),
        }
        return new_ids, metrics

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 16,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        stop_on_eos: bool = True,
        seed: Optional[int] = 42,
        prefill_chunk_size: Optional[int] = None,
    ) -> Tuple[str, Dict[str, float]]:
        """Encode `prompt`, generate up to `max_new_tokens`, and decode back to text."""
        if self.tokenizer is None:
            raise RuntimeError("GGUF file does not contain tokenizer metadata; use generate_ids().")
        prompt_ids = self.tokenizer.encode(prompt)
        new_ids, metrics = self.generate_ids(
            prompt_ids=prompt_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            stop_on_eos=stop_on_eos,
            seed=seed,
            prefill_chunk_size=prefill_chunk_size,
        )
        return self.tokenizer.decode(new_ids, skip_special_tokens=True), metrics

    def generate_batch_ids(
        self,
        batch_prompt_ids: Sequence[Sequence[int]],
        max_new_tokens: int = 16,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        stop_on_eos: bool = True,
        seed: Optional[int] = 42,
        prefill_chunk_size: Optional[int] = None,
    ) -> Tuple[List[List[int]], Dict[str, float]]:
        """
        Process a batch of prompt token sequences continuously while reusing the
        allocated KV cache and SSD weight streamer.
        """
        outputs: List[List[int]] = []
        total_tokens = 0.0
        t_start = time.perf_counter()

        for i, p_ids in enumerate(batch_prompt_ids):
            seq_seed = None if seed is None else seed + i
            gen_ids, m = self.generate_ids(
                prompt_ids=p_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                stop_on_eos=stop_on_eos,
                seed=seq_seed,
                prefill_chunk_size=prefill_chunk_size,
            )
            outputs.append(gen_ids)
            total_tokens += m["tokens_generated"]

        t_total = time.perf_counter() - t_start
        batch_metrics = {
            "batch_size": float(len(batch_prompt_ids)),
            "total_tokens_generated": total_tokens,
            "total_time_s": t_total,
            "tokens_per_sec": total_tokens / max(t_total, 1e-9),
        }
        return outputs, batch_metrics

    def generate_batch(
        self,
        prompts: Sequence[str],
        max_new_tokens: int = 16,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        stop_on_eos: bool = True,
        seed: Optional[int] = 42,
        prefill_chunk_size: Optional[int] = None,
    ) -> Tuple[List[str], Dict[str, float]]:
        """Encode and generate completions for a batch of text prompts."""
        if self.tokenizer is None:
            raise RuntimeError("GGUF file does not contain tokenizer metadata; use generate_batch_ids().")
        encoded = [self.tokenizer.encode(p) for p in prompts]
        out_ids, metrics = self.generate_batch_ids(
            batch_prompt_ids=encoded,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            stop_on_eos=stop_on_eos,
            seed=seed,
            prefill_chunk_size=prefill_chunk_size,
        )
        texts = [self.tokenizer.decode(ids, skip_special_tokens=True) for ids in out_ids]
        return texts, metrics

    def close(self) -> None:
        """Release the KV cache and weight mapping. Never raises: a cleanup
        failure must not mask the original constructor error — cleanup errors
        are warned instead (7D-3)."""
        self._out_norm_w = None
        kv = getattr(self, "kv_cache", None)
        if kv is not None:
            try:
                kv.close()
            except Exception as exc:
                warnings.warn(
                    f"LlamaInferenceEngine.close(): KV cache cleanup failed: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
        st = getattr(self, "streamer", None)
        if st is not None:
            try:
                st.close()
            except Exception as exc:
                warnings.warn(
                    f"LlamaInferenceEngine.close(): weight streamer cleanup "
                    f"failed: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )

    def __enter__(self) -> "LlamaInferenceEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gfx1150-infer",
        description="SSD-offloaded GGUF LLM inference engine for AMD gfx1150 GPUs",
    )
    parser.add_argument("--model", "-m", required=True, help="Path to .gguf model file")
    parser.add_argument("--prompt", "-p", default="Hello", help="Input prompt text")
    parser.add_argument("--max-new-tokens", "-n", type=int, default=32, help="Tokens to generate")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="Max KV cache sequence length")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature (0 = greedy)")
    parser.add_argument("--top-k", type=int, default=40, help="Top-K sampling cutoff")
    parser.add_argument("--top-p", type=float, default=0.95, help="Top-P nucleus sampling cutoff")
    parser.add_argument("--repetition-penalty", type=float, default=1.0, help="Repetition penalty")
    parser.add_argument("--prefill-chunk-size", type=int, default=None, help="Chunk size for prompt prefill")
    parser.add_argument("--offload-kv-cpu", action="store_true", help="Offload KV cache to CPU RAM")
    parser.add_argument("--kv-mmap-dir", default=None, help="Directory for SSD mmap-backed KV cache")
    parser.add_argument("--rope-neox", action="store_true", default=None, help="Use NeoX half-dim RoPE rotation")
    parser.add_argument(
        "--residency",
        choices=["auto", "pin", "stream"],
        default=None,
        help=(
            "Weight page-cache residency policy: 'auto' (default) pins in the host "
            "page cache when the model fits the measured budget, else streams; "
            "'pin' keeps pages resident (explicit request; warns over budget); "
            "'stream' evicts after each layer (best-effort). Not GTT pinning: "
            "weights are still copied H2D per projection."
        ),
    )
    parser.add_argument(
        "--cache-weights",
        action="store_true",
        help="(deprecated alias for --residency pin; --residency wins if both given)",
    )
    parser.add_argument(
        "--residency-budget-mb",
        type=int,
        default=None,
        help="Override the measured weight-residency budget with MB (for reproducible tests)",
    )
    parser.add_argument(
        "--max-kv-bytes",
        type=int,
        default=None,
        help="User cap on the KV cache bytes (the allocation also refuses requests exceeding available GTT/host/cgroup)",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args(argv)

    with LlamaInferenceEngine(
        model_path=args.model,
        max_seq_len=args.max_seq_len,
        offload_kv_to_cpu=args.offload_kv_cpu,
        kv_mmap_dir=args.kv_mmap_dir,
        rope_neox=args.rope_neox,
        residency=args.residency,
        cache_weights=args.cache_weights,
        residency_budget_mb=args.residency_budget_mb,
        max_kv_bytes=args.max_kv_bytes,
    ) as engine:
        text, metrics = engine.generate(
            prompt=args.prompt,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_k=args.top_k,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            seed=args.seed,
            prefill_chunk_size=args.prefill_chunk_size,
        )
        print(text)
        print(
            f"\n[gfx1150-infer] Generated {int(metrics['tokens_generated'])} tokens in "
            f"{metrics['total_time_s']:.2f}s ({metrics['tokens_per_sec']:.2f} tok/s, "
            f"decode: {metrics['decode_tokens_per_sec']:.2f} tok/s)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
