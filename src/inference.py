"""
End-to-End SSD-Streamed Llama Inference Engine (`LlamaInferenceEngine`) for AMD gfx1150.

Coordinates:
1. GGUF metadata, tokenizer (`GGUFTokenizer`), and memory-mapped weight streaming (`WeightStreamer`).
2. GPU-resident offset-addressed GQA KV Cache (`KVCacheManager`) with zero per-step host slice copies.
3. Layer-wise ping-pong SSD prefetching (`MADV_WILLNEED` on Layer L+1 while GPU computes Layer L,
   followed by `MADV_DONTNEED` page eviction on Layer L) so RAM usage stays strictly bounded.
4. Final RMSNorm, LM Head projection (`output.weight` or tied `token_embd.weight`), and
   configurable Top-K / Top-P / Temperature / Repetition-Penalty token sampling.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import GGUFTensorInfo
from weight_loader import WeightStreamer
from kv_cache import KVCacheManager
from layer import LlamaLayerConfig, TransformerLayer, linear_project, norm_weight_fp16
from tokenizer import GGUFTokenizer, embed_tokens
import matmul_module


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
    Uses greedy argmax when `temperature <= 0.0` or `top_k == 1`.
    """
    logits = logits_fp16.astype(np.float32).reshape(-1).copy()

    if repetition_penalty != 1.0 and generated_ids:
        for tid in set(generated_ids):
            if 0 <= tid < logits.size:
                if logits[tid] > 0:
                    logits[tid] /= repetition_penalty
                else:
                    logits[tid] *= repetition_penalty

    if temperature <= 0.0 or top_k == 1:
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
        sorted_probs /= np.sum(sorted_probs)
        if rng is None:
            rng = np.random.default_rng()
        choice = int(rng.choice(sorted_idx, p=sorted_probs))
        return choice

    if rng is None:
        rng = np.random.default_rng()
    return int(rng.choice(logits.size, p=probs))


