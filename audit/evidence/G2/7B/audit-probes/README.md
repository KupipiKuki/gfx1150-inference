# Auditor probes — 7B tokenizer (G2)

**Auditor:** DeepSeek V4.1 Flash
**Date:** 2026-11-05
**Candidate:** `70c5ab2` · **Tip:** `e091fcf` · **Parent:** `8426ec6`

This directory is the primary auditor’s independent evidence for the 7B
review. It is not the coder’s or QAQC’s bundle (those are one level up).

| File | What it is |
|---|---|
| `probe_reference_diff.py` | Candidate vs pinned `llama-tokenize` on 11 mixed-text and common-text cases |
| `probe_commands.log` | Reference build/version, the 11/11 SPM golden replay, the differential output, candidate lanes, fixture provenance |

The reference binary is built from the same pinned commit that produced the
7A-3 goldens:
`llama.cpp@149f5641b931aaf33697d70f9abc90c3e5300247`. It reproduces all 11
SPM goldens exactly, which is why its disagreement with the candidate on
common words and mixed special text is a real defect, not a version mismatch.

Result: **10/11 probe cases differ**. See the audit report and G2 signoff.

To reproduce:

```bash
# build the pinned reference (see probe_commands.log for the exact commands)
export LLAMA_TOKENIZE=/path/to/llama-tokenize
export STORIES260K_GGUF=/path/to/stories260K.gguf
python3 audit/evidence/G2/7B/audit-probes/probe_reference_diff.py
```
