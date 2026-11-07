"""
Phase 7D (Gate G4) memory-honesty and robustness tests (CPU lane).

Covers the coder brief work packages:

- 7D-1 page-cache eviction honesty: STREAM calls
  `posix_fadvise(POSIX_FADV_DONTNEED)` (+ optional `MADV_PAGEOUT`); PIN does
  not; missing syscalls fall back safely with a clear warning instead of
  crash; `MADV_DONTNEED` is only a warned last-resort PTE-only fallback.
- 7D-2 budgeted residency: AUTO pins a fitting model and streams an
  over-budget one; PIN_ALL/STREAM honor explicit requests; over-budget PIN
  warns; `cache_weights` maps True→PIN / False→AUTO; CLI precedence.
- 7D-3 KV/allocation hardening: budget/cgroup caps refuse cleanly,
  unlink-before-map mmap files, disk-space check, symlink rejection,
  `block_count` cross-check, duplicate names, exception preservation,
  fd/mmap leak probe (1,000× open/close).
- measured best-effort residency probe: VmRSS delta PIN vs STREAM.

GPU execution is out of scope here (see `tests/test_phase5_scale.py` for the
gpu lane); `KVCacheManager` runs in CPU/mmap offload mode behind the same
`matmul_module` stub `tests/test_cpu_only.py` uses.
"""

from __future__ import annotations

import os
import sys
import types
import warnings
from typing import Dict, List, Tuple

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gguf_parser import (  # noqa: E402
    GGMLType,
    GGUFParser,
    GGUFValueType,
    write_synthetic_gguf,
)
import memory_budget  # noqa: E402
from memory_budget import (  # noqa: E402
    BudgetSources,
    OverBudgetWarning,
    NoBudgetFallbackWarning,
    ResidencyPolicy,
    compute_weight_budget,
    decide_residency,
    estimate_activation_bytes,
)

# Phase 7D (G4) memory tests: pure CPU (KV cache runs in CPU/mmap offload mode
# behind the matmul_module stub); the GPU-lane residency probes live on the
# gfx1150 hardware host.
pytestmark = pytest.mark.cpu


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _build_layer_model(
    path: str,
    num_layers: int = 3,
    elems_per_tensor: int = 64 * 1024,
    declared_block_count: int | None = None,
    layer_tensor_names: Tuple[str, ...] = ("big.weight",),
    with_global: bool = True,
) -> int:
    """Write a small synthetic llama GGUF with F16 tensors and return its size.

    Each layer holds one F16 tensor of `elems_per_tensor` elements (2x that
    in bytes). `declared_block_count=None` writes the real count; an integer
    value is written verbatim (to build a hostile header).
    """
    rng = np.random.default_rng(7)
    declared = num_layers if declared_block_count is None else declared_block_count
    metadata: Dict[str, Tuple[GGUFValueType, object]] = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, declared),
    }
    tensors: List[Tuple[str, Tuple[int, ...], GGMLType, bytes]] = []
    payload = rng.standard_normal(elems_per_tensor, dtype=np.float32).astype(
        np.float16
    ).tobytes()
    for i in range(num_layers):
        for name in layer_tensor_names:
            tensors.append((f"blk.{i}.{name}", (elems_per_tensor,), GGMLType.F16, payload))
    if with_global:
        tensors.append(
            ("token_embd.weight", (elems_per_tensor,), GGMLType.F16, payload)
        )
    with open(path, "wb") as fh:
        write_synthetic_gguf(fh, metadata, tensors)
    return os.path.getsize(path)


def _matmul_stub() -> types.SimpleNamespace:
    """Same minimal stub as tests/test_cpu_only.py (CPU path)."""
    return types.SimpleNamespace(
        kv_cache_init=lambda *a: None,
        kv_cache_free=lambda *a: None,
        gqa_attention=lambda *a: None,
        gqa_attention_cached=lambda *a: None,
        rmsnorm=lambda *a: None,
    )


@pytest.fixture()
def kv_modules(monkeypatch):
    """Import kv_cache/inference with a matmul stub when the real extension is
    is not installed (mirrors tests/test_cpu_only.py)."""
    import importlib

    stub_installed = False
    if "matmul_module" not in sys.modules:
        try:
            import matmul_module  # noqa: F401
        except ImportError:
            monkeypatch.setitem(sys.modules, "matmul_module", _matmul_stub())
            stub_installed = True
    kv_cache = importlib.import_module("kv_cache")
    inference = importlib.import_module("inference")
    yield kv_cache, inference


def _vm_rss_kb() -> int:
    with open("/proc/self/status", "r") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    raise RuntimeError("VmRSS not found in /proc/self/status")


def _proc_count(name: str, needle: str) -> int:
    try:
        with open(f"/proc/self/{name}", "r") as fh:
            return sum(1 for line in fh if needle in line)
    except OSError:
        return -1


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


# --------------------------------------------------------------------------- #
# 7D-1: page-cache eviction honesty
# --------------------------------------------------------------------------- #


