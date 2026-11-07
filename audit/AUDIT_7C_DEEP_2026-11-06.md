# AUDIT 7C (G3) — Model-family support, deep review

**Auditor:** DeepSeek V4.1 Flash (primary auditor)
**Date:** 2026-11-06
**Gate:** G3 (Phase 7C model families)
**Target:** `wp/7C-model-families` @ work `20f1165` / evidence `4b930ec`, plus the post-audit CI fixes `d64ad48` (packaging) and `1c53afd` (claims canary); final integration `vibe/phase7-220201`
**Brief:** `PHASE7_7C_MODEL_FAMILY_BRIEF.md`; **contract:** `audit/evidence/G3/7C/README.md`

---

## 1. Verdict summary

**G3: PASS — signed after the two CI blockers below were found and fixed.**
The first local-only signoff was premature: the source-tree lanes were green, but
the clean-install and claims-canary jobs were not. The final state is CI-green
(CPU + clean-clone; GPU queued as C-G1-3).

Every check below was re-run by the auditor on the candidate, not only read from the
coder's logs. Where the auditor wrote new probes, they are in
`audit/evidence/G3/7C/qaqc-probes/probe_auditor_7c.py` (+ `.log`,
`probe_auditor_parent_red.log`, `*.auditor-rerun.txt`).

### 1.1 CI blockers found after the first signoff (both fixed)

- **BLOCKER-7C-1 — clean/sdist install missing `model_spec`.** The first pushed
  merge (`6820932`) failed CPU/sdist/clean-clone CI because
  `pyproject.toml` `[tool.setuptools] py-modules` did not list the new
  `model_spec.py`. Source-tree tests could not catch this. Fixed in `d64ad48`:
  add `model_spec` to `py-modules`; extend `tests/test_cpu_only.py` V-8 to require
  every top-level `src/*.py` module in `py-modules` and `src/model_spec.py` in the
  sdist. Local sdist install + `import model_spec` verified.
- **BLOCKER-7C-2 — claims canary expected the old baseline count.** After the
  resolution of row 10, the reviewed baseline has 14 entries, but
  `scripts/qa/canary_claims.py` still expected 15; the CPU canary step failed on
  `eab3771`. Fixed in `1c53afd`: constant 15→14 (and the success message uses
  the constant). `canary_claims.py` now passes 12/12.

Final CI on `1aa4e75` (canary-fixed merge): CPU `42317321414` **success**,
Clean-Clone `42317321409` **success**, Self-Hosted GPU `42317321450` **queued**
(expected — C-G1-3). See `BLOCKER-7C-1.md`, `BLOCKER-7C-2.md`,
`packaging-fix.log`, and `canary.log`.

## 2. Scope / allowed-forbidden set

`git diff 2eaa242..20f1165 --stat` touches exactly 12 files: 11 are in the brief
§2 allowed set — `README.md`, `audit/CLAIMS_LEDGER.md`, `src/inference.py`,
`src/layer.py`, `src/model_spec.py` (new), `tests/**` (incl. the additive
`EXPECTED_LANES` entries in `test_harness_contract.py`) — and
`audit/claims_baseline.txt` is the claims baseline's own maintenance removal of
the resolved row-10 entry (QF-7C-6; future claims packages should name this file
explicitly).
No diff lines in `src/gguf_parser.py`, `src/kv_cache.py`, `src/kernels/**`,
`src/python_bindings/`, `CMakeLists.txt`, CI, or the tokenizer. No removed
asserts or pytest marks in existing tests (scanned the tests/ diff). Ledger diff
is rows 10/11/12 only; the `claims_baseline.txt` diff removes only the resolved
`10 README.md qwen2` entry with the header comment's own removal rule cited.
No new kernel target was added (GeGLU is a documented host FP32 path — allowed).

