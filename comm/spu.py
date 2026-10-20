import time

from .usbclient import USBClient


MSTPCR2  = 0xA4150038
FSICLKCR = 0xA4150008
SPUCLKCR = 0xA415003C

SPUSRST = 0xFE2FFC24

PBANKC0 = 0xFE2FFC00
PBANKC1 = 0xFE2FFC04
XBANKC0 = 0xFE2FFC10
XBANKC1 = 0xFE2FFC14

DSPRST =     [0xFE2FFD00, 0xFE3FFD00]
DSPCORERST = [0xFE2FFD04, 0xFE3FFD04]

PRAM = [0xFE200000, 0xFE300000]
XRAM = [0xFE240000, 0xFE340000]
YRAM = [0xFE280000, 0xFE380000]

BITS_32 = (1 << 32) - 1

def words_to_bytes(words: list[int]) -> bytes:
    buf = bytearray()
    for word in words:
        buf.extend((word << 8).to_bytes(4, 'big'))
    return bytes(buf)

def bytes_to_words(data: bytes) -> list[int]:
    out = []
    for i in range(0, len(data), 4):
        out.append(int.from_bytes(data[i:i+4]) >> 8)
    return out

def sign_extend(value: int, bits: int):
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

def q23_encode(vals: list[float]) -> list[int]:
    return [
        min(max(-0x800000, int(val * (1 << 23))), 0x7FFFFF) & 0xFFFFFF
        for val in vals
    ]

def q23_decode(vals: list[int]) -> list[float]:
    return [
        sign_extend(val, 24) / (1 << 23)
        for val in vals
    ]

class SPUDriver:
    def __init__(self, client: USBClient) -> None:
        self.client = client
        self.dsp0 = DSPCore(client, 0)
        self.dsp1 = DSPCore(client, 1)

    def start_clock(self) -> None:
        self.client.mask_and(MSTPCR2,  ~0x200 & BITS_32)
        self.client.mask_and(FSICLKCR, ~0x100 & BITS_32)
        self.client.mask_and(SPUCLKCR, ~0x100 & BITS_32)

    def reset_spu(self) -> None:
        self.client.mask_and(SPUSRST, ~1 & BITS_32)
        time.sleep(0.1)
        self.client.mask_or(SPUSRST, 1)

    def start_banks(self) -> None:
        self.client.put(PBANKC0, 0x00FF)
        self.client.put(PBANKC1, 0xFF00)
        self.client.put(XBANKC0, 0x00FF)
        self.client.put(XBANKC1, 0xFF00)

    def full_reset(self) -> None:
        self.start_clock()
        self.start_banks()

        self.reset_spu()

        self.dsp0.reset(True)
        self.dsp1.reset(True)

        self.dsp0.hold(True)
        self.dsp1.hold(True)

        time.sleep(0.1)

        self.dsp0.reset(False)
        self.dsp1.reset(False)

class DSPCore:
    def __init__(self, client: USBClient, index: int) -> None:
        self.client = client
        self.index = index

    def reset(self, reset: bool) -> None:
        self.client.put(DSPRST[self.index], reset)

    def hold(self, hold: bool) -> None:
        self.client.put(DSPCORERST[self.index], hold)

    def write_pram(self, addr: int, data: bytes) -> None:
        self.client.write(PRAM[self.index] + addr, data)

    def write_xram(self, off: int, data: list[int]) -> None:
        self.client.write(XRAM[self.index] + off * 4, words_to_bytes(data))

    def write_yram(self, off: int, data: list[int]) -> None:
        self.client.write(YRAM[self.index] + off * 4, words_to_bytes(data))

    def read_pram(self, addr: int, size: int) -> bytes:
        return self.client.read(PRAM[self.index] + addr, size)

    def read_xram(self, off: int, count: int) -> list[int]:
        return bytes_to_words(self.client.read(XRAM[self.index] + off * 4, count * 4))

    def read_yram(self, off: int, count: int) -> list[int]:
        return bytes_to_words(self.client.read(YRAM[self.index] + off * 4, count * 4))

