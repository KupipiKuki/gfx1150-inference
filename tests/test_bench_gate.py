"""7F-3 benchmark-aggregation/gate tests (CPU-only; no GPU needed).

Pins the 7F-3 contract pieces:

* median/p95 summaries from a known sample;
* the gates: >= 20 measured iterations, like-for-like comparisons only,
  a stated allowed regression ratio (15%) enforced on the throughput medians
  and on the per-projection kernel-time medians.
"""

from __future__ import annotations

import os
import sys

import pytest

pytestmark = pytest.mark.cpu

_BENCH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "bench"))
if _BENCH_DIR not in sys.path:
    sys.path.insert(0, _BENCH_DIR)

from aggregate import (  # noqa: E402
    ALLOWED_REGRESSION_RATIO,
    BENCH_SCHEMA,
    MIN_ITERATIONS,
    IterationRecord,
    aggregate,
    check_regression,
    median_p95,
)


def _record(**overrides) -> IterationRecord:
    base = dict(
        prefill_tok_per_s=100.0,
        decode_tok_per_s=50.0,
        total_tok_per_s=60.0,
        wall_seconds=1.0,
        prompt_tokens=64,
        generated_tokens=16,
        per_projection_kern_ms_median={"q": 0.08, "down": 0.17},
        layer_kern_ms_median=0.8,
        layer_copy_ms_median=0.95,
        disk_read_bytes_delta=0,
        major_faults_delta=0,
    )
    base.update(overrides)
    return IterationRecord(**base)


def _payload(
    throughput_scale: float = 1.0,
    kern_scale: float = 1.0,
    gpu: str = "gfx1150",
    sha: str = "deadbeef",
    iterations: int = 20,
) -> dict:
    timings = aggregate([_record()] * 3)
    for metric in ("prefill_tok_per_s", "decode_tok_per_s", "total_tok_per_s"):
        for key in ("median", "mean", "min", "max", "p95"):
            timings[metric][key] = timings[metric][key] * throughput_scale
    for name in timings["per_projection_kern_ms_median"]:
        for key in ("median", "mean", "min", "max", "p95"):
            timings["per_projection_kern_ms_median"][name][key] = (
                timings["per_projection_kern_ms_median"][name][key] * kern_scale
            )
    return {
        "schema": BENCH_SCHEMA,
        "hardware": {"gpu": gpu},
        "model": {"sha256": sha, "config_label": "lane-1"},
        "config": {"iterations": iterations, "warmup": 2},
        "timings": timings,
    }


def test_allowed_ratio_is_stated() -> None:
    """The agreed regression ratio from the 7F-3 brief is 15% — pinned here so
    a silent change fails this test and must be re-agreed in evidence."""
    assert ALLOWED_REGRESSION_RATIO == 0.15
    assert MIN_ITERATIONS == 20


def test_median_p95_math() -> None:
    out = median_p95([1.0, 2.0, 3.0, 4.0, 5.0])
    assert out["median"] == 3.0
    assert out["min"] == 1.0 and out["max"] == 5.0
    assert out["n"] == 5.0
    assert out["min"] <= out["p95"] <= out["max"]
    assert median_p95([]) == {"n": 0.0}


def test_aggregate_shapes_and_projection_keys() -> None:
    timings = aggregate([_record(), _record()])
    assert set(timings) == {
        "prefill_tok_per_s", "decode_tok_per_s", "total_tok_per_s",
        "wall_seconds", "layer_kern_ms_median", "layer_copy_ms_median",
        "disk_read_bytes_delta", "major_faults_delta",
        "per_projection_kern_ms_median",
    }
    assert timings["decode_tok_per_s"]["n"] == 2.0
    assert set(timings["per_projection_kern_ms_median"]) == {"down", "q"}


def test_gate_passes_within_ratio() -> None:
    baseline = _payload()
    # exactly at the boundary (15% slower) must pass; the bound is > ratio.
    result = _payload(throughput_scale=1 - ALLOWED_REGRESSION_RATIO,
                      kern_scale=1 + ALLOWED_REGRESSION_RATIO)
    assert check_regression(baseline, result) == []


def test_gate_fails_on_throughput_regression() -> None:
    baseline = _payload()
    result = _payload(throughput_scale=1 - ALLOWED_REGRESSION_RATIO - 0.01)
    failures = check_regression(baseline, result)
    assert any("decode_tok_per_s" in f for f in failures), failures
    assert all("gpu mismatch" not in f for f in failures)


def test_gate_fails_on_kernel_time_regression() -> None:
    baseline = _payload()
    result = _payload(kern_scale=1 + ALLOWED_REGRESSION_RATIO + 0.02)
    failures = check_regression(baseline, result)
    assert any("per_projection_kern_ms_median" in f for f in failures)


def test_gate_refuses_cross_model_or_cross_gpu_results() -> None:
    baseline = _payload()
    assert any("model mismatch" in f for f in
               check_regression(baseline, _payload(sha="other")))
    assert any("gpu mismatch" in f for f in
               check_regression(baseline, _payload(gpu="gfx1103")))


def test_gate_refuses_underpowered_results_and_wrong_schema() -> None:
    baseline = _payload()
    assert any("below the required 20" in f for f in
               check_regression(baseline, _payload(iterations=5)))
    wrong = _payload()
    wrong["schema"] = "other/1"
    assert any("schema" in f for f in check_regression(baseline, wrong))


def test_gate_reports_missing_medi() -> None:
    baseline = _payload()
    result = _payload()
    del result["timings"]["decode_tok_per_s"]
    result["timings"]["per_projection_kern_ms_median"].pop("q")
    failures = check_regression(baseline, result)
    assert any("decode_tok_per_s" in f for f in failures)
    assert any("per_projection_kern_ms_median[q]" in f for f in failures)
