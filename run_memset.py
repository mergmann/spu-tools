import math
import sys
import time

from comm.draw import Color, DrawClear, DrawUpdate, RemoteScreen
from comm.spu import DSPCore, SPUDriver
from comm.usbclient import USBClient


if '--stop' in sys.argv:
    with USBClient.connect() as client:
        client.stop()
        exit(0)

if len(sys.argv) < 2:
    print(f'{sys.argv[0]} <memset.bin>')
    print(f'{sys.argv[0]} --stop')
    exit(2)

# PRAM
with open(sys.argv[1], 'rb') as f:
    program = f.read()

def dsp_memset(dsp: DSPCore, addr: int, value: int, count: int):
    dsp.com[0] = addr >> 24
    dsp.com[1] = addr
    dsp.com[2] = value
    dsp.com[3] = count
    # Start transfer
    dsp.com[7] = 1
    while dsp.com[7]: time.sleep(0.01)
    screen.add(DrawUpdate())
    screen.push()

with USBClient.connect() as client:
    if '--stop' in sys.argv:
        client.stop()
        exit()

    client.debug = True
    client.set_status('Starting')

    screen = RemoteScreen(client)

    spu = SPUDriver(client)
    spu.full_reset()
    dsp = spu.dsp0

    client.set_status('Uploading')
    dsp.write_pram(0x0000, program)

    screen.add(DrawClear(Color.WHITE), DrawUpdate())
    screen.push()

    # Disable transfer
    dsp.com[7] = 0

    # Run the DSP
    dsp.hold(False)
    time.sleep(0.5)

    # Get physical VRAM address
    vram = screen.get_vram() & 0x1FFFFFFF
    width = screen.get_width()
    height = screen.get_height()

    for i in range(32):
        s0 = i * height // 32
        s1 = (i + 1) * height // 32
        addr = (vram + s0 * width * 2)
        count = (s1 - s0) * width
        dsp_memset(dsp, addr, int(Color.rgb((31 - i) * 8, 0, i * 8)), count)

    # Hold the core
    dsp.hold(True)
