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
| [CLAIMS_LEDGER.md](CLAIMS_LEDGER.md) | Machine-checkable ledger of every public capability/performance claim: status, README match string, inline qualification, evidence pointer; enforced by `scripts/qa/check_claims.py` with a G6-expiring baseline |
| [evidence/README.md](evidence/README.md) | Evidence-bundle layout and rules for each Phase 7 gate |
| [remediation_plan.md](remediation_plan.md) | Phase 1 review & remediation plan (build/kernel defects) |
| [HANDOFF_PHASE2.md](HANDOFF_PHASE2.md) | Phase 2 handoff: review fixes and doc reconciliation |
| [QAQC_FINAL_REPORT_PHASE5.md](QAQC_FINAL_REPORT_PHASE5.md) | QA/QC final report for the Phase 5 review |

**Current status:** buildable and hardware-verified for text-only llama-family `Q4_0`/`Q4_K`/`Q8_0` models. The v0.6.2 §6 P0 backlog (chat special tokens, `add_bos_token`, Phi-3/Gemma, residency/stream honesty) remains open; see [VERIFICATION_2026-11-01.md](VERIFICATION_2026-11-01.md) §4.
