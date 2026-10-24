from argparse import ArgumentParser
import struct

from dataclasses import dataclass
from enum import Enum
from typing import Iterator
from usb.core import Configuration, Device, find, USBTimeoutError


@dataclass
class Version:
    major: int
    minor: int

    def __gt__(self, other: Version) -> bool:
        if self.major == other.major:
            return self.minor > other.minor
        return self.major > self.minor

    def __lt__(self, other):
        if self.major == other.major:
            return self.minor < other.minor
        return self.major < self.minor

    def __str__(self) -> str:
        return f'v{self.major}.{self.minor}'

class PacketType(Enum):
    PING     = 0x00001001
    STOP     = 0x00001002
    EXEC     = 0x00001003
    STATUS   = 0x00001004
    WRITE_8  = 0x00002001
    WRITE_16 = 0x00002002
    WRITE_32 = 0x00002003
    MASK_8   = 0x00002021
    MASK_16  = 0x00002022
    MASK_32  = 0x00002023
    READ_8   = 0x00002011
    READ_16  = 0x00002012
    READ_32  = 0x00002013

ERRORS = {
    0xF0000000: 'Other',
    0xF0000001: 'Unknown packet',
    0xF0000002: 'Out of memory',
    0xF0000011: 'Invalid argument',
    0xF0000012: 'Unexpected EOF',
    0xF0000021: 'Address unaligned',
    0xF0000022: 'Size unaligned',
}

class DeviceError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        name = ERRORS.get(code, '?')
        super().__init__(f'{name} ({code:08X}) - {msg}')

STREAM = 0x80000001

VID = 0x07cf
PID = 0x6102
EP_IN  = 0x81
EP_OUT = 0x02

TIMEOUT = 2000
VERSION = Version(0, 5)

class NotFoundError(Exception):
    def __init__(self, vid: int, pid: int) -> None:
        super().__init__(f'Device {vid:04x}:{pid:04x} not foudn')

class VersionError(Exception):
    def __init__(self, has: Version) -> None:
        super().__init__(f'Device has a newer version: {has}, supporter: {VERSION}')

