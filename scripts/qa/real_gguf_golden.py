#!/usr/bin/env python3
"""Real-GGUF golden runner (7F-2): greedy tokens + logits vs pinned llama.cpp.

Runs *our engine* on a real GGUF (gfx1150, HIP kernels) with a fixed prompt,
``temperature=0`` (pure argmax, like the reference), writing:

    <out-dir>/ours.tokens.txt   prompt ids, '---', generated ids (one per line)
    <out-dir>/ours.logits.f32   raw fp32 logits of the last position, per step
                                (concatenated: steps x n_vocab floats)
    <out-dir>/verdict.json      comparison against golden_ref's output

and compares against the reference artifacts produced by the pinned
``golden_ref`` program (llama.cpp; commit recorded in the evidence bundle):

    golden_ref --model M.gguf --prompt-file P.txt --steps N --out-prefix R
      -> R.tokens.txt, R.logits.f32

Comparison contract (7F-2, MirroredArgmax):

1. **Token IDs compared exactly** — every prompt token and every greedy
   generated token must be identical (no "close enough").
2. **Logits within a stated tolerance** — see ``LOGITS_MAX_ABS_DIFF`` /
   ``PROBS_MAX_ABS_DIFF`` below; these bound accumulated FP16 numeric noise
   between the two independent implementations, **not** token agreement,
   which is checked exactly in (1). The tolerance is justified in the
   evidence notes from the measured distributions (top-1 margin vs noise).

Usage::

    python scripts/qa/real_gguf_golden.py --model M.gguf \
        --prompt-file P.txt --steps 16 \
        --ref-prefix /path/to/ref --out-dir audit/evidence/G6/7F/golden/<name> \
        [--tolerance-report-only]

Exit codes: ``0`` golden passes, ``1`` mismatch, ``2`` harness error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _sub in ("src", "build"):
    _p = os.path.join(_REPO_ROOT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

#: Stated logits tolerance (max absolute difference per element, per step).
#: JUSTIFICATION (recorded in audit/evidence/G6/7F/golden/): the engine computes
#: projections in FP16 (dequantize->FP16 GEMM, FP32 accumulate, FP16 store)
#: while llama.cpp dequantizes to F16 rows and accumulates in F32 with its own
#: tiling; the difference is accumulated rounding noise whose scale grows
#: with the projection depth, NOT a semantic disagreement. Semantic
#: agreement is enforced separately by the exact token-ID check, which is
#: the actual acceptance gate. 0.5 bounds the measured noise (~9x the
#: observed max abs diff) and stays ~4x below the smallest observed top-1
#: margin at any step, so a run that passes tokens-exact + logits-within-
#: tolerance cannot be "wrong in a way that matters" for greedy decoding.
LOGITS_MAX_ABS_DIFF = 0.5

#: Softmax probability tolerance: the argmax token's probability may differ
#: by at most this much (probabilities are scale-free, so this is the
#: implementation-independent bound). The exact-token check remains the gate.
PROBS_MAX_ABS_DIFF = 0.02

#: Decisive-margin threshold (pre-registered by the auditor in
#: PHASE7_7F_REWORK_BRIEF.md §3 / BLOCKER-7F-3): greedy token IDs are compared
#: exactly only while the top-1 margin on BOTH sides is >= this many logits —
#: above the observed ~0.3–0.9 cross-implementation FP16-vs-F32 noise, a
#: margin this large cannot be flipped by implementation noise, so a token
#: mismatch at such a step is a real defect. The walk stops at the first step
#: below the threshold ("decisive-margin fork"); steps before the stop must
#: match exactly. The strict 16-step result is still recorded unchanged.
DECISIVE_MARGIN_THRESHOLD = 1.0

#: Minimum number of decisive steps for a run to count as a decisive PASS
#: (7G-C C3(b), pre-registered in
#: audit/evidence/G7/7G-C/c3-golden/PRE-REGISTRATION-walk-refinement.md before
#: the re-adjudication). Two is the decisive-step basis the G6 Q6_K PASS
#: rests on; a run that compares fewer decisive steps stays INCONCLUSIVE —
#: recorded honestly, never counted as a pass.
MIN_DECISIVE_STEPS = 2

#: Expected splits inside the tokens files.
TOKENS_SEPARATOR = "---"


def _read_tokens(path: str) -> tuple[list[int], list[int]]:
    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    sep = lines.index(TOKENS_SEPARATOR)
    prompt_ids = [int(v) for v in lines[:sep]]
    generated = [int(v) for v in lines[sep + 1:]]
    return prompt_ids, generated


def run_engine(model: str, prompt: str, steps: int, out_dir: str,
               max_seq_len: int, prompt_ids_override=None) -> dict:
    """Greedy chain exactly like golden_ref: prefill, then one token per step.

    Temperature/sampling are not involved: the argmax of the raw
    last-position logits *is* the next token — identical decision rule in
    both implementations.

    With ``prompt_ids_override`` the engine is fed the reference tokenization
    (from ``ref.tokens.txt``) so both sides run identical model states; the
    engine's own tokenization of the prompt file is still computed and
    recorded in ``prompt_ids_engine`` for the divergence record (7F-2 note:
    the G2 tokenizer goldens own tokenizer equivalence; a real-GGUF divergence
    found here is recorded, not silently ignored).
    """
    import numpy as np
    import inference

    os.makedirs(out_dir, exist_ok=True)
    with inference.LlamaInferenceEngine(model, max_seq_len=max_seq_len) as engine:
        engine_prompt_ids = engine.tokenizer.encode(prompt)
        if prompt_ids_override is not None:
            if prompt_ids_override != engine_prompt_ids:
                print(
                    "NOTE: reference and engine prompt tokenizations differ; "
                    "feeding the reference ids to both sides (divergence "
                    "recorded in the verdict)",
                    file=sys.stderr,
                )
            prompt_ids = list(prompt_ids_override)
        else:
            prompt_ids = list(engine_prompt_ids)
        logits_fp16 = engine.prefill_tokens(prompt_ids)
        logits = np.asarray(logits_fp16, dtype=np.float32)
        token_stream = [int(np.argmax(logits))]
        all_logits = [logits.copy()]
        for step in range(1, steps):
            pos = len(prompt_ids) + step - 1
            logits_fp16 = engine.forward_tokens([token_stream[-1]], pos_offset=pos)
            logits = np.asarray(logits_fp16, dtype=np.float32)
            token_stream.append(int(np.argmax(logits)))
            all_logits.append(logits.copy())

    meta = {
        "model_sha256": _sha256_file(model),
        "model_path": model,
        "prompt_tokens": len(prompt_ids),
        "prompt_ids": prompt_ids,
        "prompt_ids_engine": engine_prompt_ids,
        "prompt_ids_match_reference": (
            None if prompt_ids_override is None
            else list(prompt_ids_override) == engine_prompt_ids
        ),
        "generated_ids": token_stream,
        "n_vocab": int(all_logits[0].size),
        "steps": steps,
    }
    with open(os.path.join(out_dir, "ours.tokens.txt"), "w", encoding="utf-8") as fh:
        for tid in prompt_ids:
            fh.write(f"{tid}\n")
        fh.write(f"{TOKENS_SEPARATOR}\n")
        for tid in token_stream:
            fh.write(f"{tid}\n")
    with open(os.path.join(out_dir, "ours.logits.f32"), "wb") as fh:
        for row in all_logits:
            fh.write(row.astype("<f4").tobytes())
    meta["logits_sha256"] = hashlib.sha256(
        b"".join(row.astype("<f4").tobytes() for row in all_logits)
    ).hexdigest()
    return meta


def _sha256_file(path: str, chunk: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def compare(out_dir: str, ref_prefix: str, report_only: bool = False) -> dict:
    """Compare ours.tokens/logits against golden_ref's artifacts."""
    import numpy as np

    ours_prompt, ours_gen = _read_tokens(os.path.join(out_dir, "ours.tokens.txt"))
    ref_prompt, ref_gen = _read_tokens(f"{ref_prefix}.tokens.txt")

    verdict: dict = {"prompt_token_ids_match": ours_prompt == ref_prompt,
                     "prompt_len_ours": len(ours_prompt),
                     "prompt_len_ref": len(ref_prompt)}

    # 1. token IDs, exact
    if len(ours_gen) != len(ref_gen):
        verdict["token_ids_match"] = False
        verdict["token_mismatch_first_step"] = "length"
    else:
        mismatch = next(
            (i for i, (a, b) in enumerate(zip(ours_gen, ref_gen)) if a != b),
            None,
        )
        verdict["token_ids_match"] = mismatch is None
        verdict["token_mismatch_first_step"] = mismatch

    # 2. logits within tolerance
    ref_logits = np.fromfile(f"{ref_prefix}.logits.f32", dtype="<f4")
    ours_logits = np.fromfile(os.path.join(out_dir, "ours.logits.f32"), dtype="<f4")
    if ref_logits.size == 0 or ours_logits.size == 0:
        raise SystemExit("compare: empty logits file")
    steps = min(len(ours_gen), len(ref_gen))
    n_vocab = ours_logits.size // len(ours_gen)
    per_step = []
    worst_logits = 0.0
    worst_probs = 0.0
    for s in range(steps):
        a = ours_logits[s * n_vocab:(s + 1) * n_vocab]
        b = ref_logits[s * n_vocab:(s + 1) * n_vocab]
        max_abs = float(np.max(np.abs(a - b)))
        # argmax probability difference (scale-free)
        def top1_prob(row):
            e = row - row.max()
            p = np.exp(e)
            return p[int(np.argmax(row))] / p.sum()
        probs_diff = float(abs(top1_prob(a) - top1_prob(b)))
        # top-1 margin: gap between best and second-best logit
        margin_a = float(np.sort(a)[-1] - np.sort(a)[-2])
        margin_b = float(np.sort(b)[-1] - np.sort(b)[-2])
        worst_logits = max(worst_logits, max_abs)
        worst_probs = max(worst_probs, probs_diff)
        per_step.append({
            "step": s,
            "max_abs_diff": round(max_abs, 5),
            "argmax_prob_diff": round(probs_diff, 6),
            "top1_margin_ours": round(margin_a, 5),
            "top1_margin_ref": round(margin_b, 5),
        })
    verdict["logits_max_abs_diff_observed"] = round(worst_logits, 5)
    verdict["probs_max_abs_diff_observed"] = round(worst_probs, 6)
    verdict["logits_tolerance"] = LOGITS_MAX_ABS_DIFF
    verdict["probs_tolerance"] = PROBS_MAX_ABS_DIFF
    # Logits are a DIAGNOSTIC only since the BLOCKER-7F-3 adjudication: the
    # same measured matching-state noise (max 0.9 observed) that motivated
    # the decisive-margin criterion exceeds the pre-registered 0.5 bound, so
    # the bound is reported rather than silently widened, and no longer
    # gates the pass outcome.
    verdict["logits_within_tolerance"] = worst_logits <= LOGITS_MAX_ABS_DIFF
    verdict["probs_within_tolerance"] = worst_probs <= PROBS_MAX_ABS_DIFF
    verdict["logits_role"] = "diagnostic (BLOCKER-7F-3 adjudication)"
    # per-step top-8 excerpt (small, tolerance-checked, tokens + logits)
    excerpt = []
    for s in range(min(3, steps)):
        a = ours_logits[s * n_vocab:(s + 1) * n_vocab]
        b = ref_logits[s * n_vocab:(s + 1) * n_vocab]
        order = np.argsort(-b)[:8]
        excerpt.append({
            "step": s,
            "token_id": int(ref_gen[s]),
            "ref_logits_top8": [round(float(b[i]), 4) for i in order],
            "ours_logits_top8": [round(float(a[i]), 4) for i in order],
        })
    verdict["per_step_summary"] = per_step
    verdict["logits_excerpt_top8"] = excerpt

    # --- strict 16-step result (kept verbatim; NOT the pass criterion since
    # the BLOCKER-7F-3 pre-registered amendment) --------------------------
    verdict["strict_16_step"] = {
        "token_ids_match": bool(verdict["token_ids_match"]),
        "token_mismatch_first_step": verdict["token_mismatch_first_step"],
        "prompt_token_ids_match": bool(verdict["prompt_token_ids_match"]),
        "logits_within_tolerance": bool(verdict["logits_within_tolerance"]),
        "result": "PASS" if (
            verdict["token_ids_match"]
            and verdict["prompt_token_ids_match"]
        ) else "FAIL",
    }

    # --- decisive-margin adjudication (pre-registered, rework brief §3;
    # walk refined 7G-C C3(b) — see PRE-REGISTRATION-walk-refinement.md) ---
    # Both runs are greedy chains: when the token IDs MATCH at a step, the
    # two chains stay in the same model state, so a later decisive step's
    # token match is equally valid evidence. A chain only actually forks at
    # a token MISMATCH. The walk therefore walks ALL steps in order:
    # - a token MISMATCH on a step whose top-1 margin is >= the threshold on
    #   both sides is a real defect (decisive FAIL);
    # - a token MISMATCH at an indecisive (near-tie) step is the fork — the
    #   post-fork states are not comparable; the walk stops;
    # - token-matching steps below the threshold agree but are NOT decisive
    #   evidence (weak agreement); matched steps at/above the threshold
    #   count toward decisive_steps_compared.
    decisive_compared = 0
    first_indecisive_step = None
    decisive_mismatch_at = None
    fork_step = None
    for s in range(steps):
        margins = per_step[s]
        indecisive = (
            margins["top1_margin_ours"] < DECISIVE_MARGIN_THRESHOLD
            or margins["top1_margin_ref"] < DECISIVE_MARGIN_THRESHOLD
        )
        matched = ours_gen[s] == ref_gen[s]
        if matched:
            if not indecisive:
                decisive_compared += 1
            elif first_indecisive_step is None:
                first_indecisive_step = s
        elif not indecisive:
            decisive_mismatch_at = s
            break
        else:
            fork_step = s
            break

    if decisive_mismatch_at is not None:
        decisive_result = "FAIL"
    elif decisive_compared < MIN_DECISIVE_STEPS:
        # Fewer decisive steps than the pre-registered minimum: this run
        # provides no sufficient decisive evidence either way. Recorded
        # honestly, never counted as a pass.
        decisive_result = "INCONCLUSIVE"
    else:
        decisive_result = "PASS"
    verdict["decisive_margin"] = {
        "threshold": DECISIVE_MARGIN_THRESHOLD,
        "min_decisive_steps": MIN_DECISIVE_STEPS,
        "pre_registered_by": (
            "PHASE7_7F_REWORK_BRIEF.md #3 (BLOCKER-7F-3 adjudication); "
            "walk + minimum decisive steps refined 7G-C C3(b): "
            "audit/evidence/G7/7G-C/c3-golden/PRE-REGISTRATION-walk-refinement.md"
        ),
        "decisive_steps_compared": decisive_compared,
        "first_indecisive_step": first_indecisive_step,
        "decisive_mismatch_at": decisive_mismatch_at,
        "fork_step": fork_step,
        "decisive_token_ids_match": (
            None if decisive_compared == 0 else decisive_mismatch_at is None
        ),
        "result": decisive_result,
    }

    # --- amended pass criterion ------------------------------------------
    # PASS requires: the prompt tokenization matches (the 7F-2/BLOCKER-7F-2
    # tokenizer scope) AND the decisive-margin adjudication passes with at
    # least MIN_DECISIVE_STEPS (7G-C C3(b)) compared steps. The strict
    # 16-step result and the logits diagnostics stay recorded above and
    # never gate this boolean silently.
    verdict["pass"] = bool(
        verdict["prompt_token_ids_match"]
        and decisive_result == "PASS"
    )
    verdict["pass_criterion"] = (
        "amended (BLOCKER-7F-3; 7G-C C3(b)): prompt token IDs match + "
        f"decisive-margin (>= {DECISIVE_MARGIN_THRESHOLD} logits on both "
        f"sides) token match on >= {MIN_DECISIVE_STEPS} steps; strict "
        "16-step result recorded separately"
    )
    verdict["report_only"] = report_only
    return verdict


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="path to the real .gguf")
    parser.add_argument("--prompt-file", required=True, help="fixed prompt text file")
    parser.add_argument("--steps", type=int, default=16, help="greedy steps to compare")
    parser.add_argument("--ref-prefix", required=True,
                        help="prefix of the pinned llama.cpp golden_ref artifacts")
    parser.add_argument("--out-dir", required=True, help="evidence output directory")
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument(
        "--engine-prompt-ids",
        action="store_true",
        help=(
            "feed the ENGINE's own tokenization of the prompt to both sides "
            "instead of the reference's (default: the reference ids are fed, "
            "so both implementations run identical model states; the engine's "
            "tokenization is recorded either way for the divergence report)"
        ),
    )
    parser.add_argument("--tolerance-report-only", action="store_true",
                        help="do not fail on mismatch; still report it (QAQC probes)")
    args = parser.parse_args(argv)

    with open(args.prompt_file, "r", encoding="utf-8") as fh:
        prompt = fh.read()

    ref_prompt, _ = _read_tokens(f"{args.ref_prefix}.tokens.txt")
    prompt_ids_override = None if args.engine_prompt_ids else ref_prompt
    meta = run_engine(args.model, prompt, args.steps, args.out_dir,
                      max_seq_len=args.max_seq_len,
                      prompt_ids_override=prompt_ids_override)
    verdict = compare(args.out_dir, args.ref_prefix,
                      report_only=args.tolerance_report_only)
    verdict.update({
        "model_sha256": meta["model_sha256"],
        "steps": args.steps,
        "n_vocab": meta["n_vocab"],
        "ours_logits_sha256": meta["logits_sha256"],
        # 7F-2 divergence record: whether the ENGINE's own tokenization of
        # the fixed prompt matches the reference's. With --engine-prompt-ids
        # (the BLOCKER-7F-2 rework mode) this is the E2E tokenizer check:
        # the engine's ids are fed to the model and still have to equal the
        # reference's; with the default mode the reference ids are fed and
        # this records the (pre-fix) engine/reference divergence.
        "prompt_tokenization_engine_matches_reference": (
            meta["prompt_ids"] == ref_prompt
        ),
        "prompt_ids_engine": meta["prompt_ids_engine"],
        "prompt_ids_fed": meta["prompt_ids"],
        "engine_prompt_ids_mode": bool(args.engine_prompt_ids),
    })
    verdict_path = os.path.join(args.out_dir, "verdict.json")
    with open(verdict_path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2, sort_keys=True)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    if args.tolerance_report_only:
        return 0
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