**Post-audit CI fixes (justified scope exceptions):** `pyproject.toml` was
touched only to add `model_spec` to `py-modules` (BLOCKER-7C-1), and
`scripts/qa/canary_claims.py` only to update the reviewed baseline count 15→14
after the row-10 resolution (BLOCKER-7C-2). Both are packaging/claims
infrastructure required for the new module and the legitimate baseline removal;
neither adds feature scope. `tests/test_cpu_only.py` was extended for the
py-modules/sdist regression.

## 3. Lanes (auditor re-run on candidate `4b930ec` working tree)

| Check | Result |
|---|---|
| `pytest -m "not gpu" -q` | **461 passed**, 34 deselected |
| `pytest -m gpu -q` | **34 passed**, 461 deselected |
| `pytest -m "not gpu" -q -k "model_spec or phi3 or gemma or compat"` | **19 passed** |
| `pytest -m gpu -q -k "phi3 or gemma or llama_regression"` | **10 passed** |
| `tests/test_cpu_only.py` / `-O` | **OK / OK** (12/12 each) |
| `scripts/qa/check_claims.py` | **PASS** — 0 new, 16 baselined, 0 expired, 0 findings |

Matches the coder's `cpu-lane.log` / `gpu-lane.log` / `claims.log` exactly.

## 4. Red/green (auditor re-run on a fresh parent worktree at `8426ec6`)

- `tests/test_model_families.py` on the parent with the 7C test files copied in:
  **9 failed, 1 passed** — phi3 `KeyError: 'blk.0.attn_q.weight'` (5 tests),
  gemma wrong logits (`max err 8.715…` on the Q4_K fixture) / spec-less engine
  AttributeError / cleanup BufferError, and the llama regression test passing on
  both. `tests/test_model_spec.py` fails collection on the parent
  (`ModuleNotFoundError: model_spec`). Identical to `red.log`.
- `probe_red_families.py` on parent: rc=1 (RED). On candidate: ALL GREEN
  (phi3 max_err 0.002729, gemma 0.001982, tol 6e-3).
- `probe_llama_regression.py`: **byte-identical** output on parent `8426ec6` and
  candidate — logits sha256 `a31dfc6f…32441b`, greedy ids `[9, 15, 9, 0, 3, 9, 14, 9]`.
  Llama-family path unchanged. Recorded in `qaqc-probes/probe_auditor_parent_red.log`
  and `*.auditor-rerun.txt`.

## 5. Independent auditor probe (`probe_auditor_7c.py`, 14/14 PASS)

Written by the auditor without importing `tests/reference_model.py`; expected
logits come from a second, independently written FP32 forward (own vectorized
causal GQA / NeoX rope / RMSNorm), using only `gguf_parser`'s format layer for
dequantization:

- phi3 fused F16+biases vs auditor forward: max_err **0.003432**
- phi3 fused Q4_K/Q6_K vs auditor forward: max_err **0.004916**
- phi3 fused vs separate layout, engine vs engine: max_err **0.000000**
- gemma F16+softcap vs auditor forward: max_err **0.003531**
- gemma Q4_K vs auditor forward: max_err **0.005918**
- fail-fast distinctness (all observed live): unknown arch names the supported
  set; gemma2 variant message; missing required lists **all** names in one error
  (`blk.0.ffn_down.weight, blk.1.attn_output.weight, output_norm.weight`);
  missing optional biases → no error; shape mismatch names tensor/expected/actual
  (`(64, 65), expected (64, 64)`); phi3 rope factors; `key_length != value_length`;
  sliding window.
- reference independence (AST scan): `tests/reference_model.py` imports only
  `numpy`/`math`/`typing`/`os`/`sys`/`gguf_parser` — never `layer`/`inference`/
  `model_spec`/`matmul_module`.

## 6. Real-name authority

