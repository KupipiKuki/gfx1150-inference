# 02 — Capability abstraction: include the cards before the kernels

> **Scope note (2026-11-15):** Strata is gfx1150-only for now. gfx1103 is a
> separate dense project (`10-project-split.md`); the descriptor can express it
> later, but it is not in the Strata plan.

**Purpose:** make a new GPU a **data** change (descriptor + build target +
validation run), not a new kernel branch. This is the P1–P2 deliverable that
prevents the "add the 780M or a stretch card later and recode" failure.

## 1. Principles

1. **Capability is data, not `#ifdef`.** Every device difference lives in a
   descriptor; kernels select a path from the descriptor at dispatch time.
2. **Fail early and in one line.** A card/model/backend combination that is not
   supported is refused at startup with the card, arch, reason and the closest
   supported path — not a crash or a silent CPU fallback.
3. **The binary declares what it was built for.** The engine compares the
   device arch with the compiled arch list and refuses a mismatch.
4. **Every path is named in telemetry.** The claims ledger records
   `capability_profile`, `kernel_path`, `dtype_path`, `gemm_backend`; a claim
   on one profile never applies to another.
5. **Numerical parity is a gate, not an afterthought.** Each fallback path is
   compared with a reference on a synthetic fixture; the result is recorded.

## 2. Device descriptor

A JSON object (one per target) that is both documentation and runtime data:

```json
{
  "id": "gfx1103-780m",
  "arch": "gfx1103",
  "family": "rdna3",
  "card": "Radeon 780M",
  "memory_model": "unified",
  "vram_bytes": null,
  "gtt_bytes": null,
  "system_ram_bytes": null,
  "bandwidth_gbps": 100,
  "wave_size": 32,
  "matrix_cores": "wmma",
  "dtypes": {"fp32": true, "fp16": true, "bf16": true, "int8": true, "fp8": false},
  "dot4": true,
  "packed_fp16": true,
  "lds_kb": 64,
  "runtime": {"rocm_min": "7.1", "hsa_override": null, "notes": "Linux opt-in; firmware resets possible"},
  "libraries": {"hipblaslt": true, "rocblas": true, "miopen": true, "tuning_table": "gfx1103-hipblaslt-100401.txt"},
  "model_families": ["qwen3.8", "qwen3.6"],
  "build": {"cmake_arch": "gfx1103", "experimental_flag": "STRATA_EXPERIMENTAL_GFX1103=1", "compat": null},
  "fallbacks": ["wmma-int8", "fp16-simt", "cpu-i-quant"]
}
```

Required fields for every target: `arch`, `family`, `memory_model`,
`wave_size`, `matrix_cores`, `dtypes`, `runtime`, `libraries`,
`model_families`, `build`, `fallbacks`.

The descriptor is checked into the repo under `devices/` and is the single
source for the build matrix and the runtime probe tests.

## 3. Runtime probe

- **Source of truth:** `rocminfo` / `hipGetDeviceProperties` / KFD topology.
  Read arch, memory pools, integrated flag, wave size, workgroup limits,
  library versions.
- **`strata-device --list-devices --json`** (extend the existing device tool)
  emits the descriptor actually observed, plus the binary's compiled arch list.
- **Startup gate:** if `device.arch` is not in the binary's arch list → stop
  with: `engine built for gfx1100; card is gfx1103; rebuild with
  -DCMAKE_HIP_ARCHITECTURES=gfx1103 or use the gfx1103 package`.
- **Model gate:** if the requested model family is not in
  `descriptor.model_families` → stop with the supported list.
- **Runtime overrides** (`HSA_OVERRIDE_GFX_VERSION`, `ROCR_VISIBLE_DEVICES`,
  `HIP_VISIBLE_DEVICES`) are recorded in telemetry, never silently applied.

## 4. Build matrix

