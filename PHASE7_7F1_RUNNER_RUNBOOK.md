# 7F-1 — Self-hosted gfx1150 runner: registration runbook (Gate G6)

**Status:** prepared 2026-11-09. G6 is open **only** on 7F-1.
**Owner:** repository owner (GitHub admin + sudo on the gfx1150 host).
**Auditor:** verifies the runner/labels, the first green run, the required
check, and the red-team block; then signs G6.
**Preflight:** `bash scripts/qa/preflight_gpu_runner.sh` (read-only).

---

## 0. What the gate needs (exact)

7F-1 is done only when **all** of these are true:

1. A self-hosted runner with labels **`gfx1150`** and **`rocm`** is online and
   dedicated to `KupipiKuki/gfx1150-inference`.
2. The `Self-Hosted GPU CI` job runs on it and is **green** with the real
   `pytest -m gpu` lane (**45 passed, 0 skipped** at the current tip).
3. `continue-on-error: true` is removed from `.github/workflows/ci-gpu.yml`.
4. Branch protection requires the check **`GPU correctness (self-hosted
   gfx1150)`** on the release branch(es), alongside the CPU / clean-clone
   checks.
5. A deliberately red GPU suite on a scratch branch is **blocked** by the
   required check (red-team).

Until then G6 cannot be signed and `wp/7F-evidence-release` must not merge.

---

## 1. Host preflight (already verified 2026-11-09)

| Item | State |
|---|---|
| Host | Linux Mint 22.3 (Ubuntu 24.04 base), x86_64, systemd, 406 GiB free |
| GPU | gfx1150 (Radeon 890M), `rocminfo` visible, `/dev/kfd` + `/dev/dri/renderD*` |
| User | `kupipi` is in `render` + `video` groups |
| Toolchain | HIP 7.16 (`/usr/bin/hipcc`), CMake 3.28.3, make, git |
| Interpreter | `/home/kupipi/.pyenv/shims/python3` → **3.14.10**, pip 26.3, numpy 2.5.4, pytest 9.2.0, pybind11 3.1.0 |
| Clean-env build | `env -i … PATH=<pyenv shims>:… cmake -B … && cmake --build …` → **success** |
| Clean-env GPU lane | `PYTHONPATH=<build>:src python3 -m pytest -m gpu -q` → **45 passed** |

**Key provisioning fact:** `/usr/bin/python3` (3.12.3) has **no pip**. The
runner service does not inherit your interactive shell, so its `PATH` must put
the pyenv shims first (or a dedicated venv). Otherwise the workflow's
`python3 -m pip install` fails before the build.

**Preflight warnings (owner decisions):** the repository is **public**, and
`ci-gpu.yml` still has `continue-on-error: true` (correct before the first
green run).

---

## 2. Security decision — do this before registering

> **A self-hosted runner on a public repository can execute arbitrary fork-PR
> code on this host.** This host has your home directory, SSH keys, and repo
> checkout. Do not skip this step.

Choose one:

### Option A — make the repository private during the runner phase (recommended)

Settings → General → Danger Zone → **Change repository visibility → Private**.
Only collaborators can push/PR, so untrusted fork code cannot reach the
runner. Revisit visibility after the release; if you make it public again,
remove the runner or enable the fork-approval gate below first.

### Option B — keep it public, require approval for all outside collaborators

Settings → Actions → General → **Fork pull request workflows from outside
collaborators** → **Require approval for all outside collaborators**.
Also set **Workflow permissions** to *Read repository contents and packages* and
disable **Allow GitHub Actions to create and approve pull requests**.
Every fork PR then waits for a maintainer approval before any job runs.

### Runner identity

- **Quick path (Option A):** run the runner as `kupipi`; the pyenv interpreter
  and GPU groups are ready.
- **Hardened path (Option B):** run as a dedicated unprivileged user
  (`gh-runner`) in `render`/`video`, with its own home and a venv; no sudo, no
  SSH keys. See §8.

---

## 3. Register the runner (GitHub UI)

1. GitHub → **Settings → Actions → Runners → New self-hosted runner**.
2. Choose **Linux / x64**. GitHub shows a download URL and a `./config.sh`
   command containing a **registration token** (valid ~1 hour).
3. On the gfx1150 host (as `kupipi` for the quick path):