`header-dumps/` contains text dumps of real GGUF header slices with URL, repo
revision, byte range, and sha256 (`PROVENANCE.md`): Phi-3-mini-4k-instruct-q4
(fused `blk.N.attn_qkv.weight` dims (3072, 9216) = q + 2·kv with head_dim 96,
fused `blk.N.ffn_up.weight` (3072, 16384) = 2·8192, tied output) and
gemma-2b-it Q4_K_M (separate `attn_q/k/v`, explicit `key_length = value_length =
256`, `hidden 2048 / heads 8`, separate `ffn_gate/up/down`, no `output.weight`).
The implemented tensor maps match these names/shapes; the 7B-style
`key_length != hidden//heads` case is covered by the synthetic gemma fixture
(key_dim 32 vs hidden//heads 24), which the parent got wrong (red log) and the
candidate gets right. No weights committed.

## 7. Claims honesty

**Claims correction (audit):** the matrix/ledger initially cited the coder-fixture
maxima (`≤2.9e-3` Phi-3, `≤2.1e-3` Gemma); the independent auditor probe observed
`4.9e-3` (Phi-3 Q4_K/Q6_K) and `5.9e-3` (Gemma Q4_K). README, the matrix, and
ledger rows 11/12 now cite the **6e-3 test tolerance and the observed maxima**,
not the smaller coder-fixture numbers. This was the only claims-accuracy issue
found; the status/scope (PARTIAL synthetic, qwen2 NOT YET, 7F-2 for real GGUFs)
is unchanged. `check_claims.py` remains PASS.

## 8. QFs / carry-forwards (non-blocking)

- **QF-7C-1:** gemma-2b-it has `key_length == hidden//heads` (256); the
  divergent-dims path rests on the synthetic fixture only. Real Gemma 7B files
  (`key_length 256`, `hidden//heads 192`) remain 7F-2 evidence — noted, not a gap
  for G3.
- **QF-7C-2:** GeGLU is host-side NumPy (documented in the matrix); a HIP GeGLU
  kernel is performance work, out of 7C scope.
- **QF-7C-3:** `key_length != value_length` files fail fast; extending the KV
  cache is 7D scope.
- **QF-7C-4:** `red.log`'s gemma parent failures include cleanup `BufferError`s
  masking the primary wrong-logits assertion on two tests; the primary causes
  (head_dim 24 vs 32, no scale/GeGLU/softcap) are documented and reproduced.
- **QF-7C-5 (claims accuracy, fixed in audit):** the matrix/ledger initially
  cited the coder-fixture maxima (`≤2.9e-3` Phi-3, `≤2.1e-3` Gemma); the
  independent probe observed `4.9e-3` (Phi-3 Q4_K/Q6_K) and `5.9e-3` (Gemma
  Q4_K). Corrected to the 6e-3 test tolerance/observed maxima in README,
  `compat-matrix.md`, and ledger rows 11/12. No status change.
- **QF-7C-6 (process):** `audit/claims_baseline.txt` was edited to remove the
  resolved `10 README.md qwen2` entry; this is the baseline's own maintenance
  rule, but the 7C brief's allowed-file list did not name it. Acceptable here;
  future claims packages should list the baseline explicitly.

### Blockers found by CI after the first signoff (fixed)

- **BLOCKER-7C-1 (fixed, `d64ad48`):** clean/sdist install could not import
  `model_spec`; `pyproject.toml` `py-modules` omitted it. Fixed plus a CPU-only
  `py-modules`/sdist regression. Local sdist install and clean-clone CI green.
- **BLOCKER-7C-2 (fixed, `1c53afd`):** the claims canary still expected 15
  baseline entries after the resolved row-10 entry was removed (actual 14).
  Fixed; `canary_claims.py` 12/12 PASS. CPU CI green on `1aa4e75`.

## 9. Gate state

G3 signed after the CI fixes (`1aa4e75`: CPU `42317321414` + clean-clone
`42317321409` success; GPU `42317321450` queued as C-G1-3). 7C is accepted at
synthetic-fixture scope. 7D is unblocked after this merge; real-GGUF
Phi-3/Gemma goldens are 7F-2; release/G6 still blocked by 7D/7E/7F and the GPU
runner.
