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
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
import numpy as np

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.append(_SRC_DIR)

from gguf_parser import (
    GGMLType,
    GGUFTensorInfo,
    dequantize_q4_0_cpu,
    dequantize_q8_0_cpu,
    dequantize_q4_k_cpu,
    dequantize_q6_k_cpu,
)

SPIECE_UNDERLINE = "\u2581"  # '▁' used by SentencePiece / Llama tokenizers
GPT2_SPACE = "\u0120"        # 'Ġ' used by GPT-2 / Llama-3 / Qwen2 byte-level BPE tokenizers

#: The GPT-2 pre-tokenizer, on the Unicode classes of the reference pattern
#: `'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+`.
#:
#: Python's `re` has no `\p{...}` classes. `[^\W\d_]` is `\w` without digits
#: and the underscore, which is the `\p{L}` run in every 7A-3 golden case;
#: `[^\s\w]|_` is the `[^\s\p{L}\p{N}]` class (the underscore is `\w` but
#: not a letter). Verified against all 7A-3 GPT-2 goldens, including `a_b`,
#: `don't`, `café`, `Ω`, and the emoji case.
_GPT2_PRETOKENIZE_RE = re.compile(
    r"'s|'t|'re|'ve|'m|'ll|'d| ?[^\W\d_]+| ?\d+| ?(?:[^\s\w]|_)+|\s+(?!\S)|\s+"
)

#: The SentencePiece unk penalty: fallback byte tokens always score below
#: every real unigram piece, the way the reference tokenizer treats them.
_UNK_PENALTY = 10.0


def _gpt2_bytes_to_unicode() -> Tuple[Dict[int, str], Dict[str, int]]:
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    b2u = {b: chr(c) for b, c in zip(bs, cs)}
    u2b = {chr(c): b for b, c in zip(bs, cs)}
    return b2u, u2b


_GPT2_B2U, _GPT2_U2B = _gpt2_bytes_to_unicode()