class TestEvictionHonesty:
    def test_stream_calls_fadvise_dontneed(self, tmp_path, monkeypatch) -> None:
        """STREAM eviction issues posix_fadvise(POSIX_FADV_DONTNEED) on the
        model fd, with page-aligned offsets/lengths."""
        from weight_loader import WeightStreamer

        model = str(tmp_path / "stream.gguf")
        _build_layer_model(model, num_layers=1)
        calls: List[Tuple[int, int, int, int]] = []
        real_fadvise = os.posix_fadvise

        def fake_fadvise(fd, offset, length, advice):
            calls.append((fd, offset, length, int(advice)))
            return real_fadvise(fd, offset, length, advice)

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
            assert ws.policy == ResidencyPolicy.STREAM
            ws.release_layer(0)
        assert calls, "STREAM must call posix_fadvise at least once"
        assert all(c[3] == int(os.POSIX_FADV_DONTNEED) for c in calls)
        # page-aligned spans
        assert all(c[1] % 4096 == 0 and c[2] % 4096 == 0 for c in calls)

    def test_stream_missing_fadvise_and_pageout_falls_back_with_warning(
        self, tmp_path, monkeypatch
    ) -> None:
        """Removing BOTH posix_fadvise and MADV_PAGEOUT must not crash; the
        warned MADV_DONTNEED fallback is PTE-only best-effort."""
        import mmap as _mmap

        from weight_loader import EvictionFallbackWarning, WeightStreamer

        model = str(tmp_path / "fallback.gguf")
        _build_layer_model(model, num_layers=1)
        monkeypatch.delattr(os, "posix_fadvise", raising=False)
        monkeypatch.delattr(_mmap, "MADV_PAGEOUT", raising=False)
        with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
            assert ws.policy == ResidencyPolicy.STREAM
            with pytest.warns(EvictionFallbackWarning, match="best-effort"):
                ws.release_layer(0)
            # Deterministic: further evictions do not warn again (one-time).
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                ws.release_layer(0)
            assert ws._eviction_warned is True, "warn-once flag set by the fallback"

    def test_stream_missing_syscall_only_fadvise_keeps_quiet(
        self, tmp_path, monkeypatch
    ) -> None:
        """Pageout missing but fadvise present: no fallback warning (fadvise
        is doing the real page-cache work)."""
        import mmap as _mmap

        from weight_loader import EvictionFallbackWarning, WeightStreamer

        model = str(tmp_path / "nopageout.gguf")
        _build_layer_model(model, num_layers=1)
        if not hasattr(_mmap, "MADV_PAGEOUT"):
            monkeypatch.setattr(_mmap, "MADV_PAGEOUT", 21, raising=False)
        called: List[int] = []
        real_fadvise = os.posix_fadvise

        def fake_fadvise(fd, offset, length, advice):
            called.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
                monkeypatch.delattr(_mmap, "MADV_PAGEOUT", raising=False)
                ws.release_layer(0)
        assert called, "fadvise DONTNEED must still drive STREAM eviction"
        assert not [
            w for w in caught if issubclass(w.category, EvictionFallbackWarning)
        ]

    def test_failing_fadvise_warns_and_continues(self, tmp_path, monkeypatch) -> None:
        from weight_loader import EvictionFallbackWarning, WeightStreamer

        model = str(tmp_path / "badfadvise.gguf")
        _build_layer_model(model, num_layers=1)

        def failing_fadvise(fd, offset, length, advice):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(os, "posix_fadvise", failing_fadvise)
        import mmap as _mmap

        monkeypatch.delattr(_mmap, "MADV_PAGEOUT", raising=False)
        with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
            with pytest.warns(EvictionFallbackWarning, match="failed"):
                ws.release_layer(0)
            assert ws._eviction_warned is True, "warn-once flag set after failure"

    def test_pin_all_skips_eviction(self, tmp_path, monkeypatch) -> None:
        from weight_loader import ResidencyPolicy as _P
        from weight_loader import WeightStreamer

        model = str(tmp_path / "pin.gguf")
        _build_layer_model(model, num_layers=1)
        calls: List[int] = []

        def fake_fadvise(fd, offset, length, advice):
            calls.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with WeightStreamer(model, policy=_P.PIN_ALL) as ws:
            assert ws.eviction_enabled is False
            ws.release_layer(0)
            ws.release_tensor("token_embd.weight")
        assert calls == [], "PIN_ALL must not issue page-cache eviction advice"

    def test_prefetch_survives_missing_madv_willneed(self, tmp_path, monkeypatch) -> None:
        import mmap as _mmap

        from weight_loader import WeightStreamer

        model = str(tmp_path / "nowillneed.gguf")
        _build_layer_model(model, num_layers=2)
        monkeypatch.delattr(_mmap, "MADV_WILLNEED", raising=False)
        with WeightStreamer(model, policy=ResidencyPolicy.STREAM) as ws:
            ws.prefetch_layer(1)  # must not raise without MADV_WILLNEED
            ws.prefetch_tensor("token_embd.weight")
            assert "token_embd.weight" in ws.gguf.tensors


# --------------------------------------------------------------------------- #
# 7D-2: budgeted residency policy
# --------------------------------------------------------------------------- #


