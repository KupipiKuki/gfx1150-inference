# 7F-1 — Required self-hosted GPU CI: **BLOCKED** (owner action outstanding)

## Status

`BLOCKED`. The runner registration (and making the job required) needs
GitHub **owner/repo-admin** actions that this work package cannot perform:

* no self-hosted runner is installed on the gfx1150 host
  (`~/actions-runner` does not exist; no runner service is registered);
* the GitHub connector available to this work package exposes no
  Actions/runner registration or branch-protection operations
  (repository-file and PR operations only);
* `ci-gpu.yml` therefore still carries `continue-on-error: true`, exactly
  as 7A-7 documented, and the GPU lane must NOT be counted as a green
  required CI in this bundle.

Per the brief (§3 7F-1): *"If the runner is unavailable: stop and record
the blocker; do not claim G6."* Nothing was weakened to work around it.

## What the evidence does show

* The GPU lane itself is real and green **locally** on the target hardware:
  `python -m pytest -m gpu -q` → **39 passed** on this gfx1150 host
  (`gpu-lane.log` in this bundle). This is supporting evidence only — the
  contract says "a GPU lane result only counts from the self-hosted real
  runner once 7F-1 lands".
* The CI job already enforces "a skip is not a pass" (junit count parsing)
  and retains logs/artifacts, so once the runner registers, a green run of
  the current workflow gives the required-gate behavior with no additional
  logic.

## Owner steps to unblock (exact)

1. Register a self-hosted runner for `KupipiKuki/gfx1150-inference`
   (Settings → Actions → Runners → *New self-hosted runner*), executing the
   generated `config.sh`/`run.sh` **on this gfx1150 host**, with labels:
   `gfx1150`, `rocm` (the job selects `runs-on: [self-hosted, gfx1150, rocm]`).
   Install it as a service so nightly scheduling works:
   `sudo ./svc.sh install && sudo ./svc.sh start`.
2. Verify one green run of **Self-Hosted GPU CI** (it must report
   `PASS: the GPU lane ran, with no skips`).
3. Apply the workflow diff below (remove `continue-on-error`) and delete
   the advisory comment.
4. Make the job required: Settings → Branches → Branch protection for
   `main` (and the release branches): require the status check
   `GPU correctness (self-hosted gfx1150)`, plus `CPU Parser, Tokenizer,
   Sampler & Packaging Suite` / `Sdist Install`.
5. Red-team it: push a deliberately red GPU suite on a scratch branch and
   confirm the job blocks the PR (brief acceptance criterion).

## Ready-to-apply workflow diff (`.github/workflows/ci-gpu.yml`)

```diff
@@ jobs.gpu-correctness
     name: GPU correctness (self-hosted gfx1150)
     runs-on: [self-hosted, gfx1150, rocm]
-    # Advisory until the self-hosted runner is registered (7F-1). While this is
-    # true the job is queued rather than passing, and it is not a G1 gate.
-    continue-on-error: true
     timeout-minutes: 60
```

(The header comment block above the job should also drop the "advisory"
sentences once the first green run exists; that wording is in the same
file's top comment.)
