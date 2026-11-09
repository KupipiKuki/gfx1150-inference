# 7F-4 telemetry — `--stats` / `--json` schema `gfx1150-stats/1`

Source: `src/inference.py` (Phase 7F-4). The CLI flags:

* `--stats` — prints a human-readable `[stats]` block to **stderr** in
  addition to the normal completion on stdout.
* `--json` — prints exactly one JSON object (the payload below) to
  **stdout** *instead of* the completion text. The generation itself is
  unchanged; only the output mode differs.

Decisions that shape the schema (and why):

* **Prompt-safety is structural.** The `TelemetryCollector` only receives
  the numeric metrics dict and a prompt *token count*
  (`record_generation`); it never sees the prompt, token IDs, or the
  completion. Every payload leaf is a number/boolean, except the
  whitelisted identifiers (`schema`, `model.arch` from the model resolver,
  `residency.decision` from the 7D policy enum). `tests/test_telemetry.py`
  enforces this by walking the payload and asserting leaf types; the GPU
  test additionally asserts the live prompt words never appear in the
  serialized payload.
* **`GFX1150_STREAM_TRACE=1` is enabled by telemetry**, so per-projection
  kernel times are `hipEventElapsedTime` values from the 7E trace
  (`src/kernels/attention.hip`), captured by redirecting fd 2 through a
  pipe (`_StderrTap`) that re-emits every line on the real stderr and
  records `[7E-trace]` lines. `trace_enabled` records this: the
  (periodic, per-layer-bounded) trace overhead is included in the timing
  sections, which is why the benchmark harness — which measures the same
  way — is the consistent reference for kernel times (7F-3).
* **Counters** use Linux `/proc/self/io` (`read_bytes` = bytes the kernel
  actually fetched from storage, `rchar` = logical reads including
  page-cache hits; a warm/pinned model measures 0 disk bytes), `getrusage`
  (`ru_majflt`/`ru_minflt` deltas), and AMDGPU sysfs
  `mem_info_gtt_used` sampled every 50 ms by a daemon thread
  (`_GttMonitor`; sysfs reads only — no GPU/runtime calls, so the
  single-engine workspace guard is untouched).

## Payload

| Path | Type | Meaning |
|---|---|---|
| `schema` | str | `gfx1150-stats/1` |
| `wall_seconds` | float | `perf_counter` seconds of the whole collected run (engine construction + generation) |
| `trace_enabled` | bool | true when `[7E-trace]` lines were captured (`GFX1150_STREAM_TRACE`) |
| `trace_lines_parsed` | int | number of `[7E-trace]` layer summaries parsed |
| `timing.prefill_seconds` | float | `perf_counter` prefill wall time (`generate_ids` metrics) |
| `timing.decode_seconds` | float | decode wall time |
| `timing.total_seconds` | float | generation total |
| `timing.tokens_per_sec` / `decode_tokens_per_sec` | float | generation throughput (unchanged 7A metrics) |
| `counts.prompt_tokens` | int | prompt token **count** (never the IDs) |
| `counts.tokens_generated` | float | tokens generated |
| `io.disk_read_bytes_delta` | int | `/proc/self/io read_bytes` delta across the run |
| `io.logical_read_bytes_delta` | int | `rchar` delta |
| `faults.major_faults_delta` / `minor_faults_delta` | int | `getrusage` deltas |
| `gtt.start_bytes` / `peak_bytes` / `end_bytes` | int | sysfs `mem_info_gtt_used` (null when unreadable) |
| `gtt.samples` | int | number of samples taken (~50 ms interval) |
| `kernels.layer_calls` | number | traced `forward_layer_cached` invocations |
| `kernels.layer_kern_ms`/`layer_copy_ms`/`layer_overlap_ms` | summary | median/mean/min/max/p95/n summarize of the per-layer hipEvent totals |
| `kernels.per_projection_kern_ms` / `per_projection_copy_ms` | `{q,k,v,o,gate,up,down → summary}` | per-projection hipEvent kernel/copy windows |
| `model.arch` / `num_layers` / `hidden_size` / `vocab_size` | ident/int | model identity (resolver-sourced; no user data) |
| `residency.decision` | enum repr | the 7D `ResidencyDecision` recorded on the engine |
| `residency.weight_bytes` / `kv_device_bytes` / `max_seq_len` | int | context sizes |

`summary` objects are `{median, mean, min, max, p95, n}`.

## Reproducing

```bash
PYTHONPATH=build:src python3 src/inference.py \
    --model tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf \
    --prompt "The quick brown fox jumps over the lazy dog. Careful checks before release." \
    --max-new-tokens 8 --stats        # human-readable block on stderr
# same command with --json for the machine form (run twice and compare)
```

## Measured variance and prompt-leak check (this bundle)

* `sample-json-run1.json` vs `sample-json-run2.json`: decode tok/s 17.24 →
  16.80 (**−2.5%**), prefill 0.207 s → 0.220 s (6% of a ~0.2 s interval):
  telemetry timing fields reproduce within ~±6% on this host for short
  runs (the 7F-3 harness establishes the long-run medians).
* Leak check: prompt words ("quick", "brown", "fox", "lazy", "release",
  "The quick") are absent from both serialized payloads and from the
  `--stats` stderr block except the trace lines (which are timings only).
* `tests/test_telemetry.py` (4 CPU + 2 GPU tests) covers the aggregation
  math, payload structure, live hipEvent capture, and the CLI `--json`
  prompt-safety.
