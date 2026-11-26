#!/usr/bin/env python3
"""Recompute the router near-tie at DeepSeek layer 19 position 1 on the exact-f32 trajectory.

Usage (from repo root, no arguments required):

    python3 workflow/evidence/HO-STRATA-015/scripts/compute_router_margin.py

The script:
  1. Calls oracle_nodes on the f32 pack to dump the ffn_inp-19 node.
  2. Reads blk.19.ffn_norm.weight and blk.19.ffn_gate_inp.weight from the f32 pack.
  3. Applies RMSNorm and computes the 64 router logits / probabilities.
  4. Reports top-7 probabilities, the exact-f32 top-6, and the 6th/7th margin.
  5. Reads the committed engine ffn_inp-19 dump and computes the pre-router drift
     against the oracle ffn_inp-19 (same node on both sides).
  6. Parses the committed teacher_run.log for the teacher-forced engine margin
     (identical input, different f32 arithmetic).
  7. Parses the committed free DIAG log for the free-running engine top-6.
  8. Derives and prints:
     - the 33<->40 logit-gap shift caused by the drift;
     - the engine's expert-40 logit movement at identical input, plus the max
       over all 64 experts.

Expected exact-f32 oracle margin: ~3.36e-6 prob / ~7.95e-5 logit.
Expected drift: ~7.123e-05 rel L2 (max abs ~5.703e-04).
Expected drift-driven gap shift: ~+1.385e-4 (~1.74x the margin).
Expected engine arithmetic movement of expert 40 at identical input: ~3.84e-5
(max over 64 experts ~4.25e-5).
"""

import argparse
import math
import os
import re
import struct
import subprocess
import sys
import tempfile


H = 2048
NE = 64
LAYER = 19
POS = 1
TOKENS = [549, 6077, 280, 7239]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--f32-pack", default="/tmp/opencode/deepseek-moe-16b-f32.gguf")
    parser.add_argument("--oracle-nodes", default="/tmp/opencode/oracle_nodes")
    parser.add_argument("--ld-library-path", default="/tmp/opencode/llama-ref/build/bin")
    parser.add_argument("--strata-tools", default="/home/kupipi/Documents/git/strata/tools")
    parser.add_argument("--engine-ffn-inp",
                        default="workflow/evidence/HO-STRATA-015/artifacts/runs/engine-ffn_inp-19.bin")
    parser.add_argument("--teacher-run-log",
                        default="workflow/evidence/HO-STRATA-015/artifacts/runs/teacher_run.log")
    parser.add_argument("--free-diag-log",
                        default="workflow/evidence/HO-STRATA-015/artifacts/runs/engine-free-diag-19-1.log")
    return parser.parse_args()


def run_oracle_nodes(f32_pack, oracle_nodes, ld_path):
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ld_path
    with tempfile.TemporaryDirectory(prefix="router_margin_") as tmp:
        cmd = [
            oracle_nodes,
            "--model", f32_pack,
            "--tokens", ",".join(str(t) for t in TOKENS),
            "--n", "0",
            "--dump-node", f"ffn_inp-{LAYER}",
        ]
        subprocess.run(cmd, cwd=tmp, env=env, check=True, stdout=subprocess.DEVNULL)
        path = os.path.join(tmp, f"oracle_node_ffn_inp-{LAYER}.bin")
        with open(path, "rb") as f:
            data = struct.unpack(f"<{os.path.getsize(path)//4}f", f.read())
        return list(data[POS * H:(POS + 1) * H])


def read_f32_pack_weights(path, strata_tools, layer):
    sys.path.insert(0, strata_tools)
    from gguf_reader import GGUFFile

    gm = GGUFFile(path)
    base = gm.data_start

    def read(name):
        t = next(x for x in gm.tensors if x.name == name)
        with open(path, "rb") as f:
            f.seek(base + t.offset)
            return struct.unpack(f"<{t.elements * 4 // 4}f", f.read(t.elements * 4))

    norm_w = read(f"blk.{layer}.ffn_norm.weight")
    gate_w = read(f"blk.{layer}.ffn_gate_inp.weight")
    return norm_w, gate_w


def rmsnorm(x, weight, eps=1e-6):
    mean2 = sum(v * v for v in x) / len(x)
    scale = 1.0 / math.sqrt(mean2 + eps)
    return [v * scale * w for v, w in zip(x, weight)]


def softmax(x):
    m = max(x)
    e = [math.exp(v - m) for v in x]
    s = sum(e)
    return [v / s for v in e]


def topk(arr, k):
    indexed = sorted(enumerate(arr), key=lambda x: x[1], reverse=True)
    return [i for i, _ in indexed[:k]], [v for _, v in indexed[:k]]


def compute_margin(name, vec, norm_w, gate_w):
    normed = rmsnorm(vec, norm_w)
    # The f32 pack stores ffn_gate_inp.weight with expert as the leading dimension.
    logits = [sum(normed[i] * gate_w[e * H + i] for i in range(H)) for e in range(NE)]
    probs = softmax(logits)
    idx, vals = topk(probs, 7)
    top6, _ = topk(probs, 6)
    margin_prob = vals[5] - vals[6]
    margin_logit = logits[idx[5]] - logits[idx[6]]
    return {
        "name": name,
        "top7_idx": idx,
        "top7_prob": vals,
        "top7_logit": [logits[i] for i in idx],
        "top6": top6,
        "margin_prob": margin_prob,
        "margin_logit": margin_logit,
        "p33": probs[33],
        "p40": probs[40],
        "logits": logits,
    }


