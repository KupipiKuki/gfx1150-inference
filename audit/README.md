# Audit & Remediation Reports

Historical audit, review, and handoff documents for gfx1150-inference, kept for traceability.

| File | Description |
|---|---|
| [AUDIT_REPORT_v0.5.0.md](AUDIT_REPORT_v0.5.0.md) | Overall package audit of v0.5.0 (post-Phase-5 merge), findings A-1..A-8 |
| [AUDIT_REPORT_DEEP_2026-10-31.md](AUDIT_REPORT_DEEP_2026-10-31.md) | Deep technical audit of v0.5.0 (`af5fff4`): packaging blocker B-1, tokenizer/arch/quant correctness (C-*), streaming/performance (P-*), security (S-*), robustness (R-*), testing (T-*) |
| [AUDIT_REMEDIATION_v0.6.0.md](AUDIT_REMEDIATION_v0.6.0.md) | Post-v0.5.0 audit with security/performance/packaging taxonomy (S/P/D) + v0.6.0 resolution log |
| [AUDIT_REMEDIATION_v0.6.1.md](AUDIT_REMEDIATION_v0.6.1.md) | Second-pass review of remediation commit `64b8a8d`, reconciled with the DeepSeek 2026-10-31 audit (B/C/S/R/T/L) |
| [REVIEW_v0.6.1_c75914b.md](REVIEW_v0.6.1_c75914b.md) | Independent review of `c75914b`: verifies the sdist/Q6_K/GPT-2/parser fixes and documents the still-open special-token, `add_bos`, Phi-3/Gemma, residency, and stream-topology issues |
| [AUDIT_REMEDIATION_v0.6.2.md](AUDIT_REMEDIATION_v0.6.2.md) | Third-pass review of commit `c75914b`, **finalized** with the independent-review reconciliation and the P0/P1/P2 testing-phase backlog (authoritative remediation report) |
| [VERIFICATION_2026-11-01.md](VERIFICATION_2026-11-01.md) | Build + hardware verification on a real gfx1150 host: CMake/sdist/`pip install` results, all 12 CPU tests and all 5 GPU suites passing, the `pybind11_DIR` sdist-install fix, and the still-open v0.6.2 backlog |
| [VERIFICATION_MISTRAL4_SANDBOX_2026-11-03.md](VERIFICATION_MISTRAL4_SANDBOX_2026-11-03.md) | Sandbox-side (CPU-only, non-GPU) verification of `vibe/phase7-220201` @ `cb74921`: pytest lanes, CPU suite, claims checker exit codes, CI status — PASS, no issues; complements the on-host DeepSeek audits |
| [AUDIT_G0_BASELINE_DEEP_2026-11-01.md](AUDIT_G0_BASELINE_DEEP_2026-11-01.md) | Independent G0 audit of `wp/7.0-baseline` (clean-clone build/suites/sdist reproduction) — **PASS WITH CONDITIONS**: setup.py attribution error, pytest return-value/CPU-marker defects, ledger flag inconsistency, and the C-1/7A file-set gap; conditions for G1 |
| [AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md](AUDIT_7A-1_PYTEST_HARNESS_DEEP_2026-11-02.md) | Independent 7A-1 audit of `wp/7A-1-pytest-harness` — **PASS WITH CONDITIONS**: harness criteria reproduced; two meta-test guards accept wrong-lane and nested-raise modules; QF-1..3 record corrections; 7A-1 follow-up before merge |
| [AUDIT_7A-1_FOLLOWUP_DEEP_2026-11-02.md](AUDIT_7A-1_FOLLOWUP_DEEP_2026-11-02.md) | Independent audit of the 7A-1 follow-up — **PASS**: C-7A1-1/2/3 closed; exact-lane, nested-def, wrong-marker, hard-dependency and nested-assert canaries reproduced; QF corrections verified; merge approved |
| [AUDIT_7A-6_CLAIMS_CHECKER_DEEP_2026-11-02.md](AUDIT_7A-6_CLAIMS_CHECKER_DEEP_2026-11-02.md) | Independent 7A-6 audit — **PASS WITH CONDITIONS**: checker/canaries/adversarial probes reproduce; strict-clean output prints FAIL with exit 0; QAQC probe-log inconsistencies; evidence-provenance and ID 3 literal conditions |
| [AUDIT_7A-6_FOLLOWUP_DEEP_2026-11-02.md](AUDIT_7A-6_FOLLOWUP_DEEP_2026-11-02.md) | Independent 7A-6 follow-up audit — **PASS**: C-7A6-1/2/3/4 closed; strict-clean, 12 canaries, mutations, ID 3 removal and QAQC log corrections reproduced; QF-1/2/3 closed by auditor evidence erratum |
| [AUDIT_7A-8_BUILD_ENTRYPOINT_DEEP_2026-11-02.md](AUDIT_7A-8_BUILD_ENTRYPOINT_DEEP_2026-11-02.md) | Independent 7A-8 audit — **PASS WITH CONDITIONS**: red/green build, lucky-PATH, override, guard and 43/18/61 reproduced; QF-1 missing pytest in `ci-build.yml` blocks CI acceptance; QF-2 merge-time ledger refresh (+19 lines) |
| [AUDIT_7A-8_FOLLOWUP_DEEP_2026-11-02.md](AUDIT_7A-8_FOLLOWUP_DEEP_2026-11-02.md) | Independent 7A-8 follow-up audit — **PASS**: C-7A8-1 closed; RED/GREEN CI runs and tip check-runs verified via the public API; QF-2 merge checklist recorded for execution |
| [AUDIT_7A-7_GPU_CI_DEEP_2026-11-03.md](AUDIT_7A-7_GPU_CI_DEEP_2026-11-03.md) | Independent 7A-7 audit — **PASS**: workflow 20/20, skip guard four cases, host lane 18/0 and API gate state verified; accepted as queued-not-green; QF-1/QF-2 closed |
| [AUDIT_7A-5_CI_SDIST_DEEP_2026-11-03.md](AUDIT_7A-5_CI_SDIST_DEEP_2026-11-03.md) | Independent 7A-5 audit — **PASS**: sdist red/green, conftest present, clean install/module split, API-verified CI run, 7A-2 closeout; host-dependence caveat recorded for the sdist job |
| [CLAIMS_LEDGER.md](CLAIMS_LEDGER.md) | Machine-checkable ledger of every public capability/performance claim: status, README match string, inline qualification, evidence pointer; enforced by `scripts/qa/check_claims.py` with a G6-expiring baseline |
| [evidence/README.md](evidence/README.md) | Evidence-bundle layout and rules for each Phase 7 gate |
| [remediation_plan.md](remediation_plan.md) | Phase 1 review & remediation plan (build/kernel defects) |
| [HANDOFF_PHASE2.md](HANDOFF_PHASE2.md) | Phase 2 handoff: review fixes and doc reconciliation |
| [QAQC_FINAL_REPORT_PHASE5.md](QAQC_FINAL_REPORT_PHASE5.md) | QA/QC final report for the Phase 5 review |

**Current status:** buildable and hardware-verified for text-only llama-family `Q4_0`/`Q4_K`/`Q8_0` models. The v0.6.2 §6 P0 backlog (chat special tokens, `add_bos_token`, Phi-3/Gemma, residency/stream honesty) remains open; see [VERIFICATION_2026-11-01.md](VERIFICATION_2026-11-01.md) §4.

**Independent reconciliation (2026-11-02):** Mistral 4.0 reviewed the G0, 7A-1, and 7A-1 follow-up audits and found no issues; no separate report was filed. No reconciliation changes were required.
