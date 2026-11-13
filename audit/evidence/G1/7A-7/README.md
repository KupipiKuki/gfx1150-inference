# G1 / 7A-7 — evidence bundle

GPU CI scaffold: `.github/workflows/ci-gpu.yml` for a self-hosted gfx1150 runner,
with the guard that makes a skipped GPU lane a failure rather than a pass.

| file | what it is |
|---|---|
| `notes.md` | what was added, the skip-guard red/green, the gate state, and the two stated deviations |
| `workflow.yml` | the shipped workflow, copied verbatim |
| `yaml-validation.log` | the mechanical check of every clause of the brief's section 3 (20/20), by `validate-workflow.py` |
| `validate-workflow.py` | regenerates `yaml-validation.log` |
| `skip-guard.log` | the guard's red/green pair, with the guard extracted verbatim from the parsed workflow |
| `gpu-lane.log` | the GPU lane executed on the gfx1150 host with the workflow's exact commands (18 passed / 0 skipped) |
| `gpu-lane.xml` | the junit report the guard parses |
| `configure.log` / `build.log` | the configure and build steps, same host |
| `actions-state.log` | what the GitHub REST API knows about the workflow right now |
| `env.txt` | environment, the runner state, and the lane result |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the base of the branch (`a873a9c`) |
| `candidate-sha.txt` | the work commit under review (`955fa04`) |

No self-hosted runner is registered, so the workflow was **not** executed by GitHub
Actions; its steps were executed verbatim on the gfx1150 host instead.
