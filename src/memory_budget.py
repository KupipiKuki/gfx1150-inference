"""
Host memory-budget helpers for the residency policy and KV allocation caps
(Phase 7D, Gate G4).

Reads the actual budget sources available on this host, without inventing a
budget when none is readable:

- GTT (unified-memory aperture) free bytes:
  ``/sys/class/drm/card*/device/mem_info_gtt_{total,used}``
- Host available memory: ``MemAvailable`` from ``/proc/meminfo``
- cgroup v2 ``memory.max``/``memory.current`` (or v1
  ``memory.limit_in_bytes``/``memory.usage_in_bytes``) for the process's own
  cgroup, when the limit is finite

A source that is absent or unreadable is skipped and recorded as such; when no
source is available, callers fail safe to streaming (never to pinning) and no
budget is fabricated.

This module uses the standard library only, so it runs on CPU-only CI hosts.
"""

from __future__ import annotations

import glob
import os
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class ResidencyPolicy(str, Enum):
    """Weight page-cache residency policy.

    - ``AUTO``: pin when the model's weight bytes fit the computed budget,
      otherwise stream (the decision and its reason are recorded).
    - ``PIN_ALL``: keep the model's file pages resident in the **host page
      cache** (skip eviction, optionally prefetch the whole file). This is NOT
      a device/GTT weight cache: kernels still copy quantized weights
      host-to-device per projection. No throughput claim is made.
    - ``STREAM``: layer-wise mmap with best-effort page-cache eviction
      after each layer/tensor use (the previous default behavior, now using
      ``posix_fadvise(POSIX_FADV_DONTNEED)`` / optional ``MADV_PAGEOUT``).
    """

    AUTO = "auto"
    PIN_ALL = "pin_all"
    STREAM = "stream"

    @classmethod
    def coerce(cls, value) -> "ResidencyPolicy":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.AUTO
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {
                "auto": cls.AUTO,
                "pin": cls.PIN_ALL,
                "pin_all": cls.PIN_ALL,
                "pin-all": cls.PIN_ALL,
                "stream": cls.STREAM,
            }
            if normalized in aliases:
                return aliases[normalized]
            try:
                return cls(normalized)
            except ValueError:
                pass
        raise ValueError(
            f"Invalid residency policy {value!r}: expected one of "
            f"auto/pin/pin_all/stream (or a ResidencyPolicy)"
        )


class OverBudgetWarning(UserWarning):
    """A PIN_ALL residency policy was requested for a model that does not fit
    the computed budget (an explicit user request; we warn, we do not refuse)."""


class NoBudgetFallbackWarning(UserWarning):
    """No memory-budget source could be read; AUTO failed safe to STREAM."""


#: Conservative flat safety subtracted from the available bytes before
#: comparing against the model weight bytes (documented, overridable).
DEFAULT_SAFETY_MARGIN_BYTES = 512 * (1 << 20)  # 512 MiB

#: Activation estimate: hidden × max_seq_len × fp16 × this many live buffers
#: (hidden states, normed hidden, attention output, MLP intermediate), plus
#: logits and a flat workspace margin. The formula is deliberately
#: conservative; it is documented in README/PLAN and the evidence bundle.
_ACTIVATION_BUFFERS = 4
_ACTIVATION_WORKSPACE_BYTES = 64 * (1 << 20)  # 64 MiB logits/workspace margin


@dataclass
class BudgetSources:
    """Available-memory readings plus which sources were actually used."""

    readings: Dict[str, int] = field(default_factory=dict)
    """Mapping source name -> free/available bytes. Only sources that were
    successfully read appear here; the names match the sysfs/proc paths."""

    @property
    def available_bytes(self) -> Optional[int]:
        """``min`` over the successfully read sources, or ``None`` when no
        source could be read (fail safe: no budget is invented)."""
        if not self.readings:
            return None
        return min(self.readings.values())

    @property
    def used_sources(self) -> Tuple[str, ...]:
        return tuple(sorted(self.readings.keys()))


@dataclass
class WeightBudget:
    """Computed host weight budget (bytes) and its provenance."""

    weight_budget: int
    available_bytes: Optional[int]
    safety_margin_bytes: int
    kv_bytes: int
    activation_bytes: int
    sources: BudgetSources


@dataclass
class ResidencyDecision:
    """Resolved residency policy for one model plus why."""

    requested: ResidencyPolicy
    effective: ResidencyPolicy
    reason: str
    weight_bytes: int
    weight_budget: Optional[int] = None
    over_budget: bool = False


# --------------------------------------------------------------------------- #
# Budget sources
# --------------------------------------------------------------------------- #


