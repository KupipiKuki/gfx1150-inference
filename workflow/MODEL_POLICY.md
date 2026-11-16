# Model selection policy

**Status:** adopted 2026-11-15 · **auditor applied under WAIVER-001; QAQC
applied (Gemini); architect/coders pending.** The HO-001 QAQC review ran before
the QAQC assignment on the session model; it is a setup exception, not an
independent QAQC, and must be re-run on Gemini before the audit. The active agent
must not be modified while in use.
**Enforcement:** `workflow/check_model_policy.py` (`--strict` once all five are
assigned).
**Decisions:** `DECISIONS.md` DEC-006 (rules), DEC-009 (temporary auditor
waiver).

---

## 1. Why

A model that can serve two roles can approve or review its own work. The
architect approves; the auditor reviews; the coder implements; QAQC checks. If
the same model family occupies two of those seats, the separation of duties is
fake, even when the role prompts are correct.

## 2. Rules

| # | Rule |
|---|---|
| **R1** | The **Architect** model family is exclusive to the architect. It MUST NOT be configured for `coder-primary`, `coder-secondary`, `qaqc`, or `auditor`. |
| **R2** | The **Auditor** model family is exclusive to the auditor. It MUST NOT be configured for the architect, the coders, or QAQC. |
| **R3** | The Auditor uses the **project’s strongest reasoning model**, chosen once for the project and recorded below. It stays constant; a change is an architect decision in `DECISIONS.md`. |
| **R4** | **QAQC MUST use a different model family from the coder.** The coder’s model must not check its own work. |
| **R5** | **No self-review.** No model reviews work it produced: the coder family ≠ QAQC family; the auditor family ≠ coder/QAQC; the architect family ≠ any other role. |
| **R6** | **Explicit models.** Once applied, each of the five role agents MUST have an explicit `model`; no implicit inheritance for the five roles. |
| **R7** | **Family, not variant.** `provider/model#high` and `provider/model#max` are the same model. The family is the model ID’s first `-` token after the provider (`deepseek-v4-pro` → `deepseek`, `qwen3.8-flash` → `qwen3.8`). Use a different family, not a different variant, to satisfy the separation. |
| **R8** | **Record the selection.** The exact `provider/model#variant` for each role, the date and the reason are recorded in this file. Changes are architect decisions. |
| **R9** | **Fallback.** If the strong auditor model is unavailable, choose a different strong family, record it as a deviation/waiver, and keep the exclusivity. |

## 3. Role assignment

The exact IDs below are from the current `opencode-go` catalogue. If the
architect runs on the separate DeepSeek API, replace its row with that
provider’s model; the family rule is what matters.

| Role | Model (`provider/model#variant`) | Exclusive? | Why |
|---|---|---|---|
| **Architect** | `opencode-go/deepseek-v4-pro#max` (or the DeepSeek API equivalent) | **yes** | firm choice: DeepSeek; planning/orchestration |
| **Auditor** | `opencode-go/deepseek-v4.1-flash` — **WAIVED (WAIVER-001)**; target: `opencode-go/gpt-6-luna#max` | **yes** | temporarily DeepSeek (same family as the architect); move to a different family when the APIs are available |
| **coder-primary** | `opencode-go/kimi-k2.7-code` | no | code-tuned; implementation |
| **coder-secondary** | `opencode-go/qwen3.8-flash#low` | no | cheap/fast; low-priority work |
| **QAQC** | `opencode-go/gemini-4-argon#high` | no | strong reviewer; different family from both coders |

**Status: PARTIALLY APPLIED.** The auditor is set in
`.opencode/agents/auditor.md` under WAIVER-001. The architect, coders and QAQC
are proposed but unset. `check_model_policy.py` reports `PENDING` for the unset
roles and `WAIVED` for the auditor/architect family once both are set.

### Complementary coverage

```text
Coder (Kimi/Qwen) -> QAQC (Gemini) -> Auditor (temporarily DeepSeek; target GPT-6 Luna) -> Architect (DeepSeek) -> Owner
```

