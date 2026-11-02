# G1 / 7A-8 — clean-clone build entry point

**Package:** 7A-8 (closes G0 condition C-1)
**Branch:** `wp/7A-8-build-entrypoint`
**Base:** `4bcffeb` (the branch base; 7A-8 starts in parallel from there)
**Audit trace:** G0 `AUDIT_G0_BASELINE_DEEP_2026-11-01.md` §AUD-4 / AUD-9 (C-1),
`PHASE7_IMPLEMENTATION_HANDOFF.md` §6 (7A-8 row)
**red/green:** **applies** — `red.log` (the documented command fails on the parent) and
`green.log` (it succeeds on the candidate). The red/green pair is the deliverable here,
because the package *is* a build fix.

---

## The defect (G0 C-1)

The README documents:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
```

On a clean tree that fails:

```
CMake Error at CMakeLists.txt:17 (find_package):
  Could not find a package configuration file provided by "pybind11" with any
  of the following names:
    pybind11Config.cmake
    pybind11-config.cmake
-- Configuring incomplete, errors occurred!
```

`pybind11` is a Python package: its CMake package ships inside `site-packages`, which
is not on `CMAKE_PREFIX_PATH`. So `find_package(pybind11 REQUIRED)` only worked when
the caller happened to export `pybind11_DIR` — which is exactly what `setup.py` does for
`pip install`. The developer build and the packaging build therefore used different
prerequisites, and the documented command was not reproducible.

### A detail the audit did not record

The failure was **environment-dependent**, which is why it had survived. CMake also
searches prefixes derived from `PATH`. On a host whose `PATH` contains the interpreter's
own `bin` directory, the interpreter's prefix is searched and pybind11 is found
there — so the parent's command *worked* by luck. On a host whose `PATH` contains only
the interpreter's `shims` directory (the G0 auditor's host, and this one when `cmake` is
invoked by hand), it failed.

Both are recorded in `red.log`: the failure, and the "lucky" case. The point is that a
build must not depend on which of the two the environment happens to be — the fix
removes the dependency on either.

## The fix

### `CMakeLists.txt`

The build now discovers pybind11 the way `setup.py` does — from the interpreter it is
building for:

1. `find_package(pybind11 CONFIG QUIET)` — succeeds unchanged when pybind11 is
   installed system-wide, and honours an explicit `-Dpybind11_DIR=...`.
2. Otherwise ask the interpreter: `python -m pybind11 --cmakedir` (pybind11 ≥ 2.6),
   falling back to `python -c "import pybind11; print(pybind11.get_cmake_dir())"`.
3. Configure with the directory that was found.
4. If neither works, fail with an actionable message naming the interpreter and the
   `pip install` / `-Dpybind11_DIR` remedies.

Two deliberate choices:

* **The discovery runs before `project()`.** A missing pybind11 is then reported as
  such instead of being masked by a missing HIP toolchain, and — the practical
  reason — the discovery can be exercised on a host without ROCm, which is what lets
  the regression test and the CI job check the C-1 fix on any runner. The ROCm paths
  (`ROCM_ROOT`, `CMAKE_HIP_COMPILER`, `CMAKE_PREFIX_PATH`) are still set before
  `project()`, unchanged.
* **The status line `pybind11 CMake package: <path>`** reports what was found. It is
  what the regression test asserts, so a build that only works because of an ambient
  hint cannot pass silently.

`setup.py` is unchanged: it still passes `-Dpybind11_DIR=...`, which now simply
takes the fast path in step 1.

### `tests/test_build_configure.py` (new)

The regression test. It runs the documented command against a **fresh** build directory
(no CMake cache) with `pybind11_DIR` removed from the environment and asserts:

| test | asserts | needs ROCm |
|---|---|---|
| `test_documented_configure_locates_pybind11_without_an_ambient_hint` | pybind11 was discovered explicitly (the status marker) and CMake did not report it missing | no |
| `test_documented_configure_succeeds_with_the_hip_toolchain` | the configure exits 0 | yes (skipped otherwise) |
| `test_configure_does_not_leave_a_cache_outside_the_build_directory` | the configure writes nothing into the source tree | no |

The module is registered in the 7A-1 lane contract (`EXPECTED_LANES`) as a CPU-lane
test: it needs neither the compiled extension nor a GPU.

### `README.md`

The build section gained a **Prerequisites** table (ROCm, Python with development
headers, `pybind11` installed for the interpreter, CMake, a host C++ compiler) and now
states that the configure finds pybind11 through the interpreter, so no `pybind11_DIR`
is needed. The documented command itself is unchanged.

### `.github/workflows/ci-build.yml` (new)

Runs on every push and pull request, from a fresh checkout:

1. install the documented prerequisites (`numpy`, `setuptools`, `wheel`, `pybind11`);
2. register AMD's stable ROCm apt repository and install `amdrocm-core-dev` (the HIP
   compiler, headers and runtime);
3. `env -u pybind11_DIR cmake -B build -DCMAKE_BUILD_TYPE=Release` — the documented
   command, with no ambient hint and no build cache;
4. `cmake --build build -j`;
5. the configure smoke test;
6. build the sdist and install it in a clean venv (full install, with the extension).

Step 2 follows AMD's documented package-manager instructions
(`rocm.docs.amd.com`, "Register ROCm repositories"), including the signing key
published at `https://stable.repo.amd.com/rocm/gpg/packages.gpg`. That key's
fingerprint (`D0F0 04A0 025A 1145 C780 7FCD 0701 EAC4 D5E0 2107`) is the one this
host's keyring already uses — verified, not assumed.