class LlamaInferenceEngine:
    """
    Full-model SSD-offloaded LLM inference engine for AMD gfx1150.
    """

    def __init__(self, model_path: str, max_seq_len: int = 2048):
        self.model_path = model_path
        self.streamer = WeightStreamer(model_path)
        self.metadata = self.streamer.gguf.metadata
        self.num_layers = int(self.metadata["llama.block_count"])
        self.layer_cfg = LlamaLayerConfig.from_gguf_metadata(self.metadata)
        self.layer_runner = TransformerLayer(self.layer_cfg)
        self.max_seq_len = int(max_seq_len)

        self.tokenizer: Optional[GGUFTokenizer] = None
        if "tokenizer.ggml.tokens" in self.metadata:
            self.tokenizer = GGUFTokenizer.from_gguf_metadata(self.metadata)
            self.vocab_size = self.tokenizer.vocab_size
        else:
            emb_info = self.streamer.gguf.tensors["token_embd.weight"]
            self.vocab_size = emb_info.shape_row_major[0]

        self.kv_cache = KVCacheManager(
            num_layers=self.num_layers,
            max_seq_len=self.max_seq_len,
            num_kv_heads=self.layer_cfg.num_kv_heads,
            head_dim=self.layer_cfg.head_dim,
        )

    def _get_global_tensor(self, name: str) -> Tuple[GGUFTensorInfo, np.ndarray]:
        info = self.streamer.gguf.tensors[name]
        view = self.streamer.get_tensor_view(name)
        return info, view

    def forward_tokens(
        self,
        token_ids: Sequence[int],
        pos_offset: int = 0,
    ) -> np.ndarray:
        """
        Run a full-model forward pass for `token_ids` starting at `pos_offset`,
        streaming each transformer layer from SSD with ping-pong prefetch (`MADV_WILLNEED`)
        and immediate page eviction (`MADV_DONTNEED`).

        Returns:
            Next-token logits `(vocab_size,)` in `np.float16` for the last token in `token_ids`.
        """
        emb_info, emb_view = self._get_global_tensor("token_embd.weight")
        hidden = embed_tokens(token_ids, emb_info, emb_view, self.layer_cfg.hidden_size)
        del emb_view

        # Kick off SSD prefetch for Layer 0 before entering the layer loop
        if self.num_layers > 0:
            self.streamer.prefetch_layer(0)

        for layer_idx in range(self.num_layers):
            hidden, _ = self.layer_runner.forward_streamed(
                hidden_states=hidden,
                streamer=self.streamer,
                layer_idx=layer_idx,
                pos_offset=pos_offset,
                kv_cache=self.kv_cache,
                prefetch_next=(layer_idx + 1 < self.num_layers),
            )

        # Final RMSNorm only on the last token position `(1, hidden_size)` to save compute
        last_hidden = np.ascontiguousarray(hidden[-1:, :], dtype=np.float16)
        out_norm_entry = self._get_global_tensor("output_norm.weight")
        out_norm_w = norm_weight_fp16(out_norm_entry)
        normed_last = np.empty_like(last_hidden)
        matmul_module.rmsnorm(
            last_hidden,
            out_norm_w,
            normed_last,
            1,
            self.layer_cfg.hidden_size,
            self.layer_cfg.rms_norm_eps,
        )
        del out_norm_entry, out_norm_w

        # LM Head projection (`output.weight` or weight-tied `token_embd.weight`)
        head_name = (
            "output.weight"
            if "output.weight" in self.streamer.gguf.tensors
            else "token_embd.weight"
        )
        head_entry = self._get_global_tensor(head_name)
        logits_2d = linear_project(normed_last, head_entry, self.vocab_size)
        del head_entry

        return logits_2d.reshape(-1)

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
    ) -> Tuple[List[int], Dict[str, float]]:
        """
        Autoregressively generate up to `max_new_tokens` token IDs from `prompt_ids`.
        Returns `(generated_token_ids, metrics_dict)`.
        """
        if not prompt_ids:
            raise ValueError("prompt_ids must not be empty")

        self.kv_cache.reset()
        rng = np.random.default_rng(seed)
        all_ids: List[int] = [int(t) for t in prompt_ids]
        new_ids: List[int] = []

        t_start = time.time()
        # 1. Prompt prefill
        logits = self.forward_tokens(all_ids, pos_offset=0)
        t_prefill = time.time() - t_start

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
        t_decode_start = time.time()
        eos_id = self.tokenizer.eos_token_id if self.tokenizer is not None else -1

        for _ in range(max_new_tokens - 1):
            if stop_on_eos and next_id == eos_id:
                break
            pos = len(all_ids) - 1
            logits = self.forward_tokens([next_id], pos_offset=pos)
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

        t_decode = time.time() - t_decode_start
        t_total = time.time() - t_start
        decode_steps = max(len(new_ids) - 1, 1)

        metrics = {
            "prefill_time_s": t_prefill,
            "decode_time_s": t_decode,
            "total_time_s": t_total,
            "tokens_generated": float(len(new_ids)),
            "tokens_per_sec": len(new_ids) / max(t_total, 1e-9),
            "decode_tokens_per_sec": decode_steps / max(t_decode, 1e-9),
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
    ) -> Tuple[str, Dict[str, float]]:
        """Encode `prompt`, generate up to `max_new_tokens`, and decode back to text."""
        if self.tokenizer is None:
            raise RuntimeError("GGUF file does not contain tokenizer metadata; use generate_ids().")
        prompt_ids = self.tokenizer.encode(prompt, add_bos=True)
        new_ids, metrics = self.generate_ids(
            prompt_ids=prompt_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            stop_on_eos=stop_on_eos,
            seed=seed,
        )
        return self.tokenizer.decode(new_ids, skip_special_tokens=True), metrics

    def close(self) -> None:
        if getattr(self, "kv_cache", None) is not None:
            self.kv_cache.close()
        if getattr(self, "streamer", None) is not None:
            self.streamer.close()

    def __enter__(self) -> "LlamaInferenceEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

