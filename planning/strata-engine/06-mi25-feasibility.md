# 06 — MI25 feasibility (deferred, separate from Strata)

**Status: DEFERRED (2026-11-15).** The OCuLink adapters and a hardware build
are not ready; this is not a priority. The file is the test plan for when one
card is physically usable.

**Goal:** decide whether five Instinct MI25 cards on OCuLink are usable for
**general LLM software** before spending Strata time on gfx900. This track is
independent; it never blocks the Strata plan.

## 1. Inventory and constraints

| | |
|---|---|
| Cards | 5× AMD Instinct MI25 (Vega 10, **gfx900**) |
| Memory | 16 GB HBM2 each, 80 GB aggregate; ~484 GB/s per card |
| Compute | ~9.8 TFLOPS FP32 / ~25 TFLOPS FP16; **wave64, no WMMA, no bf16** |
| Link | **OCuLink**, typically PCIe x4 (3.0/4.0), far below HBM2 bandwidth |
| Power | ~300 W each → ~1.5 kW for five, plus the host; cooling and PSU are first-class |
| Software | current ROCm does not ship gfx900; a legacy/custom stack or a llama.cpp HIP build is required |

Why OCuLink matters: single-card inference and model loads are fine at x4;
tensor parallel or expert streaming **across** five cards is bandwidth-bound.
Do not expect NVLink-like scaling.

## 2. Pre-flight (before any model)

Prerequisites before this track starts: OCuLink adapters/cables, a host with
enough PCIe lanes/bifurcation, a PSU and cooling for ~1.5 kW, and above-4G
decoding. None of these are ready today.

- Physical: OCuLink cables/adapters seated, PCIe bifurcation, above-4G
  decoding, IOMMU setting, airflow, PSU rails.
- Host: `lspci -nn | grep -i vga`, `dmesg | grep -i amdgpu`, `rocminfo`,
  `rocm-smi` (if available), kernel/firmware versions.
- One card only for the first boot; add cards one at a time.
- Record the exact host, BIOS setting, kernel, firmware and adapter model.

## 3. Software matrix (the actual question)

Try in this order; stop at the first path that works and is stable:

1. **llama.cpp HIP** — build with `-DAMDGPU_TARGETS=gfx900` (or the current
   `CMAKE_HIP_ARCHITECTURES` equivalent), run a small Q4_0 GGUF. This is the
   best first test: llama.cpp has broad AMD support and is the base of many
   “general LLM” tools.
2. **Legacy ROCm + PyTorch** — a ROCm version that still ships gfx900 kernels
   (or a community build); a matmul and a tiny model. If no gfx900 kernel set
   exists, document it.
3. **Ollama** — only if llama.cpp works; it uses the same engine.
4. **vLLM / other** — likely unsupported on gfx900; record the refusal, do not
   spend time.

Do **not** build a custom ROCm/LLVM stack before step 1. If llama.cpp cannot
use gfx900, a custom stack is a large bet; the feasibility result should say so.

## 4. Tests and metrics

| Test | Command / setup | Pass |
|---|---|---|
| Single card probe | `rocminfo`, `hipcc`, vector-add | card visible, correct result |
| GEMM | `rocblas-bench` or a small HIP matmul | correct, no reset |
| llama.cpp small GGUF | Q4_0 1B–7B, 128 tokens | tokens/s, prompt tok/s, `dmesg` clean |
| PCIe bandwidth | `rocm-bandwidth-test` (or a copy kernel) | record host↔card GB/s at x4 |
| Two cards | `HIP_VISIBLE_DEVICES=0,1`, layer/pipeline split | no regression; record scaling |
| Five cards | all visible, model split or independent runs | stable within power/thermal |
| Stability | 1-hour run, `dmesg`/`rocm-smi` sampling | no resets, no XNACK/VM errors |
| Power/thermal | wall meter, `rocm-smi` temps | within PSU/cooling limits |

Record tokens/s, prompt tok/s, PCIe GB/s, power, temperature, resets and
`dmesg` errors. These are observations, not claims.

## 5. Go/no-go

- **Go** if one card runs a small GGUF correctly for an hour with usable
  tokens/s, and two cards show no regression. Five cards become a multi-GPU
  lab; a later Strata gfx900 stretch descriptor is worth planning.
- **No-go** if the card cannot be made visible, llama.cpp cannot build/run, or
  the run is unstable. Repurpose the cards; the Strata plan proceeds unchanged.

Either result is useful: a no-go saves months of gfx900 engine work.

## 6. Risks

- gfx900 is not in current ROCm; the gfx906 community image is not a gfx900
  solution.
- OCuLink x4 bandwidth; five cards on one host may be power/thermal-bound.
- Above-4G/IOMMU/reset issues on older platforms.
- No bf16, no WMMA, wave64: modern kernels may assume features the card lacks.
- Software support: PyTorch/Ollama/vLLM may never support gfx900; llama.cpp is
  the realistic path.

## 7. What not to do

- Do not put the MI25 on the Strata critical path or in P0–P9 gates.
- Do not buy more cards until one works.
- Do not build a custom ROCm stack before trying llama.cpp/legacy ROCm.
- Do not claim MI25 LLM performance from a single unverified run.