The workflow pins `ubuntu-24.04` because the ROCm repository path is per-release
(`ubuntu2404`).

## Verification

| check | result |
|---|---|
| documented command, fresh clone, no `pybind11_DIR`, no cache | **exit 0** (was exit 1) — `red.log` → `green.log` |
| the same, with the interpreter's prefix on `PATH` | exit 0 — and now for the right reason (the explicit discovery) |
| the same with an explicit `-Dpybind11_DIR=...` | exit 0 — no regression for callers that pass the hint |
| `cmake --build build -j` | exit 0, `matmul_module.so` linked |
| `pytest -m gpu` | 18 passed, 43 deselected |
| `pytest -m "not gpu"` | 43 passed, 18 deselected (37 before + 3 new + 3 lane-contract cases) |
| full `pytest -q` | 61 passed |
| `test_cpu_only.py` / `-O` | 12/12 each |
| sdist build + **full** clean-venv install | exit 0; `inference`, `gguf_parser`, `matmul_module`, `kv_cache`, `tokenizer` import; the `gfx1150-infer` CLI is installed — `sdist-install.log` |
| the new smoke test against the **parent** | **fails** (the discovery marker is absent) — the regression guard works |
| `audit/claims_baseline.txt` | untouched |
| `scripts/qa/**`, `audit/CLAIMS_LEDGER.md`, the 7A-6 evidence | untouched |

## Limitations and follow-ups

1. **The compiled artifact's digest is not reproducible.** `matmul_module.so` embeds
   its build path, so the digest differs between build directories (the G0 artifact's
   digest, `c8f6b19b…`, is the one in the repo's `build/`). The GPU lane passing
   18/18 is the functional check; no digest is claimed.
2. **The CI job installs ROCm from AMD's stable repository**, which is a multi-gigabyte
   download on every push. It is the faithful reproduction of the documented
   prerequisites, but it is expensive; if that turns out to be a burden, the job can be
   narrowed to the configure step and the build moved to the self-hosted gfx1150
   runner (7A-7's `ci-gpu.yml`, 7F-1's runner). Not decided here.
3. **`find_package(Python COMPONENTS ... Development.Module)` still requires the
   Python development headers.** That is pre-existing and is now documented as a
   prerequisite. On a host without them the configure fails at that line, before
   anything pybind11-related.
4. **The 7A-1 follow-up's C-7A1-5 is still open** (`conftest.py` is not in the
   sdist). `tests/` is not shipped in the sdist at all, so the new test module does
   not change the sdist contents. 7A-5 owns that.
5. **Not implemented here:** the handoff's release-time "ledger vs README diff"
   check, and the GPU CI workflow — both belong to 7F-5 and 7A-7.

## Rollback

Revert the commit. The changes are confined to `CMakeLists.txt`, the README build
section, `tests/test_build_configure.py`, the lane registration in
`tests/test_harness_contract.py`, the new `.github/workflows/ci-build.yml` and this
evidence directory. `setup.py`, `pyproject.toml`, `MANIFEST.in`, `src/` and the
runtime are unchanged, so reverting restores the previous behaviour exactly.

## Claims changed

None. No public claim was added, removed or re-qualified. The README's build section
gained a prerequisites table and an explanation of how pybind11 is found; the
documented build command itself is unchanged and now actually works.
