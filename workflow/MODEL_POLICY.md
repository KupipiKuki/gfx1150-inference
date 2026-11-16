# Model selection policy

**Status:** adopted 2026-11-15 · **application pending** (the active agent is in
use; do not edit its model now).
**Enforcement:** `workflow/check_model_policy.py` (`--strict` after application).
**Decision:** `DECISIONS.md` DEC-006.

---

## 1. Why

A model that can serve two roles can approve or review its own work. The
architect approves; the auditor reviews; the coder implements; QAQC checks. If
the same model occupies two of those seats, the separation of duties is fake,
even when the role prompts are correct.

## 2. Rules

| # | Rule |
|---|---|
| **R1** | The **Architect** model is exclusive to the architect. It MUST NOT be configured for `coder-primary`, `coder-secondary`, `qaqc`, or `auditor`. |
| **R2** | The **Auditor** model is exclusive to the auditor. It MUST NOT be configured for the architect, the coders, or QAQC. |
| **R3** | The Auditor uses the **project’s strongest reasoning model**, chosen once for the project and recorded below. It stays constant; a change is an architect decision in `DECISIONS.md`. |
| **R4** | **QAQC MUST use a different base model from the coder.** The coder’s model must not check its own work. |
| **R5** | **No self-review.** No model reviews work it produced: the coder model ≠ QAQC model; the auditor model ≠ coder/QAQC; the architect model ≠ any other role. |
| **R6** | **Explicit models.** Once applied, each of the five role agents MUST have an explicit `model`; no implicit inheritance for the five roles. |
| **R7** | **Variants are not different models.** `provider/model#high` and `provider/model#max` are the same base model for R1/R2/R4. Use a different base model, not a different variant, to satisfy the separation. |
| **R8** | **Record the selection.** The exact `provider/model#variant` for each role, the date and the reason are recorded in this file. Changes are architect decisions. |
| **R9** | **Fallback.** If the strong auditor model is unavailable, choose a different strong base model, record it as a deviation, and keep the exclusivity. |

## 3. Role assignment (proposed 2026-11-15)

The exact IDs below are from the current `opencode-go` catalogue. If the
architect runs on the separate DeepSeek API, replace its row with that
provider’s model; the family rule is what matters.

| Role | Model (`provider/model#variant`) | Exclusive? | Why |
|---|---|---|---|
| **Architect** | `opencode-go/deepseek-v4-pro#max` (or the DeepSeek API equivalent) | **yes** | firm choice: DeepSeek; planning/orchestration |
| **Auditor** | `opencode-go/gpt-6-luna#max` | **yes** | strongest reasoning; different family from coder, QAQC and architect |
| **coder-primary** | `opencode-go/kimi-k2.7-code` | no | code-tuned; implementation |
| **coder-secondary** | `opencode-go/qwen3.8-flash#low` | no | cheap/fast; low-priority work |
| **QAQC** | `opencode-go/gemini-4-argon#high` | no | strong reviewer; different base from both coders |

**Status: PROPOSED.** The agent files are still unset (the active agent must not
be modified while in use). `check_model_policy.py` reports `PENDING`.

### Complementary coverage

```text
Coder (Kimi/Qwen)  ->  QAQC (Gemini)  ->  Auditor (GPT-6 Luna)  ->  Architect (DeepSeek)  ->  Owner
```

- The **coder** is code-tuned (Kimi) with a cheap secondary (Qwen); the **QAQC**
  is a different family (Gemini) so it does not share the coder’s blind spots.
- The **auditor** is a stronger reasoning family (GPT-6 Luna) so it can catch
  QAQC’s misses.
- The **architect** is DeepSeek (firm) so it can catch the auditor’s misses and
  own the final approval.
- The owner remains the last check on the architect.
- No two roles share a base model; variants do not count as different (R7).

## 4. Applying the policy

When the active agent is free:

1. Choose the models and fill §3.
2. Add `model: <provider/model#variant>` to each of the five agent files
   (`.opencode/agents/*.md`), or the equivalent `agents.<id>.model` in the
   config.
3. Run `python3 workflow/check_model_policy.py --strict` — it must exit 0.
4. Record the change in `DECISIONS.md`.
5. Start the project session with the architect model selected.

Do not start the first coding handoff while the policy is `PENDING`; the build
spike may run under the session model only as a setup exception, recorded in the
handoff log.

## 5. Enforcement

`workflow/check_model_policy.py` reads the five agent files and checks:

- every role has an explicit `model` (strict);
- the architect base model is used by no other role;
- the auditor base model is used by no other role;
- QAQC’s base model differs from both coder base models;
- variants are collapsed to the base model for these checks.

It cannot judge “strongest”; R3 is a human decision recorded in §3. The script
prints a reminder.

Exit codes: `0` valid or pending (non-strict), `1` violation, `2` strict mode
with unassigned roles.

## 6. Current state

- The proposed assignment is in §3; it is not applied yet.
- All five agent files have **no** `model` field; they inherit the session
  model.
- `check_model_policy.py` reports `PENDING` and exits 0; `--strict` exits 2.
- The active agent must not be modified while it is in use.
- When it is free: fill the agent `model:` fields from §3, run
  `check_model_policy.py --strict` (must exit 0), and record the change in
  `DECISIONS.md`.
