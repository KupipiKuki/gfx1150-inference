"""Pure aggregation helpers for the gfx1150 benchmark harness (7F-3).

This module is importable without the HIP extension (no ``src`` imports): the
CPU CI lane unit-tests the aggregation and the regression gate directly.
``scripts/bench/run.py`` uses it on the GPU host.

Conventions
-----------

* Per-iteration samples are collected as ``IterationRecord`` (one measured
  generation). The aggregation produces median/p95/min/max/n summaries per
  metric across the measured iterations (warm-up excluded).
* The regression gate compares a result file against a checked-in baseline
  file. Like-for-like only: same schema, same GPU name, same model identity
  (sha256). The allowed regression ratio is a single documented constant
  (``ALLOWED_REGRESSION_RATIO``).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

BENCH_SCHEMA = "gfx1150-bench/1"

#: Agreed regression ratio (7F-3): a result fails the gate when the median of
#: either throughput metric drops more than 15% below the baseline, or when a
#: per-projection kernel median rises more than 15% above it. Justification:
#: on this shared-memory APU host, run-to-run variance comes from page-cache
#: residency (first-run disk faults vs warm), GTT pressure from the desktop,
#: and thermal/power limits; the measured rerun variance recorded in
#: ``audit/evidence/G6/7F/bench/`` stays well inside 15% for the medians,
#: while a real regression (a broken kernel path, an added sync, an eviction
#: bug) moves medians far beyond it.
ALLOWED_REGRESSION_RATIO = 0.15

#: Minimum number of measured iterations the brief requires (>= 20).
MIN_ITERATIONS = 20

#: Metrics that may not regress by more than ``ALLOWED_REGRESSION_RATIO``.
#: Higher is better.
THROUGHPUT_METRICS = ("prefill_tok_per_s", "decode_tok_per_s", "total_tok_per_s")


def median_p95(values: Sequence[float]) -> Dict[str, float]:
    """Median/p95/min/max/n summary of a numeric sample (p95 in-sample)."""
    sample = sorted(float(v) for v in values)
    if not sample:
        return {"n": 0.0}
    p95_index = max(0, min(len(sample) - 1, int(round(0.95 * (len(sample) + 1))) - 1))
    return {
        "median": statistics.median(sample),
        "mean": statistics.fmean(sample),
        "min": sample[0],
        "max": sample[-1],
        "p95": sample[p95_index],
        "n": float(len(sample)),
    }


@dataclass
class IterationRecord:
    """One measured generation (warm-up iterations are never recorded)."""

    prefill_tok_per_s: float
    decode_tok_per_s: float
    total_tok_per_s: float
    wall_seconds: float
    prompt_tokens: int
    generated_tokens: int
    per_projection_kern_ms_median: Dict[str, float] = field(default_factory=dict)
    layer_kern_ms_median: float = 0.0
    layer_copy_ms_median: float = 0.0
    disk_read_bytes_delta: int = 0
    major_faults_delta: int = 0


def aggregate(records: Sequence[IterationRecord]) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Aggregate the per-iteration records into the bench payload's
    ``timings`` section: a summary per throughput metric and a per-projection
    kernel summary (the metric per iteration is that iteration's median)."""
    timings: Dict[str, Dict[str, Dict[str, float]]] = {}
    for metric in THROUGHPUT_METRICS:
        values = [float(getattr(record, metric)) for record in records]
        timings[metric] = median_p95(values)
    timings["wall_seconds"] = median_p95([r.wall_seconds for r in records])
    timings["layer_kern_ms_median"] = median_p95([r.layer_kern_ms_median for r in records])
    timings["layer_copy_ms_median"] = median_p95([r.layer_copy_ms_median for r in records])
    timings["disk_read_bytes_delta"] = median_p95([r.disk_read_bytes_delta for r in records])
    timings["major_faults_delta"] = median_p95([r.major_faults_delta for r in records])
    projection_names = (
        set().union(*(r.per_projection_kern_ms_median.keys() for r in records))
        if records
        else set()
    )
    per_projection: Dict[str, Dict[str, Dict[str, float]]] = {}
    for name in sorted(projection_names):
        values = [
            r.per_projection_kern_ms_median[name]
            for r in records
            if name in r.per_projection_kern_ms_median
        ]
        per_projection[name] = median_p95(values)
    timings["per_projection_kern_ms_median"] = per_projection
    return timings


