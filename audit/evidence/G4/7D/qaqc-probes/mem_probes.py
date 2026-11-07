#!/usr/bin/env python3
"""QAQC probes for Phase 7D (Gate G4) — memory eviction / residency evidence.

Independent of the pytest suite: prints raw syscall-sequence traces, policy
decisions, and measured RSS / major-fault deltas for PIN vs STREAM on a
synthetic model, plus the fd/mmap leak probe and the budget sources actually
readable on this host. Runs on the CPU; no HIP extension needed.

Usage: python3 audit/evidence/G4/7D/qaqc-probes/mem_probes.py [workdir]
"""

from __future__ import annotations

import os
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "src"))
sys.path.insert(0, os.path.join(_REPO, "tests"))

import numpy as np  # noqa: E402

from gguf_parser import GGMLType, GGUFValueType, write_synthetic_gguf  # noqa: E402
from memory_budget import (  # noqa: E402
    ResidencyPolicy,
    compute_weight_budget,
    decide_residency,
    estimate_activation_bytes,
    read_budget_sources,
)
from test_memory_residency import _build_layer_model, _engine_model  # noqa: E402
from weight_loader import WeightStreamer  # noqa: E402

RESULTS: list[str] = []


def log(msg: str) -> None:
    print(msg)
    RESULTS.append(msg)



def probe_budget_sources() -> None:
    log("=== budget sources readable on this host ===")
    sources = read_budget_sources()
    for name in sorted(sources.readings):
        log(f"  source {name}: {sources.readings[name]} bytes")
    if not sources.readings:
        log("  (none readable — AUTO would fail safe to STREAM)")
    log(f"  available = min(sources) = {sources.available_bytes}")
    act = estimate_activation_bytes(hidden_size=8192, max_seq_len=4096, vocab_size=32000)
    log(
        f"  activation estimate example (hidden=8192, seq=4096, vocab=32000): "
        f"{act} bytes ({act / (1 << 20):.1f} MiB)"
    )
    budget = compute_weight_budget(kv_bytes=2 << 30, activation_bytes=act, sources=sources)
    log(f"  weight budget example (kv=2 GiB): {budget.weight_budget} bytes")


def probe_eviction_syscalls(tmp: str) -> None:
    log("=== eviction syscall trace (STREAM vs PIN) ===")
    model = os.path.join(tmp, "evict.gguf")
    _build_layer_model(model, num_layers=2)
    calls: list[tuple[str, int, int]] = []
    real_fadvise = os.posix_fadvise

    def rec_fadvise(fd, offset, length, advice):
        calls.append(("posix_fadvise", offset, int(advice)))
        return real_fadvise(fd, offset, length, advice)

    os.posix_fadvise = rec_fadvise
    try:
        with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
            ws.release_layer(0)
            stream_calls = list(calls)
        calls.clear()
        with WeightStreamer(model, policy=ResidencyPolicy.PIN_ALL) as ws:
            ws.release_layer(0)
            pin_calls = list(calls)
    finally:
        os.posix_fadvise = real_fadvise
    log(f"  STREAM release_layer -> {len(stream_calls)} fadvise calls, first: "
        f"{stream_calls[:1]} (advice == POSIX_FADV_DONTNEED="
        f"{int(os.POSIX_FADV_DONTNEED)})")
    log(f"  PIN release_layer   -> {len(pin_calls)} fadvise calls (expected 0)")


def probe_eviction_fallback_missing(tmp: str) -> None:
    log("=== missing syscall fallback (posix_fadvise + MADV_PAGEOUT removed) ===")
    import mmap as _mmap
    import warnings

    from weight_loader import EvictionFallbackWarning

    model = os.path.join(tmp, "fallback.gguf")
    _build_layer_model(model, num_layers=1)
    saved_fadvise = os.posix_fadvise
    saved_pageout = getattr(_mmap, "MADV_PAGEOUT", None)
    del os.posix_fadvise
    if saved_pageout is not None:
        del _mmap.MADV_PAGEOUT
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
                ws.release_layer(0)  # must not crash
                still_streaming = ws.policy == ResidencyPolicy.STREAM
    finally:
        os.posix_fadvise = saved_fadvise
        if saved_pageout is not None:
            _mmap.MADV_PAGEOUT = saved_pageout
    log(f"  still_streaming={still_streaming}; warnings="
        f"{[c.category.__name__ for c in caught]}")
    if caught:
        log(f"    first warning: {caught[0].message}")
    log("  NOTE: the fallback is a PTE-drop only (best-effort, not page-cache "
        "eviction) and inference continued without crashing.")


