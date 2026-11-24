# HO-STRATA-014 — DeepSeek S4a: forward skeleton + block-0 layer parity

| Field | Value |
|---|---|
| **ID** | HO-STRATA-014 |
| **Type** | ARCHITECT_TO_CODER |
| **State** | **IN_PROGRESS** (S4a) — READY (owner authorized 2026-11-23) → IN_PROGRESS → DEVIATION (DR-HO-STRATA-014-1 **APPROVED**, DEC-043: split into S4a/S4b, `dsref.cu` cut) → IN_PROGRESS again. First gate is AC-5a (layer 0, 4 cells) |
| **Created / updated (UTC)** | 2026-11-23 / 2026-11-23 |
| **From → To** | Architect → Primary Coder (`coder-primary`) |
| **Work package** | `deepseek-s4a` |
| **Branch (workflow)** | `wp/strata-014-deepseek-s4` / base `main` @ `d1a974db0ace2cc78d77efd1eec123ea93bb865b` |
| **Branch (Strata checkout)** | `strata-014-deepseek-s4`, cut from `strata-012-deepseek-s1` @ `bac859ef91fb0d432eaf9675fc769bc3afe313cf` (S1–S3 included; never `main`) |
| **Priority / timebox** | P1 · 2 working days coder time, + 1 day per gate cycle |
| **Owner task** | OT-STRATA-001 (checkpoint 4 — "a DeepSeek number") |
| **Plan** | `planning/strata-engine/13-family-support-test-plan.md` §4 **S4** |
| **Evidence gate** | `workflow/tools/check_bundle.py` (DEC-041), bundle **must** pass `--strict` before `CODER_DONE` |

## 0. What this handoff is, and what it is not

DeepSeek-MoE-16B is *recognised* but does not *run* (DEC-037). This handoff makes
the **forward pass exist** and proves it **layer by layer** against the HO-010
oracle. That is stage S4 of the family plan.

It is **not** the support claim. `model_family_runs()` stays `false`; normal runs
keep the named refusal; `--families` keeps printing `qwen4exp qwen35moe`. Exact
**token** parity is S5 (HO-STRATA-015) and is the only thing that can flip the
flag. S4 can pass and the family still not be supported — that is the intended
shape, not an oversight (DEC-042).

The tolerance is **pre-registered in §12 before any run**. Seeing a number and
then proposing a bound is the failure mode this section exists to prevent.

**Amended 2026-11-23 (DEC-043, after AC-10).** The coder found that the generic
engine has no standard-MHA path (T1) and that a dedicated `src/deepseek/` engine
crosses T2. The architect approved the dedicated path and **split the stage** so
that the non-MoE machinery is gated first:

| Increment | Handoff | Scope | Gate |
|---|---|---|---|
| **S4a** | **this file** | skeleton, tensor mapping, geometry, RMSNorm/rope/MHA, **block 0 dense FFN**, `--dump-layers` plumbing, `--parity-run`, tests, comparison tool | **layer 0** at 4 positions — 4 cells, max relative L2 ≤ 5e-3 |
| S4b | HO-STRATA-015 | the MoE blocks: router, top-6 **without** renormalisation, 2 shared experts, expert matmuls | layers 1–27 (108 cells), then the full 112-cell AC-5 |

`dsref.cu` (an in-repo reference implementation) is **dropped from both**: the
llama.cpp dumps are the reference, and a second implementation would double the
parity work before any optimisation exists (DEC-043). The engine stays simple —
no pooling, no expert cache/streaming, no batching, no MTP, no new fast-path
kernels.

## 1. Scope (in)

### 1.1 A forward path for `deepseek`

Implement the forward pass for the pack's geometry, taken from metadata — never
from constants that happen to match:

