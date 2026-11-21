# Audit report — HO-STRATA-012

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-012 (DeepSeek S1–S3), `CODER_DONE` → `AUDIT_REVIEW` via the embedded `QAQC_TO_AUDITOR` record (DEC-018) |
| **Reviewer** | Auditor (`auditor`), runtime model `opencode-go/deepseek-v4.1-flash` (family `deepseek`) — **reported as WAIVED under WAIVER-001**, not a clean independent-family PASS |
| **Date (UTC)** | 2026-11-20 |
| **Verdict** | **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`, conditions C1–C4 before `DONE` |
| **Evidence reviewed** | `workflow/evidence/HO-STRATA-012/` (10 artifacts) on `wp/strata-012-deepseek-s1` @ `764ae79`; bundle assembled at `4395f48`, QAQC-verified at `b15b4bc` |
| **QAQC report** | `workflow/reports/qaqc/HO-STRATA-012-qaqc.md` (`opencode/claude-sonnet-5-5` under DEC-036, PASS, no rework) |
| **Scope reviewed** | Strata `bac859ef9` vs `baf16363b`; exported patch `9a7b280f…`; 6 files, 234 insertions, 31 deletions |
| **Profile (one only)** | gfx1150 / Radeon 890M / Ryzen AI 9 HX 370 · ROCm `core-10.1`, HIP `7.16.26385` · DeepSeek-MoE-16B-base Q4_K_M (`f00ecd83…`) for inspect/refusal; Qwen3.6-35B-A3B UD-Q4_K_XL (`55983c5a…`) for regression. No perf/support claim. |

---

## 1. Evidence verification

- [x] **Manifest complete; commands reproducible.** 10 commands (C1–C10) with CWD, env and exit codes; C10 includes both the `git apply --check` on clean `baf16363` and the patch export. I re-ran C4–C7 and C9 myself (§1.1) and every output is byte-identical to its artifact.
- [x] **Outputs raw; failures/skips preserved.** The refusals (C6, C7) are stored verbatim with exit 2; no skip is presented as a pass. No test skips.
- [x] **Artifacts/hashes match.** `sha256sum -c workflow/evidence/HO-STRATA-012/hashes.txt` from the repo root → **10/10 OK, exit 0**. The evidence patch `9a7b280f…` is byte-equal to `git -C strata format-patch -1 bac859ef9`. All 11 evidence files are **tracked** (`git ls-files` diff empty), none matched by `git check-ignore`.
- [x] **Environment recorded and true.** Mint 22.3, kernel `7.0.0-42-generic`, ROCm `/opt/rocm/core-10.1`, CMake 3.28.3, g++ 13.3.0 — confirmed in this session.
- [x] **No secrets.** Pattern scan over the bundle, handoff and QAQC report (`hf_*`, `ghp_*`, `api_key=`, `Bearer …`) → zero matches. Largest committed evidence file is the 475-line patch; no weights in git.
- [x] **Pins carry digests — NO (A1).** The three mutable pins read "(this bundle's commit)" with "recorded at bundle commit" and no SHA or digest; DEC-024 requires both. Values are supplied in A1 so closure is minutes. Nothing needed by a claim rests on these pins.
- [x] **No untracked/ignored inputs.** All model packs are outside the repo with recorded digests (`f00ecd83…`, `55983c5a…`); I did not re-hash 33.7 GB of packs this session and do not rely on them for a new claim.

### 1.1 Independent re-run (this audit, `build-deepseek/`, signed binary untouched)

```text
--inspect <deepseek.gguf>          rc=0  sha256 9c191c4d…  BYTE-IDENTICAL to artifacts/inspect-deepseek.txt (377 lines: family + 12 fields + tensors: 363 + 363 shape lines)
--inspect deepseek-mismatched.gguf rc=2  strata inspect: blk.0.attn_q.weight is [2049, 2048], the DeepSeek-MoE-16B-base layout wants [2048, 2048]
--native <deepseek.gguf> …          rc=2  BYTE-IDENTICAL to artifacts/native-deepseek-refusal.txt; grep -ci ple = 0
--families                         rc=0  qwen4exp qwen35moe
--native <qwen.gguf> --n 32        rc=0  32/32 IDs identical to HO-STRATA-007/artifacts/generated-token-ids.txt
model_family_test / gguf_geometry_test  rc=0 / rc=0  ALL PASSED / all passed, BYTE-IDENTICAL to artifacts
sha256sum build-hip/strata         d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858  (mtime Nov 15, predates the work)
```

---

## 2. Claim and scope audit

**Patch scope — metadata only. PASS.** I read all 475 lines of `patches/0001-deepseek-family.patch`; the six files are `model_family.hpp`, `geometry.hpp`, `family_layout.hpp`, `gguf_reader.hpp`, `generate.cpp`, `tests/core/model_family_test.cpp`. There is **no kernel, no forward pass, no attention/RoPE/MoE compute, no `src/core/` or `src/kernels/` change, no CMake/docs**. `DeepseekMoe` is referenced only in those six files — **zero occurrences under `src/`** — so the enum cannot reach a run path. `--inspect` reads metadata and tensor headers only and touches no GPU.

**`model_family_runs()` is still false for DeepSeek — the refusal is honest.** The function is byte-identical to the base commit (`return f == ModelFamily::Qwen4Exp;`, no hunk touches it). The refused message ("…is recognised by Strata but this build does not run it yet") is therefore true, and every engine entry point (`generate.cpp:4812`, `native_dense.cpp:358`, `native_head.cpp:43/191`) goes through `model_family_not_supported` and stops.

**Refusal line (AC-2). PASS.** `strata generate: --native …deepseek-moe-16b-base-q4_k_m.gguf: DeepSeek-MoE-16B-base (architecture 'deepseek') is recognised by Strata but this build does not run it yet`, exit **2**, no PLE text, reproduced twice (coder, this audit).

**`--inspect` (AC-1/4/5/6). PASS.** 12 §2 fields all equal (28, 2048, 16, 16, 64, 6, 2, 1408, 10944, 1, 10000, 1e-06); `tensors: 363` with 363 name+shape lines; the real pack exits 0 through the complete-layout check, which means every one of its 363 tensors is named by the table; a 1-shape mutation is refused by name with both shapes. Geometry values come from metadata keys that `check_architecture_deepseek` requires present — no constant can stand in for a missing key.

**Qwen regression (AC-7). PASS.** 32/32 IDs identical to HO-007 on an independent run; `--families` unchanged. The only qwen-observable change is refusal **wording** on the qwen35moe guard path (F1), not behaviour.

**Signed binary (AC-8), patch export (AC-10). PASS.** `d58ee239…` unchanged; patch applies cleanly to `baf16363`; exported patch = `format-patch` of `bac859ef9`.

**T2 accounting — consistent.** 6 files / 234 insertions / 31 deletions / 265 delta, recorded identically in `manifest.md` §2+§7, `hashes-notes.txt`, `commands.log` C10, `DR-HO-STRATA-012-1.md` §2 and `DECISIONS.md` DEC-034 (line 621 records 265 delta; line 638's "234 lines" means insertions). This is **under** T2's 300-inserted-line clause and **over** the 5-file clause by one; DEC-034 approved it as a reviewed trigger, not a ban. Accounting is correct.

**One rationale error (A2).** DR-1 §3 and DEC-034 say `gguf_reader.hpp` is required to make the **`--native`** refusal named. It is not: `generate.cpp` never calls `check_architecture`; the refusal at `:4812` fires as soon as `model_family()` returns `DeepseekMoe`, i.e. from `model_family.hpp` alone. The sixth file **is** genuinely required, but for **`--inspect`**: `inspect_gguf` → `geometry_from_gguf` calls `check_architecture`, which would otherwise return the qwen4exp-only error. Conclusion (6 files) stands; the stated mechanism is wrong and should be corrected in the record.

---

## 3. Findings and F1–F3 disposition

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| A1 | Minor | `hashes-notes.txt` pins three mutable files as "(this bundle's commit)" with no SHA/digest (DEC-024 unmet). Bundle commit is `4395f48`; digests: `HO-STRATA-012.md` `80fff670af07a9cb8064fdbaf576296013fc7f566b08f1f8e836538b9188fca3`, `DECISIONS.md` `843ed7c02b532de548e60a1c3f9051249ad00a9893c27eee56f486ec6fcbd8aa`, `13-family-support-test-plan.md` `023a37de06e785f96f94890fc16cec9279ca000513c1d2eedb6d779f28450bec`. | Record SHA+digests; update the `hashes-notes.txt` line in `hashes.txt` and re-verify 10/10 | Coder (C1) |
| A2 | Minor | DR-1/DEC-034 attribute the sixth file to the `--native` refusal; it is required for `--inspect` (§2). 6-file conclusion unaffected. | Correct the rationale in DEC-034 / DR-1; no code change | Architect (C3) |
| A3 | Minor | DEC-035 records the signed binary as `d58ee359…`; actual is `d58ee239…`. | Typo fix in the decision record | Architect (C3) |
| A4 | Minor | Bookkeeping: `HO-STRATA-012.md:7` still `CODER_DONE`, `HO-STRATA-012-QAQC.md` still `PROPOSED`, `STATUS.md:18` still `BLOCKED (DEC-035)` although QAQC passed at `764ae79`. Under DEC-018 the QAQC report is the authoritative transition record, so this is the architect's mirror duty, not a QAQC defect. | Mirror the state, unstale STATUS on signoff | Architect (C4) |

**QAQC's minor findings — none disqualifying for S1–S3:**

- **F1 (shared refusal wording) — upheld Minor, correctly carried, and it is the one item needing an explicit architect decision.** The change is text-only in a family-generic function; the qwen4exp **run** path is untouched (regression exact) and the qwen35moe tests still assert the retained substring. It does drop the CUDA/HIP/SYCL guidance from the qwen35moe guard message, which the handoff's out-of-scope clause ("no qwen behaviour changes of any kind") sweeps broadly — so it should be **recorded as accepted scope rather than silently absorbed**. Making it DeepSeek-only would have duplicated the sentence, and the old text ("runs on the … HIP builds") is false *on this HIP build*, so the change is defensible. No rework; C2.
- **F2 (shallow arch check) — upheld, correctly carried to S4.** `check_architecture_deepseek` checks key presence/numeric only, but the sanity checks (non-zero widths, `n_head % n_head_kv`, dense-block range) run in `geometry_from_gguf`, which both `--inspect` and any future loader call; and no DeepSeek run path exists, every entry point refuses. A stricter guard is an S4 prerequisite, not an S1–S3 defect.
- **F3 (temp reuse) — upheld, correctly carried, non-blocking.** The mismatch **refusal** is independently reproduced by me and names the parsed shape, so AC-6 holds; but the fixture's *generation* is not in the bundle (only the coder's C7 command assumes the file). That is a reproducibility gap for the fixture, not for the claim: C2 adds the recipe. The stale `/tmp/opencode/q12` worktree QAQC found and discarded was handled correctly (fresh worktree rebuilt); the shared scratch root is the risk, not QAQC's method. The 10.8 GB fixture still in `/tmp/opencode` should be deleted after C2.

---

## 4. Verdict

- **PASS (WAIVED — WAIVER-001)** → `ARCHITECT_APPROVAL`. Attach this report and `workflow/evidence/HO-STRATA-012/`. No `RW-HO-STRATA-012-*` is opened: every acceptance criterion reproduces, no claim is unsupported, and the patch is the metadata-only overlay DEC-034 approved.
- The PASS is conditional on records, not measurements:

| # | Condition | Owner |
|---|---|---|
| **C1** | Add the SHA+digests in A1 to `hashes-notes.txt`, refresh its line in `hashes.txt`, re-verify 10/10 | Coder, same work-package branch |
| **C2** | Record the command/recipe that produced `deepseek-mismatched.gguf` (or a synthetic fixture) so AC-6 is reproducible from the bundle; delete the 10.8 GB copy afterwards | Coder |
| **C3** | Correct DEC-034/DR-1's sixth-file rationale (A2) and DEC-035's `d58ee359` (A3); record F1 (qwen35moe guard wording) as accepted scope, or queue a restore | Architect |
| **C4** | Mirror `AUDIT_REVIEW`/QAQC PASS into `HO-STRATA-012.md` + `HO-STRATA-012-QAQC.md` (DEC-018), unstale `STATUS.md:18`, then SIGNED → `DONE` and merge per DEC-015 | Architect |

**Not signed by the auditor.** The architect decides `DONE` and merges.

---

## 5. Owner-task oversight

- Owner task: `OT-STRATA-001`. This handoff is the enabling work for **checkpoint 4 (DeepSeek baseline)**, authorized by DEC-031/DEC-033 after the owner chose DeepSeek first.
- Checkpoint status: S1–S3 (recognition, geometry, inventory) is now proven; **checkpoint 4 itself stays open** — the forward pass is S4 and is not authorized, so no baseline can be claimed.
- Owner acceptance: **pending** — not recorded until the architect signs.

---

## 6. Statement

I did not modify code, tests, docs, configuration, evidence, handoffs, or the Strata checkout. My only write is this report; my scratch outputs are under `/tmp/opencode/`. I ran the built `build-deepseek/strata` and the two test binaries read-only (inspect ×2, mismatch refusal, native refusal, `--families`, one Qwen regression, two test binaries) and verification commands (`sha256sum`, `git`, `uname`, `hipcc`, `cmake`, `g++`). `build-hip/` was not touched.

---

### AUDITOR_TO_ARCHITECT (embedded per DEC-018)

| Field | Value |
|---|---|
| **Type** | AUDITOR_TO_ARCHITECT |
| **From → To** | Auditor (`auditor`, `deepseek-v4.1-flash`, WAIVER-001) → Architect |
| **Handoff** | HO-STRATA-012 (DeepSeek S1–S3, DEC-033) |
| **State** | `AUDIT_REVIEW` → **`ARCHITECT_APPROVAL`** |
| **Report** | `workflow/reports/audit/HO-STRATA-012-audit.md` |
| **Evidence** | `workflow/evidence/HO-STRATA-012/` — 10/10 hashes OK at `764ae79` (bundle `4395f48`) |
| **Patch** | `patches/0001-deepseek-family.patch` `9a7b280f…`; Strata `bac859ef9` vs base `baf16363b`; 6 files / 234+31 |
| **Verdict** | PASS (WAIVED) with conditions C1–C4 |
| **Open items** | A1 pins (Coder), A2/A3/F1 records (Architect), A4 state mirror + sign (Architect) |
| **Owner** | OT-STRATA-001 checkpoint 4 enabling work; acceptance pending |
