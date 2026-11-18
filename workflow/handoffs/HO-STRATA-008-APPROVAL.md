# Architect approval — HO-STRATA-008

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-008 — family probe on unsupported GGUFs |
| **Architect** | architect (session model; WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-18 |
| **Decision** | **SIGNED** → state `DONE`; recorded as **DEC-026** |
| **Evidence** | `workflow/evidence/HO-STRATA-008/` at `3eafe26` |
| **Branch / base** | `wp/strata-008-family-probe` / `3660925` |

## 1. Result

| Family | GGUF arch | Attempt | Exit | Verdict | Justifying line |
|---|---|---|---|---|---|
| Mixtral 8x7B Q3_K_M | `llama` | `--max-new 8` | 2 | **REFUSED** | `strata generate: --native requires --ple-gguf (the PLE key is native too), and no shard of the model holds per_layer_token_embd.weight` |
| DeepSeek-MoE-16B Q4_K_M | `deepseek` | `--max-new 8` | 2 | **REFUSED** | same |

No tokens, no load, no allocation. The first attempt (`--n 8`) is kept and
labelled `CLI parse — family path not reached`: `--n` belongs to the `qwen35`
path (`q36_engine.cu:3902`); the generic parser takes `--max-new`.

## 2. What the refusal actually is

Not a missing family string — a **loader contract**. `generate.cpp:4810-4823`:

```cpp
if (o.ple_gguf.empty() && !o.no_ple) {           // look for the PLE table by name
    if (model.find("per_layer_token_embd.weight", &at) != nullptr) o.ple_gguf = o.native_shards[at];
}
if (o.no_ple || o.ple_gguf.empty()) {            // no table -> refuse
    ... "requires --ple-gguf ... no shard holds per_layer_token_embd.weight" ...
    return 2;
}
```

The generic native path **requires a per-layer-embedding table**. Mixtral and
DeepSeek do not have one, because PLE is a model-architecture component, not a
file the user can supply. `--no-ple` is a diagnostic ablation (`generate.cpp:1178`)
and is itself refused at 4819 — there is no bypass.

So the build has three shapes: the `qwen35` path for `qwen35moe`, the PLE-shaped
generic path for `qwen4exp`, and **nothing** for `llama`/`deepseek`. Supporting
either family means adding a model class, not flipping a switch.

## 3. The feared outcome did not happen

The handoff's worry was a silent dense fallback on Mixtral's `llama` arch. It did
not occur: the engine refuses before allocating, so there is no wrong-answer risk
from this build. That is a cleaner failure than predicted, and worth stating
plainly.

## 4. Criteria

| # | Criterion | Evidence | Architect |
|---|---|---|---|
| 1 | Signed binary, clean checkout | `manifest.md` §1; `git status --porcelain` empty; `d58ee239…` | PASS |
| 2 | Raw stdout/stderr/exit per attempt | `artifacts/*.stdout.txt`, `*.stderr.txt` (first + generic) | PASS |
| 3 | Classification with justifying line | `manifest.md` §3 | PASS (after RW-008-1) |
| 4 | Token IDs if any | none generated; recorded as none | PASS |
| 5 | Envelope + `dmesg` | `artifacts/amd-smi-envelope.txt`; idle envelope | PASS |
| 6 | Hashes match `MODELS.md` | `sha256sum -c` 17/17 OK | PASS |
| 7 | No source change / tuning / support work | diff; command log | PASS |
| 8 | No performance/support claim | report review | PASS |

## 5. Rework note

`RW-HO-STRATA-008-1` was needed because the first attempts measured the CLI
surface, not the engine. The rework did not change scope; it changed the flag to
the one the generic parser accepts. The handoff's state field was left at
`REWORK` by the coder after the re-run; the architect corrected it at this gate
and added the closing log line. Recorded here rather than silently.

## 6. Decision recorded

**DEC-026**: the probe is accepted as T1 evidence; the build cannot load non-PLE
families; whether support is a localized patch or a model class is unsettled and
belongs to a scoped investigation (HO-006), which remains held under DEC-016.

## 7. Limits

- One quant per family; one prompt; 8-token cap; refusals only — nothing about
  model quality, throughput, or support.
- `qwen4exp` (Qwen3.8-Flash-Next) was not probed (no pack downloaded) and remains
  supported-but-unmeasured.
- No claim that Mixtral or DeepSeek "do not work" in general; the claim is about
  this build's loader.

| Role | Signature | Date |
|---|---|---|
| Architect | architect | 2026-11-18 |