| Property | Value | Consequence |
|---|---|---|
| blocks | 28 | 28 residual updates, `slot 1..28` in the dump. **S4a runs block 0 only** (`slot 1`); blocks 1–27 are S4b |
| hidden | 2048 | comparison width |
| attention | MHA 16/16 heads, **no GQA** | head dim 128; no KV broadcast path |
| rope | base 1e4 | no scaling, no yarn |
| norm | RMSNorm, eps 1e-6, pre-norm | — |
| block 0 | **dense**, FF 10944 | a loader that assumes "every block has experts" mis-maps it — this is S4a's FFN |
| blocks 1–27 | **MoE**: 64 experts, top-6, **2 shared**, expert FF 1408 | **S4b (HO-STRATA-015)**; shared experts always active; top-k selection and whether the router normalises over the selected set are **read from the cited graph (§1.1), never assumed** |

**Arithmetic source of truth:** the oracle's llama.cpp tree at
`78e05298f0d68abff41d08d79fa7469264b2aff0` (HO-010). Extract the `deepseek`
graph builder and its FFN/attention structure into
`artifacts/llama-ref-graph.md` with file:line citations, and implement from
those citations. Do not port from memory, blog posts or `docs/DEEPSEEK41.md`
(that document describes the removed **V4.1-Flash** engine, prior art only).

Reuse existing kernels (dequant, GEMM, RMSNorm, rope, attention) rather than
writing new ones wherever the arithmetic is identical.

### 1.2 Which code shape — **decided: (B)**

Two shapes were acceptable; the coder reported at AC-10 (2026-11-23) and the
architect approved **(B)**, because (A) is not a localized patch:

- **(A) extend the generic path** — rejected: it has **no standard-MHA path**.
  `family_layout.hpp:178-181` makes every layer `Attention` (QSA) or `Gdn`, and
  QSA requires `attn_q_norm` / `attn_k_norm` / `indexer.*` (`:262-269`) that the
  DeepSeek layout does not declare (`:196-220`). Adding an MHA layer kind to the
  generic engine is a structural change (T1) with regression risk to `qwen4exp`.
- **(B) a dedicated `src/deepseek/` path**, dispatched from `generate.cpp` for
  `deepseek` GGUFs **only** under `--parity-run`, in the `src/qwen35` mould. This
  is what DR-HO-STRATA-014-1 proposed and DEC-043 approved, with the split, the
  `dsref.cu` cut and the simplicity condition.

### 1.3 Diagnostic run mode (gating, not support)

A new CLI switch, `--parity-run`, makes a recognised-but-not-supported family
runnable **for parity work only**:

- `--parity-run` is accepted only together with `--dump-layers PATH`; without the
  dump path it is a usage error (exit ≠ 0);
- with `--parity-run`, the engine prints **one stderr line** before the first
  token, e.g. `strata generate: parity run: architecture 'deepseek' is not
  supported; this path exists for HO-STRATA-014/015 parity only`;
- `model_family_runs()` is **not** changed, so a run without `--parity-run` still
  refuses by name with today's exact message;
- `--parity-run` never bypasses the unknown-family refusal.

### 1.4 Layer dump contract

Reuse `--dump-layers` (`generate.cpp:9969-9985`, `:21888`). Its layout is
`[position][slot][hidden]`, `n_layers + 1` slots, **slot 0 = the residual the
layer loop was entered with** (post-embedding), **slot `l+1` = after block `l`**.

The oracle dumps `l_out-<il>` for `il = 0..27`: `[position][block][hidden]`,
**no embedding slot**. The mapping is therefore

```text
strata slot l+1  ↔  oracle block l        (l = 0 … 27)
strata slot 0    =  not comparable (the oracle does not dump it)
```

A comparison that reshapes the engine dump as `[-1, 28, 2048]` is off by one and
will "fail every layer" for a reason that is not the engine's. Drop slot 0 first.

**How many slots:** the engine dumps **what it computed** — `N + 1` slots, where
`N` is the number of blocks the engine actually ran. S4a computes block 0, so
`N = 1` and the file is `2` slots per position; S4b raises `N` to 28. The
comparison tool derives `N` from the dump size and checks oracle blocks `0…N-1`
against engine slots `1…N`. Never pad uncomputed slots to look like a full stack.

### 1.5 Comparison tool

Add `workflow/evidence/HO-STRATA-014/scripts/compare_layers.py` (committed, stdlib
+ numpy, reproducible) with this CLI:

