"""
Memory-mapped SSD weight streamer with Linux page-cache management (`madvise`)
for AMD gfx1150 unified memory systems.
"""

from __future__ import annotations

import contextlib
import mmap
import os
import sys
from typing import Dict, FrozenSet, Iterator, Optional, Tuple
import numpy as np

try:
    from .gguf_parser import GGMLType, GGUFParser, GGUFTensorInfo
except ImportError:
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SRC_DIR not in sys.path:
        sys.path.append(_SRC_DIR)
    from gguf_parser import GGMLType, GGUFParser, GGUFTensorInfo


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096

SUPPORTED_COMPUTE_GGML_TYPES: FrozenSet[GGMLType] = frozenset({
    GGMLType.F32,
    GGMLType.F16,
    GGMLType.Q4_0,
    GGMLType.Q8_0,
    GGMLType.Q4_K,
    GGMLType.Q6_K,
})


def _page_align_span(offset: int, length: int) -> tuple[int, int]:
    """Align `(offset, length)` outward to OS page boundaries for `madvise`."""
    aligned_start = (offset // PAGE_SIZE) * PAGE_SIZE
    end = offset + length
    aligned_end = ((end + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
    return aligned_start, aligned_end - aligned_start


class WeightStreamer:
    """
    Streams GGUF model tensors directly from SSD via read-only `mmap` (`ACCESS_READ`)
    with explicit `MADV_WILLNEED` prefetching and `MADV_DONTNEED` clean page-cache
    reclamation hints. When `cache_weights=True`, skips `MADV_DONTNEED` eviction so
    models that fit within host/unified RAM stay resident in the OS page cache.
    """

    def __init__(
        self,
        model_path: str,
        cache_weights: bool = False,
        validate_types: bool = True,
    ):
        self.model_path = model_path
        self.cache_weights = bool(cache_weights)
        self._file = open(model_path, "rb")
        self._mm = None
        try:
            self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            self.gguf = GGUFParser(self._mm)
            arch = str(self.gguf.metadata.get("general.architecture", "llama"))
            self.num_layers = int(
                self.gguf.metadata.get(
                    f"{arch}.block_count",
                    self.gguf.metadata.get("llama.block_count", 0),
                )
            )
            if validate_types:
                self.validate_supported_tensors()

            # Advise sequential access pattern by default
            if hasattr(mmap, "MADV_SEQUENTIAL"):
                self._mm.madvise(mmap.MADV_SEQUENTIAL)
        except BaseException:
            self.close()
            raise

    def validate_supported_tensors(self) -> None:
        """
        Fail-fast load-time check that all tensors in the GGUF file use a supported
        compute quantization type (`F32`, `F16`, `Q4_0`, `Q8_0`, `Q4_K`, `Q6_K`).
        """
        unsupported = [
            f"{info.name} ({info.ggml_type.name})"
            for info in self.gguf.tensors.values()
            if info.ggml_type not in SUPPORTED_COMPUTE_GGML_TYPES
        ]
        if unsupported:
            supported_names = ", ".join(sorted(t.name for t in SUPPORTED_COMPUTE_GGML_TYPES))
            raise ValueError(
                f"Model contains tensors with unsupported quantization types: "
                f"{', '.join(unsupported[:8])}. Supported types: {supported_names}."
            )

    def get_tensor_view(self, name: str) -> np.ndarray:
        """
        Return a zero-copy 1D `uint8` NumPy view over the raw tensor bytes in the `mmap`.
        For F16/F32 tensors, returns a typed view reshaped to `shape_row_major`.
        """
        info = self.gguf.tensors[name]
        raw_view = np.frombuffer(
            self._mm, dtype=np.uint8, count=info.n_bytes, offset=info.abs_offset
        )
        if info.ggml_type == GGMLType.F16:
            return raw_view.view(np.float16).reshape(info.shape_row_major)
        if info.ggml_type == GGMLType.F32:
            return raw_view.view(np.float32).reshape(info.shape_row_major)
        return raw_view

    def prefetch_layer(self, layer_idx: int) -> None:
        """Asynchronously prefetch all contiguous tensor spans for `layer_idx` into the OS page cache."""
        if not hasattr(mmap, "MADV_WILLNEED"):
            return
        try:
            spans = self.gguf.get_layer_byte_spans(layer_idx)
        except KeyError:
            return
        mm_len = len(self._mm)
        for offset, length in spans:
            aligned_offset, aligned_len = _page_align_span(offset, length)
            aligned_len = min(aligned_len, mm_len - aligned_offset)
            if aligned_len > 0:
                self._mm.madvise(mmap.MADV_WILLNEED, aligned_offset, aligned_len)

    def release_layer(self, layer_idx: int) -> None:
        """
        Advise the OS kernel that clean file-backed pages for `layer_idx` can be
        reclaimed from the page cache (`MADV_DONTNEED` on read-only `ACCESS_READ` mmap).
        No-op when `self.cache_weights` is True.
        """
        if self.cache_weights or not hasattr(mmap, "MADV_DONTNEED"):
            return
        try:
            spans = self.gguf.get_layer_byte_spans(layer_idx)
        except KeyError:
            return
        mm_len = len(self._mm)
        for offset, length in spans:
            aligned_offset, aligned_len = _page_align_span(offset, length)
            aligned_len = min(aligned_len, mm_len - aligned_offset)
            if aligned_len > 0:
                self._mm.madvise(mmap.MADV_DONTNEED, aligned_offset, aligned_len)

    def prefetch_tensor(self, name: str) -> None:
        """Asynchronously prefetch a named tensor (`token_embd.weight`, `output.weight`) from SSD."""
        if not hasattr(mmap, "MADV_WILLNEED") or name not in self.gguf.tensors:
            return
        info = self.gguf.tensors[name]
        aligned_offset, aligned_len = _page_align_span(info.abs_offset, info.n_bytes)
        aligned_len = min(aligned_len, len(self._mm) - aligned_offset)
        if aligned_len > 0:
            self._mm.madvise(mmap.MADV_WILLNEED, aligned_offset, aligned_len)

    def release_tensor(self, name: str) -> None:
        """Advise the kernel to reclaim clean page-cache pages for a named tensor (`MADV_DONTNEED`)."""
        if self.cache_weights or not hasattr(mmap, "MADV_DONTNEED") or name not in self.gguf.tensors:
            return
        info = self.gguf.tensors[name]
        aligned_offset, aligned_len = _page_align_span(info.abs_offset, info.n_bytes)
        aligned_len = min(aligned_len, len(self._mm) - aligned_offset)
        if aligned_len > 0:
            self._mm.madvise(mmap.MADV_DONTNEED, aligned_offset, aligned_len)

    @contextlib.contextmanager
    def layer_context(
        self, layer_idx: int, prefetch_next: bool = True
    ) -> Iterator[Dict[str, Tuple[GGUFTensorInfo, np.ndarray]]]:
        """
        Context manager for layer-wise inference:
        1. Prefetches `layer_idx + 1` from SSD (`MADV_WILLNEED`).
        2. Yields zero-copy views for all tensors in `layer_idx`.
        3. Evicts `layer_idx` pages (`MADV_DONTNEED`) upon completion (unless `cache_weights=True`).
        """
        if prefetch_next and (self.num_layers == 0 or layer_idx + 1 < self.num_layers):
            self.prefetch_layer(layer_idx + 1)

        layer_infos = self.gguf.get_layer_tensors(layer_idx)
        views = {name: (info, self.get_tensor_view(name)) for name, info in layer_infos.items()}
        try:
            yield views
        finally:
            views.clear()
            self.release_layer(layer_idx)

    def close(self) -> None:
        try:
            if getattr(self, "_mm", None) is not None:
                self._mm.close()
                self._mm = None
        finally:
            if getattr(self, "_file", None) is not None:
                self._file.close()
                self._file = None

    def __enter__(self) -> "WeightStreamer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