class GGUFTokenizer:
    """
    SentencePiece (`▁`) and GPT-2 byte-level (`Ġ`) BPE tokenizer initialized directly
    from GGUF metadata:
      - `tokenizer.ggml.tokens`
      - `tokenizer.ggml.scores` (optional)
      - `tokenizer.ggml.merges` (optional)
      - `tokenizer.ggml.token_type` (optional)
      - `tokenizer.ggml.model` (optional)
      - `tokenizer.ggml.add_bos_token` (optional)
      - `tokenizer.ggml.bos_token_id`
      - `tokenizer.ggml.eos_token_id`
    """

    def __init__(
        self,
        tokens: Sequence[str],
        scores: Optional[Sequence[float]] = None,
        bos_token_id: int = 1,
        eos_token_id: int = 2,
        merges: Optional[Sequence[str]] = None,
        token_types: Optional[Sequence[int]] = None,
        tokenizer_model: Optional[str] = None,
        add_bos_token: Optional[bool] = None,
    ):
        self.id_to_token: List[str] = list(tokens)
        self.vocab_size: int = len(self.id_to_token)
        self.token_to_id: Dict[str, int] = {tok: i for i, tok in enumerate(self.id_to_token)}
        self.scores: List[float] = (
            [float(s) for s in scores] if scores is not None else [0.0] * self.vocab_size
        )
        self.bos_token_id: int = int(bos_token_id)
        self.eos_token_id: int = int(eos_token_id)
        self.tokenizer_model: Optional[str] = (
            str(tokenizer_model).lower() if tokenizer_model is not None else None
        )
        # The `tokenizer.ggml.add_bos_token` metadata value, or None when the
        # key is absent.
        self.add_bos_token: Optional[bool] = (
            None if add_bos_token is None else bool(add_bos_token)
        )
        self._token_types: Optional[List[int]] = (
            [int(t) for t in token_types] if token_types is not None else None
        )

        self.merge_ranks: Dict[Tuple[str, str], int] = {}
        if merges:
            for rank, entry in enumerate(merges):
                parts = str(entry).split(" ", 1)
                if len(parts) == 2:
                    self.merge_ranks[(parts[0], parts[1])] = rank

        # Detect SentencePiece ('▁') vs GPT-2 byte-level ('Ġ') vocabulary
        self._uses_spiece = any(SPIECE_UNDERLINE in t for t in self.id_to_token)
        self._uses_gpt2 = (
            not self._uses_spiece
            and (
                self.tokenizer_model == "gpt2"
                or bool(self.merge_ranks)
                or any(GPT2_SPACE in t for t in self.id_to_token)
            )
        )

        # Collect special/control token IDs (GGUF token_type 3=CONTROL, 4=USER_DEFINED)
        self._special_token_ids: Set[int] = set()
        if 0 <= self.bos_token_id < self.vocab_size:
            self._special_token_ids.add(self.bos_token_id)
        if 0 <= self.eos_token_id < self.vocab_size:
            self._special_token_ids.add(self.eos_token_id)
        if token_types is not None:
            for idx, ttype in enumerate(token_types):
                if idx < self.vocab_size and int(ttype) in (3, 4):
                    self._special_token_ids.add(idx)

        # Longest-match table over the special token strings. A special token
        # in the input is emitted as its own ID even when it is a proper
        # prefix of another special token (the longer match wins).
        self._special_token_to_id: Dict[str, int] = {}
        for tid in sorted(self._special_token_ids):
            self._special_token_to_id.setdefault(self.id_to_token[tid], tid)
        self._special_max_len: int = max(
            (len(tok) for tok in self._special_token_to_id), default=0
        )

    @classmethod
    def from_gguf_metadata(cls, metadata: Dict[str, Any]) -> "GGUFTokenizer":
        tokens = metadata.get("tokenizer.ggml.tokens")
        if not tokens:
            raise KeyError("GGUF metadata missing 'tokenizer.ggml.tokens'")
        scores = metadata.get("tokenizer.ggml.scores")
        merges = metadata.get("tokenizer.ggml.merges")
        token_types = metadata.get("tokenizer.ggml.token_type")
        tokenizer_model = metadata.get("tokenizer.ggml.model")
        bos_id = int(metadata.get("tokenizer.ggml.bos_token_id", 1))
        eos_id = int(metadata.get("tokenizer.ggml.eos_token_id", 2))
        add_bos_token = metadata.get("tokenizer.ggml.add_bos_token")
        return cls(
            tokens=tokens,
            scores=scores,
            bos_token_id=bos_id,
            eos_token_id=eos_id,
            merges=merges,
            token_types=token_types,
            tokenizer_model=str(tokenizer_model) if tokenizer_model is not None else None,
            add_bos_token=bool(add_bos_token) if add_bos_token is not None else None,
        )

    def _is_normal_piece(self, idx: int) -> bool:
        """A Viterbi candidate: a NORMAL token (or any non-special token when
        the GGUF carries no `tokenizer.ggml.token_type` array)."""
        if self._token_types is not None:
            return idx < self.vocab_size and self._token_types[idx] == 1
        return idx not in self._special_token_ids

    def _default_add_bos(self) -> bool:
        """The family default the reference tokenizer applies when the GGUF
        carries no `tokenizer.ggml.add_bos_token` key: a BOS for
        SentencePiece, none for a byte-level BPE vocabulary."""
        return self._uses_spiece

    def _bpe_merge_symbols(self, symbols: List[str]) -> List[int]:
        n = len(symbols)
        if n == 0:
            return []
        if n == 1:
            tok_id = self.token_to_id.get(symbols[0])
            if tok_id is None:
                raise ValueError(f"Token {symbols[0]!r} not found in vocabulary")
            return [tok_id]

        prev_idx = [i - 1 for i in range(n)]
        next_idx = [i + 1 if i + 1 < n else -1 for i in range(n)]
        alive = [True] * n
        ver = [0] * n
        heap: List[Tuple[float, int, int, int, int]] = []
        use_ranks = bool(self.merge_ranks)

        def _try_push(left: int, right: int) -> None:
            if left < 0 or right < 0:
                return
            l_sym = symbols[left]
            r_sym = symbols[right]
            merged = l_sym + r_sym
            tid = self.token_to_id.get(merged)
            if tid is None:
                return
            if use_ranks:
                rank = self.merge_ranks.get((l_sym, r_sym))
                if rank is None:
                    return
                priority = float(rank)
            else:
                priority = -self.scores[tid]
            heapq.heappush(heap, (priority, left, right, ver[left], ver[right]))

        for i in range(n - 1):
            _try_push(i, i + 1)

        while heap:
            _, left, right, v_left, v_right = heapq.heappop(heap)
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

        out_ids: List[int] = []
        cur = 0
        while cur != -1:
            sym = symbols[cur]
            tid = self.token_to_id.get(sym)
            if tid is None:
                raise ValueError(f"Merged symbol {sym!r} not found in vocabulary")
            out_ids.append(tid)
            cur = next_idx[cur]
        return out_ids

    def _chars_to_symbols(self, piece: str) -> List[str]:
        symbols: List[str] = []
        for ch in piece:
            if ch in self.token_to_id:
                symbols.append(ch)
            else:
                for b in ch.encode("utf-8"):
                    hex_tok = f"<0x{b:02X}>"
                    if hex_tok in self.token_to_id:
                        symbols.append(hex_tok)
                    else:
                        raise ValueError(
                            f"Unmappable character {ch!r} (byte 0x{b:02X}) not in vocabulary"
                        )
        return symbols

    def encode(
        self,
        text: str,
        add_bos: Optional[bool] = None,
        parse_special: bool = True,
    ) -> List[int]:
        """
        Encode text into token IDs.

        A special token (`tokenizer.ggml.token_type` CONTROL or USER_DEFINED,
        or the BOS/EOS token) inside the text is emitted as its own token ID
        when `parse_special` is true -- lowercase `<|endoftext|>`-style
        look-alikes that are not in the vocabulary stay ordinary text.

        The BOS token is added when, in precedence order: the explicit
        `add_bos` argument is true; else the `tokenizer.ggml.add_bos_token`
        metadata is true; else the family default (a BOS for SentencePiece,
        none for byte-level BPE) is true.

        Raises `ValueError` if input contains bytes/characters that cannot
        be represented.
        """
        if not isinstance(text, str):
            raise TypeError(f"encode() expects a string, got {type(text).__name__}")
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as exc:
            # A lone surrogate cannot be represented as UTF-8 at all; report
            # it in the same vocabulary terms as any other unmappable byte.
            raise ValueError(f"Input text is not encodable as UTF-8: {exc}") from exc

        ids: List[int] = []
        if add_bos is None:
            add_bos = (
                self.add_bos_token if self.add_bos_token is not None
                else self._default_add_bos()
            )
        if add_bos and 0 <= self.bos_token_id < self.vocab_size:
            ids.append(self.bos_token_id)

        if not text:
            return ids

        if parse_special and self._special_token_to_id:
            for chunk, offset, special_id in self._split_special_tokens(text):
                if special_id is not None:
                    ids.append(special_id)
                elif chunk:
                    # Only a chunk at offset 0 opens the input: only it gets
                    # the SentencePiece dummy `▁` prefix. A chunk that follows
                    # a special token continues the text.
                    ids.extend(self._encode_plain(chunk, prepend_dummy=offset == 0))
        else:
            ids.extend(self._encode_plain(text, prepend_dummy=True))
        return ids

    def _split_special_tokens(self, text: str) -> List[Tuple[Optional[str], int, Optional[int]]]:
        """Split `text` into `(ordinary chunk, chunk offset, special ID)` runs.

        Ordinary chunks (`special_id is None`) report where they start; a
        special ID run reports the position of the token. Longest match: a
        special token that is a proper prefix of another special token loses
        to the longer one.
        """
        out: List[Tuple[Optional[str], int, Optional[int]]] = []
        buf: List[str] = []
        smap = self._special_token_to_id
        max_len = self._special_max_len
        i = 0
        n = len(text)
        while i < n:
            matched_id: Optional[int] = None
            for length in range(min(max_len, n - i), 0, -1):
                tid = smap.get(text[i : i + length])
                if tid is not None:
                    matched_id = tid
                    i += length
                    break
            if matched_id is None:
                buf.append(text[i])
                i += 1
                continue
            if buf:
                out.append(("".join(buf), i - len(buf), None))
                buf = []
            out.append((None, i, matched_id))
        if buf:
            out.append(("".join(buf), i - len(buf), None))
        return out

    def _encode_plain(self, text: str, prepend_dummy: bool = True) -> List[int]:
        """Encode text known to contain no special tokens."""
        if self._uses_gpt2:
            return self._encode_gpt2(text)
        if self._uses_spiece:
            return self._encode_spiece(text, prepend_dummy=prepend_dummy)
        # An undetermined family: character symbols and score-priority merges.
        symbols = self._chars_to_symbols(text)
        return self._bpe_merge_symbols(symbols)

    def _encode_gpt2(self, text: str) -> List[int]:
        ids: List[int] = []
        for chunk in _GPT2_PRETOKENIZE_RE.findall(text):
            mapped = "".join(_GPT2_B2U[b] for b in chunk.encode("utf-8"))
            # If individual byte-level chars are absent from a minimal synthetic vocab
            # but the whole chunk token exists, emit it directly.
            if any(ch not in self.token_to_id for ch in mapped) and mapped in self.token_to_id:
                ids.append(self.token_to_id[mapped])
                continue
            symbols = self._chars_to_symbols(mapped)
            ids.extend(self._bpe_merge_symbols(symbols))
        return ids

    def _encode_spiece(self, text: str, prepend_dummy: bool = True) -> List[int]:
        """SentencePiece unigram segmentation: Viterbi over the byte string
        of the normalized text, maximizing the sum of the GGUF unigram
        scores, with `<0xXX>` byte tokens as the penalized fallback."""
        normalized = text.replace(" ", SPIECE_UNDERLINE)
        if prepend_dummy and not normalized.startswith(SPIECE_UNDERLINE):
            normalized = SPIECE_UNDERLINE + normalized
        return self._viterbi_unigram(normalized)

    def _viterbi_unigram(self, text: str) -> List[int]:
        data = text.encode("utf-8")
        n = len(data)
        neg_inf = float("-inf")

        # Candidates: NORMAL pieces, grouped by byte length.
        candidates: Dict[int, Dict[bytes, int]] = {}
        max_len = 1
        normal_scores: List[float] = []
        for idx in range(self.vocab_size):
            if not self._is_normal_piece(idx):
                continue
            piece = self.id_to_token[idx].encode("utf-8")
            candidates.setdefault(len(piece), {})[piece] = idx
            max_len = max(max_len, len(piece))
            normal_scores.append(self.scores[idx])

        min_normal = min(normal_scores) if normal_scores else 0.0
        byte_score = min_normal - _UNK_PENALTY

        dp = [neg_inf] * (n + 1)
        prev: List[Optional[Tuple[int, int]]] = [None] * (n + 1)
        dp[0] = 0.0
        for i in range(n):
            if dp[i] == neg_inf:
                continue
            base = dp[i]
            top = min(max_len, n - i)
            for length in range(1, top + 1):
                table = candidates.get(length)
                if not table:
                    continue
                tid = table.get(data[i : i + length])
                if tid is None:
                    continue
                score = base + self.scores[tid]
                if score > dp[i + length]:
                    dp[i + length] = score
                    prev[i + length] = (i, tid)
            # Penalized `<0xXX>` byte fallback for every byte of the input.
            byte_token = self.token_to_id.get(f"<0x{data[i]:02X}>")
            if byte_token is not None and byte_token not in self._special_token_ids:
                score = base + byte_score
                if score > dp[i + 1]:
                    dp[i + 1] = score
                    prev[i + 1] = (i, byte_token)

        if dp[n] == neg_inf:
            # The segmentation stalled at the last reachable position; report
            # the byte that could not be covered (never a byte before one that
            # could, so a multi-byte codepoint is named by the byte that
            # actually stopped the walk, not by an earlier boundary).
            last = 0
            for i in range(1, n + 1):
                if dp[i] != neg_inf:
                    last = i
            ch = data[last:].decode("utf-8", errors="ignore")[:1]
            raise ValueError(
                f"Unmappable character {ch!r} (byte 0x{data[last]:02X}) not in vocabulary"
            )

        ids: List[int] = []
        cur = n
        while cur > 0:
            at, tid = prev[cur]  # type: Tuple[int, int]
            ids.append(tid)
            cur = at
        ids.reverse()
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
            if skip_special_tokens and tid in self._special_token_ids:
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
        if self._uses_gpt2:
            byte_out = bytearray()
            out_parts: List[str] = []
            for ch in text:
                if ch in _GPT2_U2B:
                    byte_out.append(_GPT2_U2B[ch])
                else:
                    if byte_out:
                        out_parts.append(byte_out.decode("utf-8", errors="replace"))
                        byte_out.clear()
                    out_parts.append(ch)
            if byte_out:
                out_parts.append(byte_out.decode("utf-8", errors="replace"))
            return "".join(out_parts)
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

    if embd_info.ggml_type == GGMLType.Q6_K:
        row_bytes = (hidden_size // 256) * 210
        raw_u8 = embd_view.view(np.uint8).reshape(-1, row_bytes)
        _validate_token_ids(ids_arr, raw_u8.shape[0])
        gathered = np.ascontiguousarray(raw_u8[ids_arr])
        return dequantize_q6_k_cpu(gathered, seq_len * hidden_size).reshape(seq_len, hidden_size)

    raise ValueError(f"Unsupported token_embd.weight type: {embd_info.ggml_type}")