def check_regression(
    baseline: Dict[str, object],
    result: Dict[str, object],
    ratio: float = ALLOWED_REGRESSION_RATIO,
    min_iterations: int = MIN_ITERATIONS,
) -> List[str]:
    """Compare a bench result against the baseline; return failure reasons.

    An empty list means the gate passes. The gate refuses to compare results
    measured on a different GPU or model, and refuses results with fewer than
    ``min_iterations`` measured iterations (the reproducibility requirement).
    """
    failures: List[str] = []
    for payload, label in ((baseline, "baseline"), (result, "result")):
        if payload.get("schema") != BENCH_SCHEMA:
            failures.append(f"{label}: schema is not {BENCH_SCHEMA!r}")
            return failures
        config = dict(payload.get("config", {}))
        if int(config.get("iterations", 0)) < min_iterations:
            failures.append(
                f"{label}: {config.get('iterations')} measured iterations "
                f"is below the required {min_iterations}"
            )

    base_hw = dict(baseline.get("hardware", {}))
    res_hw = dict(result.get("hardware", {}))
    if base_hw.get("gpu") != res_hw.get("gpu"):
        failures.append(
            f"gpu mismatch: baseline {base_hw.get('gpu')!r} vs result "
            f"{res_hw.get('gpu')!r} (the gate compares like-for-like only)"
        )
    base_model = dict(baseline.get("model", {}))
    res_model = dict(result.get("model", {}))
    if base_model.get("sha256") != res_model.get("sha256"):
        failures.append(
            f"model mismatch: baseline sha256 {base_model.get('sha256')!r} vs "
            f"result {res_model.get('sha256')!r}"
        )
    if base_model.get("config_label") != res_model.get("config_label"):
        failures.append(
            "workload label mismatch: "
            f"{base_model.get('config_label')!r} vs {res_model.get('config_label')!r}"
        )
    if failures:
        return failures

    base_timings = dict(baseline.get("timings", {}))
    res_timings = dict(result.get("timings", {}))
    for metric in THROUGHPUT_METRICS:
        base_value = dict(base_timings.get(metric, {})).get("median")
        res_value = dict(res_timings.get(metric, {})).get("median")
        if base_value is None or res_value is None:
            failures.append(f"{metric}: missing median (baseline={base_value}, result={res_value})")
            continue
        floor = float(base_value) * (1.0 - ratio)
        if float(res_value) < floor:
            failures.append(
                f"{metric}: median regressed {res_value:.2f} < "
                f"baseline {base_value:.2f} by more than {ratio:.0%} "
                f"(floor {floor:.2f})"
            )
    base_proj = dict(base_timings.get("per_projection_kern_ms_median", {}))
    res_proj = dict(res_timings.get("per_projection_kern_ms_median", {}))
    for name, base_summary in base_proj.items():
        base_value = dict(base_summary).get("median")
        res_value = dict(res_proj.get(name, {})).get("median")
        if base_value is None or res_value is None:
            failures.append(
                f"per_projection_kern_ms_median[{name}]: missing median "
                f"(baseline={base_value}, result={res_value})"
            )
            continue
        ceiling = float(base_value) * (1.0 + ratio)
        if float(res_value) > ceiling:
            failures.append(
                f"per_projection_kern_ms_median[{name}]: median rose "
                f"{res_value:.4f} > baseline {base_value:.4f} by more than "
                f"{ratio:.0%} (ceiling {ceiling:.4f})"
            )
    return failures
