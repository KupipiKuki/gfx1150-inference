# Evidence manifest — HO-STRATA-012

| Field | Value |
|---|---|
| **Handoff** | HO-STRATA-012 |
| **Commit / branch** | `wp/strata-012-deepseek-s1` / see §7 for Strata branch `strata-012-deepseek-s1` @ `bac859ef9` |
| **Author / date (UTC)** | `coder-primary` / 2026-11-20 |
| **Environment** | Linux Mint 22.3 (Zena), kernel 7.0.0-42-generic, AMD Radeon 890M `gfx1150`, Ryzen AI 9 HX 370, HIP 7.16.26385, ROCm `/opt/rocm/core-10.1`, hipBLASLt 1.4.1, CMake 3.28.3, g++ 13.3.0 |
| **Working directory** | `/home/kupipi/Documents/git/strata` for build/test; `/home/kupipi/Documents/git/gfx1150-inference` for evidence |

**One profile only.** AMD Radeon 890M / `gfx1150`. No performance, throughput or support claim is made.

## 1. Commands

Full transcript with cwd, env and exit codes: **`commands.log`**. Raw outputs: `artifacts/`.

| # | Command (copy-paste) | CWD | Exit | Output file |
|---|---|---|---|---|
| C1 | `cmake -S . -B build-deepseek … -DCMAKE_PREFIX_PATH=/opt/rocm/core-10.1` | strata | 0 | `commands.log` |
| C2 | `cmake --build build-deepseek --target strata model_family_test gguf_geometry_test -j$(nproc)` | strata | 0 | `commands.log` |
| C3 | `sha256sum build-hip/strata` | strata | 0 | `commands.log` |
| C4 | `LD_LIBRARY_PATH=/opt/rocm/core-10.1/lib ./build-deepseek/strata --families` | strata | 0 | `commands.log` |
| C5 | `LD_LIBRARY_PATH=… ./build-deepseek/strata --inspect <deepseek.gguf>` | strata | 0 | `artifacts/inspect-deepseek.txt` |
| C6 | `LD_LIBRARY_PATH=… ./build-deepseek/strata --native <deepseek.gguf> --tokens 1,2,3 --max-new 32 --max-context 1024` | strata | 2 | `artifacts/native-deepseek-refusal.txt` |
| C7 | `LD_LIBRARY_PATH=… ./build-deepseek/strata --inspect /tmp/opencode/deepseek-mismatched.gguf` | strata | 2 | `artifacts/inspect-mismatch.txt` |
| C8 | `LD_LIBRARY_PATH=… ./build-deepseek/strata --native <qwen.gguf> --tokens 760,6511,314,9338,369 --n 32 --max-context 1024` | strata | 0 | `artifacts/qwen-regression.txt` |
| C9 | `./build-deepseek/model_family_test`; `./build-deepseek/gguf_geometry_test` | strata | 0 | `artifacts/model_family_test-output.txt`, `artifacts/gguf_geometry_test-output.txt` |
| C10 | `git diff --stat bac859ef9^..bac859ef9`; `git format-patch`; `git apply --check` | strata / tmp | 0 | `commands.log`, `patches/0001-deepseek-family.patch` |

## 2. Acceptance criteria ↔ evidence

| # | Criterion | Command | Observed | Pass? |
|---|---|---|---|---|
| 1 | `deepseek` recognized with title | `model_family_test`; `--inspect` | `DeepseekMoe` enum; title "DeepSeek-MoE-16B-base" printed | **PASS** |
| 2 | `--native` refuses with named message, no PLE | C6 | Exit 2; "DeepSeek-MoE-16B-base (architecture 'deepseek') is recognised by Strata but this build does not run it yet"; no PLE text | **PASS** |
| 3 | `--families` unchanged | C4 | `qwen4exp qwen35moe` exactly | **PASS** |
| 4 | Geometry matches §2 field by field | C5 | See table below; all 12 fields match | **PASS** |
| 5 | `--inspect` prints 363 tensors | C5 | `tensors: 363` and full name+shape list | **PASS** |
| 6 | Metadata/tensor mismatch refused | C7 | Exit 2; shape mismatch named | **PASS** |
| 7 | Qwen regression: 32 IDs match HO-007 | C8 | IDs identical to `workflow/evidence/HO-STRATA-007/artifacts/generated-token-ids.txt` | **PASS** |
| 8 | Signed binary untouched | C3 | `d58ee239…` unchanged | **PASS** |
| 9 | Patch size ≤ T2 (with DR approval) | C10 | 6 files / 234 insertions; DR-HO-STRATA-012-1 approved (DEC-034) | **PASS** |
| 10 | Patch exported and applies cleanly | C10 | `patches/0001-deepseek-family.patch`; `git apply --check` exit 0 | **PASS** |