def read_gtt_free_bytes() -> Optional[int]:
    """Free GTT bytes from AMDGPU sysfs, minimized over all DRM cards.

    Reads ``mem_info_gtt_total``/``mem_info_gtt_used`` from
    ``/sys/class/drm/card*/device/``. Unavailable or unparsable cards are
    skipped; returns ``None`` when no card provides a reading.
    """
    frees: list[int] = []
    for base in sorted(glob.glob("/sys/class/drm/card*/device")):
        try:
            with open(os.path.join(base, "mem_info_gtt_total"), "r") as fh:
                total = int(fh.read().strip())
            with open(os.path.join(base, "mem_info_gtt_used"), "r") as fh:
                used = int(fh.read().strip())
        except (OSError, ValueError):
            continue
        free = total - used
        if free > 0:
            frees.append(free)
    if not frees:
        return None
    return min(frees)


def read_host_available_bytes() -> Optional[int]:
    """``MemAvailable`` from ``/proc/meminfo`` in bytes, or ``None``."""
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def _cgroup_v2_available_bytes(
    proc_path: str = "/proc/self/cgroup",
    base: str = "/sys/fs/cgroup",
) -> Optional[int]:
    """cgroup v2 ``memory.max - memory.current`` for this process's cgroup.

    The path parameters exist for unit tests with fake cgroup trees.
    """
    try:
        with open(proc_path, "r") as fh:
            rel = None
            for line in fh:
                parts = line.strip().split(":", 2)
                if len(parts) == 3 and parts[0] == "0":
                    rel = parts[2]
                    break
        if rel is None:
            return None
        cgdir = os.path.join(base, rel.lstrip("/"))
        with open(os.path.join(cgdir, "memory.max"), "r") as fh:
            raw_max = fh.read().strip()
        if raw_max == "max":
            return None  # no limit set
        with open(os.path.join(cgdir, "memory.current"), "r") as fh:
            raw_cur = fh.read().strip()
        limit = int(raw_max)
        current = int(raw_cur)
    except (OSError, ValueError):
        return None
    if limit <= 0 or limit >= (1 << 62):
        return None
    free = limit - current
    return max(0, free)


def _cgroup_v1_available_bytes(
    proc_path: str = "/proc/self/cgroup",
    base: str = "/sys/fs/cgroup/memory",
) -> Optional[int]:
    """cgroup v1 ``memory.limit_in_bytes - memory.usage_in_bytes``."""
    try:
        with open(proc_path, "r") as fh:
            rel = None
            for line in fh:
                parts = line.strip().split(":", 2)
                if len(parts) == 3 and "memory" in parts[1].split(","):
                    rel = parts[2]
                    break
        cgdir = base
        if rel:
            cgdir = os.path.join(base, rel.lstrip("/"))
        with open(os.path.join(cgdir, "memory.limit_in_bytes"), "r") as fh:
            limit = int(fh.read().strip())
        with open(os.path.join(cgdir, "memory.usage_in_bytes"), "r") as fh:
            current = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    if limit <= 0 or limit >= (1 << 62):
        return None  # "unlimited"
    free = limit - current
    return max(0, free)


def read_cgroup_available_bytes() -> Optional[int]:
    """cgroup (v2 then v1) available bytes for this process, or ``None`` when
    no finite cgroup memory limit applies on this host."""
    for reader in (_cgroup_v2_available_bytes, _cgroup_v1_available_bytes):
        value = reader()
        if value is not None:
            return value
    return None


def read_budget_sources(
    gtt: Optional[int] = None,
    host: Optional[int] = None,
    cgroup: Optional[int] = None,
) -> BudgetSources:
    """Collect every available-memory source that is actually readable.

    The parameters exist for tests and callers with pre-fetched readings;
    ``None`` means "read it from the host". Sources that cannot be read are
    skipped, never fabricated.
    """
    sources = BudgetSources()
    if gtt is None:
        gtt = read_gtt_free_bytes()
    if host is None:
        host = read_host_available_bytes()
    if cgroup is None:
        cgroup = read_cgroup_available_bytes()
    if gtt is not None:
        sources.readings["gtt_sysfs"] = gtt
    if host is not None:
        sources.readings["host_memavailable"] = host
    if cgroup is not None:
        sources.readings["cgroup"] = cgroup
    return sources


# --------------------------------------------------------------------------- #
# Budget computation and policy decision
# --------------------------------------------------------------------------- #


