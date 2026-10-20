import os
import sys

from iset import INSTRUCTIONS

assembler = INSTRUCTIONS.build()

inp = sys.argv[1]

if len(sys.argv) > 2: out = sys.argv[2]
else:
    subdir = os.path.join(os.path.dirname(inp), 'out')
    if not os.path.isdir(subdir):
        os.mkdir(subdir)

    file = os.path.basename(inp)
    name, _ = os.path.splitext(file)
    out = os.path.join(subdir, name + '.bin')

with open(inp, 'rt') as f:
    if not assembler.assemble(f):
        print('Stop')
        sys.exit(1)

if not assembler.link():
    print('Stop')
    sys.exit(1)

with open(out, 'wb') as f:
    assembler.emit(f)