- The **coder** is code-tuned (Kimi) with a cheap secondary (Qwen); the **QAQC**
  is a different family (Gemini) so it does not share the coder’s blind spots.
- The **auditor** is temporarily DeepSeek V4.1 Flash (same family as the
  architect) because the other APIs are not incorporated yet; the **target** is
  GPT-6 Luna, a different family, so it can catch QAQC’s misses.
- The **architect** is DeepSeek (firm) and owns the final approval; with the
  temporary auditor it is also the stronger check on the auditor.
- The owner remains the last check on the architect.

### WAIVER-001 — auditor on DeepSeek V4.1 Flash (temporary)

- **Approved:** owner, 2026-11-15.
- **Violation:** R2/R5 — the auditor shares the **DeepSeek** family with the
  architect. This is a known, accepted exception, not a pass.
- **Scope:** auditor only. The other roles remain as proposed.
- **Risk:** correlated blind spots between the architect and auditor. The
  architect’s final review and the owner are the compensating checks; QAQC and
  the evidence bundle are unchanged.
- **Expiry:** when the owner incorporates the other APIs and moves the auditor
  to a different family (target: `opencode-go/gpt-6-luna#max`).
- **Closure:** change the auditor `model:`, run
  `python3 workflow/check_model_policy.py --strict` (must return PASS), remove
  WAIVER-001 from `workflow/model_policy.json`, and record the change in
  `DECISIONS.md`.
- **Enforcement:** the check reports `WAIVED`, never `PASS`, while the waiver
  is in force.

## 4. Applying the policy

When the active agent is free:

1. Choose the models and fill §3.
2. Add `model: <provider/model#variant>` to each of the five agent files
   (`.opencode/agents/*.md`), or the equivalent `agents.<id>.model` in the
   config.
3. Run `python3 workflow/check_model_policy.py --strict` — it must exit 0
   (`PASS`; `WAIVED` only for an approved exception).
4. Record the change in `DECISIONS.md`.
5. Start the project session with the architect model selected.

Do not start the first coding handoff while the policy is `PENDING`; the build
spike may run under the session model only as a setup exception, recorded in the
handoff log.

**Launch rule (learned from HO-001).** A subagent's model is fixed when its
child session starts. Assign the role model *before* launching; a mid-run file
change does not affect a running child. If the policy is `PENDING` for a role,
do not launch that role. After changing an agent model, reload the config or
start a fresh session before launching the review. The architect must never
pass a `model` override to the subagent tool; the agent file is the source of
truth.

## 5. Enforcement

`workflow/check_model_policy.py` reads the five agent files and checks:

- every role has an explicit `model` (strict);
- the architect family is used by no other role;
- the auditor family is used by no other role;
- QAQC’s family differs from both coder families;
- variants are collapsed and the family is the model ID’s first `-` token.

Approved exceptions are read from `workflow/model_policy.json` and reported as
`WAIVED`; they are never reported as `PASS`. It cannot judge “strongest”; R3 is
a human decision recorded in §3.

Exit codes: `0` valid/pending/waived (non-strict), `1` violation, `2` strict
mode with unassigned roles.

## 6. Current state

- **Auditor:** `opencode-go/deepseek-v4.1-flash` — applied, WAIVED (WAIVER-001).
- **QAQC:** `opencode-go/gemini-4-argon#high` — applied. The HO-001 QAQC review
  started before the assignment and ran on the session model (DeepSeek V4.1
  Flash); it is a setup exception and does not satisfy the QAQC/auditor
  separation. Re-run the QAQC review on Gemini before the audit.
- **Architect, coder-primary, coder-secondary:** proposed in §3, unset in the
  agent files; the active agent must not be modified while in use.
- `check_model_policy.py` reports `PENDING` for the architect/coders; `--strict`
  exits 2. With the architect set, the auditor/architect conflict is `WAIVED`;
  QAQC (Gemini) and auditor (DeepSeek) are distinct families.
- Closure of WAIVER-001: move the auditor to a different family, rerun the
  check, remove the waiver, record the change.
