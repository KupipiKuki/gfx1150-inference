# 01 — Hardware matrix and ROCm/build status

**Sources:** `Strata/docs/AMD_HIP.md` (fetched 2026-11-15), ROCm gfx1103
discussions, card specifications. Treat "maintainer-tested" vs "opt-in" vs
"not supported" as the planning boundary; do not upgrade a status without a
measurement.

## 1. Matrix

| | **gfx1100** | **gfx1103** | **gfx900** | **gfx1150** |
|---|---|---|---|---|
| Card | RX 7900 XTX/XT/GRE | Radeon 780M / 760M | Instinct MI25 (Vega 10) | Radeon 890M (Strix Point) |
| Memory | 24/20/16 GB GDDR6 | shared LPDDR5 (iGPU) | 16 GB HBM2 | shared LPDDR5 (iGPU) |
| Memory model | discrete | unified | discrete | unified |
| Bandwidth (vendor) | ~960/800/576 GB/s | ~100 GB/s class | ~484 GB/s | ~100 GB/s class |
| Wave | 32 | 32 | **64** | 32 |
| Matrix cores | WMMA (RDNA3) | WMMA (RDNA3) | **none** | WMMA (RDNA3.5) |
| dtypes | fp32/fp16/bf16/int8 | fp32/fp16/bf16/int8 | fp32/fp16/int8; **no bf16** | fp32/fp16/bf16/int8 |
| ROCm status | mainline, mature | **7.1+ has gfx1103 rocBLAS**; older stacks need `HSA_OVERRIDE_GFX_VERSION=11.0.0` | **dropped by current ROCm**; legacy/custom build required | experimental; TheRock/community builds |
| Strata status | maintainer-tested | Linux opt-in (`RADEON_780M.md`, `STRATA_EXPERIMENTAL_GFX1103=1`); Windows not supported | **no path**; closest is the gfx906 wave64 compat build, not gfx900 | builds as an unvalidated target; setup does not install |
| Build | `-DCMAKE_HIP_ARCHITECTURES=gfx1100` | gfx1103 build + experimental flag + `gfx1103-hipblaslt-100401.txt` | `STRATA_HIP_GFX906`-style wave64 compat is the starting point, but gfx900 needs its own LLVM/rocBLAS targets | `-DCMAKE_HIP_ARCHITECTURES=gfx1150` + `gfx1150-hipblaslt-100401.txt` |
| Measured (Strata docs) | 1.7K prompt 682→1,038 tok/s with table; 6.5K 857→1,524; 131K 926→1,687 | 4K prompt 90→187 tok/s with table; 277 with WMMA opt-ins; decode ~16.6 | none for MI25; gfx906 reference: 2x MI50 49.2→66.9 tok/s with pipelining | community: decode 15–19, prompt 125–130 (1.5–1.7x with table) |
| Main risk | supply/price; VRAM size for the expert cache | shared-memory iGPU; firmware GPU resets; opt-in build | ISA/toolchain: wave64, no WMMA, no bf16, no current ROCm kernels; model-family support unknown | experimental; not a product target |

## 2. Per-card notes

### gfx1100 — the primary target

- Strata's `AMD_HIP.md` lists RX 7900 XT/XTX as **maintainer-tested**,
  hipBLASLt tables ship (`gfx1100-hipblaslt-100401.txt`, `-100500.txt`).
- The engine's expert cache scales with VRAM: 24 GB holds more of the 24,576
  experts; 16 GB (GRE) is the minimum practical target.
- This is the card where the Strata claims (expert cache, CPU fallback,
  speculation, long context) have the most evidence. Use it as the reference
  target, not the only target.

### gfx1103 — Radeon 780M

- The 780M is an **iGPU with shared memory**; the "VRAM" is a carve-out of
  system RAM. The engine's integrated-GPU detection and prompt switches
  (`STRATA_IGPU_PROMPT_SET`, `STRATA_PF_FUSED`, `STRATA_HIP_PROMPT_F16`) are
  the relevant path.
- ROCm: gfx1103 is supported in ROCm 7.1+ (rocBLAS); older stacks need
  `HSA_OVERRIDE_GFX_VERSION=11.0.0`. A custom TheRock build with
  `gfx110X-igpu` may still be needed for the exact stack the owner wants.
