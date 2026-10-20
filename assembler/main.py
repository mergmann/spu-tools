import os
import sys

from iset import INSTRUCTIONS

assembler = INSTRUCTIONS.build()

inp = sys.argv[1]

if len(sys.argv) > 2: out = sys.argv[2]
else:
    name, _ = os.path.splitext(inp)
    out = name + '.bin'

with open(inp, 'rt') as f:
    if not assembler.assemble(f):
        print('Stop')
        sys.exit(1)

if not assembler.link():
    print('Stop')
    sys.exit(1)

with open(out, 'wb') as f:
    assembler.emit(f)

