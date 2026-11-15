# 03 — Phased implementation plan (skeleton)

**How to use:** this is the plan skeleton. `05-deepseek-prompt.md` asks the
planning model to expand each WP into tasks, acceptance criteria, artifacts and
estimates. Do not start P3 before P1/P2 are gated: the whole point is that the
780M and MI25 are designed in, not ported later.

**Effort scale:** S (days), M (1–2 weeks), L (3–6 weeks), XL (6+ weeks), for one
person. Calendar dates are deliberately omitted.

## Phase map

| Phase | Milestone | Gate |
|---|---|---|
| P0 | ADR and scope | signed ADR: fork vs thin layer, hardware, model, process |
| P1 | Toolchain and driver matrix | `rocminfo` + HIP vector-add on each available card; MI25 go/no-go |
| P2 | Capability abstraction + build matrix | descriptor/probe/dispatch accepted; every target compiles |
| P3 | Engine substrate | ported golden rig reproduces the current verdicts |
| P4 | MoE correctness spike | synthetic routing/grouped GEMM parity |
| P5 | Expert cache + residency | measured hit rate and resident-byte guarantee |
| P6 | CPU fallback + heterogeneous compute | cold-expert latency split; parity |
| P7 | Speculation | acceptance + gain with identical greedy output |
| P8 | Long context / KV | measured 32K context per card |
| P9 | Evidence, CI, claims | no claim without an artifact; per-card CI |

---

## P0 — ADR and scope (effort S)

**Goal:** make the decisions the code cannot.

| WP | Work | Deliverable |
|---|---|---|
| P0.1 | Fork Strata vs thin layer on llama.cpp | ADR with the B/C/D recommendation and the evidence from `b-vs-c.md` |
| P0.2 | Target hardware | gfx1100, 780M, MI25, gfx1150: which is available for dev/CI, which is experimental |
| P0.3 | Model family | Qwen3.8-Flash-Next and/or Qwen3.6-35B-A3B; license, GGUF/pack availability, reference implementation |
| P0.4 | Process | one gate per milestone; claims ledger; golden rig; who audits |
| P0.5 | Non-goals | no app/product work; no Windows 780M; no MI25 claims until measured |

**Gate:** signed ADR. No code before it.

**Risk:** the model choice gates P4–P8. If no MoE GGUF with a known-good
reference is available, P4 uses synthetic fixtures only and the plan says so.

---

## P1 — Toolchain and driver matrix (effort M–L)

**Goal:** prove each target can compile and run a trivial HIP program before
the engine depends on it. This is the earliest place to descope the MI25.

| WP | Work | Deliverable |
|---|---|---|
| P1.1 | gfx1100 baseline | system ROCm 7.x, `rocminfo`, `hipcc`, rocBLAS/hipBLASLt; vector-add |
| P1.2 | gfx1150 baseline | current host, TheRock/ROCm; vector-add; record the exact stack |
| P1.3 | gfx1103 (780M) | ROCm 7.1+ gfx1103; `HSA_OVERRIDE_GFX_VERSION` only if needed; `STRATA_EXPERIMENTAL_GFX1103`; firmware check; vector-add |
| P1.4 | gfx900 (MI25) spike | legacy/custom ROCm/LLVM with gfx900; rocBLAS/hipBLAS kernels; vector-add. If impossible, descope to CPU-only and record it |
| P1.5 | Version matrix | exact ROCm/LLVM/kernel/firmware/rocBLAS/hipBLASLt per card; tuning-table versions |
| P1.6 | Driver build decision | use a supported ROCm/TheRock build vs build ROCm/LLVM from source; who maintains it |

**Gate:** a `toolchain/` evidence note with `rocminfo`, `hipcc --version`, a
vector-add result per available card, and the MI25 go/no-go. **No engine code
depends on an unproven toolchain.**

**Risks:** MI25 (high) — gfx900 is not in current ROCm; the gfx906 community
image is a template, not a solution. 780M firmware resets (medium).

---

## P2 — Capability abstraction + build matrix (effort L)

**Goal:** make the cards data, not code. See `02-capability-abstraction.md`.

| WP | Work | Deliverable |
|---|---|---|
| P2.1 | Descriptor schema | `devices/*.json` for gfx1100, gfx1103, gfx900, gfx1150, gfx906 (reference) |
| P2.2 | Runtime probe | `strata-device --list-devices --json`; arch-list check; model-family gate |
| P2.3 | Dispatch/fallback ladder | attention, expert GEMM, dense GEMM, dtypes, residency, speculation, KV |
| P2.4 | Build matrix | CMake targets incl. `STRATA_HIP_GFX900`; one backend per build |
| P2.5 | Telemetry hooks | `capability_profile`, `kernel_path`, `dtype_path`, `gemm_backend`, `rocm`, `model_family` |
| P2.6 | Tests | probe mocks, compile-only matrix, dispatch unit tests, refusal messages, synthetic parity |

**Gate:** acceptance in `02` §8. Adding a target requires no kernel change.

