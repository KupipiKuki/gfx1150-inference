# RW-HO-STRATA-001-1 — rework request

| Field | Value |
|---|---|
| **Rework ID** | RW-HO-STRATA-001-1 |
| **Type** | `REWORK` |
| **Original handoff** | HO-STRATA-001 (`ARCHITECT_TO_CODER`), state `QAQC_REVIEW` |
| **From → To** | `qaqc` → `coder-primary` |
| **State** | **REWORK** |
| **Created (UTC)** | 2026-11-16 |
| **Reviewer** | `qaqc` (re-check); architect on escalation |
| **Work package / branch** | `strata-001-gfx1150-build` / `wp/strata-001-gfx1150-build` (tip at review: `86bed35`; reviewed coder commit `290922d`) |
| **Evidence root** | `workflow/evidence/HO-STRATA-001/` |
| **Priority / timebox** | P0 · acknowledge within 4 working hours, fix within 1 working day (`ENGINEERING_WORKFLOW.md` §10, §14) |
| **Review report** | `workflow/reports/qaqc/HO-STRATA-001-qaqc.md` (verdict FAIL) |

**This is a documentation-accuracy rework.** Every *measurement* in HO-STRATA-001 reproduces: QAQC
re-ran AC-1, AC-2 (including rebuilding the hipBLASLt probe from the quoted source → `100401`),
both AC-3 configure variants, AC-4, AC-5 and the full AC-8 hash set. The build (`build-hip/strata`,
39,736,088 B, `d58ee239…f5858`), the surface (`qwen4exp qwen35moe`, `flash_next`), the
Control refusal (exit 2) and the tuning verdict (match / default = plain hipBLAS) are **correct and
stay as they are**. What is wrong is one factual sentence and a set of line citations.

---

## 1. Failed criterion/criteria

| # | Criterion | Evidence (command + output/line) | Verdict |
|---|---|---|---|
| 1 | **AC-4 — Engine support surface**, element *"unsupported families named"* | The bundle states, as an AC-4 result and as observation (i): *"Families **not** supported by this build include **Qwen3.8-Flash-Next** (the family the gfx1150 bench note measured)"* (`manifest.md:51`), *"measured **Qwen3.8-Flash-Next**, which is *not* in this build's family list. This matters for HO-STRATA-002/003/004"* (`manifest.md:122-126`), *"in particular **Qwen3.8-Flash-Next is *not* in this build's list**"* (`commands.log:166-169`), *"`--families` does **not** list Qwen3.8-Flash-Next, the family the cited gfx1150 community bench measured"* (`HO-STRATA-001.md:249-251`). **False.** Disproved at the same pinned checkout by the three lines in §2.1. No command in `commands.log` supports the inference; it was read off the printed string alone. The claim reached the architect as a HO-002 scope finding and had to be corrected in the handoff log (`HO-STRATA-001.md:290-296`). | **FAIL** |
| 2 | **AC-7 — Tuning table match/fallback** (recorded as a *defect*, not a criterion failure) | The gfx1151 gate is cited as `src/prefill/gemm.cu:310-311`; those lines are the **HIP device-query failure branch** (`if (hipGetDevice(&device) != hipSuccess || …`). The quoted line `if (!table_forced && arch != "gfx1151") return nullptr;` is **`src/prefill/gemm.cu:322`** (via `grep -n 'table_forced && arch' src/prefill/gemm.cu` → `322:`). The verdict ("default = plain hipBLAS on gfx1150") is **true** and QAQC verified it at `:322`; only the pointer is wrong, in six places. | **Defect — fix in the same pass** |

## 2. Required fix

Everything below; nothing else. All paths are relative to the two checkouts named in
`HO-STRATA-001.md` §0.

### 2.1 AC-4 — replace the false claim with the verified statement (F1)

The true mapping, at the pinned checkout `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`:

```sh
$ grep -n 'FAMILY_MODEL_NAMES' serve/server.py
9695:FAMILY_MODEL_NAMES = {"qwen4exp": "qwen3.8-flash-next", "qwen35moe": "qwen3.6-35b-a3b"}

$ grep -n 'TARGET_ARCH' strata_control/drafting.py
476:TARGET_ARCH = "qwen4exp"                  # general.architecture of the Qwen3.8-Flash-Next GGUFs (tools/gguf_writer.py)

$ grep -n 'MODEL_FAMILIES_INSTALLABLE' strata_control/feed.py
155:MODEL_FAMILIES_INSTALLABLE = ("qwen4exp", "qwen35moe")   # GGUF architectures the engine runs: `strata --families`
```