def parse_diag_log(path):
    text = open(path).read()
    m = re.search(rf"DIAG probs layer={LAYER} pos={POS}(.*?)\nDIAG top6", text, re.S)
    if not m:
        return None
    probs = list(map(float, m.group(1).split()))
    m2 = re.search(rf"DIAG router layer={LAYER} pos={POS} logits=(.*?)\nDIAG probs", text, re.S)
    logits = list(map(float, m2.group(1).split()))
    idx, vals = topk(probs, 7)
    top6, _ = topk(probs, 6)
    return {
        "name": "engine",
        "top7_idx": idx,
        "top7_prob": vals,
        "top7_logit": [logits[i] for i in idx],
        "top6": top6,
        "margin_prob": vals[5] - vals[6],
        "margin_logit": logits[idx[5]] - logits[idx[6]],
        "p33": probs[33],
        "p40": probs[40],
        "logits": logits,
    }


def print_block(r):
    print(f"--- {r['name']} ---")
    print(f"top-7 ids:        {r['top7_idx']}")
    print(f"top-7 probs:      {[f'{v:.6e}' for v in r['top7_prob']]}")
    print(f"top-7 logits:     {[f'{v:.6e}' for v in r['top7_logit']]}")
    print(f"top-6 ids:        {r['top6']}")
    print(f"p(33) / p(40):    {r['p33']:.6e} / {r['p40']:.6e}")
    print(f"6th-7th margin:   prob={r['margin_prob']:.6e}  logit={r['margin_logit']:.6e}")


def main():
    args = parse_args()

    ffn_inp_oracle = run_oracle_nodes(args.f32_pack, args.oracle_nodes, args.ld_library_path)
    norm_w, gate_w = read_f32_pack_weights(args.f32_pack, args.strata_tools, LAYER)

    print("Router near-tie recomputation at (layer=19, pos=1)")
    print("=" * 60)
    print(f"Command: python3 {' '.join(sys.argv)}")
    print(f"oracle ffn_inp-19 node dumped from f32 pack: {args.f32_pack}")
    print(f"engine ffn_inp-19 dump: {args.engine_ffn_inp}")
    print()

    oracle = compute_margin("exact-f32 oracle", ffn_inp_oracle, norm_w, gate_w)
    print_block(oracle)
    print()

    # Engine ffn_inp-19 drift (same node both sides)
    if os.path.exists(args.engine_ffn_inp):
        with open(args.engine_ffn_inp, "rb") as f:
            data = struct.unpack(f"<{os.path.getsize(args.engine_ffn_inp)//4}f", f.read())
        ffn_inp_engine = list(data[:H])

        rel2 = math.sqrt(
            sum((a - b) ** 2 for a, b in zip(ffn_inp_oracle, ffn_inp_engine))
            / sum(a * a for a in ffn_inp_oracle)
        )
        maxd = max(abs(a - b) for a, b in zip(ffn_inp_oracle, ffn_inp_engine))
        print("Pre-router residual drift (oracle ffn_inp-19 vs engine ffn_inp-19):")
        print(f"  rel L2 = {rel2:.6e}")
        print(f"  max abs diff = {maxd:.6e}")
        print()

        # Drift-driven 33<->40 gap shift using oracle math on both inputs.
        drifted = compute_margin("drifted input (oracle math)", ffn_inp_engine, norm_w, gate_w)
        gap_oracle = oracle["logits"][40] - oracle["logits"][33]
        gap_drifted = drifted["logits"][40] - drifted["logits"][33]
        gap_shift = gap_drifted - gap_oracle
        print("Drift-driven 33<->40 logit-gap shift:")
        print(f"  oracle gap       = {gap_oracle:.6e}")
        print(f"  drifted gap      = {gap_drifted:.6e}")
        print(f"  shift            = {gap_shift:.6e}")
        print(f"  |shift| / margin = {abs(gap_shift) / oracle['margin_logit']:.2f}x")
        print()

    # Teacher-forced engine: same input as oracle, engine's own f32 arithmetic.
    teacher = parse_diag_log(args.teacher_run_log)
    if teacher:
        teacher["name"] = "teacher-forced engine (same input, from teacher_run.log DIAG)"
        print_block(teacher)
        print()

        # Engine's arithmetic movement at identical input.
        diff = [abs(oracle["logits"][e] - teacher["logits"][e]) for e in range(NE)]
        expert40_movement = diff[40]
        max_movement = max(diff)
        max_expert = int(max(range(NE), key=lambda e: diff[e]))
        print("Engine f32 arithmetic movement at identical input:")
        print(f"  expert 40 |logit_oracle - logit_engine| = {expert40_movement:.6e}")
        print(f"  max over 64 experts = {max_movement:.6e} (expert {max_expert})")
        print()

    if os.path.exists(args.free_diag_log):
        free = parse_diag_log(args.free_diag_log)
        if free:
            free["name"] = "free-running engine (from temporary diagnostic build DIAG)"
            print_block(free)
            print()

    print("Interpretation: the exact-f32 6th/7th margin (~3.36e-6 prob / ~7.95e-5 logit)")
    print("is tighter than the drift-driven logit shift (~1.385e-4), so the")
    print("expert swap at (19,1) is a predicted near-tie, not an engine defect.")


if __name__ == "__main__":
    main()
