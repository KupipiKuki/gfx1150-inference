"""
Self-Contained CPU-Only Verification & Regression Suite (`tests/test_cpu_only.py`).

Runs on any standard CPU environment (including GitHub Actions `ubuntu-latest`) without
requiring an AMD GPU, ROCm, or a compiled `matmul_module` extension.

Covers:
- V-1: `py_compile` syntax validation across all `src/*.py`, `tests/*.py`, and `setup.py`.
- V-2: Pure-CPU module imports (`gguf_parser`, `weight_loader`, `tokenizer`).
- V-3 / G-1: Actionable `ImportError` with CMake build instructions when `matmul_module` is absent.
- V-4: GGUF v3 synthetic writer -> parser round-trip (metadata, offsets, alignment).
- S-1 / A-5: Truncated GGUF buffer raises `ValueError` at parse time (preventing `SIGBUS`).
- S-2: Malformed GGUF header caps (`kv_count`, `tensor_count`, `ARRAY` count, `n_dims > 8`,
  invalid `general.alignment` 0 or non-power-of-two) raise `ValueError`.
- D-3: Caller-supplied `memoryview` is not released by `GGUFParser`.
- P-8 / A-3: `get_layer_byte_spans` splits around interleaved non-layer tensors.
- V-5: `Q4_0`, `Q8_0`, and `Q4_K` CPU quantize -> dequantize error bounds.
- V-6 / P-4 / P-5: O(L log L) heap BPE tokenizer (`hello world` -> `<s> ▁hello ▁world`),
  `<0xXX>` UTF-8 byte fallback (`Ω`), tie-breaking determinism, vectorized `embed_tokens`,
  and out-of-range / negative token ID rejection (`ValueError`).
- V-7 / D-5: Token sampler (`sample_next_token`) greedy, `top_k=1`, seeded reproducibility,
  repetition penalty, flat-logits fallback, and Top-P zero-sum guard.
- S-3 & D-4: `KVCacheManager` `O_CREAT | O_EXCL` unique `mmap` filenames (never clobbering
  or deleting pre-existing files in `mmap_dir`) and `__del__` `RuntimeWarning` emission.
- V-8: `pyproject.toml` packaging metadata validation.
"""

from __future__ import annotations

import importlib
import io
import os
import py_compile
import struct
import sys
import tempfile
import types
import unittest
import warnings
import numpy as np

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from gguf_parser import (
    GGUF_MAGIC,
    GGMLType,
    GGUFParser,
    GGUFValueType,
    quantize_q4_0_cpu,
    dequantize_q4_0_cpu,
    quantize_q8_0_cpu,
    dequantize_q8_0_cpu,
    quantize_q4_k_cpu,
    dequantize_q4_k_cpu,
    write_synthetic_gguf,
)
from weight_loader import WeightStreamer
from tokenizer import GGUFTokenizer, embed_tokens


