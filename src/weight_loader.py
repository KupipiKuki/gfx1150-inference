"""
Memory-mapped SSD weight streamer with Linux page-cache management for AMD
gfx1150 unified-memory systems (Phase 7D: eviction honesty + residency policy).

Page-cache eviction (STREAM) uses ``os.posix_fadvise(fd, ..., POSIX_FADV_DONTNEED)``
on the model file descriptor as the **primary** page-cache hint. Because the kernel
will not free pages that a live mapping still maps, the span is first dropped from
this read-only mapping's page table — ``mmap.MADV_PAGEOUT`` when the host exposes
it, otherwise ``mmap.MADV_DONTNEED`` (the same PTE drop on an ``ACCESS_READ``
mapping; an enabler for the fadvise, not page-cache eviction in itself, no data
loss — pages re-fault from the file on next use). When neither fadvise nor
``MADV_PAGEOUT`` exists, the PTE drop alone is a best-effort fallback with a
one-time warning. All advice is best-effort: it is not a hard RAM bound.

Residency policy (7D-2): ``AUTO`` / ``PIN_ALL`` / ``STREAM`` (see
``memory_budget.ResidencyPolicy``). ``PIN_ALL`` keeps the model's file pages
resident in the **host page cache** (skip eviction, optionally prefetch the
whole file) — it is not a device/GTT weight cache; kernels still copy
quantized weights host-to-device per projection.

The legacy boolean ``cache_weights`` maps ``True`` → ``PIN_ALL`` and ``False``
→ ``AUTO`` (which, like the old default, streams when the model does not fit
the budget; without a budget it fails safe to STREAM).
"""

from __future__ import annotations

import contextlib
import mmap
import os
import re
import sys
import warnings
from typing import Dict, FrozenSet, Iterator, Optional, Tuple
import numpy as np

try:
    from .gguf_parser import GGMLType, GGUFParser, GGUFTensorInfo
except ImportError:
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SRC_DIR not in sys.path:
        sys.path.append(_SRC_DIR)
    from gguf_parser import GGMLType, GGUFParser, GGUFTensorInfo

try:
    from .memory_budget import ResidencyDecision, ResidencyPolicy
except ImportError:
    _SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if _SRC_DIR not in sys.path:
        sys.path.append(_SRC_DIR)
    from memory_budget import ResidencyDecision, ResidencyPolicy


PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096

SUPPORTED_COMPUTE_GGML_TYPES: FrozenSet[GGMLType] = frozenset({
    GGMLType.F32,
    GGMLType.F16,
    GGMLType.Q4_0,
    GGMLType.Q8_0,
    GGMLType.Q4_K,
    GGMLType.Q6_K,
})

_BLK_INDEX_RE = re.compile(r"^blk\.(\d+)\.")


class EvictionFallbackWarning(UserWarning):
    """Eviction fell back to ``MADV_DONTNEED`` (PTE-only, best-effort) because
    neither ``posix_fadvise(POSIX_FADV_DONTNEED)`` nor ``MADV_PAGEOUT`` is
    available on this host."""