class TestBudgetedResidency:
    def test_auto_pins_fitting_model(self, tmp_path, monkeypatch) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "small.gguf")
        _build_layer_model(model, num_layers=1)
        calls: List[int] = []

        def fake_fadvise(fd, offset, length, advice):
            calls.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with WeightStreamer(model, policy="auto", weight_budget=1 << 40) as ws:
            assert ws.policy == ResidencyPolicy.PIN_ALL
            ws.release_layer(0)
        assert calls == []

    def test_auto_streams_over_budget_model(self, tmp_path, monkeypatch) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "sock.gguf")
        _build_layer_model(model, num_layers=1)
        calls: List[int] = []

        def fake_fadvise(fd, offset, length, advice):
            calls.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        # budget smaller than the model's weight bytes
        with WeightStreamer(model, policy="auto", weight_budget=16) as ws:
            assert ws.policy == ResidencyPolicy.STREAM
            ws.release_layer(0)
        assert calls, "over-budget AUTO must stream (eviction advice issued)"

    def test_explicit_stream_honored_and_pin_over_budget_warns(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "explicit.gguf")
        _build_layer_model(model, num_layers=1)
        with WeightStreamer(model, policy="stream") as ws:
            assert ws.policy == ResidencyPolicy.STREAM
            weight_bytes = ws.weight_bytes
        assert weight_bytes > 1
        with pytest.warns(OverBudgetWarning, match="exceed the computed budget"):
            with WeightStreamer(
                model,
                policy=ResidencyPolicy.PIN_ALL,
                weight_budget=1,
            ) as ws:
                assert ws.policy == ResidencyPolicy.PIN_ALL  # explicit request honored

    def test_standalone_default_streams_without_warning(self, tmp_path) -> None:
        """No policy, no cache_weights, no budget: a safe STREAM default with
        no spurious NoBudgetFallbackWarning (the engine supplies the budget
        later via set_residency)."""
        from weight_loader import WeightStreamer

        model = str(tmp_path / "default.gguf")
        _build_layer_model(model, num_layers=1)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with WeightStreamer(model) as ws:
                assert ws.policy == ResidencyPolicy.STREAM
        assert not [w for w in caught if issubclass(w.category, NoBudgetFallbackWarning)]

    def test_cache_weights_mapping(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "legacy.gguf")
        _build_layer_model(model, num_layers=1)
        with WeightStreamer(model, cache_weights=True) as ws:
            assert ws.policy == ResidencyPolicy.PIN_ALL
            assert ws.cache_weights is True
        with WeightStreamer(model, cache_weights=False) as ws:
            # False maps to AUTO; standalone AUTO without budget streams safely
            assert ws.policy == ResidencyPolicy.STREAM
            assert ws.cache_weights is False

    def test_auto_without_budget_warns_on_set_residency(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "nobudget.gguf")
        _build_layer_model(model, num_layers=1)
        with WeightStreamer(model) as ws:
            with pytest.warns(NoBudgetFallbackWarning, match="no memory-budget source"):
                ws.set_residency(ResidencyPolicy.AUTO, None)
            assert ws.policy == ResidencyPolicy.STREAM

    def test_decision_records(self) -> None:
        sources = BudgetSources(readings={"host_memavailable": 1 << 30})
        budget = compute_weight_budget(kv_bytes=0, activation_bytes=0, sources=sources)
        pin = decide_residency(ResidencyPolicy.AUTO, 1024, budget.weight_budget, sources)
        assert pin.effective == ResidencyPolicy.PIN_ALL
        assert "fit the budget" in pin.reason
        stream = decide_residency(
            ResidencyPolicy.AUTO, 1 << 40, budget.weight_budget, sources
        )
        assert stream.effective == ResidencyPolicy.STREAM
        assert "exceed the budget" in stream.reason

    def test_budget_sources_and_activation_formula(self) -> None:
        sources = BudgetSources()
        assert sources.available_bytes is None  # no source: no budget invented
        budget = compute_weight_budget(
            kv_bytes=1 << 20,
            activation_bytes=1 << 21,
            sources=BudgetSources(readings={"gtt_sysfs": 1 << 30}),
            safety_margin_bytes=1 << 20,
        )
        assert budget.weight_budget == (1 << 30) - (1 << 20) - (1 << 21) - (1 << 20)
        # documented formula: hidden*seq*2bytes*4 buffers + vocab*2 + 64 MiB
        act = estimate_activation_bytes(hidden_size=8, max_seq_len=7, vocab_size=5)
        assert act == 8 * 7 * 2 * 4 + 5 * 2 + (64 << 20)

    def test_cgroup_readers_from_fake_trees(self, tmp_path) -> None:
        """cgroup v2 (and v1) readers against fake /proc/self/cgroup +
        sysfs trees: finite limits produce headroom; 'max'/unlimited produce
        None; malformed content is skipped, never fatal."""
        base = tmp_path / "cg2"
        (base / "sub").mkdir(parents=True)
        (base / "sub" / "memory.max").write_text("1048576")
        (base / "sub" / "memory.current").write_text("262144")
        proc = tmp_path / "cgroup_v2.txt"
        proc.write_text("0::/sub\n")
        assert (
            memory_budget._cgroup_v2_available_bytes(str(proc), str(base)) == 786432
        )
        (base / "sub" / "memory.max").write_text("max")
        assert memory_budget._cgroup_v2_available_bytes(str(proc), str(base)) is None

        v1 = tmp_path / "cg1" / "a"
        v1.mkdir(parents=True)
        (v1 / "memory.limit_in_bytes").write_text("2097152")
        (v1 / "memory.usage_in_bytes").write_text("524288")
        proc1 = tmp_path / "cgroup_v1.txt"
        proc1.write_text("8:memory:/a\n10:cpuset:/\n")
        assert (
            memory_budget._cgroup_v1_available_bytes(str(proc1), str(tmp_path / "cg1"))
            == 1572864
        )
        (v1 / "memory.limit_in_bytes").write_text("9223372036854775807")
        assert (
            memory_budget._cgroup_v1_available_bytes(
                str(proc1), str(tmp_path / "cg1")
            )
            is None
        )

    def test_gtt_and_host_readers(self) -> None:
        host = memory_budget.read_host_available_bytes()
        assert host is None or host > 0
        gtt = memory_budget.read_gtt_free_bytes()
        assert gtt is None or gtt > 0


