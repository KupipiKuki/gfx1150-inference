# AUDIT — 7F CI status (2026-11-11): runner deleted + two CI failures

**Auditor:** DeepSeek V4.1 Flash
**Gate:** G6 (Phase 7F)
**Branch:** `wp/7F-evidence-release` @ `cc03d1c`
**Prior audit:** `audit/AUDIT_7F_REWORK_2026-11-09.md` (blockers 7F-2..7F-5
closed; 7F-1 remained)

---

## 1. Verdict

**G6 remains NOT SIGNED.** The previous "only 7F-1 remains" statement is now
superseded by the live CI state. Three items were open; two of the CI/cleanup
items are now fixed in `6533a00`:

1. **7F-1 runner registration was deleted server-side** — the service is dead
   and the GPU job is queued with no runner. **OPEN.**
2. **CPU CI is red** — `test_measured_rss_delta_pin_vs_stream` fails on the
   GitHub-hosted runner (`refault majflt=0`, page cache retained). **OPEN.**
3. **Clean-clone CI was red** — disk exhaustion installing ROCm. **FIX APPLIED
   in `6533a00`** (free-disk step); verify the next run is green.

The stale `ci-gpu.yml` comment and the accidental `cc03d1c` scope (`build-ptds/`,
`7c/RESUME.md`) were also fixed in `6533a00` (plus `.gitignore` entries).

The 7F-2..7F-5 evidence remains closed and audited; do not redo the golden,
benchmark, telemetry, or claims work.

---

## 2. 7F-1 runner — registration deleted (blocker)

Evidence on the gfx1150 host:

```
systemctl status actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service
  Active: inactive (dead)
  "Failed to create a session. The runner registration has been deleted from
   the server, please re-configure. Runner registrations are automatically
   deleted for runners that have not connected to the service recently."
```

`~/actions-runner/.runner` is stale (`agentId 21`), the service is enabled but
exits immediately, and no `Runner.Listener` process exists. The GPU job is
therefore **queued, not running**.

Clock: `timedatectl` shows `System clock synchronized: yes`, so the
"token is not valid until" line is a symptom of the deleted registration, not
a clock problem.

**Fix:** re-register with a new token and restart the service.

```bash
cd ~/actions-runner
# token from GitHub -> Settings -> Actions -> Runners -> New self-hosted runner
./config.sh --url https://github.com/KupipiKuki/gfx1150-inference \
  --token <NEW_TOKEN> --name gfx1150-host --labels gfx1150,rocm \
  --work _work --unattended --replace
sudo ./svc.sh stop
sudo ./svc.sh start
sudo ./svc.sh status
```

If `config.sh` refuses because the local config is already present, remove the
stale local config first (the server-side registration is already gone):

```bash
./config.sh remove --token <REMOVE_TOKEN>   # only if the server still lists it
# or:
rm -f .runner .credentials .credentials_rsaparams
```

Keep `.env` (PATH/ROCM) and `.path`; they are correct. Verify the runner is
**Idle/Active** with labels `self-hosted, Linux, X64, gfx1150, rocm`, then
cancel/re-run the queued GPU workflow.

---

## 3. CPU CI — page-cache assertion (blocker)

Failure (GitHub-hosted CPU lane):

```
tests/test_memory_residency.py::test_measured_rss_delta_pin_vs_stream
AssertionError: re-touching a STREAM-evicted layer must take major faults
assert 0 > 0
[RSS probe] PIN dRSS=65540 kB (warm re-touch majflt=0);
            STREAM dRSS=0 kB (refault majflt=0)
```

The test writes a 64 MiB synthetic GGUF, touches it, evicts via
`MADV_DONTNEED`/`posix_fadvise(POSIX_FADV_DONTNEED)`, then requires a re-touch
to take major faults. On the runner the page cache retained the pages, so the
re-touch was served from cache (0 major faults). `fadvise(DONTNEED)` is
best-effort and will not drop **dirty** pages; the synthetic file is written and
immediately used, with no `fsync`.

Two code-level contributors:

1. **No `fsync` in the test helper.** `tests/test_memory_residency.py:100-102`
   writes then closes the file; pages can still be dirty when eviction runs.
   Fix: `fh.flush(); os.fsync(fh.fileno())` before close.
2. **`MADV_PAGEOUT` failure has no `MADV_DONTNEED` fallback.**
   `src/weight_loader.py::_evict_spans` only uses `MADV_DONTNEED` when
   `mmap.MADV_PAGEOUT` is *absent*. If `MADV_PAGEOUT` exists but raises (e.g.
   not supported for a read-only file mapping), the PTE drop is skipped, so the
   subsequent `fadvise` cannot drop the mapped pages. Fix: on `OSError`, fall
   back to `MADV_DONTNEED` when available.

If the runner kernel still retains the pages after those fixes, make the
**major-fault proof** a documented `pytest.skip` when `refault_majflt == 0`
(the 7D claim is explicitly best-effort), while keeping the PIN/STREAM RSS and
PTE assertions. Do not silently delete the test; record the skip and the
gfx1150 host evidence (`audit/evidence/G4/7D/`).

This is a narrow 7D test/eviction robustness fix, not a claim change.

---

## 4. Clean-clone CI — ROCm install disk — **FIX APPLIED in `6533a00`**

Reported failure: the GitHub-hosted `ubuntu-24.04` runner ran out of disk
installing `amdrocm-core-dev` (~9 GiB). `6533a00` adds the free-disk step
(removes dotnet/Android/ghc/CodeQL/boost, cleans apt) and an apt clean after
the ROCm install. **Pending:** confirm the next clean-clone run is green.

---

## 5. Cleanup items — **FIXED in `6533a00`**

- Removed `build-ptds/Makefile`, `build-ptds/cmake_install.cmake`,
  `7c/RESUME.md` from the branch; added `build-ptds/` and `7c/` to
  `.gitignore`.
- `ci-gpu.yml` no longer says "runner is not registered"; the commented-out
  `# continue-on-error` line is gone and the header states the lane is
  required. **Note:** the runner is currently deleted server-side, so this
  statement will only be true again after re-registration.

---

## 6. G6 status and order

1. Re-register/start the runner; confirm Online + labels.
2. Apply the CPU test/eviction fix; rerun the CPU lane; confirm green.
3. Confirm the `6533a00` clean-clone free-disk fix is green.
4. Rerun all four checks green.
5. Configure the ruleset (four checks, `main` + `vibe/phase7-220201`).
6. Red-team a failing GPU PR; confirm the block.
7. Auditor verifies and signs G6; merge.

**Signed:** DeepSeek V4.1 Flash, primary auditor — 2026-11-11.
