#!/usr/bin/env python3
"""Generate the teacher-forcing input files for the HO-STRATA-015 gate.

Produces:
  - teacher_inputs.bin: [layer][position][hidden] reference residuals,
    with layer 0 taken from the f32 pack's token embeddings and layers 1..27
    taken from the exact-f32 oracle dump.
  - teacher_kv.bin: [layer][position][K/V][hidden] reference K/V history,
    obtained by running `oracle_nodes --dump-node Kcur-l,Vcur-l` against the
    f32 pack.

Run from the repo root (gfx1150-inference):

    python3 workflow/evidence/HO-STRATA-015/scripts/gen_teacher_inputs.py

Defaults write into workflow/evidence/HO-STRATA-015/artifacts/runs/.
To reproduce into a scratch directory:

    python3 workflow/evidence/HO-STRATA-015/scripts/gen_teacher_inputs.py \
      --output-dir /tmp/opencode/rw1
"""

import argparse
import hashlib
import os
import struct
import subprocess
import sys
import tempfile


H = 2048
LAYERS = 28
POS = 4
TOKENS = [549, 6077, 280, 7239]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate teacher-forcing inputs for HO-STRATA-015")
    parser.add_argument("--f32-pack", default="/tmp/opencode/deepseek-moe-16b-f32.gguf",
                        help="path to the f32 DeepSeek-MoE-16B GGUF pack")
    parser.add_argument("--oracle-layers", default="workflow/evidence/HO-STRATA-014/artifacts/runs/deepseek_f32_p1_4_layers.bin",
                        help="path to the exact-f32 layer oracle dump")
    parser.add_argument("--oracle-nodes", default="/tmp/opencode/oracle_nodes",
                        help="path to the oracle_nodes harness binary")
    parser.add_argument("--ld-library-path", default="/tmp/opencode/llama-ref/build/bin",
                        help="LD_LIBRARY_PATH needed by oracle_nodes")
    parser.add_argument("--strata-tools", default="/home/kupipi/Documents/git/strata/tools",
                        help="path to Strata's tools/ directory (for gguf_reader)")
    parser.add_argument("--output-dir", default="workflow/evidence/HO-STRATA-015/artifacts/runs",
                        help="directory to write teacher_inputs.bin and teacher_kv.bin")
    return parser.parse_args()


def generate_teacher_inputs(f32_pack, oracle_layers, out_path):
    # gguf_reader must already be on sys.path (set by main).
    from gguf_reader import GGUFFile

    g = GGUFFile(f32_pack)
    base = g.data_start
    t = next(x for x in g.tensors if x.name == "token_embd.weight")
    n_vocab = t.shape[1]
    with open(f32_pack, "rb") as f:
        f.seek(base + t.offset)
        embd = struct.unpack(f"<{t.elements*4//4}f", f.read(t.elements * 4))

    inputs = [0.0] * (LAYERS * POS * H)
    for p in range(POS):
        tok = TOKENS[p]
        for i in range(H):
            inputs[(0 * POS + p) * H + i] = embd[tok * H + i]

    with open(oracle_layers, "rb") as f:
        oracle = struct.unpack(f"<{os.path.getsize(oracle_layers)//4}f", f.read())
    for l in range(1, LAYERS):
        for p in range(POS):
            src_start = (p * LAYERS + (l - 1)) * H
            dst_start = (l * POS + p) * H
            inputs[dst_start:dst_start + H] = list(oracle[src_start:src_start + H])

    with open(out_path, "wb") as f:
        f.write(struct.pack(f"<{len(inputs)}f", *inputs))
    print(f"wrote {out_path} ({len(inputs) * 4} bytes)")


def generate_teacher_kv(f32_pack, oracle_nodes, ld_path, out_path):
    nodes = ",".join(f"{kind}{l}" for l in range(LAYERS) for kind in ("Kcur-", "Vcur-"))
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ld_path
    with tempfile.TemporaryDirectory(prefix="gen_teacher_kv_") as tmp:
        cmd = [
            oracle_nodes,
            "--model", f32_pack,
            "--tokens", ",".join(str(t) for t in TOKENS),
            "--n", "0",
            "--dump-node", nodes,
        ]
        print("running:", " ".join(cmd))
        subprocess.run(cmd, cwd=tmp, env=env, check=True)

        out = []
        for l in range(LAYERS):
            for p in range(POS):
                for kind in ("Kcur-", "Vcur-"):
                    name = f"oracle_node_{kind}{l}.bin"
                    path = os.path.join(tmp, name)
                    with open(path, "rb") as f:
                        data = struct.unpack(f"<{os.path.getsize(path)//4}f", f.read())
                    out.extend(data[p * H:(p + 1) * H])

    with open(out_path, "wb") as f:
        f.write(struct.pack(f"<{len(out)}f", *out))
    print(f"wrote {out_path} ({len(out) * 4} bytes)")


def main():
    args = parse_args()
    sys.path.insert(0, args.strata_tools)

    os.makedirs(args.output_dir, exist_ok=True)
    inputs_path = os.path.join(args.output_dir, "teacher_inputs.bin")
    kv_path = os.path.join(args.output_dir, "teacher_kv.bin")

    generate_teacher_inputs(args.f32_pack, args.oracle_layers, inputs_path)
    generate_teacher_kv(args.f32_pack, args.oracle_nodes, args.ld_library_path, kv_path)

    for path in (inputs_path, kv_path):
        h = hashlib_sha256(path)
        print(f"sha256 {path} = {h}")


def hashlib_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    main()
