# QAQC Report — Work package 7A-4 (Deterministic GGUF fuzz)

**Role:** QAQC (independent session, per handoff §1 and `PHASE7_7A-4_BRIEF.md`)
**Date:** 2026-11-04
**Tree tested:** work commit `a14fcfa5e0be1ad4a118a2c0b171881559dc2b04` on `wp/7A-4-fuzz`
(tip `5795107`; prep/brief `758e500`; base `d2d55ea` — 7A-3 merged). CI verified against
the **public GitHub API**; the defect reproduced from the test's own helper.
**Probes:** `probe-commands.log` (this directory).

---

## Verdict

**PASS.** The fuzz meets every acceptance criterion — 10,000 deterministic examples,
zero unhandled exceptions over the drawn space, two runs identical modulo timings —
and it did what a fuzz exists to do: **it found a real parser defect**. BLOCKER-7A4-1
is verified end to end: the minimized example reproduces **byte-for-byte** (11,962
bytes, sha256 `28fe58bf…` — exact match), the defect is confirmed in
`src/gguf_parser.py` (`_read_value` recurses on an `ARRAY` element type with no scalar
check), the pinned strict xfail fails today under `--runxfail`, and the proposed fix
is correct. Per the brief, `src/` was not touched — the defect is pinned and filed,
not fixed here. One wording correction for the blocker report (§4, minor).

## 1. BLOCKER-7A4-1 — independently reproduced

| Probe | Result |
|---|---|
| The code defect | ✅ confirmed at `src/gguf_parser.py:165-171`: `elem_type` is read and recursed via `self._read_value(elem_type)` with **no scalar check** — an `ARRAY` element type recurses once per nesting level |
| The minimised example | ✅ **byte-for-byte**: `_nested_array_header(992)` = 11,962 bytes, sha256 `28fe58bf8fee9e0d9e0987b3cc2e09922ffb968f9f8809de34c7305d086bbebb` — exact match with BLOCKER.md |
| The boundary | ✅ reproduced: at depth 300 (3.6 KiB) the invalid file is **PARSED** (the format rule is unenforced); at ~992-993 the parser raises **RecursionError** — undocumented. **Verification nuance:** at my stack depth the flip is at 993, not 992 — exactly the stack-depth variability BLOCKER.md itself documents ("Hypothesis's find reports the threshold as flaky"); the *example* is deterministic, only the *threshold* is caller-dependent. The report's caveat is accurate and necessary |
| The pinned test | ✅ `test_nested_arrays_are_rejected_with_a_value_error` is `xfail(strict=True)` and **fails under `--runxfail`** — it asserts the *should-be* behaviour (`ValueError`), so it fails today whichever side of the threshold, and the fix cannot land unnoticed (strict) |
| The proposed fix | ✅ correct: reject `elem_type == GGUFValueType.ARRAY` at the read point. A recursion limit is genuinely unnecessary afterwards — a *valid* GGUF has no nesting at all, so the rejected-element-type check bounds depth by the format |

## 2. The fuzz — contract, statistics, determinism

- **Settings exactly per the brief**: `max_examples=10_000, derandomize=True,
  deadline=None, database=None` on both 10k tests; the property is the brief's —
  `ValueError` (documented rejection) or clean parse; **any other exception is a
  failure**; plus a buffer-size bound, layer-helper exercise on accepted parses, and an
  fd-leak assertion.
- **Statistics reproduced exactly** via the committed `measure-fuzz-coverage.py`:
  **6,386 rejected (all ValueError) / 3,614 accepted (929 with a tensor table) / 0
  other exceptions** — matching the recorded evidence and the handoff summary; every
  mutation-class count matches (n_dims 1,270; unknown types 2,275; version 2,215;
  tensor_count 1,456; name lengths 1,128; offsets 763; array lengths 708; reserved
  types 801).
- **Determinism**: my 10k run passed (22.2s); the recorded `fuzz.log` vs
  `fuzz-rerun.log` are identical except timings (42.48s vs 42.49s) and headers; a
  second in-module test (`test_fuzz_gguf_headers_are_deterministic`) also asserts
  parse-twice equivalence.