**Risk:** the gfx900 compat layer is a real port; if P1.4 says no, the gfx900
descriptor is marked `cpu-only` and the plan proceeds.

---

## P3 — Engine substrate (effort L)

**Goal:** a working dense/engine substrate with the evidence discipline, before
MoE work.

| WP | Work | Deliverable |
|---|---|---|
| P3.1 | Fork/import the engine | `src/`, `include/` from Strata (or the llama.cpp thin layer per P0.1); drop `apps/`, `serve/` if not needed |
| P3.2 | Port the evidence assets | GGUF parser, tokenizer, model-spec validator, goldens, claims ledger/checker/canaries, bench gate |
| P3.3 | CI shape | build matrix + CPU lane + self-hosted GPU lane per card |
| P3.4 | Build the gfx1100/780M/1150 binaries | compile-only until hardware is available |

**Gate:** the ported golden rig reproduces the current project's verdicts on
the synthetic fixtures. No performance claim.

**Risk:** fork drift. Pin the upstream commit, keep a `UPSTREAM.md` with the
divergence list.

---

## P4 — MoE correctness spike (effort M)

| WP | Work | Deliverable |
|---|---|---|
| P4.1 | Synthetic MoE fixture | routing + grouped GEMM, random experts, NumPy reference |
| P4.2 | Run on gfx1150 | expected kernel path per descriptor; parity record |
| P4.3 | Run on gfx1100/780M when available | same fixture; parity per capability |
| P4.4 | Model-family check | Qwen3.8/Qwen3.6 pack loads; unsupported families refused early |

**Gate:** numerical parity on the synthetic fixture; no speed claim. The gfx900
path is tested only if P1.4 succeeded; otherwise it is CPU-only.

---

## P5 — Expert cache + residency (effort L)

| WP | Work | Deliverable |
|---|---|---|
| P5.1 | VRAM hot set | adaptive cache sized from the descriptor; per-card slots |
| P5.2 | RAM all experts + SSD table | pinned/ mmap policy; low-RAM mode |
| P5.3 | Unified vs discrete | 780M/1150 shared-pool policy; gfx1100/gfx900 discrete policy |
| P5.4 | Measurement | hit rate, resident bytes, eviction, no OOM |

**Gate:** measured hit rate and a resident-byte guarantee under the cap; one
run per capability profile. No cross-profile claim.

---

## P6 — CPU fallback + heterogeneous compute (effort L)

| WP | Work | Deliverable |
|---|---|---|
| P6.1 | CPU kernels | AVX-512/AVX2 i-quant kernels for cold experts; gfx900/gfx1103 fallbacks |
| P6.2 | Concurrency | CPU pool concurrent with the GPU; overlap measured |
| P6.3 | Per-card split | PCIe vs CPU share; `--pcie-frac`-style policy per descriptor |
| P6.4 | Parity | CPU-lane rounding vs GPU lane; KL/top-1 |

**Gate:** a cold-expert token's latency split is measured; parity recorded.

---

## P7 — Speculation (effort M)

| WP | Work | Deliverable |
|---|---|---|
| P7.1 | MTP draft | if the model has an MTP head; acceptance measured |
| P7.2 | Prompt lookup | n-gram drafts where acceptance pays |
| P7.3 | Verification | output identical to greedy; acceptance and gain measured |

**Gate:** acceptance + gain with identical greedy output; no claim on a path
that was not measured.

---

## P8 — Long context / KV (effort M)

| WP | Work | Deliverable |
|---|---|---|
| P8.1 | 8K prefill chunks | per-card chunk size; prompt speed measured |
| P8.2 | KV streaming/offload | device → RAM → disk; budget per memory model |
| P8.3 | 32K+ validation | per-card; unified vs discrete |

**Gate:** measured 32K context on each available card; no cross-card claim.

---

## P9 — Evidence, CI, claims (effort M, continuous)

| WP | Work | Deliverable |
|---|---|---|
| P9.1 | Claims ledger | one row per `(profile, model, workload)`; strict checker |
| P9.2 | Bench gate | warm-up/median/p95/ratio discipline |
| P9.3 | Per-card CI | self-hosted runners for gfx1100/780M/MI25 as they arrive; the gfx1150 host now |
| P9.4 | Audit/QAQC | one gate per milestone; evidence bundle |

**Gate:** no claim without an artifact; the machine-checked gate is green.

---

## Cross-cutting rules

1. **The 780M and MI25 are in P1/P2, not a late port.** Their descriptors and
   build targets exist before the first MoE kernel.
2. **The gfx1150 host is the development target** until a gfx1100/780M/MI25
   machine exists. It can gate P2–P4; it cannot gate gfx1100 claims.
3. **The MI25 is allowed to descope to CPU-only** if P1.4 fails. Record it; do
   not let it block the other cards.
4. **One gate per milestone**; the claims ledger and golden rig come with P3,
   not after P8.
5. **No performance claim from a synthetic fixture**; performance claims start
   at P5 with measured artifacts.