- Strata: **Linux opt-in build**, `STRATA_EXPERIMENTAL_GFX1103=1`,
  `gfx1103-hipblaslt-100401.txt` (143 rows). Setup installs for gfx1103 only
  with that flag; Windows is not supported.
- Known host risk: some firmware (gc 11.0.1 MES) resets the GPU when the
  kernel evicts queues during a barrier kernel. A newer `linux-firmware` is
  the likely cure; `STRATA_ARENA_PIN_GIB=none` only shortens the eviction
  time. This is a host-validation item, not an engine bug.
- The owner's "special drivers built from ROCm" is realistic, but the first
  plan should prefer the supported ROCm 7.1+ path and only build a custom
  stack if the measured gap justifies it.

### gfx900 — Instinct MI25 (stretch goal)

- **Five cards owned for $200**, 16 GB HBM2 each (80 GB aggregate), used over
  **OCuLink** in the existing builds. That is a cheap lab, not a supported
  target.
- Vega 10, ~484 GB/s, 9.8 TFLOPS FP32 / ~25 TFLOPS FP16 (vendor specs).
  **Wave64, no WMMA, no bf16.**
- Current ROCm releases do not ship gfx900 libraries. The Strata doc's gfx906
  section is the closest precedent: an opt-in wave64 build
  (`STRATA_HIP_GFX906=ON`), a CUDA-source compat layer, a community ROCm image
  (`mixa3607/rocm-gfx906:7.14-complete`), no hipBLASLt, and a different
  grouped-expert mode.
- **gfx900 is not gfx906.** The gfx906 build proves the compat pattern, not
  the MI25. gfx900 needs its own LLVM target, rocBLAS/hipBLAS kernels (or a
  scalar/rocBLAS fallback), and a model-family check. The Qwen3.6 family is
  explicitly not part of the gfx906 build; the MI25 support must state which
  families it can run.
- **OCuLink changes the problem.** Each card gets PCIe x4 (typically 3.0/4.0),
  far below the card's HBM2 bandwidth. That is fine for single-card inference
  and model loads, poor for tensor parallel or expert streaming across five
  cards. Five 300 W cards also mean ~1.5 kW, cooling, and enough PCIe
  lanes/bifurcation; check above-4G decoding and IOMMU.
- **The first question is not Strata; it is general LLM software.** Can
  llama.cpp (HIP), a legacy ROCm, PyTorch, or Ollama use one MI25 at all? The
  separate plan in `06-mi25-feasibility.md` answers that before any Strata
  work. If it works, the five cards are a multi-GPU lab and a later Strata
  stretch target; if it does not, they are repurposed and the Strata plan does
  not block on them.

### gfx1150 — the current APU host

- Radeon 890M, Strix Point, shared memory, experimental ROCm. Strata builds as
  an unvalidated target; the community report is 15–19 tok/s decode and
  125–130 tok/s prompt, 1.5–1.7x with the table.
- This is the host that can validate the capability layer, the synthetic MoE
  fixture and the evidence harness **before** a gfx1100/780M machine is
  available. Use it for M1–M2; do not claim gfx1100 performance from it.

## 3. What the matrix means for the plan

1. **Two different porting problems, not one.** gfx1103 is a supported-ISA,
   build-and-tune problem (shared memory, opt-in flags, firmware). gfx900 is a
   toolchain/ISA problem (wave64, no WMMA, no current ROCm kernels).
2. **The capability layer must express wave size, matrix cores, dtypes,
   memory model and supported model families as data.** A gfx900 build cannot
   be a gfx1100 build with a different `-DCMAKE_HIP_ARCHITECTURES`.
3. **The MI25 is a stretch, not a schedule risk.** Test general LLM software
   first (`06-mi25-feasibility.md`); only if one card works do we add a gfx900
   stretch descriptor. It never blocks the gfx1100/780M milestones.
4. **The 780M is the early-inclusion win.** The Linux opt-in path and the
   table already exist; the work is validation, firmware handling, and the
   capability descriptor. It can be a P2 deliverable.
