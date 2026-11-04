# G1 / 7A-3 — evidence bundle

Independent golden data: tokenizer vectors, quantized blocks and a tiny GGUF,
all produced by llama.cpp's own tools and registered with full provenance.

| file | what it is |
|---|---|
| `notes.md` | what was added, the red (the known-bug goldens), the green, and the two recorded observations |
| `provenance.log` | the mechanical provenance check (137/137) and the registry |
| `generation-commands.log` | every command that produced the fixtures, with the upstream hashes |
| `tokenizer-golden.log` | the token-ID goldens and their tests |
| `quant-golden.log` | the quantized block goldens, their layout, and the CPU and GPU tests |
| `gguf-golden.log` | the tiny GGUF, llama.cpp's reading of it, and its tests |
| `cpu-lane.log` | the CPU lane, `test_cpu_only.py` in both modes, and the claims checker |
| `gpu-lane.log` | the GPU lane on gfx1150 |
| `runxfail.log` | the two known-bug goldens failing under `--runxfail` |
| `sdist-contents.log` | the sdist contents and the golden tests in the extracted tree |
| `env.txt` | environment, toolchain, and the pinned references |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the branch base (`34f1686`) |
| `candidate-sha.txt` | the work commit under review |
| `verify-provenance.py` | regenerates `provenance.log` |

The fixtures themselves live in `tests/fixtures/`, with their registry in
`tests/fixtures/PROVENANCE.md`.
