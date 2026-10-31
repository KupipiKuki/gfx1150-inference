"""
GGUF Metadata Tokenizer & Token Embedding Lookup (`GGUFTokenizer`, `embed_tokens`)
for gfx1150-inference.

Extracts vocabulary tokens, scores, and special token IDs directly from a GGUF header
without external tokenizer file dependencies, and performs zero-copy row-wise token
embedding lookup (supporting `Q4_0`, `F16`, and `F32` `token_embd.weight` tensors).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import GGMLType, GGUFTensorInfo, dequantize_q4_0_cpu

SPIECE_UNDERLINE = "\u2581"  # '▁' used by SentencePiece / Llama tokenizers


class GGUFTokenizer:
    """
    Lightweight SentencePiece/BPE tokenizer initialized directly from GGUF metadata:
      - `tokenizer.ggml.tokens`
      - `tokenizer.ggml.scores` (optional)
      - `tokenizer.ggml.bos_token_id`
      - `tokenizer.ggml.eos_token_id`
    """

    def __init__(
        self,
        tokens: Sequence[str],
        scores: Optional[Sequence[float]] = None,
        bos_token_id: int = 1,
        eos_token_id: int = 2,
    ):
        self.id_to_token: List[str] = list(tokens)
        self.vocab_size: int = len(self.id_to_token)
        self.token_to_id: Dict[str, int] = {tok: i for i, tok in enumerate(self.id_to_token)}
        self.scores: List[float] = (
            [float(s) for s in scores] if scores is not None else [0.0] * self.vocab_size
        )
        self.bos_token_id: int = int(bos_token_id)
        self.eos_token_id: int = int(eos_token_id)

        # Detect whether vocabulary uses SentencePiece '▁' prefix
        self._uses_spiece = any(SPIECE_UNDERLINE in t for t in self.id_to_token)

    @classmethod
    def from_gguf_metadata(cls, metadata: Dict[str, Any]) -> "GGUFTokenizer":
        tokens = metadata.get("tokenizer.ggml.tokens")
        if not tokens:
            raise KeyError("GGUF metadata missing 'tokenizer.ggml.tokens'")
        scores = metadata.get("tokenizer.ggml.scores")
        bos_id = int(metadata.get("tokenizer.ggml.bos_token_id", 1))
        eos_id = int(metadata.get("tokenizer.ggml.eos_token_id", 2))
        return cls(tokens=tokens, scores=scores, bos_token_id=bos_id, eos_token_id=eos_id)

    def encode(self, text: str, add_bos: bool = True) -> List[int]:
        """
        Encode text into token IDs using SentencePiece normalization + BPE highest-score merge
        (with `<0xXX>` byte fallback for unknown UTF-8 bytes).
        """
        ids: List[int] = []
        if add_bos and 0 <= self.bos_token_id < self.vocab_size:
            ids.append(self.bos_token_id)

        if not text:
            return ids

        normalized = text.replace(" ", SPIECE_UNDERLINE) if self._uses_spiece else text
        if self._uses_spiece and not normalized.startswith(SPIECE_UNDERLINE):
            normalized = SPIECE_UNDERLINE + normalized

        # Initial character / byte-fallback split
        symbols: List[str] = []
        for ch in normalized:
            if ch in self.token_to_id:
                symbols.append(ch)
            else:
                for b in ch.encode("utf-8"):
                    hex_tok = f"<0x{b:02X}>"
                    if hex_tok in self.token_to_id:
                        symbols.append(hex_tok)

        # Iteratively merge adjacent symbol pairs with the highest vocabulary score
        while len(symbols) >= 2:
            best_idx = -1
            best_score = -float("inf")
            for i in range(len(symbols) - 1):
                merged = symbols[i] + symbols[i + 1]
                tok_id = self.token_to_id.get(merged)
                if tok_id is not None:
                    score = self.scores[tok_id]
                    if score > best_score:
                        best_score = score
                        best_idx = i
            if best_idx < 0:
                break
            symbols[best_idx] = symbols[best_idx] + symbols[best_idx + 1]
            del symbols[best_idx + 1]

        for sym in symbols:
            if sym in self.token_to_id:
                ids.append(self.token_to_id[sym])

        return ids

    def decode(self, token_ids: Iterable[int], skip_special_tokens: bool = True) -> str:
        """Convert a sequence of token IDs back into a UTF-8 string."""
        raw_bytes = bytearray()
        pieces: List[str] = []

        def _flush_bytes() -> None:
            if raw_bytes:
                pieces.append(raw_bytes.decode("utf-8", errors="replace"))
                raw_bytes.clear()

        for tid in token_ids:
            tid = int(tid)
            if skip_special_tokens and tid in (self.bos_token_id, self.eos_token_id):
                continue
            if tid < 0 or tid >= self.vocab_size:
                continue
            tok = self.id_to_token[tid]
            if len(tok) == 6 and tok.startswith("<0x") and tok.endswith(">"):
                try:
                    raw_bytes.append(int(tok[3:5], 16))
                    continue
                except ValueError:
                    pass
            _flush_bytes()
            pieces.append(tok)

        _flush_bytes()
        text = "".join(pieces)
        if self._uses_spiece:
            text = text.replace(SPIECE_UNDERLINE, " ")
            if text.startswith(" "):
                text = text[1:]
        return text


def embed_tokens(
    token_ids: Sequence[int],
    embd_info: GGUFTensorInfo,
    embd_view: np.ndarray,
    hidden_size: int,
) -> np.ndarray:
    """
    Look up token embeddings `(len(token_ids), hidden_size)` in `np.float16`
    from `token_embd.weight` without dequantizing the entire vocabulary table.
    """
    ids = [int(t) for t in token_ids]
    seq_len = len(ids)
    out = np.empty((seq_len, hidden_size), dtype=np.float16)

    if embd_info.ggml_type == GGMLType.F16:
        table = embd_view.view(np.float16).reshape(-1, hidden_size)
        for i, tid in enumerate(ids):
            out[i] = table[tid]
        return out

    if embd_info.ggml_type == GGMLType.F32:
        table = embd_view.view(np.float32).reshape(-1, hidden_size)
        for i, tid in enumerate(ids):
            out[i] = table[tid].astype(np.float16)
        return out

    if embd_info.ggml_type == GGMLType.Q4_0:
        row_bytes = (hidden_size // 32) * 18
        raw_u8 = embd_view.view(np.uint8).reshape(-1, row_bytes)
        for i, tid in enumerate(ids):
            out[i] = dequantize_q4_0_cpu(raw_u8[tid], hidden_size)
        return out

    raise ValueError(f"Unsupported token_embd.weight type: {embd_info.ggml_type}")

