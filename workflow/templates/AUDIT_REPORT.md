# Audit report — <HO-ID>

| Field | Value |
|---|---|
| **Handoff** | HO-<project>-<nnn> |
| **Reviewer** | Auditor |
| **Date (UTC)** | |
| **Verdict** | PASS / FAIL |
| **Evidence reviewed** | `workflow/evidence/<HO-ID>/` |
| **QAQC report** | `workflow/reports/qaqc/<HO-ID>-qaqc.md` |

## 1. Evidence verification

- [ ] Manifest complete; commands reproducible.
- [ ] Outputs raw; failures/skips kept verbatim.
- [ ] Artifacts/hashes match the manifest.
- [ ] Environment recorded (OS, kernel, driver, compiler, runtime).
- [ ] No secrets.

## 2. Claim and scope audit

- [ ] Every claim cites a command and an output.
- [ ] One profile per claim (hardware, model, quant, workload).
- [ ] Scope matches the handoff; no silent expansion.
- [ ] Guard rails respected.
- [ ] Rework history is closed or named.

## 3. Findings / rework

| # | Severity | Finding | Required action | Owner |
|---|---|---|---|---|
| 1 | Blocker/Major/Minor | | | |

## 4. Verdict

- **PASS** → `ARCHITECT_APPROVAL`; attach this report.
- **FAIL** → `REWORK`; create `RW-<HO-ID>-<n>` and name the reviewer.

## 5. Owner-task oversight (when applicable)

- Owner task: OT-<project>-<nnn>
- Checkpoints met: <list>
- Owner acceptance: pending / accepted / rejected

## 6. Statement

I did not modify code, tests, docs, or configuration. This report is the only
artifact I wrote.
