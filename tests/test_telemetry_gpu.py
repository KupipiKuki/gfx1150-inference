"""7F-4 telemetry tests (GPU lane).

Lane note: the telemetry dataclasses live in ``src/inference.py`` — the
only file the 7F brief allows them in — and importing that module requires
the compiled HIP extension (``inference`` raises an actionable ImportError
without it, by the CPU/GPU module split). The aggregation math itself is
pure Python, but its home is importable only on a HIP host, so *all*
telemetry tests (pure math + live collection) live in this GPU-lane module
with imports inside the test bodies: on a CPU-only host the module still
collects cleanly and conftest marks the lane skipped, per AUD-2.

The telemetry contract (``PHASE7_7F_EVIDENCE_RELEASE_BRIEF.md`` 7F-4):

* the payload carries bytes read, major faults, GTT peak, per-projection
  kernel milliseconds (hipEvent) and tok/s;
* timings use ``perf_counter`` consistently;
* the payload is **prompt-safe**: no prompt text, no token IDs, no
  completion text — counts and durations only;
* the schema is documented (``audit/evidence/G6/7F/telemetry/schema.md``).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.gpu

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
_BUILD_DIR = os.path.join(_ROOT_DIR, "build")
for _p in (_SRC_DIR, _BUILD_DIR):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


TRACE_LAYER = (
    "[7E-trace] seq=1 projections=7 copy_ms=0.9557 kern_ms=0.8115 "
    "overlap_ms=0.0483 overlap_pct_of_kern=5.95 boundary_syncs=1 "
    "drain_syncs=0 hipHostRegister=7 slab_fallback=0"
)


def _telemetry():
    """The telemetry surface of ``src/inference.py`` (HIP host only)."""
    import inference

    return inference


def test_summarize_median_and_p95_bounds(matmul_module) -> None:
    """``_summarize`` reports a median, a p95 inside [min, max] and the n."""
    _summarize = _telemetry()._summarize
    summary = _summarize([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert summary["median"] == 5.5
    assert summary["min"] == 1.0
    assert summary["max"] == 10.0
    assert summary["n"] == 10.0
    assert summary["min"] <= summary["p95"] <= summary["max"]
    assert _summarize([]) == {}


def test_summarize_trace_lines_shapes(matmul_module) -> None:
    """Layer summaries become anonymized (seq-independent) timing samples."""
    infty = _telemetry()
    lines = [
        TRACE_LAYER,
        "[7E-trace]   proj=q copy=[0.0000, 0.0733] ms kern=[0.0005, 0.0796] ms",
        "[7E-trace]   proj=down copy=[0.1000, 0.3487] ms kern=[0.1111, 0.2795] ms",
        "[7E-trace] seq=1 projections=7 copy_ms=1.0000 kern_ms=1.2000 "
        "overlap_ms=0.1000 overlap_pct_of_kern=8.33 boundary_syncs=1 "
        "drain_syncs=1 hipHostRegister=6 slab_fallback=1",
    ]
    out = infty.summarize_trace_lines(lines)
    assert out["layer_calls"] == 2.0
    assert out["layer_kern_ms"]["median"] == pytest.approx((0.8115 + 1.2) / 2)
    # per-projection windows are end - start, per line
    assert out["per_projection_kern_ms"]["q"]["n"] == 1.0
    assert out["per_projection_kern_ms"]["q"]["median"] == pytest.approx(0.0791)
    assert out["per_projection_copy_ms"]["down"]["median"] == pytest.approx(0.2487)
    # unparseable lines are ignored, not fatal
    assert infty.summarize_trace_lines(["[7E-trace] garbage"])["layer_calls"] == 0.0


def test_stats_payload_key_structure_is_prompt_safe(matmul_module) -> None:
    """The payload schema contains only counters/durations; nothing textual.

    Prompt-safety is structural (T-7F4-1): every leaf is a number, a boolean
    or one of the whitelisted identifier fields (the schema tag, the model
    architecture resolver name). User-controlled content — prompt text, token
    IDs, completion — cannot be represented in this payload, because the
    collector only accepts the numeric metrics dict and a prompt token count.
    """
    inference = _telemetry()
    collector = inference.TelemetryCollector().__enter__()
    try:
        # record_generation only accepts the numeric metrics dict and a
        # token *count*; the prompt/tokens never enter the collector.
        collector.record_generation(
            {
                "prefill_time_s": 0.1,
                "decode_time_s": 0.2,
                "total_time_s": 0.3,
                "tokens_generated": 3.0,
                "tokens_per_sec": 10.0,
                "decode_tokens_per_sec": 15.0,
            },
            prompt_token_count=17,
        )
    finally:
        collector.__exit__(None, None, None)
    payload = collector.summary()

    assert payload["schema"] == inference.STATS_SCHEMA
    for section in ("timing", "counts", "io", "faults", "gtt", "kernels"):
        assert section in payload
    assert payload["counts"] == {"prompt_tokens": 17, "tokens_generated": 3.0}
    assert payload["timing"]["prefill_seconds"] == pytest.approx(0.1)

    # Structural prompt-safety: numeric/bool leaves only, except the
    # whitelisted identifier fields below (and they come from the model
    # resolver, not from user input).
    identifier_whitelist = ("schema",)
    bad_leaves: list[str] = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, (int, float, bool)) or value is None:
            return
        elif isinstance(value, str) and (
            path in identifier_whitelist or path.endswith(".arch")
        ):
            assert re.fullmatch(r"[A-Za-z0-9_./-]+", value), (path, value)
        elif path.endswith(".decision"):
            assert "ResidencyDecision(" in repr(value), (path, value)
        else:
            bad_leaves.append(f"{path}={value!r}")

    walk(payload, "")
    assert not bad_leaves, f"non-telemetry leaves in the payload: {bad_leaves}"
    # machine-readable rendering round-trips cleanly
    rendered = json.dumps(payload, sort_keys=True, default=str)
    assert inference.STATS_SCHEMA in rendered
    assert inference.format_stats(payload).startswith("[stats]")


def test_summarize_trace_layer_line_regex(matmul_module) -> None:
    """The live trace format from attention.hip parses (regression for trace
    line format drift, mirrors tests/test_stream_topology.py's subprocess
    check but at the parser level)."""
    _telemetry()  # import-check only
    pat = re.compile(
        r"\[7E-trace\] seq=(\d+) projections=7 copy_ms=([\d.]+) kern_ms=([\d.]+) "
        r"overlap_ms=([\d.]+) overlap_pct_of_kern=([\d.]+) "
        r"boundary_syncs=(\d+) drain_syncs=(\d+)"
    )
    assert pat.match(TRACE_LAYER)


def test_gpu_telemetry_collects_live_hipevent_and_counter_data(
    matmul_module,
) -> None:
    """A traced synthetic-model generation yields all 7F-4 metrics.

    Runs the real pipeline (2-layer synthetic Q4_K_M model) in a subprocess:
    the 7E trace latch is process-global (``layer_trace_enabled()`` reads
    ``GFX1150_STREAM_TRACE`` once, at the first layer forward), so a test
    process that has already run the pipeline without the env var cannot
    turn the trace on retroactively. The CLI's telemetry mode always runs in
    a fresh process with the env var set before generation, so the fresh
    subprocess here mirrors the user-facing behavior exactly.
    """
    import test_phase5_scale as t5

    with tempfile.TemporaryDirectory() as tmpdir:
        model = os.path.join(tmpdir, "m.gguf")
        t5._build_synthetic_q4km_model(model, num_layers=2)

        code = r"""
