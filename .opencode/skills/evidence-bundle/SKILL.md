---
name: Evidence bundle
description: Build the reproducible evidence manifest for a handoff (commands, raw outputs, artifacts, hashes, environment)
---

# Evidence bundle

Use for every coder, QAQC, and audit handoff. Template:
`workflow/templates/EVIDENCE_MANIFEST.md`. Directory:
`workflow/evidence/<HO-ID>/`.

## Steps

1. Create `workflow/evidence/<HO-ID>/` with
   `manifest.md`, `commands.log`, `test-output.txt`, `artifacts/`, `hashes.txt`.
2. Record the environment: OS, kernel, driver, compiler, runtime, Python/ROCm,
   and any environment variable that changes behavior.
3. For each acceptance criterion, record the exact command, working directory,
   exit code, and output file.
4. Keep raw output. Failures and skips stay verbatim with the reason; never
   paraphrase a failure or hide a skip.
5. Hash the important artifacts: model, prompt/dataset, logs, reports
   (`sha256sum`).
6. Redact secrets: PATs, tokens, keys, private data. A secret in the evidence
   is a failed handoff.
7. State the limits: what was not tested, on which hardware/model/quant, and
   why. One profile per claim.

## Validation

- [ ] Commands are copy-paste reproducible.
- [ ] Outputs are raw and match the commands.
- [ ] Artifacts and hashes match the manifest.
- [ ] Environment is recorded.
- [ ] No secrets.
- [ ] Every claim cites an artifact.
- [ ] One profile per claim.

## Rule

No artifact, no claim. "Works", "faster", "supported" require the command and
the output that show it.
