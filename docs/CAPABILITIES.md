# Measured capability figures — gfx1150-inference

> **What this document is.** A plain statement of what this engine can
> actually do, measured on one specific host, with the conditions attached.
> Every number below was measured on **2026-11-13** on the host described in
> §1; none of it is a guarantee, a specification, or a cross-hardware claim.
> The authoritative claim record is [`audit/CLAIMS_LEDGER.md`](../audit/CLAIMS_LEDGER.md)
> and the machine-checked gate is `scripts/qa/check_claims.py --strict`.

**Measured capability figures** are the numbers in this file.

---

## 1. The measurement host

| | |
|---|---|
| CPU / iGPU | AMD Ryzen AI 9 HX 370 (Radeon 890M, `gfx1150`) |
| Memory | 91.94 GiB total, 89.46 GiB `MemAvailable` at measurement time |
| Device-visible share (GTT) | 45.92 GiB free |
| ROCm / HIP | 7.16.26385-0000000, kernel 7.0.0-42 |
| Python / NumPy | 3.14.10 / 2.5.4 |
| Toolchain | `cmake` 3.28.3, `hipcc` (HIP 7.16) |

A unified-memory APU: **there is no discrete VRAM.** Host RAM and the device
share one physical pool, and the device-visible share is roughly half of it.

## 2. What it runs

| Model class | Status | Evidence |
|---|---|---|
| llama-family **dense** `Q4_0` / `Q4_K` / `Q8_0` | kernel paths hardware-verified on synthetic GGUFs | `audit/evidence/G0/7.0-baseline/gpu-suite.log` |
| llama-family `Q4_K_M` (Q4_K+Q6_K mix) / `Q6_K` | kernels verified; **real** GGUF runs exist; **no exact golden** (strict 16-step FAIL recorded on every run; the 7G-C re-adjudication records decisive-margin comparisons passing on four of five prompts — Q6_K, both original Q4_K_M prompt 1 and two new forced-completion prompts — and one Q4_K_M prompt staying INCONCLUSIVE, 1 decisive step < the pre-registered minimum of 2) | `audit/evidence/G6/7F/golden/`, `audit/evidence/G7/7G-C/golden/` |
| `phi3` / `gemma` | **synthetic-fixture verified only** — no real GGUF ever run | `audit/evidence/G3/7C/` |
| `qwen2` | **metadata/bias regression target only** — not a support claim | `audit/evidence/G3/7C/` |
| Chat templates | **not** verified end-to-end for any family | — |
| MoE / expert models | **not supported** — no routing, no grouped GEMM | — |

Tokenizer: reference-faithful SentencePiece (score-priority greedy merge) and
byte-level BPE, verified against llama.cpp reference goldens and a 310-case
differential corpus (`audit/evidence/G2/7B/`).

## 3. Measured throughput and footprint

Single-host measurements, `temperature=0`, greedy, `≥8` decode steps unless
noted. Full telemetry for each run is reproducible with
`python src/inference.py … --stats --json` (schema `gfx1150-stats/1`).

### 3.1 Small model, warm cache — the fast lane

TinyLlama-1.1B-Chat `Q4_K_M` (667 MB weights, 22 layers, hidden 2048):

| Metric | Value |
|---|---|
| decode | **16.35 tok/s** |
| SSD bytes read during the run | 786 KB (model already cached) |
| major faults | 6 |
| device (GTT) peak | 331 MB |
| KV on device | 46 MB |
| layer kernel / copy / overlap (median) | 0.88 / 0.98 / 0.06 ms |

### 3.2 7B class, resident vs streamed — the residency trade-off

Mistral-7B-Instruct-v0.2 `Q4_K_M` (4.37 GB weights, 32 layers, hidden 4096),
16 decode tokens:

| Residency | decode tok/s | SSD bytes read | major faults | layer kern / copy / **overlap** (ms) |
|---|---|---|---|---|
| `auto` → page-cache pinned | **2.63** | 4.19 GB (one cold load) | 31,971 | 3.71 / 4.44 / 0.29 |
| `--residency stream` (evict per layer) | **0.42** | **62.8 GB** | 479,790 | 3.76 / 5.34 / **0.000** |

Streamed mode re-reads the **whole model per token** (≈3.93 GB/token) and is
copy-bound: the layer copy (5.34 ms) exceeds the kernel time (3.76 ms) with
**no** copy/compute overlap. Per-projection kernel medians (pinned):
down 0.79, gate 0.80, up 0.80, q 0.47, o 0.46, k 0.07, v 0.08 ms.

### 3.3 Long-context research profile

Mistral-7B (32K native context), a 9,121-token prompt, 8 decode steps:

| Configuration | prefill | decode | device (GTT) peak | KV on device | process max RSS |
|---|---|---|---|---|---|
| 16K context, device KV | 728.7 s (**12.5 tok/s**) | 0.736 tok/s | 3.94 GB | 2.15 GB | 4.3 GiB |
| 32K context, `--offload-kv-cpu` | 649.9 s (**14.0 tok/s**) | 0.86 tok/s | 2.30 GB | **0 bytes** | 6.8 GiB |

