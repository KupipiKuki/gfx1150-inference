# AC-7 — gfx1150 hipBLASLt tuning table: match and default

All raw output: `artifacts/tuning-table-raw.txt`, `artifacts/hipblaslt-version-probe.txt`.
One profile: AMD Radeon 890M, `gfx1150`, no model loaded.

## 1. The table is present

| Check | Value |
|---|---|
| Path | `tools/hip/gfx1150-hipblaslt-100401.txt` |
| Size | 146 lines (`wc -l`) |
| SHA256 | `aee2867c096887cccaef8bc04a9ef10adec43da58421edfdaaec04a61ec5549c` |
| Header, `head -2` | line 1 `# solution IDs are scoped to this hipBLASLt version and device architecture`<br>line 2 `STRATA_HIPBLASLT_TUNING_V1 gfx1150 100401` |

The SHA256 equals the value the Architect recorded at the pin
(`artifacts/pinned-commit.txt`), so the table in this checkout is unmodified.

A sibling `tools/hip/gfx1150-hipblaslt-100500.txt` exists (hipBLASLt 1.5.0); it is **not** the
one that matches this host.

## 2. Header vs local hipBLASLt — **MATCH**

| Source | Value |
|---|---|
| Table header (line 2) | `STRATA_HIPBLASLT_TUNING_V1 gfx1150 **100401**` |
| Local runtime, `hipblasLtGetVersion` (measured) | **100401** |
| Local dev header `HIPBLASLT_VERSION_MAJOR/MINOR/PATCH` | 1 / 4 / 1 (`libhipblaslt.so.1.4`) |
| Local arch, `rocminfo` | `gfx1150` |

The runtime number is a measurement, not an inference: a 12-line harness
(`artifacts/hipblaslt-version-probe.txt`, built in `/tmp`, not part of either repo)
calls `hipblasLtCreate` + `hipblasLtGetVersion` and prints `hipblasLtGetVersion = 100401`,
exit 0. **Both halves of the header (arch `gfx1150`, version `100401`) match this host**, so the
table would be accepted by `HipLtTable::load` (`src/prefill/hipblaslt_tuning.hpp:26-73`), which
rejects on both arch and version mismatch (`:61-70`).

## 3. Is it taken automatically on gfx1150? — **No. The default is plain hipBLAS.**

The selection rule is in `src/prefill/gemm.cu:276-339` (`create_hipblaslt_state`):

```cpp
const char* path = std::getenv("STRATA_HIPBLASLT_TUNING");   // gemm.cu:278
...
if (from_package) {
    // Unset or "auto": only Strix Halo (gfx1151) takes the packaged table by itself, the owner's
    // decision of 2026-10-19 ...: on other cards the table changes the answers' last digits for ~1%
    // (gfx1201), so they take it with STRATA_HIPBLASLT_TABLE=on only.
    if (!table_forced && arch != "gfx1151") return nullptr;    // gemm.cu:322
```

Reading it on `gfx1150` with nothing set: `STRATA_HIPBLASLT_TUNING` is unset → the `from_package`
branch is entered → `arch != "gfx1151"` is true → **`return nullptr`**, i.e. no table, and the
prompt GEMMs use plain hipBLAS. `docs/AMD_HIP.md:637` says the same in prose: *"Radeon 890M —
Setup does not use it; point `STRATA_HIPBLASLT_TUNING` at it"*, and `:542` repeats that setup does
not install for gfx1150 at all. `docs/AMD_HIP.md`'s package section also states the general case
that a hand-built engine "has no tuning table".

**Therefore: on this host, with this build and no environment override, the effective default is
plain hipBLAS (fallback), not the table.**

## 4. How to opt in, and how to see which path was taken

| Mechanism | Effect | Source |
|---|---|---|
| `STRATA_HIPBLASLT_TUNING=/abs/path/gfx1150-hipblaslt-100401.txt` | Loads that file directly; `getenv` is checked **before** the gfx1151 gate, so it wins on any card | `gemm.cu:278` |
| `<engine dir>/tuning/gfx1150-hipblaslt-100401.txt` | Found by `own_tuning_dir()` — but **still gated** by `arch != "gfx1151"` unless `STRATA_HIPBLASLT_TABLE=on` | `gemm.cu:260-274, 318-330` |
| `STRATA_HIPBLASLT_TABLE=off` | Never takes the packaged table | `gemm.cu:290` |
| `STRATA_HIPBLASLT_TABLE=on` | Forces the packaged table on a card that has one beside the engine | `gemm.cu:291` |
| `STRATA_HIPBLASLT_VERBOSE=1` | Prints each fallback with its reason (`Lt fallback; no calibration for dtype=… ` / `solution N unavailable …`) | `gemm.cu:351-376` |

Success is announced once at start on stderr:
`prefill gemm: hipBLASLt tuning enabled (<N> rows, gfx1150, version 100401)` (`gemm.cu:336`).
Absence of that line means no table was taken. `docs/AMD_HIP.md:621-622` recommends looking for
`fallbacks=0` under `STRATA_HIPBLASLT_VERBOSE=1`.

## 5. What could NOT be observed here — stated plainly

**The "taken vs fallback" half cannot be observed without a model run.** The decision happens
inside `create_hipblaslt_state`, which runs only when the prefill hipBLASLt path is initialised —
i.e. when the engine loads a pack and reaches the prompt GEMMs. This handoff has no pack
(`pack/full` is absent; AC-5's Control refused with `No model fits this computer…`), and running
a model is out of scope for HO-STRATA-001 (§2). So:

- What **is** established, by measurement: the table exists, its hash matches the pin, and
  both header fields equal the local device and runtime (`gfx1150`, `100401`).
- What **is** established, by reading the pinned source: on `gfx1150` with no override the
  function returns `nullptr` **before any file is opened**, so no table is loaded and the
  fallback is taken. This is a static reading of `gemm.cu:322`, not a runtime observation.
- What is **not** established: the actual start-log line, the `fallbacks=` count, and whether
  every solution id in the 146-line table is valid on this exact hipBLASLt build for this card.
  `docs/AMD_HIP.md:622` warns the smoke test only checks 2 rows and proves no such thing. Those
  three need HO-STRATA-002+ with a model, or a `--load-check`-style start.

No performance number is claimed here, and none could be: this handoff loads no model.