def probe_rss(tmp: str) -> None:
    log("=== measured residency: PIN vs STREAM (synthetic 64 MiB model) ===")

    def vm_rss_kb() -> int:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
        raise RuntimeError("no VmRSS")

    def faults() -> tuple[int, int]:
        with open("/proc/self/stat") as fh:
            f = fh.read().split()
        return int(f[9]), int(f[11])

    pin = os.path.join(tmp, "pin.gguf")
    stream = os.path.join(tmp, "stream.gguf")
    _build_layer_model(pin, num_layers=3, elems_per_tensor=8 * 1024 * 1024)
    _build_layer_model(stream, num_layers=3, elems_per_tensor=8 * 1024 * 1024)

    before = vm_rss_kb()
    with WeightStreamer(pin, policy=ResidencyPolicy.PIN_ALL) as ws:
        for name in ws.gguf.tensors:
            _ = float(np.asarray(ws.get_tensor_view(name)).sum())
        pin_delta = vm_rss_kb() - before
        f0 = faults()
        for name in ws.gguf.tensors:
            _ = float(np.asarray(ws.get_tensor_view(name)).sum())
        f1 = faults()
    warm_majflt = f1[1] - f0[1]
    log(f"  PIN:   touched {os.path.getsize(pin)} bytes; dRSS={pin_delta} kB; "
        f"warm re-touch majflt={warm_majflt}")

    before = vm_rss_kb()
    with WeightStreamer(stream, policy=ResidencyPolicy.STREAM) as ws:
        for layer in range(ws.num_layers):
            for name in ws.gguf.get_layer_tensors(layer):
                _ = float(np.asarray(ws.get_tensor_view(name)).sum())
            ws.release_layer(layer)
        stream_delta = vm_rss_kb() - before
        f0 = faults()
        for name in ws.gguf.get_layer_tensors(0):
            _ = float(np.asarray(ws.get_tensor_view(name)).sum())
        f1 = faults()
    refault_majflt = f1[1] - f0[1]
    log(f"  STREAM: dRSS={stream_delta} kB; re-touch of evicted layer 0 "
        f"majflt={refault_majflt} (>0 => pages really left the page cache)")
    log(f"  difference: PIN dRSS - STREAM dRSS = {pin_delta - stream_delta} kB "
        f"(RSS source: /proc/self/status VmRSS; faults: /proc/self/stat)")


def probe_decisions(tmp: str) -> None:
    log("=== policy decisions (engine-level, synthetic model) ===")
    import importlib
    import types

    stub_installed = False
    if "matmul_module" not in sys.modules:
        try:
            import matmul_module  # noqa: F401
        except ImportError:
            sys.modules["matmul_module"] = types.SimpleNamespace(
                kv_cache_init=lambda *a: None,
                kv_cache_free=lambda *a: None,
                gqa_attention=lambda *a: None,
                gqa_attention_cached=lambda *a: None,
                rmsnorm=lambda *a: None,
            )
            stub_installed = True
    try:
        inference = importlib.import_module("inference")
        model = os.path.join(tmp, "engine.gguf")
        _engine_model(model)
        for label, kwargs in [
            ("AUTO + override budget 4096 MB",
             dict(residency="auto", residency_budget_mb=4096)),
            ("AUTO + override budget 0 MB (never fits)",
             dict(residency="auto", residency_budget_mb=0)),
            ("explicit STREAM", dict(residency="stream")),
            ("explicit PIN", dict(residency="pin", residency_budget_mb=0)),
            ("deprecated cache_weights=True", dict(cache_weights=True)),
        ]:
            with inference.LlamaInferenceEngine(
                model, max_seq_len=32, offload_kv_to_cpu=True, **kwargs
            ) as eng:
                d = eng.residency_decision
                log(f"  {label}: requested={d.requested.value} -> "
                    f"effective={d.effective.value}; over_budget={d.over_budget}; "
                    f"origin={eng.residency_decision_origin.splitlines()[0]}")
    finally:
        if stub_installed:
            sys.modules.pop("matmul_module", None)


def probe_leak(tmp: str) -> None:
    log("=== fd/mmap leak probe: 1000x open/close ===")
    import gc

    model = os.path.join(tmp, "leak.gguf")
    _build_layer_model(model, num_layers=1)

    def snap() -> tuple[int, int]:
        gc.collect()
        fds = len(os.listdir("/proc/self/fd"))
        with open("/proc/self/maps") as fh:
            maps = sum(1 for line in fh if "blk." in line or ".gguf" in line)
        return fds, maps

    for _ in range(20):
        with WeightStreamer(model):
            pass
    base = snap()
    log(f"  baseline after warm-up: fds={base[0]}, model-related maps={base[1]}")
    done = 0
    for target in (100, 600, 1100):
        while done < target:
            with WeightStreamer(model) as ws:
                _ = ws.get_tensor_view("token_embd.weight")
                ws.release_tensor("token_embd.weight")
            done += 1
        cur = snap()
        log(f"  after {done} cycles: fds={cur[0]} (delta {cur[0] - base[0]}), "
            f"model-related maps={cur[1]} (delta {cur[1] - base[1]})")


def probe_cgroup() -> None:
    log("=== cgroup budget sources ===")
    import memory_budget as mb

    log(f"  /proc/self/cgroup = "
        f"{open('/proc/self/cgroup').read().strip().splitlines()}")
    v2 = mb._cgroup_v2_available_bytes()
    v1 = mb._cgroup_v1_available_bytes()
    log(f"  v2 headroom={v2} (None => memory.max is 'max'/unlimited or unreadable)")
    log(f"  v1 headroom={v1} (None => no v1 limit)")
    # fake-tree unit behavior is covered by
    # tests/test_memory_residency.py::test_cgroup_readers_from_fake_trees


def main() -> int:
    work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="7d-probes-")
    log(f"QAQC mem probes; workdir {work}")
    log(f"repo: {_REPO}")
    probe_budget_sources()
    probe_eviction_syscalls(work)
    probe_eviction_fallback_missing(work)
    probe_rss(work)
    probe_decisions(work)
    probe_leak(work)
    probe_cgroup()
    log("ALL PROBES COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
