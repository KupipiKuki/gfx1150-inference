# Reference server — pinned 2026-11-21

A llama.cpp server on this machine reproduces the HO-010 oracle for the DeepSeek
pack. It is a **convenience reference for iteration**, not the authority — see §4.

## 1. Pin

| Field | Value |
|---|---|
| Front endpoint | `http://127.0.0.1:9931` (`/health` → `{"status":"ok"}`) |
| Process | `llama serve` (manager), pid varies; parent of the worker |
| Worker | child process on `127.0.0.1:33739` — **ephemeral, do not target it** |
| Binary | `/home/kupipi/.local/bin/llama` |
| Binary SHA256 | `3d85a8b8e7bfbb97d7857456599147c5c446e9bc11dafbdbcaed57b1d243c7a3` |
| Version | `1.0.0-dev (build 12607, commit 1fdda89a4)`, Clang 24.0.0, x86-64 |
| Mode | router (`--hf-repo`), lazy load on first request |
| Model id | `Lucy-in-the-Sky/deepseek-moe-16b-base-Q4_K_M-GGUF:Q4_K_M` |
| Model file | `~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397c…/deepseek-moe-16b-base-q4_k_m.gguf` |
| Model SHA256 | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| Model size | 10,850,181,856 B — matches `workflow/MODELS.md` |

**Version skew:** the oracle was produced with llama.cpp **`b12527`
(`78e05298…`)**; this server is **`b12607` (`1fdda89a4`)** — 80 builds later. They
agree on the case below, but they are not the same binary.

## 2. The call that works

```bash
curl -s http://127.0.0.1:9931/completion \
  -H 'Content-Type: application/json' \
  -d '{"model":"Lucy-in-the-Sky/deepseek-moe-16b-base-Q4_K_M-GGUF:Q4_K_M",
       "prompt":[549,6077,280,7239,317],"n_predict":16,"temperature":0}'
```

```json
{"content":" Paris.\nParis is the capital of France.\nParis is the capital of",
 "tokens_evaluated":5,"tokens_predicted":16,"stop":true,"temperature":0.0}
```

Re-tokenized (the response carries **no** `tokens` array):

```text
POST /tokenize {"model":"…","content":"<content>"}
→ [8913,13,185,40619,317,254,6077,280,7239,13,185,40619,317,254,6077,280]
```

Identical to `workflow/evidence/HO-STRATA-010/artifacts/runs/run1.txt`
(`gen:` line, 16/16). Two consecutive calls returned byte-identical content.

## 3. The trap: never send text

| Call | Result |
|---|---|
| `/tokenize` with the prompt text | `[549,6077,280,7239,317]` — correct, no BOS |
| `/completion` with a **token array** | `tokens_evaluated: 5` — correct |
| `/v1/completions` with **text** | `prompt_tokens: 6` (BOS prepended) and a **different** continuation (`" a city of art, culture, and"`) |

The tokenizer is right; the text completion path adds a BOS. Any parity run that
sends text will fail for a reason unrelated to the engine.

## 4. Authority

- **Authoritative:** the CLI oracle (`oracle_harness` at llama.cpp `b12527`),
  because it is the pin the HO-010/HO-011 dumps and hashes were produced with.
- **Convenience:** this server — same model file, different llama.cpp build, no
  dump/logits access, ephemeral worker port, lazy load (first call pays ~8 s).
- For S4/S5 gates, the reference values must come from the pinned CLI oracle or a
  rebuild of it; the server is for fast iteration and for sanity checks between
  gate runs. If the server is ever used as a gate reference, re-derive the
  expected values with it and record the version alongside them.

## 5. Reproducing the server

Not installed from this repo. If it must be rebuilt, pin
`llama.cpp@1fdda89a4` (build 12607), build with the same Clang 24.0.0 toolchain,
and re-run the §2 call: the 16 IDs must match `8913 13 185 40619 317 254 6077 280
7239 13 185 40619 317 254 6077 280` before it is trusted.