Required replacement text (use this substance; wording may be tightened, not weakened):

> `--families` prints the **GGUF architectures** this build runs. `qwen4exp` **is** Qwen3.8-Flash-Next and
> `qwen35moe` **is** Qwen3.6-35B-A3B (`serve/server.py:9695`, `strata_control/drafting.py:476`,
> `strata_control/feed.py:153-155`); the list is compiled in at `src/program/generate.cpp:3566-3574`,
> with `qwen35moe` present because `cmake/strata_gpu_engine.cmake:545` sets `STRATA_HAVE_QWEN35=1`.
> **So the family the gfx1150 community bench measured — Qwen3.8-Flash-Next — *is* supported by this
> build (as `qwen4exp`).** The families **not** implemented at `baf16363` are **Mixtral 8x7B**,
> **Qwen3-30B-A3B** and **DeepSeek**: no such GGUF architecture exists in `src/`, `include/` or
> `strata_control/` (`grep -rni 'mixtral' …` and `grep -rni 'qwen3moe\|30b-a3b' …` both exit 1 with no
> output), and DeepSeek is a *retired* family the Control **refuses** rather than one the engine runs
> (`strata_control/retired.py:19 FAMILY = "deepseek41"`, `strata_control/runtime.py:561 _refuse_deepseek`).

Apply it in all four places, and delete observation (i) as written:

| File | Line(s) | What changes |
|---|---|---|
| `workflow/evidence/HO-STRATA-001/manifest.md` | `:51` (AC-4 row) | drop "Families **not** supported by this build include **Qwen3.8-Flash-Next**"; state the mapping + the real unsupported families |
| `workflow/evidence/HO-STRATA-001/manifest.md` | `:122-126` (§4.6) | rewrite as above; it must not contradict `HO-STRATA-001.md:290-296` |
| `workflow/evidence/HO-STRATA-001/commands.log` | `:166-169` (AC-4) | same correction; keep the transcribed output itself unchanged |
| `workflow/handoffs/HO-STRATA-001.md` | `:249-251` (log, observation (i)) | withdraw (i) and record that it was wrong, aligning with the architect's `:290-296` entry. Do not edit the architect's entry |

Also append the three `grep` lines above — and, if you use them, the two absence greps and the
`retired.py` hit — to `workflow/evidence/HO-STRATA-001/artifacts/families.txt` under a new heading
(`=== family ↔ GGUF-architecture mapping (AC-4 correction, RW-1) ===`), each with `exit=`. That is the
one artifact *addition* this rework permits.

### 2.2 AC-7 — correct the gate citation (F2, six places)

`gemm.cu:310-311` → **`gemm.cu:322`**:

| File | Line(s) |
|---|---|
| `artifacts/tuning-table.md` | `:48` (the quoted `// gemm.cu:310-311` comment) |
| `artifacts/tuning-table.md` | `:88` ("static reading of `gemm.cu:310-311`") |
| `workflow/evidence/HO-STRATA-001/commands.log` | `:238` |
| `workflow/evidence/HO-STRATA-001/manifest.md` | `:54` (AC-7 row), `:118` (§4.5) |
| `workflow/handoffs/HO-STRATA-001.md` | `:241` |

### 2.3 Minor citation corrections (F3–F7) — same pass