This is the profile the project is built for: **long prompts, long contexts,
hours of wall-clock, no interactivity requirement.** The KV cache refuses
allocations it cannot back (a 4.29 GB request against a 3 GiB cap is rejected
with an explicit error, not an OOM). Since 7G-C (C6), the offloaded-pool
budget is bounded by host RAM (and free disk for the mmap pool) rather than
the GTT share, so this profile works on hosts with a small device slice; the
32K-context `--offload-kv-cpu` acceptance run is recorded in
`audit/evidence/G7/7G-C/c6-kv-budget.log`.

## 4. Two execution paths — know which one you get

The optimized C++ **device-resident pipeline** (7E: explicit copy/compute
streams, per-projection `hipEvent` timings, copy/compute overlap) runs **only**
when *all* hold:

- the KV cache is **device-resident** (`--offload-kv-cpu` / `--kv-mmap-dir`
  disable it), **and**
- the layout is plain llama-family: separate Q/K/V weights, **no** attention
  biases, separate SwiGLU gate/up (fused-QKV `phi3` and fused gate/up `gemma`
  fall back to the Python path too).

On the Python spec-driven path there are **no per-layer or per-projection
timings** in the telemetry (`trace_lines_parsed: 0`) — the `[7E-trace]` lines
come from the HIP attention path. Choose `--offload-kv-cpu` for long contexts
on a small device share and accept that trade-off; it is documented, not
hidden.

## 5. Controls that shape memory behaviour

| Control | Effect | Notes |
|---|---|---|
| `--residency {auto,pin,stream}` | whole model pinned in the host page cache, or evicted per layer | **all-or-nothing**; there is no partial cap today |
| `--residency-budget-mb` | overrides the *computed* weight budget | absolute MB only; flips AUTO between pin/stream |
| `--max-kv-bytes` | hard cap on the KV cache | the 10% safety margin is applied on top |
| `--offload-kv-cpu` | KV lives in host RAM, **0 device bytes** | runs the Python path (§4); its allocation budget is **host RAM** (`MemAvailable`, cgroup), not the GTT share (7G-C/C6) |
| `--kv-mmap-dir` | KV is a disk-backed mmap, unlinked immediately | disk-backed; frees device memory; budget is host RAM **and** free disk space, with explicit refusals naming the shortfall (7G-C/C6) |
| `--prompt-file PATH` / `--prompt -` | read the prompt from a UTF-8 file or stdin (mutually exclusive with `--prompt`) | 7G-C/C5: multi-KB research prompts; clean one-line errors (exit 2) on missing/empty/directory/non-UTF-8; prompt content never enters the telemetry payload |
| `--prefill-chunk-size` | chunked prefill | long-prompt path |

Budget sources (7D): GTT free, host `MemAvailable`, cgroup v2/v1 — intersected,
minus KV/activation estimates and a 512 MiB margin. On this host the
**GTT share (~45.9 GiB) is the binding term**, so the effective weight budget
is ~45.1 GiB even though 89.5 GiB of RAM is available.

## 6. Telemetry surface (`gfx1150-stats/1`)

`--stats` (human-readable, stderr) / `--json` (payload, stdout). Prompt-safe by
construction: no prompt text, token IDs, or completion ever appears in the
payload.

| Section | Fields |
|---|---|
| `timing` | prefill/decode/total seconds, tok/s, decode tok/s |
| `io` | SSD bytes read, logical bytes read |
| `faults` | major (disk re-faults) and minor faults |
| `gtt` | start / peak / end device bytes + sample count |
| `kernels` | per-projection and per-layer kernel/copy/overlap ms (median/mean/min/max/p95), `layer_calls` |
| `counts`, `model`, `residency` | token counts, arch/layers/hidden/vocab, residency decision + budget + weight/KV bytes |

## 7. What it does **not** do

- No MoE / expert routing, no grouped GEMM, no expert cache.
- No CPU-side compute: layers are always computed on the GPU.
- No speculative decoding, no MTP head, no n-gram/prompt-lookup drafting.
- Dense models only; the whole model is touched per token in streamed mode.
- No 70B "without OOM" claim and no 8-hour endurance measurement (both
  UNVERIFIED in the ledger).
- No interactive-latency class: this is an overnight/long-run engine, not a
  chat server.
- No discrete-VRAM (gfx1100) target; the verification host is an APU.

## 8. Where the evidence lives

| Topic | Path |
|---|---|
| Kernel/GPU baseline | `audit/evidence/G0/7.0-baseline/` |
| Tokenizer goldens | `audit/evidence/G2/7B/` |
| Model families | `audit/evidence/G3/7C/` |
| Residency/eviction | `audit/evidence/G4/7D/` |
| Stream topology | `audit/evidence/G5/7E/` |
| Goldens, benchmarks, telemetry, claims gate | `audit/evidence/G6/7F/` |
| Claim record | `audit/CLAIMS_LEDGER.md` (machine-checked) |
| Gate signoffs | `audit/G1…G6_SIGNOFF_*.md` |

---

*Measured 2026-11-13 on the host in §1. Numbers are single-host observations
under the stated conditions; they are not guarantees, and they are not
portable to other hardware or other models.*
