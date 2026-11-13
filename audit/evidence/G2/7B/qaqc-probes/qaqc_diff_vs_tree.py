"""Run the 310-case differential golden + auditor's 11 probe cases against a
given tree's tokenizer (used for the red on the failed 7B candidate)."""
import json, sys

TREE = sys.argv[1]
sys.path.insert(0, TREE + '/src')
from tokenizer import GGUFTokenizer

FIX = '/home/kupipi/Documents/git/gfx1150-inference/tests/fixtures'
v = json.load(open(FIX + '/stories260k_vocab.json'))
tt = [1] * 512
for i, t in v['token_types'].items():
    tt[int(i)] = int(t)
tok = GGUFTokenizer(tokens=v['tokens'], scores=v.get('scores'), bos_token_id=1,
                    eos_token_id=2, merges=[], token_types=tt, tokenizer_model='llama')

diff = json.load(open(FIX + '/stories260k_differential_golden.json'))
bad = 0
for case in diff['cases']:
    ps = '--no-parse-special' not in case['reference_flags']
    got = tok.encode(case['prompt'], add_bos=case['add_bos'], parse_special=ps)
    if got != case['token_ids']:
        bad += 1
        if bad <= 5:
            print('DIFF', repr(case['prompt'])[:60], 'got', got, 'want', case['token_ids'])
print(f"differential corpus: {bad}/{len(diff['cases'])} mismatches on {TREE}")

probe = [
    ('a<s>b', True, [261, 1, 268]), ('hi<s>there', True, [270, 417, 1, 383]),
    (' <s>', True, [410, 410, 1]), ('<s>b', True, [1, 268]),
    ('hello<s>there', True, [281, 306, 414, 1, 383]), ('<s></s>', True, [1, 2]),
    ('the', False, [265]), ('and', False, [269]), ('time', False, [378]),
    ('the quick brown fox jumps over the lazy dog', False, [265, 410, 456, 425, 417, 340, 268, 420, 327, 416, 272, 414, 444, 410, 449, 425, 423, 427, 419, 334, 330, 265, 278, 412, 451, 422, 400, 428]),
    ('Once upon a time there was a little girl named Lily', False, [403, 407, 261, 378, 383, 286, 261, 376, 298, 315, 421, 395, 317]),
]
pbad = 0
for p, ps, want in probe:
    got = tok.encode(p, add_bos=False, parse_special=ps)
    if got != want:
        pbad += 1
        print('DIFF probe', repr(p), 'got', got, 'want', want)
print(f"auditor probe cases: {pbad}/{len(probe)} mismatches on {TREE}")
sys.exit(1 if (bad or pbad) else 0)