```text
compare_layers.py --oracle <oracle.bin> --dump <engine.bin> [--shape-only]
```

It derives `N` from the engine dump, prints, per the §12 contract: shape check,
NaN/Inf check, the `28 × 4`-capped per-cell relative L2 errors for the blocks in
scope, median, max, worst cell `(layer, position)`, first cell above the bound (if
any), and a single `RESULT: PASS|FAIL`. `--shape-only` stops after the size/NaN
checks. Copy the shape and verdict logic from `tools/qwen35/compare_dumps.py`; do
not import it (the evidence must stand alone).

### 1.6 Tests

Extend the existing suite for the new path: a unit test that the dense-first-block
tensor expectations are enforced (block 0 has no `*_exps` tensors, block 1 does),
and one that `--parity-run` without `--dump-layers` is refused. Keep
`tests/core/model_family_test.cpp` and the geometry test green.

## 2. Out of scope

- **Token parity, logits, KL, sampling, the lm_head** — S5 (HO-STRATA-015). S4's
  gate is the residual stream, not a generated token.
- **`model_family_runs()` / `--families` / the refusal text** — unchanged in S4.
  Flipping them is S5, after zero mismatches.
- Any tokenizer change (DeepSeek's `deepseek-llm` pre-tokenizer already works;
  S4 is driven by token IDs only).
- Any `qwen4exp` / `qwen35moe` behaviour change; any OLMoE work.
- Performance, throughput, memory or support claims of any kind.
- Rebuilding `build-hip/` or touching the signed binary; downloading packs;
  model conversion; quantising; MTP/draft models; batching/serving.
- Editing any existing evidence bundle, handoff, report, or `DECISIONS.md`.
- Widening the §12 bound. A bound that fails is a rework or a deviation.

## 3. Inputs

| Input | Path / hash | Status |
|---|---|---|
| Pack, DeepSeek-MoE-16B-base Q4_K_M | `~/.cache/huggingface/hub/models--Lucy-in-the-Sky--deepseek-moe-16b-base-Q4_K_M-GGUF/snapshots/1f2b397c…/deepseek-moe-16b-base-q4_k_m.gguf`, 10,850,181,856 B, `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5`, 363 tensors | available |
| **Oracle layer dump (the gate)** | **exact-arithmetic reference, DEC-044**: `artifacts/runs/deepseek_f32_p1_4_layers.bin` — same pack converted with `llama-quantize --outtype f32`, same llama.cpp pin, same harness, shape `[4][28][2048]` f32 (hash recorded when produced) | to produce |
| Oracle layer dump (Q4_K, **informative floor only**) | `workflow/evidence/HO-STRATA-010/artifacts/runs/deepseek_p1_4_layers.bin`, `db6eccb3e8a949827c5c961fc732159daa1a0a9d52f7f88156d669845e0c7c73`, `[4][28][2048]` | committed — **not** the layer gate (DEC-044) |
| Oracle prompt for the dump | tokens `549,6077,280,7239` (4 positions) | committed |
| Oracle logits dump (S5 only) | `…/runs/deepseek_p1_logits.bin`, `5334baef…`, `[16][2][2]` | committed |
| Oracle token line (S5 only) | `gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280` | committed |
| Oracle harness source | `workflow/evidence/HO-STRATA-010/artifacts/oracle_harness.cpp`, `bdc9303d…` | committed |
| llama.cpp pin (semantics) | `78e05298f0d68abff41d08d79fa7469264b2aff0` (tag `b12527`), CPU build recipe in HO-010 §1 | repo may be gone; the **dumps are the authority** |
| Geometry / recognition | HO-STRATA-012 (`bac859ef9`), `include/strata/core/family_layout.hpp` deepseek block | in base branch |
| Qwen regression | HO-STRATA-012 `commands.log` C8 (32 token IDs recorded) | committed |
| Threshold rationale | §12 of this file; `docs/GDN_CONTRACT.md:78` for the project's own "floor or 3× incumbent" convention | in Strata tree |
| Capture rules | DEC-041 §2 (write to `/tmp`, move with `;`, rebuild derived files, rehash last) | record |
| Base (workflow) | `main` @ `d1a974db0ace2cc78d77efd1eec123ea93bb865b` | available |

