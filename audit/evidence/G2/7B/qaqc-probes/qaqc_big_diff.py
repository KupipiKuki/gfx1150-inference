"""Stop-gate QAQC: large seeded differential vs the pinned llama-tokenize.

Not a fixture: a one-off evidence run. 2000 seeded prompts (random vocab-piece
concatenations, random common-word sequences, random printable ASCII) encoded
by both the pinned reference binary and the candidate tokenizer; exits 1 on
any mismatch.
"""
import json, os, random, subprocess, sys

REPO = '/home/kupipi/Documents/git/gfx1150-inference'
sys.path.insert(0, REPO + '/src')
from tokenizer import GGUFTokenizer

REF = '/tmp/opencode/llama.cpp-149f5641/build/bin/llama-tokenize'
GGUF = '/tmp/stories260K.gguf'
ENV = dict(os.environ, LD_LIBRARY_PATH='/tmp/opencode/llama.cpp-149f5641/build/bin')

v = json.load(open(REPO + '/tests/fixtures/stories260k_vocab.json'))
tt = [1] * 512
for i, t in v['token_types'].items():
    tt[int(i)] = int(t)
tok = GGUFTokenizer(tokens=v['tokens'], scores=v['scores'], bos_token_id=1,
                    eos_token_id=2, merges=[], token_types=tt, tokenizer_model='llama')

sp = chr(0x2581)
pieces = [t for t in v['tokens'] if t and t not in ('<unk>', '<s>', '</s>') and not t.startswith('<0x')]
words = [w for w in json.load(open(REPO + '/tests/fixtures/make_fixtures.py'.replace('.py','.py'))) ] if False else None

rng = random.Random(777)
prompts = []
for i in range(1200):
    prompts.append(''.join(rng.choice(pieces) for _ in range(rng.randint(1, 8))))
for i in range(500):
    prompts.append(' '.join(rng.choice(pieces).lstrip(sp) for _ in range(rng.randint(1, 8))))
for i in range(200):
    prompts.append(''.join(chr(rng.randint(32, 0x2fff)) for _ in range(rng.randint(1, 30))))
for i in range(100):
    p = ''.join(rng.choice(pieces) for _ in range(rng.randint(1, 4)))
    pos = rng.randint(0, len(p))
    prompts.append(p[:pos] + '<s>' + p[pos:])

def ref_ids(prompt, parse_special):
    args = [REF, '-m', GGUF, '-p', prompt, '--ids', '--no-bos']
    if not parse_special:
        args.append('--no-parse-special')
    out = subprocess.run(args, capture_output=True, text=True, env=ENV).stdout
    return json.loads([ln for ln in out.splitlines() if ln.strip().startswith('[')][-1])

bad = 0
for i, p in enumerate(prompts):
    ps = '<s>' in p
    r = ref_ids(p, ps)
    c = tok.encode(p, add_bos=False, parse_special=ps)
    if r != c:
        bad += 1
        if bad <= 5:
            print(f"DIFF {p!r}: ref={r} cand={c}")
print(f"{len(prompts)} prompts, {bad} mismatches")
sys.exit(1 if bad else 0)
