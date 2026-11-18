# RW-HO-STRATA-008-1 — the probe measured the CLI, not the engine

| Field | Value |
|---|---|
| **ID** | RW-HO-STRATA-008-1 |
| **Type** | REWORK |
| **State** | **OPEN** |
| **Created (UTC)** | 2026-11-18 |
| **From → To** | Architect → Primary Coder |
| **Original handoff** | HO-STRATA-008 (`CODER_DONE`, commit `deb4b90`) |
| **Re-checker** | Architect (evidence question; QAQC `N/A` for this handoff) |

## 1. Failed criterion

**AC-1/AC-3** — "both attempts executed on the signed binary" and "each attempt
classified REFUSED / LOADED-UNSUPPORTED / FAILED-OTHER with the evidence line that
justifies it".

The classification `REFUSED` is **not supported by the evidence**. The engine
never looked at either model.

## 2. The exact evidence

`workflow/evidence/HO-STRATA-008/artifacts/mixtral-q3_k_m.stderr.txt:1`:

```text
unknown argument: --n
```

and the recorded command (`workflow/evidence/HO-STRATA-008/commands.log:524`):

```text
... ./build-hip/strata --native .../mixtral-8x7b-v0.1.Q3_K_M.gguf \
    --tokens 760,6511,314,9338,369 --n 8 --max-context 512
```

`--n` is **not a flag of the generic engine**; it belongs to the `qwen35` path:

```text
src/qwen35/q36_engine.cu:3902     else if (a == "--n") n_gen = std::atoi(next().c_str());
src/program/generate.cpp          (generic parser: only "--max-new", no "--n")
```

and the family switch is decided before either parser runs:

```text
src/program/generate.cpp:3644-3656
    if (qwen35) return strata::qwen35::run(argc, argv);
```

So what happened is: neither GGUF took the `qwen35` path (good, expected), the
generic parser ran, and it rejected a qwen-only flag on its first argument. That
is a **CLI** refusal, not a family refusal. The bundled `usage()` output in the
same stderr file is the generic parser's, which confirms the path.

The quiet, useful signal — neither file dispatched to `qwen35` — is worth keeping,
but it does not answer the handoff's question: does the engine **refuse** a
non-`qwen35` architecture, or **load** it on the generic path.

## 3. Required fix (only this)

Re-run both attempts with the **generic** flag set, so the engine reaches the
model:

```bash
cd /home/kupipi/Documents/git/strata
LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib timeout 600 ./build-hip/strata \
  --native <GGUF> --tokens 760,6511,314,9338,369 --max-new 8 --max-context 512 \
  > <out>.stdout.txt 2> <out>.stderr.txt
echo "exit=$?"
```

- Mixtral: `.../models--TheBloke--Mixtral-8x7B-v0.1-GGUF/snapshots/*/mixtral-8x7b-v0.1.Q3_K_M.gguf`
- DeepSeek: `.../models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/*/deepseek-moe-16b-base-q4_k_m.gguf`

Then classify with the raw output, and add one line to the manifest explaining the
two-parser split (`--n` is qwen35-only; the generic parser takes `--max-new`), so
the first attempt is understood rather than erased.

## 4. What must not change

- No source edit, no rebuild, no flag tuning beyond the two commands above.
- Do not delete the first attempt's artifacts; keep them and label them
  **"CLI parse — family path not reached"**.
- No fallback quant unless the new attempt fails with an allocation/OOM error.
- No support/quality/performance claim; `LOADED-UNSUPPORTED` is a description of
  the engine's path, not a verdict.

## 5. Evidence required

New artifacts alongside the existing ones: `<family>-generic.stdout.txt`,
`<family>-generic.stderr.txt`, the `amd-smi` sampling for each attempt, `dmesg`
before/after, and the refreshed `manifest.md` / `hashes.txt` (immutable files
only; pin `workflow/MODELS.md` by commit per DEC-024).

## 6. Re-check

Architect re-reads the two new stderr files and the token IDs, confirms each
classification is quoted from raw output, and signs or reworks. A second failure
on this criterion escalates to the owner.

## 7. Log

- 2026-11-18 Architect: opened after reading `commands.log:524` and the engine's
  family switch; the `--n` refusal proves the CLI path, not the model outcome.