| # | File:line | Now | Correct |
|---|---|---|---|
| F3a | `artifacts/tuning-table.md:39` | `gemm.cu:276-337` | `gemm.cu:276-339` |
| F3b | `artifacts/tuning-table.md:66` | `gemm.cu:260-274, 310-328` | `gemm.cu:260-274, 318-330` (the `from_package` block) |
| F3c | `artifacts/tuning-table.md:67` | `gemm.cu:285-289` (TABLE=off) | `gemm.cu:290` |
| F3d | `artifacts/tuning-table.md:68` | `gemm.cu:290` (TABLE=on) | `gemm.cu:291` |
| F3e | `artifacts/tuning-table.md:69` | `gemm.cu:346-379` (verbose fallbacks) | `gemm.cu:351-376` |
| F3f | `artifacts/tuning-table.md:72` | `gemm.cu:334` (start line) | `gemm.cu:336` |
| F4 | `artifacts/engine-boundary.md:13` | "`strata.py` is a 5-line stdlib entry point" | "a **43-line** stdlib-only entry point (`wc -l strata.py` → 43) that imports `strata_cli.cli` in `__main__`" |
| F5 | `artifacts/engine-boundary.md:87` | "`--pack` and `--tokens` are the only required pair" | "`--tokens` (or `--tokens-file`) is the only **required** flag; `--pack` defaults to `pack/full` (`artifacts/help.txt:6-10`); `--ple-gguf` is not enforced by the parser but is required for a correct run" |
| F6 | `artifacts/engine-boundary.md:12` | link libs cited to `:513` only | cite `:510` + `:513` + **`:544`** (`target_link_libraries(strata PRIVATE strata_qwen35)`, inside `if(NOT STRATA_HIP_GFX906)`, `:532-546`) |
| F7 | `artifacts/tuning-table-raw.txt` section header | "`=== src/prefill/gemm.cu around 259-320 … ===`" (content runs to line 325 — the origin of F2/F3) | re-capture with `sed -n '259,325p' src/prefill/gemm.cu \| cat -n`-style numbering, or correct the header to `259-325`; a re-capture is a read, not a new measurement |

### 2.4 Bookkeeping

- Regenerate `workflow/evidence/HO-STRATA-001/hashes.txt` over the changed files (manifest,
  commands.log, the four edited artifacts); keep the pinned-input and built-artifact sections and the
  self-exclusion note; the tuning-table and binary hashes do **not** change.
- New commit on `wp/strata-001-gfx1150-build`. **Do not amend the reviewed commit `290922d`.** Subject
  per `ENGINEERING_WORKFLOW.md` §9: `HO-STRATA-001: RW-1 — correct AC-4 family mapping and citation line numbers`;
  body names `RW-HO-STRATA-001-1` and lists F1–F7.

## 3. Evidence required to prove the fix

1. The corrected sentences quoted verbatim in the reply (all four F1 places) plus the diff of each.
2. `artifacts/families.txt` containing the three `grep` lines of §2.1 with their `exit=` codes, under
   the new heading — and the absence greps if used.
3. `grep -rn '310-311' workflow/evidence/HO-STRATA-001/ workflow/handoffs/HO-STRATA-001.md` → **no
   output** (exit 1), and `grep -n 'gemm.cu:' artifacts/tuning-table.md commands.log manifest.md
   workflow/handoffs/HO-STRATA-001.md` → `322`, `318-330`, `290`, `291`, `336`, `351-376`, `276-339`
   with no stale neighbour.
4. A regenerated `hashes.txt` that **recomputes**: `sha256sum manifest.md commands.log test-output.txt artifacts/*.*`
   equals the listing, and the tuning-table SHA256 `aee2867c…ec5549c` and binary SHA256
   `d58ee239…f5858` are unchanged.
5. `git status --porcelain` **empty** on `wp/strata-001-gfx1150-build` after the new commit.
6. `git -C /home/kupipi/Documents/git/strata status --porcelain` **empty** (unchanged), HEAD still
   `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`.
7. A list of the files touched, to show nothing outside this rework changed.

## 4. Guard rails

- **Documentation-only.** No rebuild of `build-hip`; no re-run of `--families`, `--geometry` or
  `strata.py launch`; no re-measurement of the hipBLASLt version; no new model, pack or download; no
  package install or ROCm change.
- **No change to the conclusions**: the build result (exit 0, `d58ee239…`), the support surface
  (`qwen4exp qwen35moe`, `flash_next`), the Control refusal (exit 2) and the tuning verdict
  (MATCH; **default = plain hipBLAS** on gfx1150; taken-vs-fallback not observable) are correct as
  reviewed and must read the same afterwards.
- **No Strata source change** — `/home/kupipi/Documents/git/strata` stays clean at the pin (no edit,
  no patch, no commit, no `git clean` of `build-hip/`).
- **Files you may touch**: `workflow/evidence/HO-STRATA-001/manifest.md`, `commands.log`,
  `hashes.txt`, `artifacts/families.txt`, `artifacts/engine-boundary.md`, `artifacts/tuning-table.md`,
  `artifacts/tuning-table-raw.txt`, and the HO-STRATA-001 log block for RW-1. Nothing else.
