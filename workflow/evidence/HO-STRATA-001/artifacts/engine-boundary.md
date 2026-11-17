# Engine boundary — Strata at `baf16363b4` (gfx1150)

Evidence tag: every path below was read in the pinned checkout at
`/home/kupipi/Documents/git/strata`; the binary statements come from the build of
AC-3 and its runs in AC-4 (`artifacts/families.txt`, `artifacts/geometry.txt`,
`artifacts/help.txt`, `artifacts/engine-deps.txt`).

## (a) Three layers and the paths each covers

| Layer | Paths | What it is |
|---|---|---|
| **Engine core** | `src/` (500 files), `include/` (281 files) — plus the per-platform variants `metal/`, `sycl/` that are *not* in this build | The C++/HIP inference engine. The executable target `strata` is `src/program/generate.cpp` (`cmake/strata_gpu_engine.cmake:510`) linked against `strata_engine strata_prefill strata_spec` + the HIP runtime (`:513`) and, inside `if(NOT STRATA_HIP_GFX906)` (`:532-546`), against `strata_qwen35` (`:544`). |
| **Control** | `strata.py`, `strata_cli/` (56 files), `strata_control/` (126 files), `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1` | The Python "Terminal". `strata.py` is a **43-line** stdlib-only entry point (`wc -l strata.py` → 43) that imports `strata_cli.cli` in `__main__`; `bin/strata` is a sh launcher that only *finds a Python* and hands over (`bin/strata:1-20`). `strata_control/` holds the policy pieces (acquisition, calibration, `hipblaslt_tuning.py`, `setup_config.py`). |
| **App / server** | `apps/` (1,018 files: `apps/desktop` Tauri shell, `apps/host` Node host + web UI), `serve/` (201 files, `serve/server.py`) | The GUI, and the Python OpenAI/Anthropic-compatible HTTP server. `AGENTS.md:14-22` names exactly this split. |

`serve/server.py:1163` starts the engine as a **child process**: `popen("the Strata engine",
[exe, "--serve", *args], ...)`. The server drives the binary; the binary does not call the server.

## (b) What the engine needs at runtime

- **ROCm shared libraries on the loader path.** `ldd build-hip/strata` resolves only the ROCm
  math/runtime set (`libhipblas.so.3`, `librocblas.so.5`, `libhipblaslt.so.1`,
  `libamdhip64.so.7`) plus libc/libstdc++/libm/libgcc — no Python, no Node
  (`artifacts/engine-deps.txt`). On this host they are not found until
  `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` is set; without it the binary dies at
  exec with `error while loading shared libraries: libhipblas.so.3` (exit 127,
  `artifacts/families.txt`).
- **A GPU matching the compiled architecture.** `src/core/device.cu:41-64` compares the
  runtime `gcnArchName` against the `STRATA_HIP_ARCHS` string baked in at configure time and
  requires `warpSize == 32`; a mismatch is a named startup error, not a silent fallback.
- **A model pack on disk**, for real work: `--pack DIR` (default `pack/full`) and, for this
  family, `--ple-gguf PATH`. `--help` states plainly that without `--ple-gguf`, "LAYER 1's PLE
  IS SILENTLY SKIPPED" (`artifacts/help.txt`). No pack = no run; that is why AC-4 is limited
  to `--families` / `--geometry` / `--help`.
- **An optional tuning table** beside the binary (`<exe dir>/tuning/`) or named by
  `STRATA_HIPBLASLT_TUNING` — see AC-7.

## (c) Can it run headless without `apps/` and `serve/`? — **Yes**

Evidence, three independent lines:

1. **Nothing from either tree is compiled in.** The `strata` target's sources and link
   libraries are all under `src/`/`include/` (`cmake/strata_gpu_engine.cmake:510-513`). The
   build output contains only `libstrata_*.a`, ggml, and the `strata` binary
   (`artifacts/engine-deps.txt`).
2. **No trace of them in the binary.** `strings -a build-hip/strata | grep -c
   'strata_cli\|strata_control\|serve/server'` → **0**.
3. **It ran.** `build-hip/strata --families` → `qwen4exp qwen35moe`, exit 0;
   `--geometry` → `flash_next`, exit 0 — from a build directory containing neither `apps/`
   nor `serve/`, with no server process and no model. (`--families` / `--geometry` /
   `--help` only report the compiled surface; they do not load a model, so this proves the
   binary starts and answers headless, **not** that a generation run works.)

The app is also structurally optional: `AGENTS.md:17` notes the installers "carry no engine"
and fetch the matching engine package at first start.

## (d) What the Control adds that the engine does not have

The engine is a *one-shot generator* (`strata generate --pack … --tokens …`). Everything
around that is the Control's, per `strata.py launch --help`
(`artifacts/control-launch-help.txt`):

- **Model choice, acquisition and layout**: `--model`, `--family`, `--model-path`,
  `--data-dir`, `--move-data`. The engine never downloads; it reads a pack.
- **Hardware policy**: `--backend nvidia|amd|intel|auto`, `--gpu`, `--gpu-roles`,
  `--split-engine auto|on|off`, `--parallel N`, `--tune quick|thorough|skip`, `--retune`.
- **Runtime config the engine then obeys**: `--context`, `--kv`, `--mtp`, `--drafting`,
  `--preset`, `--set KEY=VALUE` — the Control writes a run config and exports env such as
  `STRATA_HIPBLASLT_TUNING` (`strata_control/setup_config.py:442`).
- **Serving and access control**: `--access local|lan|cloudflare|tailscale`, `--port`,
  `--api-key`, `--api-key-env`, `--new-key`, `--status`, `--stop` — HTTP surface, keys and
  process lifecycle, none of which exist inside the C++ binary.
- **The tuning-table policy**: `strata_control/hipblaslt_tuning.py` decides *which* table (if
  any) a card gets; the engine only loads the file it is handed.

## (e) Smallest command line that starts the engine alone

Flags from `strata generate --help` (`artifacts/help.txt`); **not executed** — no pack is
installed on this host and a model run is out of scope.

```sh
cd /home/kupipi/Documents/git/strata
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib \
  ./build-hip/strata generate --pack <PACK_DIR> --tokens "<id,id,id>" --ple-gguf <SHARD1.gguf>
```

`--tokens` (or `--tokens-file`) is the only **required** flag; `--pack` defaults to `pack/full`
(`artifacts/help.txt:6-10`); `--ple-gguf` is not enforced by the parser but is required for a
correct run per the help text. No `strata.py`, no `serve/`, no `apps/` and no TUI is involved.