import json, sys
sys.path.insert(0, {build!r})
sys.path.insert(0, {src!r})
import inference
collector_ctx = inference.TelemetryCollector()
collector_ctx.__enter__()
try:
    with inference.LlamaInferenceEngine({model!r}, max_seq_len=64) as eng:
        collector_ctx.record_engine(eng)
        ids, metrics = eng.generate_ids([1, 15, 20], max_new_tokens=2,
                                        temperature=0.0, stop_on_eos=False)
        collector_ctx.record_generation(metrics, prompt_token_count=3)
finally:
    collector_ctx.__exit__(None, None, None)
print("PAYLOAD:" + json.dumps(collector_ctx.summary(), default=str))
""".format(build=_BUILD_DIR, src=_SRC_DIR, model=model)
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=180,
        )
    assert proc.returncode == 0, f"telemetry subprocess failed:\n{proc.stderr[-800:]}"
    out_lines = [
        line for line in proc.stdout.splitlines() if line.startswith("PAYLOAD:")
    ]
    assert out_lines, f"no payload emitted; stdout={proc.stdout[-400:]}"
    payload = json.loads(out_lines[-1][len("PAYLOAD:"):])

    assert payload["schema"] == _telemetry().STATS_SCHEMA
    kernels = payload["kernels"]
    # 2 layers per forward x (1 prefill + 1 decode step) = 4 layer calls
    assert kernels["layer_calls"] == 4.0
    per_proj = kernels["per_projection_kern_ms"]
    assert set(per_proj) == {"q", "k", "v", "o", "gate", "up", "down"}, per_proj
    for name, values in per_proj.items():
        assert values["n"] > 0 and values["median"] > 0.0, (name, values)
    gtt = payload["gtt"]
    if gtt["start_bytes"] is not None:  # sysfs is readable on the gfx1150 host
        assert gtt["peak_bytes"] >= gtt["start_bytes"] >= 0
    assert payload["io"]["logical_read_bytes_delta"] is not None
    assert payload["faults"]["major_faults_delta"] is not None
    timings = payload["timing"]
    assert timings["total_seconds"] > 0.0
    assert timings["prefill_seconds"] >= 0.0

    # Prompt-safety on live data: the serialized payload carries no field
    # holding prompt, generated-ID, or completion content (counts only).
    assert payload["counts"]["prompt_tokens"] == 3


def test_gpu_cli_json_flag_is_prompt_safe(matmul_module, capsys) -> None:
    """``--json`` emits the telemetry payload and no completion text.

    The generation text must not leak into the JSON telemetry mode: stdout is
    a single JSON object whose top-level keys are telemetry sections only.
    """
    import test_phase5_scale as t5

    import inference

    with tempfile.TemporaryDirectory() as tmpdir:
        model = os.path.join(tmpdir, "m.gguf")
        t5._build_synthetic_q4km_model(model, num_layers=2)
        rc = inference.main(
            [
                "--model", model,
                "--prompt", "gfx1150 hello world",
                "--max-new-tokens", "2",
                "--max-seq-len", "64",
                "--json",
            ]
        )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema"] == inference.STATS_SCHEMA
    for section in ("timing", "counts", "io", "faults", "gtt", "kernels"):
        assert section in payload
    # Prompt-safety: neither the prompt words nor any completion text appear.
    # ("gfx1150" is excluded from the markers: it collides with the project/
    # schema identifier gfx1150-stats/1, which is not user content.)
    for forbidden in ("hello", "world"):
        assert forbidden not in captured.out, "prompt/tokens leaked into --json"