The oracle was built CPU-only. That is the authority (DEC-038): do **not**
re-derive expected values from the live `:9931` server, and do not use it for the
gate.

## 4. Acceptance criteria

`<pack>` is the §3 pack path; `<engine dump>` is AC-3's
`/tmp/opencode/s4-dump.bin`. Every command is run from the Strata checkout with
`LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib` unless stated.

| # | Criterion | Command / check | Expected |
|---|---|---|---|
| **AC-1** | Builds in the family build directory; the signed binary is untouched | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)`; `sha256sum build-hip/strata` | build exit 0; `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` unchanged |
| **AC-2** | Normal runs still refuse, unchanged | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --native <pack> --tokens 1,2,3 --max-new 32 --max-context 1024`; `--families` | exit 2; the HO-012 C6 refusal line **verbatim**; `--families` prints exactly `qwen4exp qwen35moe` |
| **AC-3** | The diagnostic mode is explicit and cannot be reached by accident | `--parity-run` **without** `--dump-layers`; `--parity-run` on an unknown-arch GGUF; `--parity-run --native <pack> --dump-layers /tmp/opencode/s4-dump.bin --tokens 549,6077,280,7239` | first two exit ≠ 0 with a usage/refusal line; the third exits 0 and prints the one-line "not supported; parity only" warning on stderr |
| **AC-4** | Dump obeys the layout contract | `stat -c%s` the dump; the run's `layers dumped` stdout line; `compare_layers.py --shape-only` | size is `k × (N+1) × 2048 × 4` B with `k ≥ 4` and `N` = blocks computed (**1 in S4a** → 16,384 B per position); the line reads `1 layer + the input x 1 streams x 2048`; zero NaN/Inf in every dumped slot. The comparison uses the **first 4 records** (the prompt positions) — if the CLI cannot express "no generation", run `--max-new 1` and ignore the 5th record; never trim the dump file |
| **AC-5a** | **Layer parity, block 0** (S4a's gate) | `python3 workflow/evidence/HO-STRATA-014/scripts/compare_layers.py --oracle workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin --dump <engine dump>` | `RESULT: PASS`; **N = 1, 4 cells** (`l=0`, `p=0…3`); max relative L2 **≤ 5e-3**; every cell finite; median and max reported; every cell's value printed; **no cell above the bound** (§12). The Q4_K oracle (`HO-STRATA-010` `deepseek_p1_4_layers.bin`) is run as an **informative floor** and reported, not gated (DEC-044). AC-5b (layers 1–27, 108 cells, then all 112) is **HO-STRATA-015** |
| **AC-6** | Deterministic | run AC-3 twice to two paths; `cmp` the two dumps | identical (byte-for-byte) |
| **AC-7** | Qwen regression exact, tests green | the HO-012 C8 command on `build-deepseek/strata`; `./build-deepseek/model_family_test`; `./build-deepseek/gguf_geometry_test` | the 32 HO-007 IDs identical, in order; both tests exit 0 |
| **AC-8** | Patch measured, exported, applies cleanly | `git -C strata diff --stat bac859ef9..HEAD`; cumulative `git diff --stat baf16363..HEAD`; `format-patch` → `workflow/evidence/HO-STRATA-014/patches/0002-s4-forward.patch`; `git apply --check` in a clean `baf16363` worktree **with `0001-…` applied** | both stats recorded verbatim; patch applies; the T2 number (cumulative files/lines) stated explicitly in the manifest |
| **AC-9** | Evidence gate green | `python3 workflow/tools/check_bundle.py workflow/evidence/HO-STRATA-014 --strict` | `RESULT: PASS`, run **before** `CODER_DONE` |
| **AC-10** | Early architecture checkpoint (first half-day) | `artifacts/plan.md` naming shape **(A)** or **(B)**, the files to be touched, the line estimate, the T2 impact, and the `llama-ref-graph.md` citations | present and referenced; if the estimate crosses §6 T1/T2, `DR-HO-STRATA-014-1` is raised **before** the code is written |

## 5. Evidence required

`workflow/evidence/HO-STRATA-014/`:

- `manifest.md` — filled `templates/EVIDENCE_MANIFEST.md`; §4 environment: OS,
  kernel, ROCm 10.1, `hipcc --version`, GCC, the pack hash, the oracle dump hash.
- `commands.log` — every command, cwd, env, exit code, **verbatim**.
- `test-output.txt` — raw AC-1…AC-10 output. A curated transcript labelled "raw"
  is a failed handoff (DEC-030 B-1).
- `artifacts/plan.md`, `artifacts/llama-ref-graph.md` (file:line citations into
  `78e05298…`), `artifacts/refusal.txt`, `artifacts/families.txt`,
  `artifacts/dump-run-1.bin`, `artifacts/dump-run-2.bin`,
  `artifacts/compare-layers.txt`, `artifacts/qwen-regression.txt`,
  `artifacts/model_family_test-output.txt`,
  `artifacts/gguf_geometry_test-output.txt`, `artifacts/patch-stat.txt`,
  `artifacts/signed-binary-hash.txt`.
- `scripts/compare_layers.py` (stand-alone, committed).
- `patches/0002-s4-forward.patch` + `patches/apply-check.txt`.
- `hashes.txt` — hash **immutable** files only (DEC-024); the oracle dump and
  any `main`-resident shared file are **pinned by commit with the digest** in
  `hashes-notes.txt`.
- `hashes-notes.txt` — pins as `<commit>:<path>` **with** the full 64-hex digest.

**Capture ordering is part of the contract (DEC-041 §2):** never redirect a
capture into a file the run inspects — write to `/tmp/opencode/…` and move with
`;`; after a command that may exit non-zero use `;` and capture the code, never
`&&`; rebuild `test-output.txt` **after** the final capture; rehash **last**, and
expect a second convergence pass.

**One profile per claim:** gfx1150 / Radeon 890M / Ryzen AI 9 HX 370 / ROCm 10.1 /
DeepSeek-MoE-16B Q4_K_M / 4-token prompt / greedy. Nothing here transfers to
another quant, family or host.

## 6. Guard rails

- **Strata edits are authorised for this handoff only** (extends DEC-033, recorded
  in DEC-042 once the owner authorises S4): branch `strata-014-deepseek-s4`, cut
  from `bac859ef9`, never `main`, patch exported. Outside this handoff the Strata
  checkout stays read-only (DEC-008).
- **Never rebuild `build-hip/`**; it is the signed Qwen baseline
  (`d58ee239…`). All family work goes to `build-deepseek/`.
- **Do not touch:** the generic Qwen paths, `src/qwen35/**`, the tokenizer, the
  `model_family_runs()` / refusal text, `--families`, any existing
  `workflow/evidence/**` bundle, `workflow/DECISIONS.md`, `workflow/STATUS.md`,
  `.opencode/**`, `.github/**`.
- **Do not add dependencies.** No new third-party library, no network at runtime.
- **Do not change acceptance criteria or the §12 bound.** Ambiguity → `NEEDS_INFO`
  to the architect, not a local reinterpretation.
- **T1 fired and was confirmed** (DEC-043): there is no standard-MHA path in the
  generic engine, so shape (A) is out. Do not "also" extend `src/core/layer.cpp`
  or the QSA path in this handoff.
- **T2 is crossed by design and approved** (DEC-043): the overlay grows by a new
  `src/deepseek/**` path. Re-measure `git diff --stat baf16363..HEAD` in **each**
  increment and record the cumulative number; keep the shared-file hunks to the
  dispatch, the build and the test. **New deviation trigger:** if the path turns
  out to need edits in shared code (`src/core/**`, shared kernels, `qwen35`),
  stop and raise a fresh DR — that is the calculus DEC-043 says to re-review.
- **The stage is already split** (DEC-043): this handoff is **S4a** (block 0).
  Do not deliver partial MoE work as if it were S4b, and do not pad the dump with
  uncomputed slots.
- **Do not merge, do not push** the Strata tree anywhere (upstream is third-party),
  do not push `main` in this repo. Commit and push only `wp/strata-014-deepseek-s4`.
- **No performance or support claim.** The only numbers in the manifest are the
  parity errors and the patch stats.
- No secrets, no weights, no absolute paths in `hashes.txt`.

## 7. Dependencies / blockers

| Dependency | Owner | Status | Needed by |
|---|---|---|---|
| **Owner authorization: lift DEC-016 for S4** | Owner | **OPEN — the single DoR blocker** | READY |
| Oracle dumps committed and hash-verified (HO-010) | Architect | available | AC-5 |
| `bac859ef9` local Strata branch with S1–S3 | Coder/Architect | available | base |
| ROCm 10.1 at `/opt/rocm/core-10.1`, gfx1150, `build-deepseek/` configured | environment | available (HO-012 C1/C2) | AC-1 |
| Reference server `:9931` (convenience only) | environment | UP 2026-11-23, 16/16 verified | optional, non-gating |
| GitHub Actions billing — 3 of 4 required checks cannot run | Owner (GitHub billing) | open since 2026-11-23 | **merge only**, not the coder |

## 8. Definition of Ready

- [x] ID/type/from/to/title/work package present
- [x] Branches and base commits named (`wp/strata-014-deepseek-s4` @ `d1a974db`;
      Strata `strata-014-deepseek-s4` @ `bac859ef9`)
- [x] Scope and out-of-scope explicit
- [x] Inputs linked with paths and hashes
- [x] Every criterion has a command/check
- [x] Evidence requirements runnable, capture rules and tool stated
- [x] Guard rails explicit (incl. T1/T2 and the read-only relaxation)
- [x] Dependencies named with owners
- [x] Priority/timebox set (P1, 2 days)
- [x] Tolerance pre-registered (§12) — no run seen before writing it
- [x] **Owner authorization (DEC-016 lift for S4)** — authorized 2026-11-23
      (recorded in DEC-042 §8)
- [x] No open `NEEDS_INFO`

## 9. Definition of Done

- [ ] AC-1…AC-10 run (AC-5 → **AC-5a**); raw output in `test-output.txt`
- [ ] **AC-5a** PASS at the pre-registered bound (block 0, 4 cells); each cell printed
- [ ] Normal refusal, `--families` and the Qwen regression unchanged
- [ ] Signed binary hash unchanged; nothing built in `build-hip/`
- [ ] Patch exported, measured against T2, `git apply --check` clean
- [ ] `check_bundle.py … --strict` PASS
- [ ] No secrets, no out-of-scope edits, no new dependencies
- [ ] `CODER_DONE`; `CODER_TO_QAQC` record attached

## 10. Signatures

| Role | Name/agent | Date | Decision |
|---|---|---|---|
| Sender (Architect) | `architect` (`opencode-go/deepseek-v4-pro#max`) | 2026-11-23 | **READY** (owner authorized S4) |
| Receiver (Coder) | `coder-primary` (`opencode-go/kimi-k2.7-code`) | | launched with this file |

## 11. Log

- 2026-11-23 Architect: created as **PROPOSED**. S4 is not authorised (DEC-037,
  DEC-016); §12's bound and the `--parity-run` gate are fixed now so that no gate
  value can be chosen after a measurement (DEC-042).
- 2026-11-23 Owner: **authorized S4** — lift DEC-016 for this handoff only,
  including the DEC-008 relaxation for Strata edits (DEC-042 §8).
- 2026-11-23 Architect: **PROPOSED → READY**. Branch `wp/strata-014-deepseek-s4`
  (workflow repo) and `strata-014-deepseek-s4` @ `bac859ef9` (Strata checkout,
  pointer only, checkout untouched) created. `coder-primary` launched. AC-10's
  `artifacts/plan.md` and any `DR-HO-STRATA-014-1` are due before the forward
  code is written.
- 2026-11-23 Coder: accepted (`IN_PROGRESS`). AC-10 delivered — `artifacts/plan.md`,
  `artifacts/llama-ref-graph.md` (citations into `78e05298…`), commit `36256b6`.
  Found that the generic engine has no standard-MHA path (T1) and that a
  dedicated engine is engine-sized (T2). Raised **DR-HO-STRATA-014-1**; Strata
  checkout untouched (`git status` empty).
- 2026-11-23 Architect: **T1 confirmed independently**
  (`family_layout.hpp:178-181`, `:262-269`, `:196-220`). **DR-1 APPROVED with
  conditions** (DEC-043): shape (B) dedicated path on Route 2 (the ~5k lines are
  additive new files; upstream-facing edits stay at three small hunks), the stage
  **split into S4a/S4b** on the oracle's per-layer resolution, **`dsref.cu` cut**,
  simplicity condition, T2 re-measured per increment. This handoff is now **S4a**
  (`IN_PROGRESS`); AC-5 becomes **AC-5a**; the MoE blocks and the full 112-cell
  gate move to HO-STRATA-015.
- 2026-11-23 Coder + Architect: AC-5a **FAIL** at 1.83e-2 … 1.23e-1, bisected to a
  **reference** defect, not an engine defect: `attn_norm-0` matches to 4.0e-8;
  the engine matches llama.cpp's own Q6_K dequant + f32 dot to 6.4e-7; and
  llama.cpp's q8_K-activation dot reproduces the oracle's `Qcur-0`/`Vcur-0` to
  1.2e-7 / 3.3e-7. The Q4_K oracle's per-layer tensors are *not* the exact
  product. **DEC-044**: AC-5a compares against an exact-arithmetic f32 reference
  of the same pack; **the 5e-3 bound is unchanged**; the Q4_K dumps remain the
  token authority for S5 and are reported here as an informative floor only.
  Bisection evidence: `artifacts/diagnosis.md`, `scripts/oracle_nodes.cpp`.
- 2026-11-23 Coder (`coder-primary`, `opencode-go/kimi-k2.7-code`): **READY → IN_PROGRESS**. AC-10: produced `artifacts/llama-ref-graph.md` and `artifacts/plan.md`; raising `DR-HO-STRATA-014-1` because the chosen shape crosses DEC-021 T2 and the alternative shape crosses T1.
- 2026-11-23 Coder: **checkpoint commit**. Strata `ad214242a` now contains the block-0 engine, `--parity-run` wiring, and temporary diagnostic dumps; workflow `34b35e43` adds `compare_layers.py` and `artifacts/diagnosis.md`. AC-5a FAIL: 4 cell relative L2 values are pos0 `1.9295e-02`, pos1 `5.3505e-02`, pos2 `5.8345e-02`, pos3 `1.2275e-01` (max `1.2275e-01`, bound `5e-3`). Embedding gather is exact; a Q6_K reference bug in the Python diagnostic was fixed. Next: re-run the corrected per-node reference at `p=0` to decide between Q8_1 activation quantization and an attention/orientation error.

## 12. Pre-registered tolerance (fixed 2026-11-23, before any S4 run)

**Definition.** For every `(layer l, position p)` cell:

```text
err(l,p) = || engine[l+1][p] - oracle[l][p] ||_2 / || oracle[l][p] ||_2
```

over `l = 0…27` (28 blocks) and `p = 0…3` (4 prompt positions) → **112 cells**.
`engine[l+1]` is the strata slot after block `l`; `oracle[l]` is `l_out-<l>`.
Nothing is averaged; the gate is on the **maximum**.

**Cells in scope = blocks computed × 4.** S4a computes block 0 (`l = 0`, 4
cells); S4b extends to `l = 0…27` (112 cells). The bound is identical; only the
cell count grows. A bound that holds on 4 cells is evidence for block 0's
arithmetic (embedding → norm → attention → rope → residual → dense FFN →
residual) and for nothing after it.

| Gate | Value | Rule |
|---|---|---|
| **max over the cells in scope** | **≤ 5e-3** | binding; one cell above ⇒ FAIL |
| finiteness | every cell finite | NaN/Inf anywhere ⇒ FAIL |
| shape | engine dump `[k][N+1][2048]` f32 with `k ≥ 4`, `N` = blocks computed (1 in S4a, 28 in S4b), oracle `[4][28][2048]` f32; the first 4 engine records are the prompt positions; oracle blocks `0…N-1` are compared | mismatch ⇒ FAIL |
| reporting | median, max, worst `(l,p)`, first cell above bound | always printed, pass or fail |
| determinism | two runs byte-identical | otherwise ⇒ FAIL |

**Basis (stated, so it can be argued with — but not after the fact):**

- Both implementations dequantise the **same** Q4_K/Q6_K bytes with the same
  reference formulas, and accumulate in fp32. What differs is summation order
  (tiling/blocking) and GPU vs CPU FMA contraction — per-dot-product relative
  error around 1e-6, RMSNorm keeps the residual well scaled, so 28 blocks of
  accumulation should land near 1e-5…1e-3.
- Semantic errors do not hide under 5e-3: wrong rope, wrong head mapping, dense
  block mis-mapped as MoE, or shared experts dropped all produce
  `err ≳ 1e-1` at the affected layer and above.
- The project's own convention (`docs/GDN_CONTRACT.md:78`) is
  `max(floor, 3 × the incumbent's error)` with a 2e-3 floor for normalised
  outputs; 5e-3 is that floor, widened once for a 28-block chain with no measured
  noise floor of its own (the CPU oracle is bit-reproducible, so it supplies
  none — llama.cpp CPU vs HIP is measured in S5, not here).

**Amended 2026-11-23 (DEC-044) — the reference, not the bound.** The first AC-5a
run measured 1.83e-2 … 1.23e-1, and the bisection proved why: the Q4_K oracle
computes its matmuls with **q8_K-quantized activations** (reproduced to 1.2e-7 /
3.3e-7 for `Qcur-0` / `Vcur-0`), so it is 4.4e-3 (Q4_K) to 5.8e-2 (Q6_K) away
from the exact product. Comparing an exact engine to that reference measures the
reference's rounding. The gate therefore compares against an **exact-arithmetic**
reference (f32 conversion of the same pack, same pin, same harness), and **5e-3
is unchanged**. The Q4_K dumps stay the authority for **tokens** (S5), never for
layers. See `artifacts/diagnosis.md` for the measurements.

**What a failure means:** a failed cell is a **finding**, not a tuning problem.
Name the first failing layer; that layer's arithmetic (norm placement, rope,
attention head layout, routing weights/top-k normalisation, shared-expert
handling) is the suspect. Report it, raise `RW`/deviation as the failure class
requires. **The bound is not widened**; widening it is a deviation for the
architect and is recorded in `DECISIONS.md`.