```bash
mkdir -p "$HOME/actions-runner" && cd "$HOME/actions-runner"
# use the exact URL from the UI (version changes; do not copy a stale one)
curl -o actions-runner-linux-x64.tar.gz -L <URL_FROM_UI>
# optional but recommended: verify the checksum shown by GitHub
sha256sum actions-runner-linux-x64.tar.gz
tar xzf actions-runner-linux-x64.tar.gz

./config.sh \
  --url https://github.com/KupipiKuki/gfx1150-inference \
  --token <REGISTRATION_TOKEN> \
  --name gfx1150-host \
  --labels gfx1150,rocm \
  --work _work \
  --unattended
```

Do **not** paste the registration token into chat or commit it. The runner
appears under Settings → Actions → Runners with labels `self-hosted`, `Linux`,
`X64`, `gfx1150`, `rocm`.

---

## 4. Give the service the right environment

The workflow calls `python3`, `cmake`, `hipcc`, and `git`; the systemd service
does **not** source `~/.bashrc`. Create `~/actions-runner/.env` (the runner
loads it from its application directory):

```bash
cat > "$HOME/actions-runner/.env" <<'EOF'
PATH=/home/kupipi/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ROCM_PATH=/opt/rocm
EOF
```

The built module already carries an RPATH to `/opt/rocm/lib`, so
`LD_LIBRARY_PATH` is not required; add it only if the GPU job cannot import the
extension.

If `.env` is not honored by your runner version, use a systemd drop-in instead
(find the unit with `systemctl list-units 'actions.runner.*'`):

```bash
sudo systemctl edit 'actions.runner.KupipiKuki-gfx1150-inference.gfx1150-host.service'
# [Service]
# Environment=PATH=/home/kupipi/.pyenv/shims:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Environment=ROCM_PATH=/opt/rocm
```

---

## 5. Install and start the service

```bash
cd "$HOME/actions-runner"
sudo ./svc.sh install kupipi     # omit "kupipi" to install as root (not recommended)
sudo ./svc.sh start
sudo ./svc.sh status
```

Also stop `needrestart` from bouncing the runner mid-job (Debian/Ubuntu):

```bash
echo '$nrconf{override_rc}{qr(^actions\.runner\..+\.service$)} = 0;' \
  | sudo tee /etc/needrestart/conf.d/actions_runner_services.conf
```

Verify online + labels in GitHub → Settings → Actions → Runners, or with an
authenticated API call (`GET /repos/KupipiKuki/gfx1150-inference/actions/runners`).

---

## 6. First green GPU run (advisory, before removing the bypass)

The workflow triggers on **pull_request**, **schedule** (03:00 UTC), and
**workflow_dispatch**. This branch has no PR yet; either:

- open a PR from `wp/7F-evidence-release` to `vibe/phase7-220201` (do **not**
  merge), or
- Actions → Self-Hosted GPU CI → **Run workflow** → branch
  `wp/7F-evidence-release`.

Expected job log at the current tip:

```
GPU lane: 45 passed, 0 skipped, 0 failed, 0 errors, 45 collected
PASS: the GPU lane ran, with no skips
```

`continue-on-error: true` still makes the check advisory, so judge the **job
log/status**, not the check badge. Keep the run URL and the log tail as
evidence.

---

## 7. Make the GPU check required

1. **Remove the bypass** in `.github/workflows/ci-gpu.yml`:

```diff
-    # Advisory until the self-hosted runner is registered (7F-1). While this is
-    # true the job is queued rather than passing, and it is not a G1 gate.
-    continue-on-error: true
```

Update the file's top comment (the "not registered yet" wording) too. Commit
and push; confirm a new GPU run is green **without** the bypass.

2. **Branch protection** (Settings → Branches → Add branch ruleset/rule) for
   `main` **and** `vibe/phase7-220201` (and any release branches):
   require these status checks:
   - `GPU correctness (self-hosted gfx1150)`
   - `CPU Parser, Tokenizer, Sampler & Packaging Suite`
   - `Sdist Install (CPU-only path, GFX1150_SKIP_CMAKE=1)`
   - `Clean-clone documented build (G0 C-1)`

   Require the branch to be up to date before merging, and require PR review if
   that is the project policy. The check names only appear after each workflow
   has run at least once.

3. **Red-team** (do not skip): create a throwaway branch from the 7F branch,
   add a GPU test that fails, register its lane, open a PR, and confirm the
   required GPU check fails and the merge button is blocked:

