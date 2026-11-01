# Evidence Bundles

Every gate in [PHASE7_IMPLEMENTATION_HANDOFF.md](../../PHASE7_IMPLEMENTATION_HANDOFF.md) must commit a reproducible evidence bundle here.

## Layout

```
audit/evidence/
  G0/
    7.0-baseline/
      env.txt
      parent-sha.txt
      candidate-sha.txt
      diffstat.txt
      cpu-suite.log
      gpu-suite.log
      sdist-install.log
      notes.md
  G1/
    7A-1-pytest-harness/
      ...
  G2/
    7B-1-special-token-encode/
      red.log
      green.log
      gate-commands.log
      claims-check.log
      qaqc-probes/
      notes.md
```

## Rules

- **Text only.** No multi-megabyte binaries. Large fixtures go in `tests/fixtures/` with provenance.
- **Exact SHAs.** Record parent and candidate; the candidate must be the reviewed, frozen SHA.
- **Red before green.** `red.log` must show the new test failing on the parent; `green.log` the same test passing on the candidate.
- **Commands + exit codes.** `gate-commands.log` contains every required command and its exit status.
- **Environment.** `env.txt` contains OS, kernel, ROCm/HIP, `rocminfo` GPU line, Python, NumPy, pybind11, CMake, and `git rev-parse HEAD`.
- **QAQC probes.** `qaqc-probes/` holds the reviewer's independent probes, not copies of the coder's tests.
- **No secrets, prompts, or model data** that cannot be redistributed.
- **Provenance.** Golden data must include upstream version/commit, command, and input/output hashes.

A bundle missing any required file is an automatic gate failure.