## 13. S4 task map (what follows this handoff)

Renumbered by DEC-043 (the S4 deviation inserted S4b). This supersedes the map
DEC-042 wrote; DEC-042's "HO-STRATA-015 = S5" reference is corrected here.

| Stage | Handoff | Gate | State |
|---|---|---|---|
| **S4a** skeleton + block-0 parity | **HO-STRATA-014** (this file) | max relative L2 ≤ 5e-3 over **4 cells** (block 0 × 4 positions) | IN_PROGRESS |
| **S4b** MoE blocks 1–27 | **HO-STRATA-015** (to be written on AC-5a PASS, with DR-HO-STRATA-014-1 as an input) | layers 1–27 (**108 cells**), then all 112; no renormalisation over the selected set, 2 shared experts | not written |
| **S5** token parity + KL + the support flip | **HO-STRATA-016** (on S4b PASS) | 3 prompts × 16 greedy tokens **zero** mismatches; KL ≤ 1.5× the CPU/HIP floor; then `model_family_runs()` → true, `--families` gains `deepseek` | not written |
| S6/S7 baseline, envelope, regression, signoff | **HO-STRATA-017** (on S5 PASS) | GTT/`dmesg` envelope, HO-007 32 IDs bit-identical, QAQC → audit → sign | not written |

HO-STRATA-015 cannot be written before AC-5a's result: its scope is "the blocks
after the one S4a proved", and its evidence starts from the dump shape S4a
produces. Writing it now would be a guess presented as a contract.