```bash
git switch -c redteam/gpu-required-check wp/7F-evidence-release
cat > tests/test_gpu_redteam.py <<'EOF'
import pytest
pytestmark = pytest.mark.gpu

def test_redteam_required_gpu_check() -> None:
    assert False, "red-team: the required GPU check must block this PR"
EOF
# add  "test_gpu_redteam.py": "gpu",  to EXPECTED_LANES in
# tests/test_harness_contract.py so the CPU lane stays green and only the GPU
# check is red.
git add tests/test_gpu_redteam.py tests/test_harness_contract.py
git commit -m "redteam: deliberately failing GPU test"
git push origin redteam/gpu-required-check
```

Open a PR to `vibe/phase7-220201`; wait for the GPU job to fail; confirm the
required check is red and merging is blocked. Close the PR and delete the
branch. Record the PR URL and the failed check screenshot.

---

## 8. Hardened runner user (if you keep the repo public)

```bash
sudo useradd -m -s /bin/bash gh-runner
sudo usermod -aG render,video gh-runner
sudo apt install -y python3.12-venv python3-pip
sudo -u gh-runner /usr/bin/python3 -m venv /home/gh-runner/venv
sudo -u gh-runner /home/gh-runner/venv/bin/pip install --upgrade pip
sudo -u gh-runner /home/gh-runner/venv/bin/pip install numpy pytest pybind11 setuptools wheel
```

Then install the runner under `/home/gh-runner/actions-runner` as `gh-runner`,
with `.env`:

```
PATH=/home/gh-runner/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ROCM_PATH=/opt/rocm
```

`sudo ./svc.sh install gh-runner`. Do not grant `gh-runner` sudo and do not put
SSH keys or personal files in its home. The GPU groups are required for
`/dev/kfd` / `/dev/dri` access. If you choose this path, run
`RUNNER_PATH=/home/gh-runner/venv/bin:… bash scripts/qa/preflight_gpu_runner.sh`
from the `gh-runner` account.

---

## 9. Evidence checklist for G6 signoff

Save under `audit/evidence/G6/7F/gpu-runner/` (add with `git add -f` for
`*.log`) and update `audit/evidence/G6/7F/gpu-runner.md`:

- [ ] Runner online + labels (UI screenshot or authenticated API JSON).
- [ ] First green GPU run URL, job ID, and the `45 passed, 0 skipped` log
      tail (before and after removing `continue-on-error`).
- [ ] Commit SHA of the `ci-gpu.yml` change removing the bypass.
- [ ] Branch-protection screenshot/API showing the required check names.
- [ ] Red-team PR URL + failed required check + merge-blocked screenshot.
- [ ] Optional: the first nightly run (03:00 UTC) and its artifact.
- [ ] `bash scripts/qa/preflight_gpu_runner.sh` output (0 FAIL).

---

## 10. Rollback

```bash
cd "$HOME/actions-runner"
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token <REMOVE_TOKEN>   # token from the UI, valid ~1 hour
```

Then delete the runner in Settings → Actions → Runners. If the repository is
made public again, remove the runner first or keep the fork-approval gate on.

---

## 11. Division of labor / timing

| Task | Who | Est. |
|---|---|---|
| Security decision (private vs approval) | Owner | 5 min |
| `preflight_gpu_runner.sh` | Owner/auditor | 2 min |
| Download/config runner (registration token) | Owner (UI + sudo) | 10 min |
| `.env` PATH + service install/start | Owner (sudo) | 10 min |
| First green GPU run | Owner (PR/dispatch) | 15–25 min (build) |
| Remove `continue-on-error` | Coder or owner | 5 min |
| Branch protection | Owner (admin UI) | 5 min |
| Red-team PR + block | Owner/coder | 15–20 min |
| Verify + sign G6 | Auditor | 10 min |

**Quick path (Option A, run as `kupipi`): ~45–60 min.**
**Hardened path (Option B, dedicated user/venv): ~75–90 min.**

---

## 12. What the auditor will verify before signing G6

1. Runner labels `gfx1150,rocm` and online state.
2. The exact first green run on the tip, with `45 passed, 0 skipped` and the
   artifacts retained.
3. No `continue-on-error` in `ci-gpu.yml` at the signoff commit.
4. The required check names in branch protection for `main` and
   `vibe/phase7-220201`.
5. The red-team PR's required GPU check is red and merge is blocked.
6. The preflight script exits 0 (warnings are the owner's documented choices).
7. Then G6 is signed and `wp/7F-evidence-release` is merged.
