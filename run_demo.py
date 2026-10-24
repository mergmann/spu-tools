import math
import sys
import time

from comm.draw import Color, DrawClear, DrawUpdate, RemoteScreen
from comm.spu import SPUDriver, q23_encode
from comm.usbclient import USBClient


if '--stop' in sys.argv:
    with USBClient.connect() as client:
        client.stop()
        exit(0)

if len(sys.argv) < 3: 
    print(f'{sys.argv[0]} <rend.bin> <points.csv>')
    print(f'{sys.argv[0]} --stop')
    exit(2)

# The DSP can only handle values in -1..1
SCALE = 0.125

# Rotate the model around an axis
THETA = math.pi / 8
ct = math.cos(THETA)
st = math.sin(THETA)
MATRIX = [
    1.0, 0.0, 0.0,
    0.0,  ct, -st,
    0.0,  st,  ct,
    0.0, 0.0, 0.3,
]

# Precomputed divisor table
RECIP = [128 / (i + 0.5) for i in range(1024)]

# PRAM
with open(sys.argv[1], 'rb') as f:
    program = f.read()

# Load model points
model = []
with open(sys.argv[2], 'rt') as f:
    f.readline()
    while line := f.readline():
        x, y, z = map(lambda x: float(x) * SCALE, line.split(','))
        model.extend((x, z, y))

# Fix for the 512 loop limit
n = len(model) // 3
model += model[-3:] * (-n % 1024)
n2 = len(model) // 3 // 1024

with USBClient.connect() as client:
    client.debug = True
    client.set_status('Starting')

    screen = RemoteScreen(client)

    spu = SPUDriver(client)
    spu.full_reset()
    dsp = spu.dsp0

    client.set_status('Uploading')
    dsp.write_pram(0x0000, program)
    dsp.write_xram(0x0000, [n2])
    dsp.write_xram(0x0001, q23_encode(model))

    dsp.write_yram(0x0000, q23_encode(RECIP))
    dsp.write_yram(0x0400, q23_encode(MATRIX))

    screen.add(DrawClear(Color.WHITE), DrawUpdate())
    screen.push()

    # Run the DSP
    dsp.hold(False)
    time.sleep(0.5)
    # Stop it, just in case
    dsp.hold(True)

    screen.add(DrawUpdate())
    screen.push()

    print(dsp.read_xram(0, 1)[0])
