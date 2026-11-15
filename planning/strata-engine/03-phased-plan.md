# 03 — Phased implementation plan (skeleton)

**Scope note (2026-11-15):** Strata is gfx1150-only. gfx1103 is a separate
> dense project (`10-project-split.md`); references to it below are historical
> escalation detail, not the active plan.

**How to use:** this is the **escalation annex**, not the starting plan. The
starting route is the audit's 4-stage lean plan (`07-plan-audit.md` §2,
`08-roadmap-decision.md`): gfx1150 baseline/tune, the three test beds, then evidence.
P0–P9 is adopted only if Strata's engine is structurally rigid or
gfx1100/gfx900 enters the critical path. The MI25 is deferred.

**Effort scale:** S (days), M (1–2 weeks), L (3–6 weeks), XL (6+ weeks), for one
person. Calendar dates are deliberately omitted.

## Phase map

| Phase | Milestone | Gate |
|---|---|---|
| P0 | ADR and scope | signed ADR: fork vs thin layer, hardware, model, process |
| P1 | Toolchain and driver matrix | `rocminfo` + HIP vector-add on gfx1150 (gfx1100 future; MI25 deferred; gfx1103 separate) |
| P2 | Capability abstraction + build matrix | descriptor/probe/dispatch accepted for gfx1150; gfx1100 future; gfx900/gfx1103 out of scope |
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
| P0.2 | Target hardware | gfx1150 now; gfx1100 future; MI25 deferred; 780M separate |
| P0.3 | Model family | Qwen3.8-Flash-Next and/or Qwen3.6-35B-A3B; license, GGUF/pack availability, reference implementation |
| P0.4 | Process | one gate per milestone; claims ledger; golden rig; who audits |
| P0.5 | Non-goals | no app/product work; no Windows support; 780M separate; no MI25 claims until measured |

**Gate:** signed ADR. No code before it.

**Risk:** the model choice gates P4–P8. If no MoE GGUF with a known-good
reference is available, P4 uses synthetic fixtures only and the plan says so.

---

## P1 — Toolchain and driver matrix (effort M–L)

**Goal:** prove each target can compile and run a trivial HIP program before
the engine depends on it. gfx1150 is the only Strata target here.

| WP | Work | Deliverable |
|---|---|---|
| P1.1 | gfx1100 baseline | system ROCm 7.x, `rocminfo`, `hipcc`, rocBLAS/hipBLASLt; vector-add |
| P1.2 | gfx1150 baseline | current host, TheRock/ROCm; vector-add; record the exact stack |
| P1.3 | gfx1103 (780M) | **separate project**; no Strata toolchain work |
| P1.4 | MI25 (gfx900) is **not** in this phase | the separate `06-mi25-feasibility.md` track; a go/no-go for general LLM software, not Strata |
| P1.5 | Version matrix | exact ROCm/LLVM/kernel/firmware/rocBLAS/hipBLASLt per card; tuning-table versions |
| P1.6 | Driver build decision | use a supported ROCm/TheRock build vs build ROCm/LLVM from source; who maintains it |

**Gate:** a `toolchain/` evidence note with `rocminfo`, `hipcc --version`, a
vector-add result for gfx1150 (and gfx1100 when available); gfx1103 is separate.
the separate track. **No engine code depends on an unproven toolchain.**

**Risks:** missing gfx1100 hardware (high). The
MI25 is a stretch, not a P1 risk.

---

## P2 — Capability abstraction + build matrix (effort L)

**Goal:** make the cards data, not code. See `02-capability-abstraction.md`.

| WP | Work | Deliverable |
|---|---|---|
| P2.1 | Descriptor schema | `devices/*.json` for gfx1150; gfx1100 later; gfx1103 is separate; gfx900 is an optional stretch descriptor |
| P2.2 | Runtime probe | `strata-device --list-devices --json`; arch-list check; model-family gate |
| P2.3 | Dispatch/fallback ladder | attention, expert GEMM, dense GEMM, dtypes, residency, speculation, KV |
| P2.4 | Build matrix | CMake targets for gfx1150; gfx1100 later; `STRATA_HIP_GFX900` only if the stretch passes; one backend per build |
| P2.5 | Telemetry hooks | `capability_profile`, `kernel_path`, `dtype_path`, `gemm_backend`, `rocm`, `model_family` |
| P2.6 | Tests | probe mocks, compile-only matrix, dispatch unit tests, refusal messages, synthetic parity |

