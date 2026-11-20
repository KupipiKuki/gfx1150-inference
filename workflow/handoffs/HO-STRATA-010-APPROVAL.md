# Architect approval — HO-STRATA-010

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-010 — reference oracle and parity harness (S0) |
| **Architect** | architect (session model; WAIVER-001 seat) |
| **Date (UTC)** | 2026-11-19 |
| **Decision** | **SIGNED** → state `DONE`; recorded as **DEC-030** |
| **Evidence** | `workflow/evidence/HO-STRATA-010/` at `0369ec8` (rework `664bd40`, rebased onto `8ce28c4`) |
| **Branch / base** | `wp/strata-010-reference-oracle` / `main` `8ce28c4` |

## 1. Result

The project now has an independent oracle for family parity. From a pinned
llama.cpp (`b12527`, `78e05298…`), the harness reproduces:

```text
gen: 8913 13 185 40619 317 254 6077 280 7239 13 185 40619 317 254 6077 280
logits 5334baef…   [16][2][2]  (bit-identical over 3 runs)
layers db6eccb3…   [4][28][2048], 112/112 rows non-zero
tokenizer parity P1/P2/P3 exact, no BOS on either side
```

Three independent parties (coder, QAQC, auditor) rebuilt the harness from the
committed source and got the same digests. `sha256sum -c` is 15/15.

## 2. Gate history (kept, not rewritten)

| Gate | Verdict | What it caught |
|---|---|---|
| Coder | CODER_DONE | scope narrowed to DeepSeek after the Mixtral pack proved to be the legacy layout |
| QAQC (1) | PASS, 5 minor | stale transcript artefacts, dump padding, hash drift |
| Audit (1) | **FAIL** | stale parity table; `stdout_diff_exit=0` for a diff that exited 1; QAQC covering an older commit |
| RW-010-1 | closed | table regenerated, true exits recorded, normalization gate documented, dead SHAs replaced |
| QAQC (2) | PASS | re-pass on `664bd40`, 15/15 hashes, full oracle re-run |
| Audit (2) | **PASS** | every prior finding closed; R1 reclassified as a Minor fidelity defect |

The first audit failing is the system working: two records asserted a result the
commands did not produce, and neither reached `main`.

## 3. Criteria

| # | Criterion | Architect |
|---|---|---|
| 1 | llama.cpp pinned, built, provenance recorded (tag, commit, flags, compiler, lib hashes) | PASS |
| 2 | Harness reproduces the same IDs across runs | PASS |
| 3 | Tokenizer parity, 3 prompts, DeepSeek, zero differences, BOS convention stated | PASS |
| 4 | Reference token IDs (DeepSeek, P1, 16 tokens) | PASS |
| 5 | Per-layer dumps complete (`[4][28][2048]`, all positions) | PASS |
| 6 | Logits/top-2 dumps, shape and layout documented | PASS |
| 7 | Harness committed and runnable from a clean checkout | PASS |
| 8 | No engine change (Strata clean at `baf16363…`, binary `d58ee239…`) | PASS |
| 9 | No performance/support claim | PASS |

## 4. Residual findings — carried, not waived

The auditor's second report leaves four minors. All are non-gating; three are
prose or bookkeeping, one is a fidelity note about the transcript:

| # | Finding | Disposition |
|---|---|---|
| **B-1** | `test-output.txt` is a **curated transcript**, not raw stdout: the diff body shows an unchanged line as changed, and the parity block omits the table header. The manifest's "outputs are raw" over-claims. | **Open, non-gating.** To be corrected at the next bundle touch (S1). No acceptance claim depends on it; the gate of record (normalized `gen:` diff) is reproducible and hashed. Recorded here so it is not discovered late. |
| **B-2** | Library digests are **build-instance** scoped, not just host-scoped (`libggml-base` changed between two builds at the same pin). | **Open, wording.** Say "this host and this build" at the next touch. |
| **B-3** | `STATUS.md` row and the QAQC handoff still carried pre-rebase SHAs and `PROPOSED`. | **Closed at this gate** (DEC-018: the architect mirrors states). |
| **B-4** | `hashes-notes.txt` records commit pins but not the resulting digests DEC-024 requires. | **Open, minor.** Pins verified by the auditor (`1883c62b…`, `023a37de…`); add the digests at the next touch. |

B-1 deserves the plainest statement: a curated transcript labelled raw is the
same class of error as the falsified exit code, just smaller. It did not survive
a second look because the auditor re-derived every value from the committed
files, but the label is wrong and will be fixed before S1's evidence cites it.

## 5. What this unlocks and what it does not

- **Unlocks:** S4/S5 parity has a fixed target; S1 may start whenever the owner
  lifts the hold for it.
- **Does not unlock:** the engine still cannot load Mixtral or DeepSeek. Mixtral's
  pack remains the legacy layout (DEC-029) — the auditor independently confirmed
  995 tensors with **zero** stacked `*_exps`, so the reason is factual, not a
  guess.
- The `qwen4exp` family remains supported-but-unmeasured; nothing here changes it.

## 6. Rework history

`RW-HO-STRATA-010-1` closed both majors. `RW-HO-STRATA-010-2` was not needed.
The branch was rebased onto `main` to resolve A-10/A-11 (citations to decisions
and a plan that had not merged); the rebase is disclosed here because it rewrote
the work-package branch.

| Role | Signature | Date |
|---|---|---|
| Architect | architect | 2026-11-19 |
