# Session handoff — 2026-11-24 (after HO-014 / S4a)

**Paste this file into a new session with the `architect` agent selected.**
Reading order: this file → `workflow/STATUS.md` → `workflow/DECISIONS.md`
(DEC-042/043/044 are this session's) → `workflow/handoffs/HO-STRATA-014-APPROVAL.md`.

---

## 1. Where the project is

gfx1150 only. Strata pinned at `baf16363` (`/home/kupipi/Documents/git/strata`);
this repo holds the workflow, evidence and the exported patches.

```text
main                       d1a974d   (plus this session's work-package branch, unmerged)
work branch                wp/strata-014-deepseek-s4   @ e6dfc88   (pushed? no — local)
Strata branch              strata-014-deepseek-s4      @ db087d511
signed binary              build-hip/strata  d58ee239…  (never rebuilt)
reference server           UP — 127.0.0.1:9931, 16/16 verified 2026-11-23
f32 oracle pack            /tmp/opencode/deepseek-moe-16b-f32.gguf  65.5 GB, 8cd778a7…
llama.cpp tree             /tmp/opencode/llama-ref @ 78e05298…  (build + build-tools)
```

**DeepSeek S4 is authorised and half-delivered:** S4a (block 0) is **DONE, SIGNED
2026-11-24**; **S4b (MoE blocks 1–27) is the next handoff, HO-STRATA-015, not yet
written.** `model_family_runs()` is still `false` — the pack still does **not**
run normally, and the named refusal is unchanged.

## 2. What this session proved

| Handoff | Result | State |
|---|---|---|
| HO-014 | **S4a**: dedicated `src/deepseek/` path, block 0 parity **9.76e-05** ≤ 5e-3 | **DONE, SIGNED** (DEC-044) |
| DR-014-1 | T1 confirmed (no MHA path in the generic engine) + T2 crossed → dedicated path approved, stage split, `dsref.cu` cut | APPROVED (DEC-043) |

The gate earned its cost twice:

1. **DR-1** stopped a 5k-line increment at the *plan* stage instead of at the
   gate, and produced a split that gates the non-MoE machinery first.
2. **DEC-044** — the first AC-5a failed at 1.83e-2 … 1.23e-1. The signed Q4_K
   oracle turned out to compute with **q8_K-quantised activations** (reproduced
   to 1.2e-7 / 3.3e-7), so it was the *reference* that was lossy. The reference
   was replaced with an f32 conversion of the same pack (**bound untouched**), and
   the gate immediately exposed a real **NEOX-vs-NORM RoPE** bug. Against the
   Q4_K reference that bug was invisible.

## 3. Decisions in force (this session)

| DEC | Meaning |
|---|---|
| **042** | S4 pre-registered: `--parity-run` gate (flag stays false until S5), 5e-3 bound, Strata edits authorised for HO-014 only |
| **043** | T1/T2: dedicated `src/deepseek/` path on Route 2; split S4a/S4b; `dsref.cu` cut; engine stays simple; re-review if shared code must change |
| **044** | The **layer** gate uses an arithmetic-exact reference (f32 conversion); the Q4_K dumps stay the **token** authority for S5; the engine stays exact f32 (no q8_K emulation) |

## 4. What S4b (HO-015) must carry — binding

From the audit (`reports/audit/HO-STRATA-014-audit.md`) and QAQC, all already
converted to criteria by `HO-STRATA-014-APPROVAL.md` §4:

- **A4 (blocking):** `compare_layers.py` derives `N` as the smallest divisor of
  `R`, so an S4b dump (`4 × 29 slots`, `R = 116`) reads as `N = 1` and **passes on
  block 0 alone**. HO-015 must pass `--slots 29` (or read the engine's
  `N layers + the input` line) and assert `N == 28` before comparing.
- **A1:** record the oracle's generating command (`oracle_nodes … --n 0
  --dump-layers`) in the bundle. **A2:** `## Commit pins` table with every digest
  inlined, so `B6-pins` runs (it silently skips flat files). **A3:** no
  caller-supplied `--bound`; echo the bound used.
- **QAQC F2:** `--parity-run` without `--dump-layers` is refused only for a
  `deepseek` file; hoist the check so a supported model cannot silently ignore it.
- **QAQC F3:** `upload_weight()` keeps the quantized payload **and** the f32 copy,
  and `q8_1_scratch` is unused — at 28 blocks that is ~76 GB against 92 GB. Drop
  the dead allocations or dequantize per block before loading the MoE.
- **A6:** the manifest must say this parity validates dequant→f32 GEMV, not the
  production quantized GEMM.
- MoE semantics to get right: **top-6 with no renormalisation over the selected
  set**, 2 shared experts inside the FFN branch, dense block 0 already proven.
  Gate: layers 1–27 (108 cells) then all 112, same 5e-3.

## 5. Reproduce the reference (do not rebuild it blind)

```bash
# f32 conversion (already on disk; ~15 s, 65.5 GB out)
/tmp/opencode/llama-ref/build-tools/bin/llama-quantize --allow-requantize \
  <Q4_K_M pack> /tmp/opencode/deepseek-moe-16b-f32.gguf f32
# oracle dump (4 tokens, block-0..27 residuals)
g++ -O2 -std=c++17 workflow/evidence/HO-STRATA-014/scripts/oracle_nodes.cpp \
  -o /tmp/opencode/oracle_nodes -I/tmp/opencode/llama-ref/include \
  -I/tmp/opencode/llama-ref/ggml/include -L/tmp/opencode/llama-ref/build/bin \
  -lllama -lggml -lggml-base -lggml-cpu -lpthread
LD_LIBRARY_PATH=/tmp/opencode/llama-ref/build/bin /tmp/opencode/oracle_nodes \
  --model /tmp/opencode/deepseek-moe-16b-f32.gguf --tokens 549,6077,280,7239 --n 0 \
  --dump-layers <out.bin>        # expect a4c56b9d…
```

The Q4_K dump (`db6eccb3…`, HO-010) regenerates identically and is the
**informative floor** (~2.05e-2), never a gate.

## 6. Open items

1. **Merge HO-014** per DEC-040 via a `merge/*` PR — **blocked**: 3 of 4 required
   GitHub checks cannot start (Actions billing, 2026-11-23). Fix in Settings →
   Billing, then open the PR. Nothing in code depends on it.
2. **HO-015 (S4b)** — write it with §4 above as criteria, then `coder-primary`.
3. Carried from earlier sessions, still open: HO-011's two unlisted artifacts
   (keep `--all` red, do not tune the tool); HO-010 B-1/B-2/B-4; HO-012 F2
   (ranges live in `geometry_from_gguf`, verify at S4b for the MoE fields).
4. `workflow/SESSION_HANDOFF_2026-11-23.md` is now committed for the record.

## 7. Budget notes

- This session cost **one** gate cycle plus a long numerics bisection
  (~40 coder turns across four sessions, one audit materialised by hand). The
  bisection was worth it: it changed a wrong reference rather than a right bound.
- Cheapest order from here: write HO-015 → coder (block 1 first, dump, compare)
  → `check_bundle.py --strict` → architect verification → QAQC → auditor.
- Do not relax 5e-3, do not emulate q8_K, do not flip `model_family_runs()` before
  S5's exact-token gate.

## 8. First message (copy-paste)

```text
Resume the Strata project. Read workflow/SESSION_HANDOFF_2026-11-24.md, then
STATUS.md and DECISIONS.md (DEC-042/043/044). Verify: signed binary d58ee239…,
check_bundle --all red only on HO-011, reference server 16/16. Then write
HO-STRATA-015 (S4b, MoE blocks 1–27) with approval §4 A1–A4 + QAQC F2/F3 as
criteria, and gate it with check_bundle.py --strict. Do not change the 5e-3
bound or model_family_runs().
```