def _page_align_span(offset: int, length: int) -> tuple[int, int]:
    """Align `(offset, length)` outward to OS page boundaries for kernel advice."""
    aligned_start = (offset // PAGE_SIZE) * PAGE_SIZE
    end = offset + length
    aligned_end = ((end + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
    return aligned_start, aligned_end - aligned_start


def _cross_check_block_count(gguf: GGUFParser) -> int:
    """Fail fast when the declared ``{arch}.block_count`` disagrees with the
    actual ``blk.N.*`` tensor index set (hostile/mis-generated headers).

    Returns the number of layers to use (the declared count when present).
    """
    arch = str(gguf.metadata.get("general.architecture", "llama"))
    declared = gguf.metadata.get(
        f"{arch}.block_count", gguf.metadata.get("llama.block_count")
    )
    found = sorted(
        {int(m.group(1)) for name in gguf.tensors for m in (_BLK_INDEX_RE.match(name),) if m}
    )
    if declared is None:
        return 0
    try:
        declared_count = int(declared)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid {arch}.block_count value: {declared!r} (expected an integer)"
        )
    if found != list(range(declared_count)):
        found_desc = (
            f"found {len(found)} blk.N.* tensor groups "
            f"(min={found[0]}, max={found[-1]})"
            if found
            else "found 0 blk.N.* tensors"
        )
        raise ValueError(
            f"{arch}.block_count ({declared_count}) disagrees with the tensor "
            f"table: {found_desc}. Refusing to emit tensor-sized error lists "
            f"for a header that does not match its own tensors."
        )
    return declared_count


class WeightStreamer:
    """
    Streams GGUF model tensors directly from SSD via read-only `mmap`
    (`ACCESS_READ`) with `MADV_WILLNEED` prefetching and best-effort page-cache
    eviction after each layer/tensor use (`posix_fadvise(POSIX_FADV_DONTNEED)`
    primary, `MADV_PAGEOUT` optional). The residency policy is `AUTO` /
    `PIN_ALL` / `STREAM` (see `memory_budget.ResidencyPolicy`): `PIN_ALL` skips
    eviction so the model's pages stay resident in the *host page cache*.

    `cache_weights=True` maps to `PIN_ALL`; `False` maps to `AUTO` (which
    streams without a budget). `policy` wins over `cache_weights`.
    """

    def __init__(
        self,
        model_path: str,
        cache_weights: bool = False,
        validate_types: bool = True,
        policy: Optional[ResidencyPolicy] = None,
        weight_budget: Optional[int] = None,
    ):
        self.model_path = model_path
        self.cache_weights = bool(cache_weights)
        self._file = open(model_path, "rb")
        self._mm: Optional[mmap.mmap] = None
        # Residency decision is initially unresolved: the effective policy is
        # derived from (cache_weights, policy, weight_budget) and can be
        # re-resolved later via `set_residency` once the engine computed a
        # budget (AUTO without a budget fails safe to STREAM).
        self._eviction_warned = False
        self.residency_decision: Optional[ResidencyDecision] = None
        try:
            self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            self.gguf = GGUFParser(self._mm)
            self.num_layers = _cross_check_block_count(self.gguf)
            if validate_types:
                self.validate_supported_tensors()

            # Initial policy resolution. An explicit policy/cache_weights
            # request is decided fully (with warnings). Without either, the
            # streamer stays on an unresolved safe STREAM default until
            # `set_residency` supplies the engine's computed budget.
            if policy is not None or self.cache_weights:
                from memory_budget import decide_residency
                base_policy = (
                    ResidencyPolicy.coerce(policy)
                    if policy is not None
                    else ResidencyPolicy.PIN_ALL
                )
                self.residency_decision = decide_residency(
                    base_policy, self.weight_bytes, weight_budget
                )
            else:
                self.residency_decision = ResidencyDecision(
                    requested=ResidencyPolicy.AUTO,
                    effective=ResidencyPolicy.STREAM,
                    reason=(
                        "pre-resolution default: stream until a policy and "
                        "budget are set via set_residency()"
                    ),
                    weight_bytes=self.weight_bytes,
                )
            self.cache_weights = (
                self.residency_decision.effective == ResidencyPolicy.PIN_ALL
            )

            # Advise sequential access pattern by default
            if hasattr(mmap, "MADV_SEQUENTIAL"):
                self._mm.madvise(mmap.MADV_SEQUENTIAL)
        except BaseException:
            self.close()
            raise

    # ------------------------------------------------------------------ #
    # Policy / decision bookkeeping
    # ------------------------------------------------------------------ #

    @property
    def weight_bytes(self) -> int:
        """Sum of the parsed tensors' `n_bytes` (data bytes, not page-aligned
        padding; per-tensor alignment overhead is at most `alignment - 1`)."""
        return sum(int(t.n_bytes) for t in self.gguf.tensors.values())

    @property
    def policy(self) -> ResidencyPolicy:
        """Effective (resolved) residency policy."""
        decision = self.residency_decision
        if decision is None:
            return ResidencyPolicy.STREAM
        return decision.effective

    def set_residency(
        self,
        policy: ResidencyPolicy,
        weight_budget: Optional[int] = None,
    ) -> None:
        """Re-resolve the residency policy (used by the engine after it has
        parsed the model and computed the host budget)."""
        from memory_budget import decide_residency
        self.residency_decision = decide_residency(
            ResidencyPolicy.coerce(policy), self.weight_bytes, weight_budget
        )
        self.cache_weights = (
            self.residency_decision.effective == ResidencyPolicy.PIN_ALL
        )

    def set_decision(self, decision: ResidencyDecision) -> None:
        """Install a residency decision computed by the caller (the engine:
        it owns the KV/activation budget inputs). Warnings were already
        emitted by `memory_budget.decide_residency`."""
        self.residency_decision = decision
        self.cache_weights = decision.effective == ResidencyPolicy.PIN_ALL

    @property
    def eviction_enabled(self) -> bool:
        """True when the effective policy is STREAM (eviction is skipped for
        PIN_ALL; a pinned model stays in the host page cache)."""
        return self.policy == ResidencyPolicy.STREAM

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Tensor access
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Prefetch / eviction (7D-1)
    # ------------------------------------------------------------------ #

    def prefetch_layer(self, layer_idx: int) -> None:
        """Prefetch all contiguous tensor spans for `layer_idx` into the OS page
        cache (`MADV_WILLNEED` on the mapping)."""
        if not hasattr(mmap, "MADV_WILLNEED"):
            return
        try:
            spans = self.gguf.get_layer_byte_spans(layer_idx)
        except KeyError:
            return
        for offset, length in self._clipped_layer_spans(spans):
            self._mm.madvise(mmap.MADV_WILLNEED, offset, length)

    def prefetch_tensor(self, name: str) -> None:
        """Prefetch a named tensor (`token_embd.weight`, `output.weight`) from
        SSD (`MADV_WILLNEED`). Prefetch happens in every policy: it populates
        the page cache, which is exactly what all three policies want."""
        if not hasattr(mmap, "MADV_WILLNEED") or name not in self.gguf.tensors:
            return
        info = self.gguf.tensors[name]
        aligned_offset, aligned_len = _page_align_span(info.abs_offset, info.n_bytes)
        aligned_len = min(aligned_len, len(self._mm) - aligned_offset)
        if aligned_len > 0:
            self._mm.madvise(mmap.MADV_WILLNEED, aligned_offset, aligned_len)

    def release_layer(self, layer_idx: int) -> None:
        """Advise the kernel to drop the clean page-cache pages for `layer_idx`
        from the page cache: `posix_fadvise(POSIX_FADV_DONTNEED)` on the model
        file descriptor (primary), plus `MADV_PAGEOUT` on the mapped span
        (best-effort addition when the host exposes it). No-op when the
        effective policy is PIN_ALL. Best-effort: not a hard RAM bound."""
        if not self.eviction_enabled:
            return
        try:
            spans = self.gguf.get_layer_byte_spans(layer_idx)
        except KeyError:
            return
        self._evict_spans(self._clipped_layer_spans(spans))

    def release_tensor(self, name: str) -> None:
        """Advise the kernel to drop a named tensor's clean page-cache pages
        (same mechanism as `release_layer`; no-op under PIN_ALL)."""
        if not self.eviction_enabled or name not in self.gguf.tensors:
            return
        info = self.gguf.tensors[name]
        aligned_offset, aligned_len = _page_align_span(info.abs_offset, info.n_bytes)
        aligned_len = min(aligned_len, len(self._mm) - aligned_offset)
        self._evict_spans([(aligned_offset, aligned_len)])

    def _clipped_layer_spans(self, spans) -> list[tuple[int, int]]:
        """Page-align and clip `(offset, length)` spans to the mapping."""
        mm_len = len(self._mm)
        clipped = []
        for offset, length in spans:
            aligned_offset, aligned_len = _page_align_span(offset, length)
            aligned_len = min(aligned_len, mm_len - aligned_offset)
            if aligned_len > 0:
                clipped.append((aligned_offset, aligned_len))
        return clipped

    def _evict_spans(self, spans) -> None:
        """Issue the page-cache eviction hints for the given spans.

        Primary page-cache hint: ``posix_fadvise(fd, offset, len,
        POSIX_FADV_DONTNEED)`` — asks the kernel to drop the clean file pages
        from the page cache. A live mapping keeps pages mapped, and the kernel
        will not free mapped pages for a mapping that still holds their PTEs,
        so the span is first dropped from this read-only mapping's page table:
        ``MADV_PAGEOUT`` when the host exposes it, otherwise ``MADV_DONTNEED``
        (identical PTE-drop effect on an ``ACCESS_READ`` mapping). The PTE drop
        is an enabler for the fadvise, not page-cache eviction in itself, and
        loses no data (read-only file mapping, zero-copy re-fault on next use).

        Last-resort fallback when neither ``posix_fadvise`` nor
        ``MADV_PAGEOUT`` exists: the PTE drop alone (best-effort, does not
        touch the page cache) with a one-time warning. Unavailable syscalls
        must never crash inference: every advice call is wrapped best-effort.
        """
        if self._mm is None or self._file is None:
            return
        fadvise = getattr(os, "posix_fadvise", None)
        fadvice_dontneed = getattr(os, "POSIX_FADV_DONTNEED", None)
        pageout = getattr(mmap, "MADV_PAGEOUT", None)
        madvise = getattr(self._mm, "madvise", None)

        fadvise_ok = callable(fadvise) and fadvice_dontneed is not None
        if not fadvise_ok and pageout is None and not self._eviction_warned:
            self._eviction_warned = True
            warnings.warn(
                "Neither posix_fadvise(POSIX_FADV_DONTNEED) nor MADV_PAGEOUT is "
                "available on this host; falling back to a MADV_DONTNEED PTE "
                "drop only (best-effort: it removes the read-only mapping's page "
                "table entries but is NOT page-cache eviction). Inference "
                "continues; memory use is not bounded by this fallback.",
                EvictionFallbackWarning,
                stacklevel=2,
            )

        have_dontneed = hasattr(mmap, "MADV_DONTNEED")
        for offset, length in spans:
            # Step 1: drop the span's PTEs so the kernel can act on the hint.
            if madvise is not None and pageout is not None:
                try:
                    madvise(pageout, offset, length)
                except OSError as exc:
                    self._warn_eviction_once(
                        f"MADV_PAGEOUT failed and was skipped (best-effort): {exc}"
                    )
            elif madvise is not None and have_dontneed:
                try:
                    madvise(mmap.MADV_DONTNEED, offset, length)
                except OSError:
                    pass  # best-effort advice; never fatal
            # Step 2: primary page-cache hint on the model fd.
            if fadvise_ok:
                try:
                    fadvise(self._file.fileno(), offset, length, fadvice_dontneed)
                except OSError as exc:
                    self._warn_eviction_once(
                        f"posix_fadvise(POSIX_FADV_DONTNEED) failed and was "
                        f"skipped (best-effort): {exc}"
                    )

    def _warn_eviction_once(self, message: str) -> None:
        if self._eviction_warned:
            return
        self._eviction_warned = True
        warnings.warn(message, EvictionFallbackWarning, stacklevel=3)

    # ------------------------------------------------------------------ #
    # Layer context
    # ------------------------------------------------------------------ #

    @contextlib.contextmanager
    def layer_context(
        self, layer_idx: int, prefetch_next: bool = True
    ) -> Iterator[Dict[str, Tuple[GGUFTensorInfo, np.ndarray]]]:
        """
        Context manager for layer-wise inference:
        1. Prefetches `layer_idx + 1` from SSD (`MADV_WILLNEED`).
        2. Yields zero-copy views for all tensors in `layer_idx`.
        3. Evicts `layer_idx` page-cache pages (`posix_fadvise(POSIX_FADV_DONTNEED)`
           / optional `MADV_PAGEOUT`, best-effort) upon completion — unless the
           effective policy is PIN_ALL.
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

    # ------------------------------------------------------------------ #
    # Cleanup (7D-3: preserve the original exception, close fds, warn on
    # live views instead of masking)
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Release the mapping and the file descriptor. Never raises: a
        cleanup failure must not mask the original constructor error. When
        the mapping still has live NumPy views (`BufferError`), a warning is
        emitted, the mapping reference is dropped, and the fd is still closed."""
        mm = getattr(self, "_mm", None)
        if mm is not None:
            try:
                mm.close()
            except BufferError as exc:
                warnings.warn(
                    f"WeightStreamer.close(): the weight mapping still has live "
                    f"views and could not be released now ({exc}); dropping the "
                    f"reference (the mapping releases when the last view dies) "
                    f"and closing the file descriptor anyway.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            finally:
                self._mm = None
        f = getattr(self, "_file", None)
        if f is not None:
            try:
                f.close()
            except OSError as exc:
                warnings.warn(
                    f"WeightStreamer.close(): closing the model file failed: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
            finally:
                self._file = None

    def __enter__(self) -> "WeightStreamer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
