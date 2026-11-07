#!/usr/bin/env python3
"""QAQC probes for Phase 7D (Gate G4) — KV/allocation hardening evidence.

Runs the hostile-input matrix against KVCacheManager (CPU/mmap offload path,
matmul_module stubbed when absent): KV budget caps, cgroup v2/v1 fake trees,
disk-space refusal, symlink rejection, unlink-before-map crash safety,
duplicate names, block_count mismatch, and the live-view close warning/ctor
exception-preservation rules. Complements the pytest suite with raw traces.

Usage: python3 audit/evidence/G4/7D/qaqc-probes/kv_probes.py [workdir]
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import warnings

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "src"))
sys.path.insert(0, os.path.join(_REPO, "tests"))

RESULTS: list[str] = []


def log(msg: str) -> None:
    print(msg)
    RESULTS.append(msg)


def _ensure_matmul_stub() -> bool:
    if "matmul_module" in sys.modules:
        return False
    try:
        import matmul_module  # noqa: F401

        return False
    except ImportError:
        sys.modules["matmul_module"] = types.SimpleNamespace(
            kv_cache_init=lambda *a: None,
            kv_cache_free=lambda *a: None,
            gqa_attention=lambda *a: None,
        )
        return True


def main() -> int:
    work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="7d-kv-")
    log(f"QAQC KV probes; workdir {work}")
    stub_installed = _ensure_matmul_stub()
    try:
        kv_cache = importlib.import_module("kv_cache")
        memory_budget = importlib.import_module("memory_budget")

        log("=== KV user cap refusal (max_kv_bytes smaller than request) ===")
        try:
            kv_cache.KVCacheManager(
                num_layers=1024, max_seq_len=4096, num_kv_heads=8, head_dim=128,
                offload_to_cpu=True, max_kv_bytes=1 << 20,
            )
            log("  FAIL: oversize request was accepted")
            return 1
        except ValueError as exc:
            log(f"  refused: {str(exc)[:220]}")

        log("=== KV cgroup-limited refusal (monkeypatched cgroup source) ===")
        from memory_budget import BudgetSources

        saved = memory_budget.read_budget_sources
        memory_budget.read_budget_sources = lambda: BudgetSources(
            readings={"cgroup": 1 << 20, "host_memavailable": 1 << 40}
        )
        try:
            kv_cache.KVCacheManager(
                num_layers=128, max_seq_len=512, num_kv_heads=8, head_dim=128,
                offload_to_cpu=True,
            )
            log("  FAIL: cgroup-limited request was accepted")
            return 1
        except ValueError as exc:
            log(f"  refused: {str(exc)[:220]}")
        finally:
            memory_budget.read_budget_sources = saved

        log("=== cgroup fake trees (v2 then v1) ===")
        base = os.path.join(work, "cg2")
        os.makedirs(os.path.join(base, "sub"), exist_ok=True)
        proc = os.path.join(work, "proc2.txt")
        with open(proc, "w") as fh:
            fh.write("0::/sub\n")
        with open(os.path.join(base, "sub", "memory.max"), "w") as fh:
            fh.write("1048576")
        with open(os.path.join(base, "sub", "memory.current"), "w") as fh:
            fh.write("262144")
        v2 = memory_budget._cgroup_v2_available_bytes(proc, base)
        log(f"  v2 limited tree: memory.max=1048576, current=262144 -> {v2} "
            f"(expected 786432)")
        with open(os.path.join(base, "sub", "memory.max"), "w") as fh:
            fh.write("max")
        log(f"  v2 'max' (unlimited) -> "
             f"{memory_budget._cgroup_v2_available_bytes(proc, base)} (expected None)")
        v1base = os.path.join(work, "cg1")
        os.makedirs(os.path.join(v1base, "a"), exist_ok=True)
        proc1 = os.path.join(work, "proc1.txt")
        with open(proc1, "w") as fh:
            fh.write("8:memory:/a\n")
        with open(os.path.join(v1base, "a", "memory.limit_in_bytes"), "w") as fh:
            fh.write("2097152")
        with open(os.path.join(v1base, "a", "memory.usage_in_bytes"), "w") as fh:
            fh.write("524288")
        v1 = memory_budget._cgroup_v1_available_bytes(proc1, v1base)
        log(f"  v1 limited tree -> {v1} (expected 1572864)")

        log("=== full-disk refusal (statvfs monkeypatched tiny) ===")
        mmap_dir = os.path.join(work, "kvfull")
        os.makedirs(mmap_dir, exist_ok=True)
        saved_statvfs = os.statvfs
        os.statvfs = lambda p: types.SimpleNamespace(f_bsize=4096, f_bavail=1)
        try:
            kv_cache.KVCacheManager(
                num_layers=4, max_seq_len=64, num_kv_heads=4, head_dim=64,
                mmap_dir=mmap_dir,
            )
            log("  FAIL: allocation on a full disk was accepted")
            return 1
        except OSError as exc:
            log(f"  refused: {str(exc)[:220]}")
        finally:
            os.statvfs = saved_statvfs
        log(f"  files left in the dir after refusal: {os.listdir(mmap_dir)}")

        log("=== symlink at the target path rejected ===")
        sym_dir = os.path.join(work, "kvsym")
        os.makedirs(sym_dir, exist_ok=True)
        victim = os.path.join(sym_dir, "victim.bin")
        with open(victim, "wb") as fh:
            fh.write(b"important_user_data")
        saved_getpid = os.getpid
        saved_id = __builtins__.id if hasattr(__builtins__, "id") else None
        os.getpid = lambda: 12345
        import builtins

        saved_bid = builtins.id
        builtins.id = lambda obj: 0xDEAD
        try:
            for kind in ("k", "v"):
                link = os.path.join(sym_dir, f"kv_cache_{kind}_12345_dead.mmap")
                if not os.path.lexists(link):
                    os.symlink(victim, link)
            kv_cache.KVCacheManager(
                num_layers=1, max_seq_len=16, num_kv_heads=1, head_dim=8,
                mmap_dir=sym_dir,
            )
            log("  FAIL: symlinked KV path was accepted")
            return 1
        except OSError as exc:
            log(f"  refused ({type(exc).__name__}: {exc})")
        finally:
            os.getpid = saved_getpid
            builtins.id = saved_bid
        with open(victim, "rb") as fh:
            log(f"  bystander untouched: {fh.read()!r}")

        log("=== unlink-before-map: crash before close() leaves no files ===")
        crash_dir = os.path.join(work, "kvcrash")
        os.makedirs(crash_dir, exist_ok=True)
        kv = kv_cache.KVCacheManager(
            num_layers=2, max_seq_len=32, num_kv_heads=2, head_dim=8,
            mmap_dir=crash_dir,
        )  # no close(): simulate a crash before close()
        on_disk = os.listdir(crash_dir)
        try:
            kv._k_host[0, 0, 0, :] = 1.0  # mapping usable after unlink
            usable = float(kv._k_host[0, 0, 0, 0]) == 1.0
        finally:
            kv.close()
        log(f"  files on disk while manager alive (pre-crash): {on_disk} (expected [])")
        log(f"  mapping usable through fd after unlink: {usable}")
        log(f"  files on disk after close(): {os.listdir(crash_dir)} (expected [])")

        log("=== block_count cross-check (999 declared vs 2 found) ===")
        import numpy as np

        from gguf_parser import GGMLType, GGUFValueType, write_synthetic_gguf
        from test_memory_residency import _build_layer_model

        lying = os.path.join(work, "lying.gguf")
        _build_layer_model(lying, num_layers=2, declared_block_count=999)
        from weight_loader import WeightStreamer

        try:
            WeightStreamer(lying)
            log("  FAIL: lying block_count was accepted")
            return 1
        except ValueError as exc:
            log(f"  refused: {exc}")

        log("=== duplicate tensor names ===")
        import io as _io

        rng = np.random.default_rng(3)
        raw = rng.standard_normal(64, dtype=np.float32).astype(np.float16).tobytes()
        buf = _io.BytesIO()
        write_synthetic_gguf(
            buf,
            metadata={
                "general.architecture": (GGUFValueType.STRING, "llama"),
                "llama.block_count": (GGUFValueType.UINT32, 1),
            },
            tensors=[
                ("blk.0.attn_norm.weight", (64,), GGMLType.F16, raw),
                ("blk.0.attn_norm.weight", (64,), GGMLType.F16, raw),
            ],
        )
        try:
            import gguf_parser

            gguf_parser.GGUFParser(buf.getvalue())
            log("  FAIL: duplicate names were accepted")
            return 1
        except ValueError as exc:
            log(f"  refused: {exc}")

        log("=== live-view close: warn, fd closed; ctor error preserved ===")
        model = os.path.join(work, "liveview.gguf")
        _build_layer_model(model, num_layers=1)
        ws = WeightStreamer(model)
        raw_file = ws._file
        _ = ws.get_tensor_view("token_embd.weight")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ws.close()
        warned = [
            w for w in caught if issubclass(w.category, RuntimeWarning)
        ]
        log(f"  close() warned instead of raising: "
            f"{[w.category.__name__ for w in warned]}; fd closed={raw_file.closed}")

        inference = importlib.import_module("inference")
        engine_model = os.path.join(work, "engine.gguf")
        from test_memory_residency import _engine_model

        _engine_model(engine_model)
        try:
            inference.LlamaInferenceEngine(
                engine_model, max_seq_len=64, offload_kv_to_cpu=True, max_kv_bytes=1
            )
            log("  FAIL: engine accepted an over-budget KV request")
            return 1
        except ValueError as exc:
            is_budget_error = "effective KV budget" in str(exc)
            log(f"  engine ctor original exception preserved: "
                f"{type(exc).__name__}, mentions budget={is_budget_error}, "
                f"first 120 chars: {str(exc)[:120]}")
        log("ALL KV PROBES COMPLETED")
        return 0
    finally:
        if stub_installed:
            sys.modules.pop("matmul_module", None)


if __name__ == "__main__":
    raise SystemExit(main())