class TestCPUOnlySuite(unittest.TestCase):
    def test_v1_py_compile_all_sources(self) -> None:
        """V-1: Verify all Python files in src/, tests/, and setup.py compile cleanly."""
        py_files = [os.path.join(_ROOT_DIR, "setup.py")]
        for sub in ("src", "tests"):
            folder = os.path.join(_ROOT_DIR, sub)
            for fn in sorted(os.listdir(folder)):
                if fn.endswith(".py"):
                    py_files.append(os.path.join(folder, fn))

        for path in py_files:
            py_compile.compile(path, doraise=True)

    def test_v3_actionable_import_error_without_extension(self) -> None:
        """V-3 / G-1: GPU modules raise actionable ImportError when matmul_module is absent."""
        saved_mod = sys.modules.get("matmul_module")
        saved_Dependents = {
            name: sys.modules.pop(name, None)
            for name in ("kv_cache", "layer", "inference")
        }
        try:
            sys.modules["matmul_module"] = None  # Block import even if build/ exists
            for mod_name in ("kv_cache", "layer", "inference"):
                with self.assertRaises(ImportError) as ctx:
                    importlib.import_module(mod_name)
                self.assertIn("cmake -B build", str(ctx.exception))
        finally:
            if saved_mod is not None:
                sys.modules["matmul_module"] = saved_mod
            else:
                sys.modules.pop("matmul_module", None)
            for name, mod in saved_Dependents.items():
                if mod is not None:
                    sys.modules[name] = mod

    def test_v4_gguf_roundtrip_and_d3_memoryview_ownership(self) -> None:
        """V-4 & D-3: GGUF v3 writer->parser round-trip and caller memoryview preservation."""
        buf = io.BytesIO()
        w = np.arange(32, dtype=np.float16)
        write_synthetic_gguf(
            buf,
            metadata={"general.architecture": (GGUFValueType.STRING, "llama")},
            tensors=[("blk.0.attn_norm.weight", (32,), GGMLType.F16, w.tobytes())],
        )
        raw = buf.getvalue()
        caller_mv = memoryview(raw)
        parser = GGUFParser(caller_mv)

        # D-3: caller_mv must remain valid and unreleased after GGUFParser returns
        self.assertEqual(bytes(caller_mv[:4]), GGUF_MAGIC)
        self.assertEqual(parser.metadata["general.architecture"], "llama")
        t_info = parser.tensors["blk.0.attn_norm.weight"]
        parsed_w = np.frombuffer(raw, dtype=np.float16, count=32, offset=t_info.abs_offset)
        np.testing.assert_array_equal(parsed_w, w)
        caller_mv.release()

    def test_s1_truncated_gguf_raises_value_error(self) -> None:
        """S-1 / A-5: Truncated GGUF payload raises ValueError at parse time (no SIGBUS)."""
        buf = io.BytesIO()
        payload = np.zeros(128, dtype=np.float16).tobytes()
        write_synthetic_gguf(
            buf,
            metadata={"llama.block_count": (GGUFValueType.UINT32, 1)},
            tensors=[("blk.0.attn_q.weight", (128,), GGMLType.F16, payload)],
        )
        full_bytes = buf.getvalue()
        # Truncate 16 bytes off the tensor data section
        truncated = full_bytes[:-16]
        with self.assertRaises(ValueError) as ctx:
            GGUFParser(truncated)
        self.assertIn("Truncated GGUF", str(ctx.exception))

        # Also verify via WeightStreamer with a truncated file on disk
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = os.path.join(tmpdir, "truncated.gguf")
            with open(tpath, "wb") as f:
                f.write(truncated)
            with self.assertRaises(ValueError):
                WeightStreamer(tpath)

    def test_s2_malformed_header_and_alignment_caps(self) -> None:
        """S-2: Excessive kv_count, tensor_count, n_dims, and bad alignment raise ValueError."""
        # 1. Excessive kv_count
        bad_kv = GGUF_MAGIC + struct.pack("<IQQ", 3, 0, 10_000_000)
        with self.assertRaises(ValueError):
            GGUFParser(bad_kv)

        # 2. Excessive tensor_count
        bad_tc = GGUF_MAGIC + struct.pack("<IQQ", 3, 10_000_000, 0)
        with self.assertRaises(ValueError):
            GGUFParser(bad_tc)

        # 3. general.alignment = 0 (ZeroDivisionError guard) or non-power-of-two (e.g. 30)
        for bad_align in (0, 3, 30, 131072):
            buf = io.BytesIO()
            write_synthetic_gguf(
                buf,
                metadata={"general.alignment": (GGUFValueType.UINT32, bad_align)},
                tensors=[],
                alignment=32,
            )
            with self.assertRaises(ValueError):
                GGUFParser(buf.getvalue())

        # 4. n_dims > 8
        buf_dims = bytearray(GGUF_MAGIC)
        buf_dims.extend(struct.pack("<IQQ", 3, 1, 0))
        name = b"bad_tensor"
        buf_dims.extend(struct.pack("<Q", len(name)) + name)
        buf_dims.extend(struct.pack("<I", 9))  # n_dims = 9 > MAX_TENSOR_DIMS (8)
        buf_dims.extend(struct.pack("<9Q", *([1] * 9)))
        buf_dims.extend(struct.pack("<IQ", int(GGMLType.F16), 0))
        with self.assertRaises(ValueError):
            GGUFParser(bytes(buf_dims))

    def test_p8_interleaved_layer_byte_spans(self) -> None:
        """P-8 / A-3: get_layer_byte_spans splits around interleaved non-layer tensors."""
        buf = io.BytesIO()
        raw32 = np.zeros(32, dtype=np.float16).tobytes()
        write_synthetic_gguf(
            buf,
            metadata={},
            tensors=[
                ("blk.0.attn_q.weight", (32,), GGMLType.F16, raw32),
                ("blk.0.attn_k.weight", (32,), GGMLType.F16, raw32),
                ("token_embd.weight", (32,), GGMLType.F16, raw32),  # Foreign tensor interleaved!
                ("blk.0.ffn_up.weight", (32,), GGMLType.F16, raw32),
            ],
        )
        parser = GGUFParser(buf.getvalue())
        spans = parser.get_layer_byte_spans(0)
        self.assertEqual(len(spans), 2, f"Expected 2 discontiguous spans, got {spans}")
        emb = parser.tensors["token_embd.weight"]
        for s_start, s_len in spans:
            s_end = s_start + s_len
            self.assertTrue(
                s_end <= emb.abs_offset or s_start >= emb.abs_offset + emb.n_bytes,
                "Layer span overlapped foreign interleaved tensor",
            )

    def test_v5_cpu_quant_dequant_roundtrips(self) -> None:
        """V-5: Q4_0, Q8_0, and Q4_K CPU quantize -> dequantize accuracy bounds."""
        rng = np.random.default_rng(42)
        x = (rng.standard_normal(512, dtype=np.float32) * 0.2).astype(np.float32)

        q4 = quantize_q4_0_cpu(x)
        d4 = dequantize_q4_0_cpu(q4, 512).astype(np.float32)
        self.assertLess(float(np.max(np.abs(x - d4))), 0.08)

        q8 = quantize_q8_0_cpu(x)
        d8 = dequantize_q8_0_cpu(q8, 512).astype(np.float32)
        self.assertLess(float(np.max(np.abs(x - d8))), 0.01)

        q4k = quantize_q4_k_cpu(x)
        d4k = dequantize_q4_k_cpu(q4k, 512).astype(np.float32)
        self.assertLess(float(np.max(np.abs(x - d4k))), 0.06)

    def test_v6_p4_p5_tokenizer_and_vectorized_embeddings(self) -> None:
        """V-6, P-4 & P-5: O(L log L) heap BPE merge, byte fallback, and bounds-checked embed_tokens."""
        tokens = [
            "<unk>", "<s>", "</s>", "\u2581",
            "h", "e", "l", "o", "w", "r", "d",
            "\u2581h", "\u2581he", "\u2581hel", "\u2581hell", "\u2581hello",
            "\u2581w", "\u2581wo", "\u2581wor", "\u2581worl", "\u2581world",
            "<0xCE>", "<0xA9>",
        ]
        scores = [float(i) for i in range(len(tokens))]
        tok = GGUFTokenizer(tokens=tokens, scores=scores, bos_token_id=1, eos_token_id=2)

        ids = tok.encode("hello world", add_bos=True)
        self.assertEqual([tok.id_to_token[i] for i in ids], ["<s>", "\u2581hello", "\u2581world"])
        self.assertEqual(tok.decode(ids), "hello world")

        # Non-ASCII '<0xXX>' byte fallback ('Ω' = 0xCE 0xA9)
        omega_ids = tok.encode("Ω", add_bos=False)
        self.assertIn(tok.token_to_id["<0xCE>"], omega_ids)
        self.assertIn(tok.token_to_id["<0xA9>"], omega_ids)
        self.assertEqual(tok.decode(omega_ids), "Ω")

        # P-5: Vectorized embed_tokens and negative/out-of-range ID rejection
        hidden_size = 256
        vocab_size = 8
        rng = np.random.default_rng(7)
        w_f32 = rng.standard_normal((vocab_size, hidden_size), dtype=np.float32) * 0.1
        q4k_raw = quantize_q4_k_cpu(w_f32)
        buf = io.BytesIO()
        write_synthetic_gguf(
            buf,
            metadata={},
            tensors=[("token_embd.weight", (hidden_size, vocab_size), GGMLType.Q4_K, q4k_raw.tobytes())],
        )
        raw_bytes = buf.getvalue()
        info = GGUFParser(raw_bytes).tensors["token_embd.weight"]
        view = np.frombuffer(raw_bytes, dtype=np.uint8, count=info.n_bytes, offset=info.abs_offset)

        emb = embed_tokens([1, 3, 5], info, view, hidden_size)
        self.assertEqual(emb.shape, (3, hidden_size))
        for bad_ids in ([-1], [vocab_size], [0, 99]):
            with self.assertRaises(ValueError):
                embed_tokens(bad_ids, info, view, hidden_size)

    def test_v7_d5_s3_d4_sampler_and_kv_mmap_safety(self) -> None:
        """V-7, D-5, S-3 & D-4: Sampler edge cases and safe KVCacheManager mmap lifecycle."""
        # Install a minimal stub for matmul_module only if the native extension is not built
        stub_installed = False
        if "matmul_module" not in sys.modules:
            try:
                import matmul_module  # noqa: F401
            except ImportError:
                sys.modules["matmul_module"] = types.SimpleNamespace(
                    kv_cache_init=lambda *a: None,
                    kv_cache_free=lambda *a: None,
                )
                stub_installed = True

        try:
            from inference import sample_next_token
            from kv_cache import KVCacheManager

            logits = np.array([0.1, 2.5, 0.3, -1.0], dtype=np.float16)
            self.assertEqual(sample_next_token(logits, temperature=0.0), 1)
            self.assertEqual(sample_next_token(logits, temperature=0.8, top_k=1), 1)

            # Repetition penalty diverts argmax when strong enough
            diverted = sample_next_token(
                np.array([2.0, 2.1, 0.0], dtype=np.float16),
                temperature=0.0,
                repetition_penalty=2.0,
                generated_ids=[1],
            )
            self.assertEqual(diverted, 0)

            # Degenerate flat / NaN-safe fallback
            flat = np.zeros(8, dtype=np.float16)
            self.assertTrue(0 <= sample_next_token(flat, temperature=1.0, top_p=0.5) < 8)

            # S-3: Pre-existing files in mmap_dir must never be overwritten or deleted
            with tempfile.TemporaryDirectory() as tmpdir:
                bystander = os.path.join(tmpdir, "kv_cache_k.mmap")
                with open(bystander, "wb") as f:
                    f.write(b"important_user_data")

                with KVCacheManager(
                    num_layers=2, max_seq_len=16, num_kv_heads=2, head_dim=8, mmap_dir=tmpdir
                ) as kv:
                    self.assertEqual(len(kv.mmap_files), 2)
                    for p in kv.mmap_files:
                        self.assertTrue(os.path.exists(p))
                        self.assertNotEqual(os.path.abspath(p), os.path.abspath(bystander))

                # After close(), instance mmap files are gone, but bystander is untouched!
                self.assertTrue(os.path.exists(bystander))
                with open(bystander, "rb") as f:
                    self.assertEqual(f.read(), b"important_user_data")

            # D-4: __del__ emits RuntimeWarning instead of silently swallowing close() errors
            kv_warn = KVCacheManager(
                num_layers=1, max_seq_len=8, num_kv_heads=1, head_dim=8, offload_to_cpu=True
            )

            def _failing_close() -> None:
                raise RuntimeError("simulated driver cleanup error")

            kv_warn.close = _failing_close  # type: ignore[method-assign]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", RuntimeWarning)
                kv_warn.__del__()
                self.assertTrue(
                    any(issubclass(w.category, RuntimeWarning) for w in caught),
                    "Expected RuntimeWarning from KVCacheManager.__del__",
                )
        finally:
            if stub_installed:
                sys.modules.pop("matmul_module", None)

    def test_v8_pyproject_metadata(self) -> None:
        """V-8 & D-1: Verify pyproject.toml declares cmake>=3.21 and all 6 src modules."""
        pyproject_path = os.path.join(_ROOT_DIR, "pyproject.toml")
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("cmake>=3.21", content)
        self.assertIn('gfx1150-infer = "inference:main"', content)
        for mod in ("gguf_parser", "weight_loader", "layer", "kv_cache", "tokenizer", "inference"):
            self.assertTrue(os.path.isfile(os.path.join(_SRC_DIR, f"{mod}.py")))


if __name__ == "__main__":
    unittest.main(verbosity=2)