# --------------------------------------------------------------------------- #
# 7D-3: KV/allocation and cleanup hardening
# --------------------------------------------------------------------------- #


class TestKVHardening:
    def test_kv_user_cap_refuses_oversized_request(self, kv_modules) -> None:
        kv_cache, _ = kv_modules
        with pytest.raises(ValueError) as ctx:
            kv_cache.KVCacheManager(
                num_layers=1024,
                max_seq_len=4096,
                num_kv_heads=8,
                head_dim=128,
                offload_to_cpu=True,
                max_kv_bytes=1 << 20,
            )
        msg = str(ctx.value)
        assert "Requested KV cache size" in msg
        assert "effective KV budget" in msg
        assert "max_kv_bytes=" in msg

    def test_kv_cgroup_limit_refuses_cleanly(self, kv_modules, monkeypatch) -> None:
        kv_cache, _ = kv_modules
        monkeypatch.setattr(
            memory_budget,
            "read_budget_sources",
            lambda: BudgetSources(
                readings={"cgroup": 1 << 20, "host_memavailable": 1 << 40}
            ),
        )
        with pytest.raises(ValueError) as ctx:
            kv_cache.KVCacheManager(
                num_layers=128,
                max_seq_len=512,
                num_kv_heads=8,
                head_dim=128,
                offload_to_cpu=True,
            )
        assert "cgroup=" in str(ctx.value), "the cgroup source must be named"

    def test_kv_mmap_files_unlinked_before_map(self, kv_modules, tmp_path) -> None:
        """Unlink-after-map: files are gone while the manager is alive (a crash
        before close() leaves nothing behind), yet the mapping stays usable."""
        kv_cache, _ = kv_modules
        mmap_dir = str(tmp_path / "kv")
        with kv_cache.KVCacheManager(
            num_layers=2,
            max_seq_len=32,
            num_kv_heads=2,
            head_dim=8,
            mmap_dir=mmap_dir,
        ) as kv:
            paths = kv.mmap_files
            assert len(paths) == 2
            for p in paths:
                assert not os.path.exists(p), (
                    "KV mmap files must be unlinked immediately after mapping"
                )
            # the mapping really is usable after the unlink
            assert kv.mode == "mmap"
            kv._k_host[0, 0, 0, :] = 1.0
            assert float(kv._k_host[0, 0, 0, 0]) == 1.0
        # closed: no files anywhere in the mmap dir
        assert os.listdir(mmap_dir) == []

    def test_kv_disk_space_check_refuses_before_alloc(self, kv_modules, tmp_path, monkeypatch) -> None:
        kv_cache, _ = kv_modules
        mmap_dir = tmp_path / "kvfull"
        mmap_dir.mkdir()
        monkeypatch.setattr(
            os,
            "statvfs",
            lambda p: types.SimpleNamespace(f_bsize=4096, f_bavail=1),
        )
        with pytest.raises(OSError, match="Insufficient disk space"):
            kv_cache.KVCacheManager(
                num_layers=4,
                max_seq_len=64,
                num_kv_heads=4,
                head_dim=64,
                mmap_dir=str(mmap_dir),
            )
        assert os.listdir(str(mmap_dir)) == [], "no partial files after refusal"

    def test_kv_symlink_target_rejected(self, kv_modules, tmp_path, monkeypatch) -> None:
        kv_cache, _ = kv_modules
        mmap_dir = tmp_path / "kvsym"
        mmap_dir.mkdir()
        victim = mmap_dir / "victim.bin"
        victim.write_bytes(b"data")
        monkeypatch.setattr(os, "getpid", lambda: 12345)
        import builtins

        monkeypatch.setattr(builtins, "id", lambda obj: 0xDEAD)
        # Predicted paths: kv_cache_k_{pid}_{id:x}.mmap with our patches
        for kind in ("k", "v"):
            predicted = mmap_dir / f"kv_cache_{kind}_12345_dead.mmap"
            predicted.symlink_to(victim)
        with pytest.raises(OSError):
            kv_cache.KVCacheManager(
                num_layers=1,
                max_seq_len=16,
                num_kv_heads=1,
                head_dim=8,
                mmap_dir=str(mmap_dir),
            )
        # pre-existing bystander is untouched
        assert victim.read_bytes() == b"data"

    def test_kv_fallocate_fallback_to_ftruncate(self, kv_modules, tmp_path, monkeypatch) -> None:
        kv_cache, _ = kv_modules
        have_fallocate = hasattr(os, "posix_fallocate")
        if have_fallocate:
            monkeypatch.delattr(os, "posix_fallocate", raising=False)
        with kv_cache.KVCacheManager(
            num_layers=1,
            max_seq_len=16,
            num_kv_heads=1,
            head_dim=8,
            mmap_dir=str(tmp_path / "kv"),
        ) as kv:
            assert kv.mode == "mmap"
            kv._v_host[0, 0, 0, :] = 2.0
            assert float(kv._v_host[0, 0, 0, 0]) == 2.0

    def test_block_count_cross_check(self, tmp_path) -> None:
        """A header declaring 999 layers over 2 actual blk.N.* groups fails
        concisely with declared vs found count/min/max."""
        from weight_loader import WeightStreamer

        model = str(tmp_path / "lying.gguf")
        _build_layer_model(model, num_layers=2, declared_block_count=999)
        with pytest.raises(ValueError) as ctx:
            WeightStreamer(model)
        msg = str(ctx.value)
        assert "999" in msg and "found 2" in msg
        assert "min=0" in msg and "max=1" in msg
        assert len(msg.splitlines()) == 1  # no 999-entry missing-tensor list

    def test_block_count_zero_with_tensors_rejected(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "zero.gguf")
        _build_layer_model(model, num_layers=2, declared_block_count=0)
        with pytest.raises(ValueError) as ctx_bz:
            WeightStreamer(model)
        assert "disagrees" in str(ctx_bz.value)

    def test_honest_block_count_loads(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "honest.gguf")
        _build_layer_model(model, num_layers=3)
        with WeightStreamer(model) as ws:
            assert ws.num_layers == 3

    def test_duplicate_tensor_names_rejected_at_load(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        buf = __import__("io").BytesIO()
        rng = np.random.default_rng(3)
        raw = rng.standard_normal(64, dtype=np.float32).astype(np.float16).tobytes()
        write_synthetic_gguf(
            buf,
            metadata={"general.architecture": (GGUFValueType.STRING, "llama"),
                      "llama.block_count": (GGUFValueType.UINT32, 1)},
            tensors=[
                ("blk.0.attn_norm.weight", (64,), GGMLType.F16, raw),
                ("blk.0.attn_norm.weight", (64,), GGMLType.F16, raw),
            ],
        )
        path = str(tmp_path / "dup.gguf")
        with open(path, "wb") as fh:
            fh.write(buf.getvalue())
        with pytest.raises(ValueError) as ctx_dup:
            WeightStreamer(path)
        assert "Duplicate tensor name" in str(ctx_dup.value)

    def test_alignment_zero_and_truncation_fail_closed(self, tmp_path) -> None:
        """Hostile parser inputs: general.alignment=0 and truncation fail
        closed with actionable errors."""
        rng = np.random.default_rng(3)
        raw = rng.standard_normal(64, dtype=np.float32).astype(np.float16).tobytes()
        base_meta = {
            "general.architecture": (GGUFValueType.STRING, "llama"),
            "llama.block_count": (GGUFValueType.UINT32, 1),
        }
        # alignment=0: rejected (power of 2 in [1, MAX_ALIGNMENT])
        b0 = __import__("io").BytesIO()
        write_synthetic_gguf(
            b0,
            metadata={**base_meta, "general.alignment": (GGUFValueType.UINT32, 0)},
            tensors=[("x.weight", (64,), GGMLType.F16, raw)],
        )
        with pytest.raises(ValueError) as ctx_al:
            GGUFParser(b0.getvalue())
        assert "general.alignment" in str(ctx_al.value)
        # truncated valid file
        b1 = __import__("io").BytesIO()
        write_synthetic_gguf(
            b1, metadata=base_meta, tensors=[("x.weight", (64,), GGMLType.F16, raw)]
        )
        with pytest.raises(ValueError) as ctx_tr:
            GGUFParser(b1.getvalue()[: len(b1.getvalue()) // 3])
        err = str(ctx_tr.value)
        assert "Truncated" in err or "EOF" in err


# --------------------------------------------------------------------------- #
# 7D-3: exception preservation & leak probe
# --------------------------------------------------------------------------- #


class TestExceptionPreservationAndLeaks:
    def test_streamer_ctor_error_not_masked_by_cleanup(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        # nonexistent file: the original FileNotFoundError survives
        with pytest.raises(FileNotFoundError) as ctx:
            WeightStreamer(str(tmp_path / "missing.gguf"))
        assert isinstance(ctx.value, FileNotFoundError), "original error must survive"
        # invalid magic: the original ValueError survives
        bad = tmp_path / "bad.gguf"
        bad.write_bytes(b"NOPE" + b"\x00" * 64)
        with pytest.raises(ValueError) as ctx2:
            WeightStreamer(str(bad))
        assert "GGUF" in str(ctx2.value) or "magic" in str(ctx2.value), (
            "the original parse error, not a cleanup error, is raised"
        )

    def test_streamer_close_with_live_view_warns_and_closes_fd(self, tmp_path) -> None:
        from weight_loader import WeightStreamer

        model = str(tmp_path / "liveview.gguf")
        _build_layer_model(model, num_layers=1)
        ws = WeightStreamer(model)
        raw_file = ws._file
        live_view = ws.get_tensor_view("token_embd.weight")
        try:
            with pytest.warns(RuntimeWarning, match="live views"):
                ws.close()
            assert raw_file.closed, "fd must be closed even with a live view"
        finally:
            del live_view

    def test_engine_ctor_error_preserved(self, kv_modules, tmp_path) -> None:
        """An over-budget KV request inside the engine constructor raises the
        KV ValueError; the cleanup close() must not mask it with a
        BufferError/RuntimeError."""
        _, inference = kv_modules
        model = str(tmp_path / "engine.gguf")
        _engine_model(model)
        with pytest.raises(ValueError) as ctx:
            inference.LlamaInferenceEngine(
                model, max_seq_len=64, offload_kv_to_cpu=True, max_kv_bytes=1
            )
        exc = ctx.value
        assert "effective KV budget" in str(exc), (
            "the original KV budget error, not a cleanup error, is raised"
        )

    def test_no_fd_or_mmap_leak_1000x(self, tmp_path) -> None:
        """1,000x open/close: /proc/self/fd and /proc/self/maps counts do not
        grow (checks at 100/600/1100 iterations)."""
        import gc

        from weight_loader import WeightStreamer

        model = str(tmp_path / "leak.gguf")
        _build_layer_model(model, num_layers=1)

        def snapshot() -> Tuple[int, int]:
            gc.collect()
            return _fd_count(), _proc_count("maps", "blk-")

        # warm-up so importers/loader allocations settle
        for _ in range(20):
            with WeightStreamer(model):
                pass
        base = snapshot()

        checkpoints = {}
        for i in range(1, 1101):
            with WeightStreamer(model) as ws:
                _ = ws.get_tensor_view("token_embd.weight")
                ws.release_tensor("token_embd.weight")
            if i in (100, 600, 1100):
                checkpoints[i] = snapshot()
        for iteration, (fds, maps) in checkpoints.items():
            assert abs(fds - base[0]) <= 2, (
                f"fd leak: baseline {base[0]} vs {fds} after {iteration} cycles"
            )
            assert abs(maps - base[1]) <= 4, (
                f"mmap leak: baseline {base[1]} vs {maps} after {iteration} cycles"
            )

    @pytest.mark.slow
    def test_kv_1000x_no_leak(self, kv_modules, tmp_path) -> None:
        kv_cache, _ = kv_modules
        import gc

        base = _fd_count()
        for _ in range(1000):
            kv = kv_cache.KVCacheManager(
                num_layers=1, max_seq_len=8, num_kv_heads=1, head_dim=8,
                offload_to_cpu=True,
            )
            kv.close()
        gc.collect()
        assert abs(_fd_count() - base) <= 2


# --------------------------------------------------------------------------- #
# 7D-2: engine-level policy integration
# --------------------------------------------------------------------------- #


def _engine_model(path: str) -> None:
    """A minimal engine-constructible llama model (meta + required tensors)."""
    rng = np.random.default_rng(11)
    hidden = 32
    inter = 64
    heads = 4
    kvh = 2
    hd = 8
    vocab = ["<unk>", "<s>", "</s>", "▁", "A"]
    scores = [0.0, 0.0, 0.0, 0.0, 0.0]
    metadata: Dict[str, Tuple[GGUFValueType, object]] = {
        "general.architecture": (GGUFValueType.STRING, "llama"),
        "llama.block_count": (GGUFValueType.UINT32, 1),
        "llama.embedding_length": (GGUFValueType.UINT32, hidden),
        "llama.feed_forward_length": (GGUFValueType.UINT32, inter),
        "llama.attention.head_count": (GGUFValueType.UINT32, heads),
        "llama.attention.head_count_kv": (GGUFValueType.UINT32, kvh),
        "llama.rope.dimension_count": (GGUFValueType.UINT32, hd),
        "llama.attention.layer_norm_rms_epsilon": (GGUFValueType.FLOAT32, 1e-5),
        "tokenizer.ggml.tokens": (GGUFValueType.ARRAY, (GGUFValueType.STRING, vocab)),
        "tokenizer.ggml.scores": (GGUFValueType.ARRAY, (GGUFValueType.FLOAT32, scores)),
        "tokenizer.ggml.bos_token_id": (GGUFValueType.UINT32, 1),
        "tokenizer.ggml.eos_token_id": (GGUFValueType.UINT32, 2),
    }

    def f16(*shape: int) -> bytes:
        return rng.standard_normal(shape, dtype=np.float32).astype(np.float16).tobytes()

    # (name, in_dim, out_dim); GGUF dims are (in_dim, out_dim) with ne[0]
    # innermost: a (out, in) row-major weight is packed as (in_dim, out_dim).
    projs = [
        ("attn_q.weight", hidden, heads * hd),
        ("attn_k.weight", hidden, kvh * hd),
        ("attn_v.weight", hidden, kvh * hd),
        ("attn_output.weight", heads * hd, hidden),
        ("ffn_gate.weight", hidden, inter),
        ("ffn_up.weight", hidden, inter),
        ("ffn_down.weight", inter, hidden),
    ]
    tensors: List[Tuple[str, Tuple[int, ...], GGMLType, bytes]] = [
        ("token_embd.weight", (hidden, len(vocab)), GGMLType.F16, f16(hidden, len(vocab))),
        ("output_norm.weight", (hidden,), GGMLType.F16, f16(hidden)),
        ("output.weight", (hidden, len(vocab)), GGMLType.F16, f16(hidden, len(vocab))),
    ]
    tensors.append(("blk.0.attn_norm.weight", (hidden,), GGMLType.F16, f16(hidden)))
    tensors.append(("blk.0.ffn_norm.weight", (hidden,), GGMLType.F16, f16(hidden)))
    for name, in_dim, out_dim in projs:
        tensors.append(
            (f"blk.0.{name}", (in_dim, out_dim), GGMLType.F16, f16(in_dim, out_dim))
        )
    with open(path, "wb") as fh:
        write_synthetic_gguf(fh, metadata, tensors)


class TestEngineResidency:
    def test_engine_auto_pins_with_big_budget(self, kv_modules, tmp_path, monkeypatch) -> None:
        kv_modules_mod, inference = kv_modules
        model = str(tmp_path / "auto_pin.gguf")
        _engine_model(model)
        calls: List[int] = []

        def fake_fadvise(fd, offset, length, advice):
            calls.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with inference.LlamaInferenceEngine(
            model,
            max_seq_len=32,
            offload_kv_to_cpu=True,
            residency="auto",
            residency_budget_mb=4096,
        ) as eng:
            assert eng.residency_requested == ResidencyPolicy.AUTO
            assert eng.streamer.policy == ResidencyPolicy.PIN_ALL
            assert "override" in eng.residency_decision_origin
            eng.streamer.release_layer(0)
        assert calls == []

    def test_engine_auto_streams_with_small_budget(self, kv_modules, tmp_path, monkeypatch) -> None:
        _, inference = kv_modules
        model = str(tmp_path / "auto_stream.gguf")
        _engine_model(model)
        calls: List[int] = []

        def fake_fadvise(fd, offset, length, advice):
            calls.append(offset)
            return 0

        monkeypatch.setattr(os, "posix_fadvise", fake_fadvise)
        with inference.LlamaInferenceEngine(
            model,
            max_seq_len=32,
            offload_kv_to_cpu=True,
            residency="auto",
            # A zero budget never fits the model: AUTO must stream, not pin.
            residency_budget_mb=0,
        ) as eng:
            assert eng.streamer.policy == ResidencyPolicy.STREAM
            eng.streamer.release_layer(0)
        assert calls, "over-budget AUTO must stream"

    def test_engine_explicit_residency_and_cache_weights_deprecation(
        self, kv_modules, tmp_path
    ) -> None:
        _, inference = kv_modules
        model = str(tmp_path / "explicit.gguf")
        _engine_model(model)
        with inference.LlamaInferenceEngine(
            model, max_seq_len=32, offload_kv_to_cpu=True, residency="stream"
        ) as eng:
            assert eng.streamer.policy == ResidencyPolicy.STREAM
        with pytest.warns(DeprecationWarning, match="deprecated"):
            with inference.LlamaInferenceEngine(
                model, max_seq_len=32, offload_kv_to_cpu=True, cache_weights=True
            ) as eng:
                assert eng.streamer.policy == ResidencyPolicy.PIN_ALL
        # explicit --residency wins over --cache-weights
        with inference.LlamaInferenceEngine(
            model,
            max_seq_len=32,
            offload_kv_to_cpu=True,
            residency="stream",
            cache_weights=True,
        ) as eng:
            assert eng.streamer.policy == ResidencyPolicy.STREAM

    def test_engine_over_budget_pin_warns(self, kv_modules, tmp_path) -> None:
        _, inference = kv_modules
        model = str(tmp_path / "overpin.gguf")
        _engine_model(model)
        with pytest.warns(OverBudgetWarning):
            with inference.LlamaInferenceEngine(
                model,
                max_seq_len=32,
                offload_kv_to_cpu=True,
                residency="pin",
                residency_budget_mb=0,
            ) as eng:
                assert eng.streamer.policy == ResidencyPolicy.PIN_ALL
                assert eng.residency_decision.over_budget is True

    def test_resolve_residency_policy_mapping(self, kv_modules) -> None:
        _, inference = kv_modules
        assert inference.resolve_residency_policy(None, False) == (
            ResidencyPolicy.AUTO,
            False,
        )
        assert inference.resolve_residency_policy("pin", False) == (
            ResidencyPolicy.PIN_ALL,
            False,
        )
        assert inference.resolve_residency_policy(None, True) == (
            ResidencyPolicy.PIN_ALL,
            True,
        )
        assert inference.resolve_residency_policy("stream", True) == (
            ResidencyPolicy.STREAM,
            False,
        )
        with pytest.raises(ValueError):
            inference.resolve_residency_policy("bogus", False)

    def test_cli_flags(self, kv_modules, monkeypatch, capsys) -> None:
        _, inference = kv_modules
        with pytest.raises(SystemExit) as exc_info:
            inference.main(["--residency", "wrong", "--model", "x.gguf"])
        assert exc_info.value.code == 2
        out = capsys.readouterr()
        assert "--residency" in (out.out + out.err)
        # accepted choices parse (they fail later at model load, not parsing)
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            inference.main(
                ["--model", "/nonexistent.gguf", "--residency", "stream",
                 "--residency-budget-mb", "512", "--max-kv-bytes", "1024"]
            )


# --------------------------------------------------------------------------- #
# Measured residency probe: VmRSS delta PIN vs STREAM
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_measured_rss_delta_pin_vs_stream(tmp_path) -> None:
    """Measured, not asserted from thin air: touching every layer under PIN
    keeps the pages resident (VmRSS grows by roughly the model size), while
    STREAM + eviction grows RSS by clearly less AND demonstrably drops the
    pages from the page cache (a re-touch after STREAM eviction takes major
    faults — real disk re-faults; a warm re-touch under PIN takes none).

    Measurement sources: VmRSS from /proc/self/status; minor/major faults from
    /proc/self/stat. Page-cache eviction is kernel best-effort; on this host
    (no MADV_PAGEOUT) the PTE drop enables the fadvise, and the major-fault
    re-touch proves the fadvise actually evicted the page cache."""
    from weight_loader import WeightStreamer

    pin_model = str(tmp_path / "pin_rss.gguf")
    stream_model = str(tmp_path / "stream_rss.gguf")
    elems = 8 * 1024 * 1024  # 16 MiB per tensor
    pin_size = _build_layer_model(pin_model, num_layers=3, elems_per_tensor=elems)
    _build_layer_model(stream_model, num_layers=3, elems_per_tensor=elems)

    def fault_counts() -> Tuple[int, int]:
        with open("/proc/self/stat", "r") as fh:
            fields = fh.read().split()
        return int(fields[9]), int(fields[11])  # minflt, majflt

    def touch_all(ws) -> None:
        for name in ws.gguf.tensors:
            _ = float(np.asarray(ws.get_tensor_view(name)).sum())

    # PIN: touch everything; a warm re-touch faults nothing.
    before_kb = _vm_rss_kb()
    with WeightStreamer(pin_model, policy=ResidencyPolicy.PIN_ALL) as ws:
        touch_all(ws)
        pin_delta_kb = _vm_rss_kb() - before_kb
        warm_before = fault_counts()
        touch_all(ws)
        warm_after = fault_counts()
    warm_majflt = warm_after[1] - warm_before[1]

    # STREAM: touch + evict each layer; re-touching an evicted layer must
    # re-fault from disk (major faults) because the pages left the page cache.
    before_kb2 = _vm_rss_kb()
    with WeightStreamer(stream_model, policy=ResidencyPolicy.STREAM) as ws:
        for layer in range(ws.num_layers):
            for name in ws.gguf.get_layer_tensors(layer):
                _ = float(np.asarray(ws.get_tensor_view(name)).sum())
            ws.release_layer(layer)
        stream_delta_kb = _vm_rss_kb() - before_kb2
        refault_before = fault_counts()
        for name in ws.gguf.get_layer_tensors(0):
            _ = float(np.asarray(ws.get_tensor_view(name)).sum())
        refault_after = fault_counts()
    refault_majflt = refault_after[1] - refault_before[1]

    print(
        f"  [RSS probe] model={pin_size} bytes PIN dRSS={pin_delta_kb} kB "
        f"(warm re-touch majflt={warm_majflt}); "
        f"STREAM dRSS={stream_delta_kb} kB (refault majflt={refault_majflt})"
    )
    assert pin_delta_kb > 0, "PIN should grow RSS while touching every layer"
    assert warm_majflt == 0, "a warm re-touch under PIN must not fault from disk"
    assert stream_delta_kb < pin_delta_kb, (
        "STREAM's eviction should keep the RSS delta below PIN's"
    )
    assert refault_majflt > 0, (
        "re-touching a STREAM-evicted layer must take major faults: the pages "
        "were really dropped from the page cache, not just from the PTEs"
    )