**Gate:** acceptance in `02` §8. Adding a target requires no kernel change.

**Risk:** if the S0 feasibility says no, the gfx900 descriptor is not added and
the plan proceeds.

---

## P3 — Engine substrate (effort L)

**Goal:** a working dense/engine substrate with the evidence discipline, before
MoE work.

| WP | Work | Deliverable |
|---|---|---|
| P3.1 | Fork/import the engine | `src/`, `include/` from Strata (or the llama.cpp thin layer per P0.1); drop `apps/`, `serve/` if not needed |
| P3.2 | Port the evidence assets | GGUF parser, tokenizer, model-spec validator, goldens, claims ledger/checker/canaries, bench gate |
| P3.3 | CI shape | build matrix + CPU lane + self-hosted GPU lane per card |
| P3.4 | Build the gfx1150 binary | compile-only until gfx1100 hardware is available |

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
| P4.3 | Run on gfx1100 when available | same fixture; parity per capability |
| P4.4 | Model-family check | Qwen3.8/Qwen3.6 pack loads; unsupported families refused early |

**Gate:** numerical parity on the synthetic fixture; no speed claim. The gfx900
path is a stretch and is tested only if the separate feasibility track passes.

---

## P5 — Expert cache + residency (effort L)

| WP | Work | Deliverable |
|---|---|---|
| P5.1 | VRAM hot set | adaptive cache sized from the descriptor; per-card slots |
| P5.2 | RAM all experts + SSD table | pinned/ mmap policy; low-RAM mode |
| P5.3 | Unified vs discrete | gfx1150 shared-pool policy; gfx1100 discrete policy (gfx900 only if the stretch passes) |
| P5.4 | Measurement | hit rate, resident bytes, eviction, no OOM |

**Gate:** measured hit rate and a resident-byte guarantee under the cap; one
run per capability profile. No cross-profile claim.

---

## P6 — CPU fallback + heterogeneous compute (effort L)

| WP | Work | Deliverable |
|---|---|---|
| P6.1 | CPU kernels | AVX-512/AVX2 i-quant kernels for cold experts; gfx1150 fallbacks (gfx900 only if the stretch passes) |
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
| P9.3 | Per-card CI | gfx1150 now; a gfx1100 runner when the card arrives; MI25 only if the stretch passes |
| P9.4 | Audit/QAQC | one gate per milestone; evidence bundle |

**Gate:** no claim without an artifact; the machine-checked gate is green.

---

## S0 — MI25 feasibility (deferred, not a priority)

**Goal:** decide whether five MI25 (gfx900) cards on OCuLink are usable for
general LLM software. **Deferred:** the OCuLink adapters and a hardware build
are not ready; this track does not start until they are. It never blocks
P0–P9.

| WP | Work | Deliverable |
|---|---|---|
| S0.1 | One card on the bench | OCuLink/PCIe, above-4G, IOMMU, power, cooling; `lspci`, `dmesg`, `rocminfo` |
| S0.2 | Toolchain attempt | legacy ROCm/LLVM with gfx900, or a llama.cpp HIP build with `AMDGPU_TARGETS=gfx900`; vector-add and a small GGUF |
| S0.3 | General LLM software matrix | llama.cpp HIP, a legacy PyTorch ROCm, Ollama (if it uses the same path); record what loads/runs |
| S0.4 | Two-card and five-card | PCIe x4 bandwidth, layer/pipeline split, power/thermal, stability |
| S0.5 | Go/no-go | a stable 1-hour run with correct output and usable tok/s, or a documented no-go |

**Gate:** `06-mi25-feasibility.md` result. If yes, the five cards become a
multi-GPU lab and a later Strata stretch descriptor. If no, repurpose the
cards; the Strata plan proceeds unchanged.

---

## Cross-cutting rules

1. **gfx1150 is the only Strata target.** The 780M is a separate dense
   project; the MI25 is deferred.
2. **The gfx1150 host is the development target** until a gfx1100 machine
   exists. It can gate P2–P4; it cannot gate gfx1100 claims.
3. **The MI25 is deferred.** The general LLM feasibility test decides; it
   never blocks the gfx1150/gfx1100 milestones.
4. **One gate per milestone**; the claims ledger and golden rig come with P3,
   not after P8.
5. **No performance claim from a synthetic fixture**; performance claims start
   at P5 with measured artifacts.
