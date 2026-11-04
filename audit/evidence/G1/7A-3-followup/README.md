# G1 / 7A-3 follow-up — evidence bundle

Closes the one open condition of the 7A-3 audit (C-7A3-1): the SentencePiece
family of the golden data carried only the BOS-absent case.

| file | what it is |
|---|---|
| `notes.md` | what was missing, what is now there, the two known mismatches and why the reference is right |
| `tokenizer-spm.log` | the 11-case SentencePiece golden and its tests |
| `runxfail.log` | the known mismatches failing under `--runxfail`, with the score analysis that shows the reference is correct |
| `provenance.log` | the provenance check (137/137) and the registry row that changed |
| `generation-commands.log` | every command that produced the golden, and the proof that the GPT-2 side did not move |
| `cpu-lane.log` | the CPU lane, `test_cpu_only.py` in both modes, and the claims checker |
| `gpu-lane.log` | the GPU lane (unchanged: 24 passed) |
| `sdist-contents.log` | the sdist contents and the golden tests in the extracted tree |
| `env.txt` | environment, toolchain, and the pinned reference |
| `diffstat.txt` | the package's file delta and the scope check |
| `parent-sha.txt` | the branch base (`c66728c`) |
| `candidate-sha.txt` | the work commit under review |

The fixture itself is `tests/fixtures/stories260k_tokenizer_golden.json`; its
row in `tests/fixtures/PROVENANCE.md` carries the command and the hash.