- **Do not touch** `workflow/DECISIONS.md`, `workflow/STATUS.md`, `.gitignore`, this RW file, the
  architect's `artifacts/pinned-commit.txt`, `artifacts/engine-boundary.md`'s (c) headless evidence,
  or any other handoff.
- **Do not amend `290922d`**; do not merge; do not push to `main`; no force-push.
- **No scope expansion**: no new acceptance criterion, no re-litigating AC-1…AC-8, no HO-002 work, no
  performance/support/quality claim. If you believe a correction in §2 is itself wrong, stop and reply
  to the architect — do not "fix" it your own way.
- Template §4's "re-run the full acceptance set" is **superseded** for this rework by the architect's
  instruction and by QAQC's re-run of the measurement set: the only re-runs required are the greps in
  §3. State that explicitly in your reply so the record is unambiguous.

## 5. Acknowledgment

| Role | Date (UTC) | Note |
|---|---|---|
| Coder (`coder-primary`) | 2026-11-16 | **ACKNOWLEDGED** (within the 4-working-hour window) and **executed**. F1: the Qwen3.8-Flash-Next claim was wrong and is withdrawn in all four places, replaced with the verified mapping (`qwen4exp` = Qwen3.8-Flash-Next, `qwen35moe` = Qwen3.6-35B-A3B; unimplemented = Mixtral 8x7B, Qwen3-30B-A3B, DeepSeek). F2: the gate citation corrected to `gemm.cu:322` in all six places (the earlier pointer was the HIP device-query failure branch). F3–F7 applied. `hashes.txt` regenerated; new commit on `wp/strata-001-gfx1150-build`, `290922d` not amended. **Three disclosed deviations, all accepted by the architect:** (a) F7's suggested header `259-325` — the capture actually starts at `gemm.cu:255`, so the header says `255-325`; a knowingly-wrong label is not literal compliance. (b) `test-output.txt` was regenerated although it is not on the touchable list: it is a derived concatenation of `artifacts/`, and leaving it stale would have re-published the withdrawn Qwen3.8 claim inside the bundle. (c) `HO-STRATA-001-QAQC.md:170` (stale gate citation) was corrected on the architect's later authorization, which widened the original "nothing else". **Amend disclosed:** the follow-up for (c) and this acknowledgment were folded into the coder's own **unreviewed** RW commit (`5308507` → the tip) with `git commit --amend --no-edit`; it does **not** touch the reviewed commit `290922d`, it rewrites no one else's work, and no other party has based work on it. (d) The commit subject follows the architect's explicit instruction (`RW-HO-STRATA-001-1: …`) rather than §2.4's `HO-STRATA-001: RW-1 — …`. Documentation-only: no rebuild, no re-measurement, no Strata change. |
| Reviewer (`qaqc`) | | re-checks **only** the AC-4 statement and the AC-7/AC-6 citations (F1–F7); the measurement verdicts are not re-opened |

**Escalation:** a second failure on F1 (the AC-4 family statement) goes to the architect
(`ENGINEERING_WORKFLOW.md` §10). F2–F7 failing again is a documentation loop, not a re-measurement.

**Filed by:** `qaqc`, 2026-11-16 UTC, from `workflow/reports/qaqc/HO-STRATA-001-qaqc.md` §4 after the
architect accepted the FAIL of F1 and F2.

## 6. Log

- 2026-11-16 `qaqc`: filed, state `REWORK`, from the FAIL verdict in
  `workflow/reports/qaqc/HO-STRATA-001-qaqc.md`.
- 2026-11-16 `coder-primary`: **accepted (ACK)** and executed as a single documentation pass. Files
  touched: `workflow/evidence/HO-STRATA-001/{manifest.md,commands.log,hashes.txt}`,
  `artifacts/{families.txt,engine-boundary.md,tuning-table.md,tuning-table-raw.txt}`, and the
  `HO-STRATA-001.md` log block. Nothing else. Re-runs performed: only the `grep`/mapping reads in
  §2.1 and §3 — the template's "re-run the full acceptance set" is **superseded** here by the
  architect's instruction and by QAQC's re-run of the measurement set, so no build, no
  `--families`/`--geometry`/`launch`, no hipBLASLt re-measurement. The measurement conclusions are
  unchanged. State returns to `qaqc` for the F1–F7 re-check.