def estimate_activation_bytes(
    hidden_size: int,
    max_seq_len: int,
    vocab_size: int,
) -> int:
    """Conservative activation-memory estimate in bytes.

    Formula (documented): fp16 ``hidden × max_seq_len × 4`` live buffers
    (hidden states, normed hidden, attention output, MLP intermediate) plus
    fp16 logits (``vocab_size × 2``) plus a flat 64 MiB workspace margin.
    """
    hidden = max(0, int(hidden_size))
    seq = max(0, int(max_seq_len))
    vocab = max(0, int(vocab_size))
    return (
        hidden * seq * 2 * _ACTIVATION_BUFFERS
        + vocab * 2
        + _ACTIVATION_WORKSPACE_BYTES
    )


def compute_weight_budget(
    kv_bytes: int,
    activation_bytes: int,
    sources: Optional[BudgetSources] = None,
    safety_margin_bytes: Optional[int] = None,
) -> WeightBudget:
    """Compute the host page-cache residency budget for model weights.

    ``weight_budget = max(0, available - kv - activations - safety_margin)``
    where ``available = min`` over every readable source (GTT sysfs,
    ``MemAvailable``, cgroup). When no source is readable the budget is ``0``
    and the decision layer must fail safe to STREAM.
    """
    if sources is None:
        sources = read_budget_sources()
    margin = (
        DEFAULT_SAFETY_MARGIN_BYTES if safety_margin_bytes is None else safety_margin_bytes
    )
    available = sources.available_bytes  # None => no source
    if available is None:
        budget = 0
    else:
        budget = max(0, available - int(kv_bytes) - int(activation_bytes) - margin)
    return WeightBudget(
        weight_budget=budget,
        available_bytes=available,
        safety_margin_bytes=margin,
        kv_bytes=int(kv_bytes),
        activation_bytes=int(activation_bytes),
        sources=sources,
    )


def decide_residency(
    policy: ResidencyPolicy,
    weight_bytes: int,
    weight_budget: Optional[int],
    sources: Optional[BudgetSources] = None,
) -> ResidencyDecision:
    """Resolve a residency policy against a computed budget.

    - ``PIN_ALL`` is always honored; if a budget exists and the model exceeds
      it, an :class:`OverBudgetWarning` is emitted (explicit user request).
    - ``STREAM`` is always honored.
    - ``AUTO`` pins when the model fits the budget and streams otherwise.
      Without a budget (no readable source) AUTO **fails safe to STREAM**
      with a :class:`NoBudgetFallbackWarning` — it never invents a budget.
    """
    policy = ResidencyPolicy.coerce(policy)
    weight_bytes = int(weight_bytes)

    if policy == ResidencyPolicy.PIN_ALL:
        over = weight_budget is not None and weight_bytes > weight_budget
        if over:
            warnings.warn(
                f"PIN_ALL requested but the model's weight bytes ({weight_bytes}) "
                f"exceed the computed budget ({weight_budget}); keeping the "
                f"explicit request (host page cache may thrash).",
                OverBudgetWarning,
                stacklevel=2,
            )
        return ResidencyDecision(
            requested=policy,
            effective=ResidencyPolicy.PIN_ALL,
            reason=(
                "explicit PIN_ALL request"
                + (" (over budget; warned)" if over else "")
            ),
            weight_bytes=weight_bytes,
            weight_budget=weight_budget,
            over_budget=over,
        )

    if policy == ResidencyPolicy.STREAM:
        return ResidencyDecision(
            requested=policy,
            effective=ResidencyPolicy.STREAM,
            reason="explicit STREAM request",
            weight_bytes=weight_bytes,
            weight_budget=weight_budget,
        )

    # AUTO
    if weight_budget is None:
        used = ", ".join(sources.used_sources) if sources else "none"
        warnings.warn(
            "AUTO residency: no memory-budget source could be read "
            f"(sources: {used}); failing safe to STREAM (no budget is invented).",
            NoBudgetFallbackWarning,
            stacklevel=2,
        )
        return ResidencyDecision(
            requested=ResidencyPolicy.AUTO,
            effective=ResidencyPolicy.STREAM,
            reason="AUTO without a budget: no readable source; failed safe to STREAM",
            weight_bytes=weight_bytes,
            weight_budget=None,
        )
    if weight_bytes <= weight_budget:
        return ResidencyDecision(
            requested=ResidencyPolicy.AUTO,
            effective=ResidencyPolicy.PIN_ALL,
            reason=(
                f"AUTO: weight bytes ({weight_bytes}) fit the budget "
                f"({weight_budget}); pinning in the host page cache"
            ),
            weight_bytes=weight_bytes,
            weight_budget=weight_budget,
        )
    return ResidencyDecision(
        requested=ResidencyPolicy.AUTO,
        effective=ResidencyPolicy.STREAM,
        reason=(
            f"AUTO: weight bytes ({weight_bytes}) exceed the budget "
            f"({weight_budget}); streaming"
        ),
        weight_bytes=weight_bytes,
        weight_budget=weight_budget,
    )