## 3. Geometry table vs §2

From `artifacts/inspect-deepseek.txt`:

| Key (§2) | Value from `--inspect` | Expected |
|---|---|---|
| `deepseek.block_count` | 28 | 28 |
| `deepseek.embedding_length` | 2048 | 2048 |
| `deepseek.attention.head_count` | 16 | 16 |
| `deepseek.attention.head_count_kv` | 16 | 16 |
| `deepseek.expert_count` | 64 | 64 |
| `deepseek.expert_used_count` | 6 | 6 |
| `deepseek.expert_shared_count` | 2 | 2 |
| `deepseek.expert_feed_forward_length` | 1408 | 1408 |
| `deepseek.feed_forward_length` | 10944 | 10944 |
| `deepseek.leading_dense_block_count` | 1 | 1 |
| `deepseek.rope.freq_base` | 10000 | 10000.0 |
| `deepseek.attention.layer_norm_rms_epsilon` | 1e-06 | 1e-6 |

## 4. Artifacts and hashes

| Artifact | Path | SHA256 |
|---|---|---|
| `--inspect` output | `artifacts/inspect-deepseek.txt` | in `hashes.txt` |
| `--native` refusal | `artifacts/native-deepseek-refusal.txt` | in `hashes.txt` |
| Mismatch refusal | `artifacts/inspect-mismatch.txt` | in `hashes.txt` |
| Qwen regression log | `artifacts/qwen-regression.txt` | in `hashes.txt` |
| `model_family_test` output | `artifacts/model_family_test-output.txt` | in `hashes.txt` |
| `gguf_geometry_test` output | `artifacts/gguf_geometry_test-output.txt` | in `hashes.txt` |
| Exported patch | `patches/0001-deepseek-family.patch` | in `hashes.txt` |
| Commands log | `commands.log` | in `hashes.txt` |
| DeepSeek pack | `/home/kupipi/.cache/huggingface/hub/…/deepseek-moe-16b-base-q4_k_m.gguf` | `f00ecd83d2fc4f28d1d5531c9583ed9c07452263c84590167bbe014f65c330f5` |
| Qwen pack | `/home/kupipi/Documents/models/gguf/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1` |
| Signed `build-hip/strata` | `/home/kupipi/Documents/git/strata/build-hip/strata` | `d58ee2398596d1a100c15d5b9459e24bd86854cb5e5fb7ce88dbc6c7ed9f5858` |

## 5. Failures, skips, limits

- Build emits ROCm/HIP `nodiscard` warnings on existing code; no new warnings from the S1–S3 edits.
- `strata-012-deepseek-s1` branch push failed because the remote uses HTTPS and no credentials are configured in this environment. The branch is committed locally at `bac859ef9`.

## 6. Statement

- [x] Commands are reproducible (cwd + env + exit code in `commands.log`).
- [x] Outputs are raw; no paraphrasing.
- [x] No secrets, tokens, or credentials anywhere in the bundle.
- [x] Every claim cites an artifact.
- [x] One profile only (890M `gfx1150`).
- [x] No performance, support, or quality claim is made.

## 7. Git

- Strata branch: `strata-012-deepseek-s1` @ `bac859ef9` (6 files, 234 insertions, 31 deletions).
- Strata base: `baf16363b4403ef0ed4f538f5d5ed11c43fb9535`.
- Workflow branch: `wp/strata-012-deepseek-s1`; the bundle is committed on this branch.