class USBClient:
    @classmethod
    def connect(cls) -> 'USBClient':
        dev = find(idVendor=VID, idProduct=PID)
        if not isinstance(dev, Device):
            raise NotFoundError(VID, PID)
        cfg = dev.get_active_configuration()
        assert isinstance(cfg, Configuration)
        intf = cfg[(0, 0)]
        mps = next(e.wMaxPacketSize for e in intf if e.bEndpointAddress == EP_IN)
        return cls(dev, mps)

    def __init__(self, dev: Device, mps: int) -> None:
        self.dev = dev
        self.mps = mps
        self.rbuf = bytearray()
        self.stopped = False
        self.debug = False

    def __enter__(self) -> 'USBClient':
        return self

    def __exit__(self, *args) -> None:
        if not self.stopped:
            self.drain()

    def _read(self, n: int, tout: int | None = TIMEOUT) -> bytes:
        if self.rbuf:
            data = bytes(self.rbuf[:n])
            self.rbuf = self.rbuf[n:]
            return data

        recved = bytes(self.dev.read(EP_IN, self.mps * 4, tout))

        self.rbuf.extend(recved[n:])
        return recved[:n]

    def _read_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self._read(n)
            if not chunk: raise IOError('Zero read')
            buf.extend(chunk)
        return bytes(buf)

    def _write(self, data: bytes, tout: int | None = TIMEOUT) -> int:
        return self.dev.write(EP_OUT, data, tout)

    def _write_exact(self, data: bytes, tout: int | None = TIMEOUT) -> None:
        # ZLP
        if not data: self._write(data, tout)

        count = len(data)
        offset = 0
        while count:
            sent = self._write(data[offset:], tout)
            if not sent: raise IOError('Zero write')
            count -= sent
            offset += sent

    def drain(self) -> bytes:
        buf = bytearray()
        try:
            while True:
                data = self._read(64, 100)
                buf.extend(data)
        except USBTimeoutError:
            pass
        return bytes(buf)

    def send(self, pty: int, payload: bytes) -> None:
        header = struct.pack('>II', pty, len(payload))
        self._write_exact(header + payload)

    def recv(self) -> Iterator[tuple[int | None, bytes]]:
        while True:
            ty, size = struct.unpack('>II', self._read_exact(8))
            data = self._read_exact(size)
            if ty != STREAM:
                yield ty, data
                return
            yield None, data

    def request(self, pty: PacketType, data: bytes) -> Iterator[bytes]:
        self.send(pty.value, data)
        for ty, data in self.recv():
            if ty is not None and ty != pty.value:
                raise DeviceError(ty, data.decode('utf-8'))
            yield data

    def request_all(self, pty: PacketType, data: bytes) -> bytes:
        return b''.join(self.request(pty, data))

    def check_version(self) -> None:
        ver, _ = self.ping(b'USBClient')
        if ver > VERSION:
            raise VersionError(ver)

    def ping(self, echo: bytes) -> tuple[Version, bytes]:
        data = self.request_all(PacketType.PING, echo)
        ver = int.from_bytes(data[:4], 'big')
        return Version(ver >> 16, ver & 0xFFFF), data[4:]

    def stop(self) -> None:
        self.request_all(PacketType.STOP, b'')
        self.stopped = True

    def exec_iter(self, code: str) -> Iterator[str]:
        if self.debug:
            text = repr(code)
            print(f'exec  len= {len(code):08x} ' + (text if len(text) < 64 else ''))
        return map(
            lambda s: s.decode('utf-8'),
            self.request(PacketType.EXEC, code.encode('utf-8'))
        )

    def exec_all(self, code: str) -> str:
        if self.debug:
            text = repr(code)
            print(f'exec  len= {len(code):08x} ' + (text if len(text) < 64 else ''))
        return self.request_all(PacketType.EXEC, code.encode('utf-8')).decode('utf-8')

    def set_status(self, text: str) -> None:
        self.request_all(PacketType.STATUS, text.encode('utf-8'))

    def write(self, addr: int, data: bytes, width: int = 32) -> None:
        if self.debug: print(f'write addr={addr:08x} len= {len(data):08x} width={width} ' + (data.hex() if len(data) < 16 else ''))
        pdata = int.to_bytes(addr, 4) + data
        match width:
            case 8:  self.request_all(PacketType.WRITE_8,  pdata)
            case 16: self.request_all(PacketType.WRITE_16, pdata)
            case 32: self.request_all(PacketType.WRITE_32, pdata)
            case _: raise ValueError(f'width must be 8, 16, 32, got {width}')

    def mask(self, addr: int, and_: int, xor: int, width: int = 32) -> None:
        if self.debug: print(f'mask  addr={addr:08x} and_={and_:08x} xor={xor:08x} width={width}')
        pdata = struct.pack('>III', addr, xor, and_)
        match width:
            case 8:  self.request_all(PacketType.MASK_8,  pdata)
            case 16: self.request_all(PacketType.MASK_16, pdata)
            case 32: self.request_all(PacketType.MASK_32, pdata)
            case _: raise ValueError(f'width must be 8, 16, 32, got {width}')

    def mask_and(self, addr: int, val: int, width: int = 32) -> None:
        self.mask(addr, val, 0, width)

    def mask_xor(self, addr: int, val: int, width: int = 32) -> None:
        bits = (1 << width) - 1
        self.mask(addr, ~bits, val, width)

    def mask_or(self, addr: int, val: int, width: int = 32) -> None:
        bits = (1 << width) - 1
        self.mask(addr, ~val & bits, val, width)

    def read(self, addr: int, size: int, width: int = 32) -> bytes:
        if self.debug: print(f'read  addr={addr:08x} size={size:08x} width={width}')
        pdata = struct.pack('>II', addr, size)
        match width:
            case 8:  return self.request_all(PacketType.READ_8,  pdata)
            case 16: return self.request_all(PacketType.READ_16, pdata)
            case 32: return self.request_all(PacketType.READ_32, pdata)
            case _: raise ValueError(f'width must be 8, 16, 32, got {width}')

    def put(self, addr: int, data: int, width: int = 32) -> None:
        self.write(addr, data.to_bytes(width // 8), width)

    def get(self, addr: int, width: int = 32) -> int:
        return int.from_bytes(self.read(addr, width // 8, width))

if __name__ == '__main__':
    args = ArgumentParser()
    with USBClient.connect() as client:
        client.check_version()
        client.set_status('Connected')
        client.write(0x8CFFC000, b'Hello World!')
        client.mask(0x8CFFC000, 0x0F, 0xFF, 8)
        print(client.read(0x8CFFC000, 12))
        client.set_status('Disconnected')
