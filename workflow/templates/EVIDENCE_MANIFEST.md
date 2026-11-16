# Evidence manifest — <HO-ID>

| Field | Value |
|---|---|
| **Handoff** | HO-<project>-<nnn> |
| **Commit / branch** | `<sha>` / `wp/...` |
| **Author / date (UTC)** | <role> / <date> |
| **Environment** | OS, kernel, driver, compiler, runtime, Python/ROCm versions |
| **Working directory** | |

## 1. Commands

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| 1 | | | | `test-output.txt` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | | | | |

## 3. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| model | | |
| prompt / data | | |
| log / JSON / report | | |

## 4. Failures, skips, limits

- <raw failure/skip, with the command and the reason>
- <what was not tested and why>

## 5. Environment notes

- <env vars that matter, e.g. `GFX1150_SKIP_CMAKE`, `HSA_OVERRIDE_GFX_VERSION`>
- <known host caveats>

## 6. Statement

- [ ] Commands are reproducible.
- [ ] Outputs are raw; no paraphrasing.
- [ ] No secrets.
- [ ] Every claim cites an artifact.
- [ ] One profile per claim.
