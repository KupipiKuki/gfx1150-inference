# Auditor rework probes — 7D (G4)

**Auditor:** DeepSeek V4.1 Flash · **Date:** 2026-11-07
**Candidate:** `wp/7D-memory-robustness` @ `0b36b26`

`rework_probes.py` is the primary auditor's red probe for the two G4 rework
items:

1. negative `llama.block_count` with zero `blk.*` tensors must raise
   `ValueError` (currently accepted with `num_layers=-1`);
2. engine `residency="auto"` with no readable budget source must emit
   `NoBudgetFallbackWarning`, select STREAM, and keep
   `residency_decision.weight_budget is None` (currently it records a
   fabricated 0-byte budget and no warning).

Run:

```bash
PYTHONPATH=src:build:tests python3 audit/evidence/G4/7D/audit-probes/rework_probes.py
```

Current result: **exit 1** (both defects present), captured in
`rework-probes.log`. After the coder/QAQC fixes, it must exit 0; QAQC should
attach the green run to the rework evidence.