| Target | CMake | Extra | Binary arch list |
|---|---|---|---|
| gfx1100 | `-DSTRATA_ENABLE_HIP=ON -DCMAKE_HIP_ARCHITECTURES=gfx1100` | tuning table | gfx1100 |
| gfx1103 | `-DCMAKE_HIP_ARCHITECTURES=gfx1103` | `STRATA_EXPERIMENTAL_GFX1103=1`, 1103 table | gfx1103 |
| gfx1150 | `-DCMAKE_HIP_ARCHITECTURES=gfx1150` | 1150 table | gfx1150 |
| gfx900 (stretch) | a new `STRATA_HIP_GFX900` compat build (wave64) | only after `06-mi25-feasibility.md` passes; legacy/custom ROCm + gfx900 kernels; no hipBLASLt | gfx900 |
| gfx906 (reference) | `-DSTRATA_HIP_GFX906=ON` | community ROCm image | gfx906 |

Rules:

- One GPU backend per build (Strata already enforces this).
- A multi-arch binary is allowed only within one family (e.g.
  `"gfx1100;gfx1101"`); cross-family splits need a system ROCm and a
  descriptor that says so.
- The build records its arch list in the binary; the probe compares it, not a
  hand-maintained string.
- **gfx900 is a stretch target, not a P2 gate.** It is a new wave64 compat
  build (the gfx906 build is only the template), and it is attempted only if
  the general-LLM feasibility test passes. The descriptor schema must be able
  to express it, but the card is not required for P2 acceptance.

## 5. Dispatch and fallback ladder

The engine selects a `KernelPlan` from the descriptor + model:

| Stage | Preferred | Fallbacks |
|---|---|---|
| Attention | WMMA int8/fp16 (gfx11/12) | SIMT wave32 (gfx10), SIMT wave64 (gfx9), CPU attention |
| MoE grouped GEMM | native expert mode (gfx11/12) | gfx906 mode 7 / gfx900 variant, CPU i-quant |
| Dense projections | hipBLASLt + tuning table | rocBLAS + table, plain hipBLAS, CPU |
| Dtypes | bf16 | fp16, fp32 |
| Residency | discrete expert cache | unified shared pool, low-RAM mode |
| Speculation | MTP + prompt lookup | MTP only, prompt lookup only, none |
| Long context | KV on device | KV stream from RAM, CPU/mmap KV |

Each row is a **capability flag**, not a card check. Adding a card means
filling flags; adding a new path means adding a row and a parity test.

## 6. Evidence hooks

Telemetry must name the path so a claim is scoped:

```text
capability_profile=gfx1103-780m
kernel_path=wmma-int8
dtype_path=fp16
gemm_backend=hipblaslt(tuned gfx1103-100401)
residency=unified
cache_slots=...
cpu_gpu_split=...
rocm=7.14.1  hsa_override=none
model_family=qwen3.8
```

The claims ledger gets one row per `(capability_profile, model_family,
workload)`. A gfx1100 result never stands in for a 780M or MI25 result.

## 7. Tests (P2 gate)

1. **Descriptor probe:** mock `rocminfo`/HIP properties for each target; the
   probe emits the expected descriptor and arch list match/mismatch.
2. **Build matrix:** compile-only for every target; record the compiler, ROCm
   and table in the artifact.
3. **Dispatch selection:** unit tests over the descriptor matrix; assert the
   selected path and the refusal message for unsupported combinations.
4. **Numerical parity:** a synthetic MoE fixture (routing + grouped GEMM) run
   through each path, compared with a NumPy reference. Record KL/top-1; no
   performance claim.
5. **Host smoke:** gfx1150 now; gfx1100 and gfx1103 when hardware is
   available; the stretch gfx900 only if the feasibility track passes. Each
   records the descriptor and a one-line result.
6. **Model gate:** a family not in the descriptor is refused with the
   supported list.

## 8. Acceptance

- Adding a target requires **no kernel code change**: a descriptor entry, a
  build target, and a validation run.
- The engine refuses an unsupported card/model with one clear line.
- Telemetry names the path; the claims ledger can scope a row to it.
- The gfx1150 host can run the synthetic fixture and the probe before any
  discrete card exists.

## 9. Failure modes to design against

- A gfx900 binary that silently falls back to CPU: refuse at startup instead,
  or mark the run `cpu-only` in telemetry.
- A 780M run that uses the discrete-card path because the integrated flag was
  not read: the probe must read the integrated flag, not the arch alone.
- A tuning table from the wrong hipBLASLt version: the engine must check the
  table header (`arch`, version) and say why it is not taken.
- A model family that the gfx906/gfx900 build does not support: refuse early,
  at model load, not at the first expert dispatch.
