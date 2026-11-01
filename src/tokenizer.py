"""
GGUF Metadata Tokenizer & Token Embedding Lookup (`GGUFTokenizer`, `embed_tokens`)
for gfx1150-inference.

Extracts vocabulary tokens, scores, and special token IDs directly from a GGUF header
without external tokenizer file dependencies, and performs vectorized row-wise token
embedding lookup (supporting `Q4_0`, `Q8_0`, `Q4_K`, `F16`, and `F32` `token_embd.weight` tensors).
"""

from __future__ import annotations

import heapq
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.abspath(os.path.join(_SRC_DIR, "..", "build"))
for _p in (_SRC_DIR, _BUILD_DIR):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from gguf_parser import (
    GGMLType,
    GGUFTensorInfo,
    dequantize_q4_0_cpu,
    dequantize_q8_0_cpu,
    dequantize_q4_k_cpu,
)

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
        Encode text into token IDs using SentencePiece normalization + O(L log L)
        priority-queue BPE highest-score merge (with `<0xXX>` byte fallback for unknown UTF-8 bytes).
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

        n = len(symbols)
        if n == 0:
            return ids
        if n == 1:
            tok_id = self.token_to_id.get(symbols[0])
            if tok_id is not None:
                ids.append(tok_id)
            return ids

        # Doubly-linked symbol list + min-heap keyed by (-score, left_pos, right_pos, ver_left, ver_right)
        prev_idx = [i - 1 for i in range(n)]
        next_idx = [i + 1 if i + 1 < n else -1 for i in range(n)]
        alive = [True] * n
        ver = [0] * n
        heap: List[Tuple[float, int, int, int, int]] = []

        def _try_push(left: int, right: int) -> None:
            if left < 0 or right < 0:
                return
            merged = symbols[left] + symbols[right]
            tid = self.token_to_id.get(merged)
            if tid is not None:
                heapq.heappush(heap, (-self.scores[tid], left, right, ver[left], ver[right]))

        for i in range(n - 1):
            _try_push(i, i + 1)

        while heap:
            neg_score, left, right, v_left, v_right = heapq.heappop(heap)
            if (
                not alive[left]
                or not alive[right]
                or next_idx[left] != right
                or ver[left] != v_left
                or ver[right] != v_right
            ):
                continue

            symbols[left] = symbols[left] + symbols[right]
            ver[left] += 1
            alive[right] = False

            nxt = next_idx[right]
            next_idx[left] = nxt
            if nxt != -1:
                prev_idx[nxt] = left

            _try_push(prev_idx[left], left)
            _try_push(left, nxt)

        cur = 0
        while cur != -1:
            sym = symbols[cur]
            tid = self.token_to_id.get(sym)
            if tid is not None:
                ids.append(tid)
            cur = next_idx[cur]

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


def _validate_token_ids(ids_arr: np.ndarray, n_rows: int) -> None:
    if ids_arr.size == 0:
        return
    oob_mask = (ids_arr < 0) | (ids_arr >= n_rows)
    if np.any(oob_mask):
        bad_id = int(ids_arr[oob_mask][0])
        raise ValueError(f"Token ID {bad_id} is out of range for embedding table with {n_rows} rows")


def embed_tokens(
    token_ids: Sequence[int],
    embd_info: GGUFTensorInfo,
    embd_view: np.ndarray,
    hidden_size: int,
) -> np.ndarray:
    """
    Look up token embeddings `(len(token_ids), hidden_size)` in `np.float16`
    from `token_embd.weight` using vectorized gather and batched row dequantization.
    """
    ids_arr = np.asarray(token_ids, dtype=np.int64).reshape(-1)
    seq_len = int(ids_arr.size)
    if seq_len == 0:
        return np.empty((0, hidden_size), dtype=np.float16)

    if embd_info.ggml_type == GGMLType.F16:
        table = embd_view.view(np.float16).reshape(-1, hidden_size)
        _validate_token_ids(ids_arr, table.shape[0])
        return np.ascontiguousarray(table[ids_arr], dtype=np.float16)

    if embd_info.ggml_type == GGMLType.F32:
        table = embd_view.view(np.float32).reshape(-1, hidden_size)
        _validate_token_ids(ids_arr, table.shape[0])
        return np.ascontiguousarray(table[ids_arr].astype(np.float16))

    if embd_info.ggml_type == GGMLType.Q4_0:
        row_bytes = (hidden_size // 32) * 18
        raw_u8 = embd_view.view(np.uint8).reshape(-1, row_bytes)
        _validate_token_ids(ids_arr, raw_u8.shape[0])
        gathered = np.ascontiguousarray(raw_u8[ids_arr])
        return dequantize_q4_0_cpu(gathered, seq_len * hidden_size).reshape(seq_len, hidden_size)

    if embd_info.ggml_type == GGMLType.Q8_0:
        row_bytes = (hidden_size // 32) * 34
        raw_u8 = embd_view.view(np.uint8).reshape(-1, row_bytes)
        _validate_token_ids(ids_arr, raw_u8.shape[0])
        gathered = np.ascontiguousarray(raw_u8[ids_arr])
        return dequantize_q8_0_cpu(gathered, seq_len * hidden_size).reshape(seq_len, hidden_size)

    if embd_info.ggml_type == GGMLType.Q4_K:
        row_bytes = (hidden_size // 256) * 144
        raw_u8 = embd_view.view(np.uint8).reshape(-1, row_bytes)
        _validate_token_ids(ids_arr, raw_u8.shape[0])
        gathered = np.ascontiguousarray(raw_u8[ids_arr])
        return dequantize_q4_k_cpu(gathered, seq_len * hidden_size).reshape(seq_len, hidden_size)

    raise ValueError(f"Unsupported token_embd.weight type: {embd_info.ggml_type}")
