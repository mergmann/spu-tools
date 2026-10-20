import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import asdict

from iset import INSTRUCTIONS
from register import BANKED, SPECIALS, name


if sys.argv[1:] == ['--registers']:
    json.dump({
        'banks': [{'name': b.name, 'suffix': sfx, 'off': b.off, 'num': b.num} for b, sfx in BANKED],
        'specials': SPECIALS,
        'names': [name(i) for i in range(64)],
    }, sys.stdout)
    sys.exit()

if len(sys.argv) > 1:
    with open(sys.argv[1], 'rt') as f: text = f.read()
else:
    text = sys.stdin.read()

assembler = INSTRUCTIONS.build()
diags = assembler.check(text.splitlines())
json.dump([asdict(d) for d in diags], sys.stdout)
