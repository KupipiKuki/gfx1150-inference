# Model inventory — gfx1150

**Purpose:** the single list of model packs the project uses, their exact bytes,
and whether the signed engine can load them. Evidence bundles cite this file
instead of restating paths.

**Engine pin:** Strata `baf16363` (`build-hip/strata`, SHA256 `d58ee239…`).
Its family switch accepts **`qwen4exp`** and **`qwen35moe`** only:

```text
$ ./build-hip/strata --families
qwen4exp qwen35moe
```

A GGUF whose `general.architecture` is anything else is **not supported** at this
pin, regardless of size or quantization. DEC-021 trigger T1 covers the response.

---

## 1. Supported

| Family (GGUF arch) | Model | Quant | Size (bytes / GiB) | SHA256 | Status |
|---|---|---|---|---|---|
| `qwen35moe` | Qwen3.6-35B-A3B | UD-Q4_K_XL | 22,853,663,008 / 21.28 | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` | **measured** — HO-007, 32 tokens, GTT peak ~26.2 GiB |

Path: `/home/kupipi/Documents/models/gguf/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`
(re-verified 2026-11-17; see `evidence/HO-STRATA-007/artifacts/model-reverify.txt`).

`qwen4exp` (Qwen3.8-Flash-Next) is supported by the engine but **no pack is
downloaded**; no test bed requires it under DEC-003.

## 2. Downloaded, unsupported at the pin

These are the DEC-003 test beds. The files are intact; the engine has no family
path for them. Running one is a **probe** (HO-STRATA-008), not a test.

| GGUF arch | Model | Quant | Size (bytes / GiB) | SHA256 |
|---|---|---|---|---|
| `llama` | Mixtral-8x7B-v0.1 | **Q3_K_M** | 20,363,355,584 / 18.96 | `542d24532f63219db9f530bd2819be9c74f514919ab661dc5162cef844bac38b` |
| `llama` | Mixtral-8x7B-v0.1 | Q4_K_M | 26,441,532,864 / 24.63 | `5e066c60d89d904db46c3bf577661040578a223a5a39ba3fd23ff091549767f0` |
| `deepseek` | DeepSeek-MoE-16B-base | **Q4_K_M** | 10,850,181,856 / 10.10 | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| `deepseek` | DeepSeek-MoE-16B-base | Q8_0 | 17,413,944,032 / 16.22 | `7734995ec7ca26cef38e7c2fa6654fdac97cfc2809ddee6451cd172d5db4ffa3` |

Recommended low-tier artifact per family is the **bold** row: Mixtral at Q3_K_M
keeps ~7 GiB of headroom under the Qwen run's 26.2 GiB GTT peak (ceiling
45.97 GiB), and DeepSeek at Q4_K_M matches the project's smallest-practical-quant
convention. The Q4_K_M Mixtral and Q8_0 DeepSeek files are kept as a fallback if
a smaller quant fails for a reason unrelated to support.

### Paths (Hugging Face cache)

```text
~/.cache/huggingface/hub/models--TheBloke--Mixtral-8x7B-v0.1-GGUF/snapshots/38762dea…/
~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397c…/
~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q8_0-GGUF/snapshots/36e786fd…/
```

The cache is not a stable interface — a prune would remove them. To pin a pack
for an evidence bundle, copy or re-fetch it under
`models/gguf/<family>/` with `hf download --local-dir` and record that path, as
HO-007 did for Qwen.

## 3. Not a test bed

`Mistral-7b/` holds **Mistral 7B** (dense, v0.2 and v0.3, Q4_K_M, 4.37 GB each).
It is neither a DEC-003 bed (those are Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek) nor
a supported family. Keep it out of test claims; the names are one letter apart
and that difference is the whole point of the MoE bed.

## 4. Rules

- A pack may be cited as evidence only with its SHA256 and the path it was read
  from on the date of the run.
- A model that the engine does not list in `--families` is **unsupported**, even
  if it loads or produces text. "It ran" is not "it is supported" (DEC-021).
- No weights in git; hashes only.
