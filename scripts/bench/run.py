#!/usr/bin/env python3
"""gfx1150 benchmark harness (7F-3): reproducible perf evidence on gfx1150.

Produces a ``gfx1150-bench/1`` JSON payload on stdout: fixed prompt,
``temperature=0``, deterministic (greedy) generation so every iteration runs
the same workload, ``--iterations`` measured iterations after ``--warmup``
warm-up iterations (default 20/2 — the brief requires >= 20 measured), and
per-iteration samples aggregated into median/p95 summaries.

Timing model
------------

* End-to-end prefill/decode wall times use ``time.per_counter`` inside
  ``LlamaInferenceEngine.generate_ids`` (unchanged in 7F).
* Per-projection GPU kernel times come from the 7E hipEvent trace
  (``GFX1150_STREAM_TRACE=1``: ``hipEventElapsedTime`` around each weight
  projection's kernel inside ``forward_layer_cached``); the harness reuses the
  7F-4 ``TelemetryCollector`` to capture its own stderr and parse the
  ``[7E-trace]`` lines. Kernel timings therefore use the same hipEvent source
  as the telemetry, so the two are consistent by construction.
* GTT / disk / fault counters are sampled per iteration for context only
  (they are recorded, never gated on).

Models
------

* ``--model synthetic`` builds the deterministic synthetic Q4_K_M fixture
  (``tests/test_phase5_scale._build_synthetic_q4km_model``) — fully
  reproducible from a clean clone with no model acquisition; measures the
  real GPU pipeline.
* ``--model /path/to.gguf`` measures the documented real-gen path on a real
  GGUF. The 7B-class real lane is what the docs describe; the file is NOT
  committed — the payload records its sha256 and the acquisition command
  (7F-2 ``audit/evidence/G6/7F/golden/README.md``).

Usage::

    python scripts/bench/run.py --model synthetic --json > synth.json
    python scripts/bench/run.py --model /path/model.gguf --json > real.json
    python scripts/bench/regress.py baseline.json real.json   # gate (exit 1)

Exit codes: ``0`` success, ``2`` harness error. A payload with fewer than 20
measured iterations is still produced (with ``config.iterations`` truthful)
but the gate will refuse it.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))
sys.path.insert(0, os.path.join(_REPO_ROOT, "build"))
sys.path.insert(0, os.path.join(_REPO_ROOT, "tests"))
sys.path.insert(0, os.path.join(_REPO_ROOT, "scripts", "bench"))

from aggregate import (  # noqa: E402
    BENCH_SCHEMA,
    MIN_ITERATIONS,
    IterationRecord,
    aggregate,
)

#: Fixed real-model benchmark prompt (committed on purpose: the workload has
#: to be identical across releases; ~60 tokens of plain text, no secrets).
BENCH_PROMPT = (
    "The quick brown fox jumps over the lazy dog. Careful fact-checking and "
    "patient research require reading every claim, weighing the evidence, and "
    "recording what the sources actually say. In a world where automated "
    "assistants summarize knowledge, the reader who checks the originals "
    "still decides what is true. The engine below verifies each sentence."
)

#: Deterministic synthetic-lane prompt token IDs (synthetic fixture vocab,
#: ids 3..30 cover the printable pieces; fixed for reproducibility).
SYNTHETIC_PROMPT_IDS = [(3 + (i % 28)) for i in range(64)]


def _sha256_file(path: str, chunk: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def collect_environment() -> Dict[str, object]:
    """Hardware/software identity for the payload (gfx1150 host)."""
    gpu = None
    try:
        proc = subprocess.run(
            ["rocminfo"], capture_output=True, text=True, timeout=30
        )
        for line in proc.stdout.splitlines():
            s = line.strip()
            if s.startswith("Marketing Name:") and gpu is None:
                gpu = s.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        gpu = None
    gcn = None
    for base in sorted(glob.glob("/sys/class/drm/card*/device")):
        try:
            with open(os.path.join(base, "gfx_target_version"), "r") as fh:
                gcn = fh.read().strip()
        except OSError:
            continue
    rocm_version = None
    for candidate in (
        "/opt/rocm/.info/version",
        "/opt/rocm-core/.info/version",
    ):
        try:
            with open(candidate, "r") as fh:
                rocm_version = fh.read().strip()
                if rocm_version:
                    break
        except OSError:
            continue
    hip_version = None
    try:
        proc = subprocess.run(
            ["hipconfig", "--version"], capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            hip_version = proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if hip_version:
        rocm_version = rocm_version or f"hip {hip_version}"
    import numpy

    return {
        "gpu": gcn if gcn else gpu,
        "gpu_marketing": gpu,
        "gfx_target_version": gcn,
        "rocm": rocm_version,
        "hip": hip_version,
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "kernel": platform.release(),
        "machine": platform.machine(),
    }


def _quant_mix(engine) -> Dict[str, int]:
    """Tensor-type histogram of the loaded model (identity, not content)."""
    from gguf_parser import GGMLType

    counts: Dict[str, int] = {}
    for info in engine.streamer.gguf.tensors.values():
        try:
            name = GGMLType(info.ggml_type).name
        except Exception:
            name = str(info.ggml_type)
        counts[name] = counts.get(name, 0) + 1
    return counts


def run_bench(
    model_label: str,
    model_path: str,
    iterations: int,
    warmup: int,
    max_new_tokens: int,
    max_seq_len: int,
) -> Dict[str, object]:
    """Execute the benchmark and return the payload dict."""
    import inference
    import test_phase5_scale as t5

    synthetic = model_label == "synthetic"
    collector_cls = inference.TelemetryCollector

    records: List[IterationRecord] = []

    with tempfile.TemporaryDirectory(prefix="gfx1150-bench-") as tmpdir:
        if synthetic:
            model_path = os.path.join(tmpdir, "m.gguf")
            t5._build_synthetic_q4km_model(model_path, num_layers=2)
        engine_cm = inference.LlamaInferenceEngine(
            model_path=model_path,
            max_seq_len=max_seq_len,
            max_kv_bytes=None,
        )
        with engine_cm as engine:
            model_sha = None if synthetic else _sha256_file(model_path)
            weight_bytes = engine.streamer.weight_bytes
            quant_mix = _quant_mix(engine)
            arch = engine.spec.arch
            num_layers = engine.num_layers
            hidden_size = engine.spec.hidden_size
            vocab_size = engine.vocab_size
            if synthetic:
                prompt_ids = list(SYNTHETIC_PROMPT_IDS)
            else:
                prompt_ids = engine.tokenizer.encode(BENCH_PROMPT)
            prompt_len = len(prompt_ids)
            prompt_fixture = list(SYNTHETIC_PROMPT_IDS) if synthetic else BENCH_PROMPT
            for index in range(warmup + iterations):
                collector = collector_cls().__enter__()
                try:
                    ids, metrics = engine.generate_ids(
                        prompt_ids=prompt_ids,
                        max_new_tokens=max_new_tokens,
                        temperature=0.0,
                        stop_on_eos=False,
                        seed=42,
                    )
                finally:
                    collector.record_generation(
                        metrics, prompt_token_count=len(prompt_ids)
                    )
                    collector.__exit__(None, None, None)
                if index < warmup:
                    continue
                summary = collector.summary()
                prefill_s = float(summary["timing"]["prefill_seconds"])
                decode_s = float(summary["timing"]["decode_seconds"])
                kern = dict(summary["kernels"])
                per_proj = {
                    name: float(dict(vals)["median"])
                    for name, vals in dict(kern["per_projection_kern_ms"]).items()
                    if vals
                }
                records.append(
                    IterationRecord(
                        prefill_tok_per_s=len(prompt_ids) / max(prefill_s, 1e-9),
                        decode_tok_per_s=metrics["decode_tokens_per_sec"],
                        total_tok_per_s=metrics["tokens_per_sec"],
                        wall_seconds=float(summary["wall_seconds"]),
                        prompt_tokens=len(prompt_ids),
                        generated_tokens=max_new_tokens,
                        per_projection_kern_ms_median=per_proj,
                        layer_kern_ms_median=float(
                            dict(kern.get("layer_kern_ms", {})).get("median", 0.0)
                        ),
                        layer_copy_ms_median=float(
                            dict(kern.get("layer_copy_ms", {})).get("median", 0.0)
                        ),
                        disk_read_bytes_delta=int(
                            (summary.get("io") or {}).get("disk_read_bytes_delta") or 0
                        ),
                        major_faults_delta=int(
                            (summary.get("faults") or {}).get("major_faults_delta") or 0
                        ),
                    )
                )

    payload: Dict[str, object] = {
        "schema": BENCH_SCHEMA,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "hardware": collect_environment(),
        "model": {
            "config_label": model_label,
            "path": None if synthetic else model_path,
            "sha256": model_sha,
            "weight_bytes": weight_bytes,
            "quant_mix": quant_mix,
            "arch": arch,
            "num_layers": num_layers,
            "hidden_size": hidden_size,
            "vocab_size": vocab_size,
        },
        "workload": {
            # prompts are committed fixtures: BENCH_PROMPT (real lane) or
            # SYNTHETIC_PROMPT_IDS (synthetic lane), both in scripts/bench/run.py;
            # the payload records the digest + token count for drift detection.
            "prompt_tokens": prompt_len,
            "prompt_sha256": hashlib.sha256(
                json.dumps(prompt_fixture).encode("utf-8")
            ).hexdigest(),
            "prompt_is_synthetic_ids": synthetic,
            "max_new_tokens": max_new_tokens,
            "temperature": 0.0,
            "seed": 42,
            "stop_on_eos": False,
        },
        "config": {
            "iterations": len(records),
            "warmup": warmup,
            "min_iterations_required": MIN_ITERATIONS,
            "max_seq_len": max_seq_len,
            "residency": "auto",
        },
        "timings": aggregate(records),
    }
    if synthetic:
        payload["workload"]["prompt_ids"] = SYNTHETIC_PROMPT_IDS
    else:
        payload["workload"]["prompt"] = BENCH_PROMPT
    return payload


def _git_sha() -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model",
        required=True,
        help="'synthetic' or a path to a real .gguf file",
    )
    parser.add_argument("--iterations", type=int, default=20,
                        help="measured iterations (>= 20 for the gate)")
    parser.add_argument("--warmup", type=int, default=2,
                        help="warm-up iterations before measuring")
    parser.add_argument("--prompt-tokens", type=int, default=64,
                        help="target prompt length in tokens (synthetic lane)")
    parser.add_argument("--max-new-tokens", type=int, default=16,
                        help="decode tokens per iteration (stop_on_eos=False)")
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--json", action="store_true",
                        help="write the payload JSON to stdout")
    args = parser.parse_args(argv)

    if args.iterations < MIN_ITERATIONS:
        print(
            f"refusing to run: {args.iterations} measured iterations is below "
            f"the required {MIN_ITERATIONS} (use --iterations {MIN_ITERATIONS})",
            file=sys.stderr,
        )
        return 2

    global SYNTHETIC_PROMPT_IDS
    SYNTHETIC_PROMPT_IDS = [(3 + (i % 28)) for i in range(args.prompt_tokens)]

    label = "synthetic" if args.model == "synthetic" else os.path.basename(args.model)
    payload = run_bench(
        model_label="synthetic" if args.model == "synthetic" else label,
        model_path=args.model,
        iterations=args.iterations,
        warmup=args.warmup,
        max_new_tokens=args.max_new_tokens,
        max_seq_len=args.max_seq_len,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
