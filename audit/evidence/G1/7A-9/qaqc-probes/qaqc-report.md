# QAQC Report — Work package 7A-9 (BLOCKER-7A4-1 parser fix)

**Role:** QAQC (independent session, per handoff §1 and §7; `PHASE7_7A-9_PARSER_FIX_BRIEF.md` §7)
**Date:** 2026-11-05
**Tree reviewed:** branch tip `d83a052` on `wp/7A-9-gguf-array-fix`; work commit under
review **`1bce3d0`**; parent **`3af32d4`** (code identical to the G1 base `e9b6b80`).
**Method:** clean git worktrees at the parent and the candidate; all red/green and lane
runs re-executed independently of the coder's logs; 21 new adversarial probes
(`probe_nested_array.py`, this directory). Transcript: `probe-commands.log`.

---

## Verdict

**PASS.** The fix is exactly the brief's required line, the scope is exactly the
allowed set, red→green reproduces from clean checkouts, the adversarial probes confirm
the invalid class is rejected at *every* depth while every valid and every pre-existing
malformed class behaves as before, and all lanes match the coder's recorded evidence.
BLOCKER-7A4-1 is closed. Ready for auditor approval.

## 1. Scope and freeze

| Check | Result |
|---|---|
| `git status --porcelain` on the branch | clean |
| `git diff 3af32d4 1bce3d0 --name-only` | `src/gguf_parser.py`, `tests/test_fuzz_gguf.py`, `IMPLEMENTATION_PLAN.md`, `audit/evidence/G1/7A-4/BLOCKER.md` — nothing else |
| `src/` diff | the entire functional change is the 2-line `ARRAY` element-type check in `_read_value`; no other parser behaviour touched |
| Forbidden set (CMake, packaging, CI, `scripts/qa`, ledger, baseline, 7A-4 evidence, 7B) | empty diff — confirmed |
| Tests | only the strict-xfail marker removed (the brief's requirement); 27 deletions / 69 additions; no test deleted, skipped, or weakened; harness-contract test passes in the lane |
| New dependency / network | none |

## 2. Red → green, independently reproduced

- **Red** (worktree at `3af32d4`): the pinned test under `--runxfail` fails with
  `RecursionError: maximum recursion depth exceeded` — matches the coder's `red.log`.
- **Green** (worktree at `1bce3d0`): `pytest tests/test_fuzz_gguf.py -k nested` →
  **3 passed** (depth 1000 pinned test, depth 300 boundary, minimized 992 example
  with its sha256 assertion) — matches `green.log` / `nested-array-boundary.log`.

## 3. Adversarial probes (21/21 in both modes)

- **Parent**: nested arrays at depths 1/2/5 and with `count=0` are *accepted* (the
  format rule was not enforced below the stack threshold); depth 992 and 5000 raise
  `RecursionError`. Defect reproduced independently.
- **Candidate**: every nesting depth (1, 2, 5, 992, 5000) and `count=0` raise
  `ValueError("GGUF array element type must not be an array")` — the check fires
  before the count is consumed and no recursion occurs at any depth. The
  stack-exhaustion path is gone, and so is the silent acceptance.
- The minimized example is exactly **11,962 bytes**, sha256
  `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` — identical to
  `../7A-4/BLOCKER.md` §2.
- **No regression**: valid arrays of int32 / string / uint64 / bool / float32 /
  uint32 and the empty array still parse with correct values; huge count, unknown
  element type 99, truncated array body, truncated header and bad magic all still
  raise the same `ValueError`s as before.

## 4. Lanes re-run from a clean candidate worktree

| Lane | Coder's claim | QAQC re-run |
|---|---|---|
| CPU lane `pytest -m "not gpu" -q` | 111 passed / 24 deselected / 4 xfailed | **identical** |
| `--runxfail -m "not gpu"` | 4 tokenizer pins fail, no parser failure | **identical** (the 4 failures are exactly the 7B/7C tokenizer goldens) |
| GPU lane `pytest -m gpu -q` | 24 passed | **24 passed** (main tree; the built extension is gitignored, so the GPU lane cannot run in a bare worktree) |
| `test_cpu_only.py` / `-O` | 12/12 both modes | **OK / OK** |
| `scripts/qa/check_claims.py` | PASS | **PASS** — 0 new violations, 17 baselined, 0 findings |
| 10k fuzz re-run | 2 passed | **2 passed** (in the lane; `fuzz.log`) |

The brief's "109 passed" is the pre-boundary-test count; the +2 are the two boundary
tests the brief itself required. The 4 remaining xfails are the tokenizer 7B/7C pins,
as stated.

## 5. Docs and record

- `BLOCKER.md` status header now reads "fixed by Phase 7A-9" and §3.1 states the
  parser's documented contract — exactly the brief's §4 wording change.
- `IMPLEMENTATION_PLAN.md` fail-closed criterion no longer carries the BLOCKER-7A4-1
  exception; it points at this evidence instead.
- The claims ledger has no parser-claim row, so leaving it untouched is correct;
  `check_claims.py` passes in default mode.
- Evidence bundle `audit/evidence/G1/7A-9/` is complete per the brief's list
  (env, parent/candidate SHAs, diffstat, red/green, boundary, fuzz, all lanes,
  runxfail, notes) plus a README.

## 6. Observations (no action required)

1. The claims checker reports pre-existing scope drift for claims 26/27
   (`IMPLEMENTATION_PLAN.md:261→300`, `266→305`) caused by the brief-prep commit
   `3af32d4`'s +2 lines, not by this package; the checker still returns PASS and
   the ledger is out of scope for 7A-9. Carried as a note for the auditor / 7A-6.
2. Rollback is trivial and plausible: revert `1bce3d0` (the `src/` change is two
   lines; the tests re-add the strict xfail).

## 7. Verdict per handoff §7.3

**PASS** — every acceptance criterion in the brief's §5 is met and independently
reproduced. BLOCKER-7A4-1 is fixed; the parser is fail-closed for the nested-array
class. No conditions. Awaiting auditor signoff; per the brief the release (G6)
remains blocked until the auditor accepts this fix.
