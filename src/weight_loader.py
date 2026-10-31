"""
Memory-mapped SSD weight streamer with Linux page-cache management (`madvise`)
for AMD gfx1150 unified memory systems.
"""

from __future__ import annotations

import contextlib
import mmap
import os
from typing import Dict, Iterator, Optional
import numpy as np

from gguf_parser import GGMLType, GGUFParser, GGUFTensorInfo


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def _page_align_span(offset: int, length: int) -> tuple[int, int]:
    """Align `(offset, length)` outward to OS page boundaries for `madvise`."""
    aligned_start = (offset // PAGE_SIZE) * PAGE_SIZE
    end = offset + length
    aligned_end = ((end + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
    return aligned_start, aligned_end - aligned_start


class WeightStreamer:
    """
    Streams GGUF model tensors directly from SSD via `mmap` with explicit
    `MADV_WILLNEED` prefetching and `MADV_DONTNEED` page eviction so unified
    system RAM is never exhausted by large (7B–70B) models.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._file = open(model_path, "rb")
        self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self.gguf = GGUFParser(self._mm)
        self.num_layers = int(self.gguf.metadata.get("llama.block_count", 0))

        # Advise sequential access pattern by default
        if hasattr(mmap, "MADV_SEQUENTIAL"):
            self._mm.madvise(mmap.MADV_SEQUENTIAL)

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
        """Asynchronously prefetch all tensors for `layer_idx` into the OS page cache."""
        if not hasattr(mmap, "MADV_WILLNEED"):
            return
        try:
            offset, length = self.gguf.get_layer_byte_span(layer_idx)
        except KeyError:
            return
        aligned_offset, aligned_len = _page_align_span(offset, length)
        aligned_len = min(aligned_len, len(self._mm) - aligned_offset)
        if aligned_len > 0:
            self._mm.madvise(mmap.MADV_WILLNEED, aligned_offset, aligned_len)

    def release_layer(self, layer_idx: int) -> None:
        """
        Evict physical RAM pages for `layer_idx` from the OS page cache (`MADV_DONTNEED`)
        so unified memory stays free for the GPU GTT allocator.
        """
        if not hasattr(mmap, "MADV_DONTNEED"):
            return
        try:
            offset, length = self.gguf.get_layer_byte_span(layer_idx)
        except KeyError:
            return
        aligned_offset, aligned_len = _page_align_span(offset, length)
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
        3. Evicts `layer_idx` pages (`MADV_DONTNEED`) upon completion.
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
        if getattr(self, "_mm", None) is not None:
            self._mm.close()
            self._mm = None
        if getattr(self, "_file", None) is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "WeightStreamer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