- **The structured strategy** draws file *descriptions* and serialises them —
  which is why 3,614 of 10,000 examples reach deep acceptance paths instead of dying at
  the first header check.

## 3. The judgement call — endorsed

Keeping the fuzz space to the format's scalar-element rule (with nested arrays covered
by the dedicated pinned test) is the right call: including nested arrays in the fuzz
space would make the 10k run *permanently* red (the pinned defect), forcing either a
red CPU lane or a weakened property (excluding `RecursionError`) — the one thing the
brief forbids. As shipped, the fuzz property stays maximally strict, the defect is
stated exactly where it lives, and nothing is hidden. G1 should indeed treat the
parser as **not yet fail-closed** until BLOCKER-7A4-1 is fixed in a new package — the
blocker says so explicitly rather than burying a negative result.

## 4. Findings (minor, non-blocking)

1. **QF-1 — one wording correction for BLOCKER.md §3.1.** "A caller that catches
   `ValueError` — … which every caller in this repository do[es]" is imprecise about
   the in-repo callers: `WeightStreamer` wraps the parse in
   `except BaseException: self.close(); raise` and the engine in
   `except Exception: self.close(); raise` — both **clean up and re-raise either
   exception** (so no fd/mmap leak difference), and the CLI catches neither (either
   surfaces as a traceback). The callers that genuinely assume `ValueError` are the
   **tests** (`test_cpu_only.py` S-1/S-2 assert it) and any *external* consumer
   following the parser's documentation — which is the impact that matters. Recommend
   softening "every caller in this repository" to "the parser's documented contract,
   asserted by the suite's own tests and followed by any consumer that reads the
   docs". The defect's substance is unaffected.
2. **Verification nuance (already documented by the coder):** the recursion threshold
   is stack-depth-dependent (my measurement: 993 vs the report's 992 at the same
   default limit) — BLOCKER.md's flakiness caveat is accurate; the sha-pinned example
   is the stable artifact and it matches exactly.

## 5. Everything else — all verified

- **Lanes** (my runs, matching the recorded logs exactly): CPU **108 passed / 24
  deselected / 5 xfailed** (4 pre-existing tokenizer pins + the new one); GPU
  **24 passed / 113 deselected**, unchanged; `test_cpu_only.py` **12/12** both modes;
  claims checker PASS (0/17/0/0); canaries 12/12.
- **CI wiring**: `hypothesis` added to the CPU job **and** the sdist venv (the shipped
  module imports it — the recorded sdist rehearsal shows it installed and the shipped
  tree collecting); the sdist job's two lane steps deselect `slow`
  (`-m "not gpu and not slow"`, `-m "not slow" -rs`) with the reasoning in a comment;
  the CPU job owns the 10k run.
- **Lane contract**: `test_fuzz_gguf.py` registered as `cpu`; `slow` carried on the
  tests individually — the correct pattern, since the contract rejects a module
  declaring two markers.
- **CI run 41762204487**: **API-verified success**, head = the work commit.
- **Scope**: exactly `ci-cpu.yml` + `test_fuzz_gguf.py` + the `EXPECTED_LANES` line +
  the evidence bundle; restricted diff (src, CMake, packaging, README/PLAN,
  scripts/qa, ledger, baseline) **empty** — the brief's "do not touch `src/`" respected
  even with a live defect in hand, which is the discipline the brief demanded.
  `candidate-sha.txt` = the work commit.

## 6. Disposition

**7A-4 passes QAQC unconditionally** (QF-1 is a one-line wording fix in the blocker
report, foldable into the fix package's evidence). With this, **every 7A package
(7A-1…7A-8, all follow-ups) is QAQC-passed and G1 has no open items on the QAQC
side**. The one carry-forward is BLOCKER-7A4-1 itself: the fix is a new `src/` work
package with the pinned strict xfail as its acceptance criterion, and G1 should be
signed with the parser explicitly marked not-yet-fail-closed until that fix lands.
G1 remains unsigned pending the auditor; 7B remains blocked until G1 and the 7A-3
goldens (which exist and are verified).

**QAQC sign-off:** 2026-11-04. Probes: `probe-commands.log` (this directory).
Scratch retained at `/tmp/opencode/qaqc-74/`.
