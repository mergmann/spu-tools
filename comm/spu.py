import time
import typing

from .usbclient import USBClient


MSTPCR2  = 0xA4150038
FSICLKCR = 0xA4150008
SPUCLKCR = 0xA415003C

SPUSRST = 0xFE2FFC24

PBANKC0 = 0xFE2FFC00
PBANKC1 = 0xFE2FFC04
XBANKC0 = 0xFE2FFC10
XBANKC1 = 0xFE2FFC14

GCOM = 0xFE2FFC40

DSPRST =     [0xFE2FFD00, 0xFE3FFD00]
DSPCORERST = [0xFE2FFD04, 0xFE3FFD04]

COM = [0xFE2FFD38, 0xFE3FFD38]

PRAM = [0xFE200000, 0xFE300000]
XRAM = [0xFE240000, 0xFE340000]
YRAM = [0xFE280000, 0xFE380000]

XRAM_SIZE = [0x40000, 0x40000]
YRAM_SIZE = [0x40000, 0x40000]

BITS_32 = (1 << 32) - 1

def words_to_bytes(words: typing.Iterable[int]) -> bytes:
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
    @property
    def gcom(self) -> Comm: return Comm(self.client, GCOM)

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
    @property
    def com(self) -> Comm:
        return Comm(self.client, COM[self.index])

    @property
    def xram(self) -> Ram24:
        return Ram24(self.client, XRAM[self.index], XRAM_SIZE[self.index])

    @property
    def yram(self) -> Ram24:
        return Ram24(self.client, YRAM[self.index], YRAM_SIZE[self.index])


    def __init__(self, client: USBClient, index: int) -> None:
        self.client = client
        self.index = index

    def reset(self, reset: bool) -> None:
        self.client.put(DSPRST[self.index], reset)

    def hold(self, hold: bool) -> None:
        self.client.put(DSPCORERST[self.index], hold)

    def write_pram(self, addr: int, data: bytes) -> None:
        self.client.write(PRAM[self.index] + addr, data)

    def read_pram(self, addr: int, size: int) -> bytes:
        return self.client.read(PRAM[self.index] + addr, size)

class Comm:
    def __init__(self, client: USBClient, base: int) -> None:
        self.client = client
        self.base = base

    def __getitem__(self, key: int) -> int:
        if key not in range(8): raise ValueError('key must be 0..7')
        return self.client.get(self.base + key * 4)

    def __setitem__(self, key: int, value: int):
        if key not in range(8): raise ValueError('key must be 0..7')
        self.client.put(self.base + key * 4, value & 0xFFFFFF)

class Ram24:
    def __init__(self, client: USBClient, base: int, count: int) -> None:
        self.client = client
        self.base = base
        self.count = count

    def read_raw(self, pos: int, count: int) -> bytes:
        return self.client.read(self.base + pos * 4, count * 4)

    def read(self, pos: int, count: int) -> list[int]:
        return bytes_to_words(self.read_raw(pos, count))

    def write_raw(self, pos: int, data: bytes) -> None:
        self.client.write(self.base + pos * 4, data)

    def write(self, pos: int, data: typing.Iterable[int]) -> None:
        self.write_raw(pos, words_to_bytes(data))

    def __len__(self) -> int: return self.count

    @typing.overload
    def __getitem__(self, key: int) -> int: ...
    @typing.overload
    def __getitem__(self, key: slice) -> list[int]: ...
    def __getitem__(self, key: int | slice) -> int | list[int]:
        match key:
            case int():
                if key < 0 or key >= self.count:
                    raise IndexError(f'key={key} is out of range for size {self.count}')
                return self.client.get(self.base + key * 4) >> 8
            case slice():
                r = range(*key.indices(self.count))
                if r.step == 1:
                    return self.read(r.start, r.stop - r.start)
                if r.step == -1:
                    data = self.read(r.start, r.stop - r.start)
                    data.reverse()
                    return data
                return [self.client.get(self.base + p * 4) >> 8 for p in r]

    @typing.overload
    def __setitem__(self, key: int, value: int) -> None: ...
    @typing.overload
    def __setitem__(self, key: slice, value: typing.Sequence) -> None: ...
    def __setitem__(self, key: int | slice, value: int | typing.Sequence) -> None:
        match key:
            case int():
                assert isinstance(value, int)
                self.client.put(self.base + key * 4, value << 8)
            case slice():
                assert isinstance(value, typing.Sequence)
                r = range(*key.indices(self.count))
                if len(value) != len(r):
                    raise IndexError(f'len={len(value)} is out of range for {len(r)}')
                if r.step == 1: self.write(r.start, value)
                if r.step == -1: self.write(r.start, reversed(value))
                for p, item in zip(r, value):
                    self.client.put(self.base + p * 4, item << 8)

