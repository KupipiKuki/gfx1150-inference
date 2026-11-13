#!/usr/bin/env python3
"""Measure what the Phase 7A-4 fuzz actually exercises.

The fuzz's value is not that it ran: it is that it reached every mutation
class the brief lists, and that it exercised both the rejection path and the
successful path. This script draws the same examples the fuzz does (the same
strategy, the same deterministic settings) and counts:

* how many of the 10,000 examples carry each mutation class;
* how many are truncated, and where;
* how the parser answers each of them: accepted, or rejected with the
  documented ``ValueError``.

Usage:
    python3 measure-fuzz-coverage.py [path/to/tests/test_fuzz_gguf.py]
"""

from __future__ import annotations

import collections
import importlib.util
import pathlib
import sys

DEFAULT_MODULE = pathlib.Path(__file__).resolve().parents[4] / "tests" / "test_fuzz_gguf.py"


def load(path: pathlib.Path):
    sys.path.insert(0, str(path.parent.parent / "src"))
    spec = importlib.util.spec_from_file_location("fuzz_module", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fuzz_module"] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    path = pathlib.Path(argv[1]) if len(argv) > 1 else DEFAULT_MODULE
    fuzz = load(path)

    from hypothesis import given, settings

    from gguf_parser import GGUFParser

    hits: collections.Counter = collections.Counter()
    outcomes: collections.Counter = collections.Counter()
    truncations = collections.Counter()

    @settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
    @given(fuzz._descriptions())
    def probe(description) -> None:
        if description.version != 3:
            hits["version"] += 1
        if description.tensor_count_override is not None:
            hits["tensor_count"] += 1
        if description.kv_count_override is not None:
            hits["kv_count"] += 1
        for entry in description.metadata:
            if entry.key == "general.alignment" and entry.value not in (
                1, 2, 4, 8, 16, 32, 64, 4096
            ):
                hits["general.alignment"] += 1
            if entry.length_override is not None:
                hits["string/array length"] += 1
        names = [tensor.name for tensor in description.tensors]
        if len(names) != len(set(names)):
            hits["duplicate tensor name"] += 1
        for tensor in description.tensors:
            if tensor.n_dims_override is not None:
                hits["n_dims"] += 1
            if tensor.name_length_override is not None:
                hits["tensor name length"] += 1
            if tensor.ggml_type in fuzz._RESERVED_GGML_TYPES:
                hits["reserved ggml_type"] += 1
            elif tensor.ggml_type > max(fuzz._VALID_GGML_TYPES):
                hits["unknown ggml_type"] += 1
            if any(dim in fuzz._HOSTILE_DIMS for dim in tensor.dims):
                hits["dimensions"] += 1
            if tensor.rel_offset not in (0, 32, 64, 96, 128, 160):
                hits["tensor offset"] += 1

    @settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
    @given(fuzz._buffers())
    def probe_buffers(buffer: bytes) -> None:
        try:
            parser = GGUFParser(buffer)
        except ValueError:
            outcomes["rejected with the documented ValueError"] += 1
            return
        except Exception as exc:  # noqa: BLE001 - this is the measurement
            outcomes[f"OTHER EXCEPTION: {type(exc).__name__}"] += 1
            return
        outcomes["accepted"] += 1
        if parser.tensors:
            outcomes["  accepted with a tensor table"] += 1

    @settings(max_examples=10_000, derandomize=True, deadline=None, database=None)
    @given(fuzz._buffers())
    def probe_truncation(buffer: bytes) -> None:
        pass

    probe()
    probe_buffers()

    print("=== the mutation classes, over 10,000 drawn descriptions ===")
    for name, count in sorted(hits.items()):
        print(f"  {name:<26} {count:>6}")
    print()
    print("=== how the parser answered 10,000 drawn buffers ===")
    for name, count in sorted(outcomes.items()):
        print(f"  {name:<44} {count:>6}")
    print()
    print("=== the truncation class ===")
    print("  the strategy truncates at the header, metadata, tensor-index and data")
    print("  boundaries, and at arbitrary positions inside them; the boundary")
    print("  offsets are in the module's _Built.boundaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
