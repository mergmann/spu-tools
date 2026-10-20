import gc
import gint
import machine
import memx
import struct

from micropython import const
import time

gc.collect()
gc.threshold(128 * 1024)

CHUNK_SIZE = const(1024)
START_TOUT = const(250)
VERSION = 0x00000005

class ErrCode:
    OTHER          = 0xF0000000
    UNKNOWN        = 0xF0000001
    MEMORY         = 0xF0000002

    INVALID_ARG    = 0xF0000011
    UNEXPECTED_EOF = 0xF0000012

    ADDR_UNALIGNED = 0xF0000021
    SIZE_UNALIGNED = 0xF0000022

class PacketType:
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

STREAM = 0x80000001

class PacketError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg = msg

    @classmethod
    def unexpected_eof(cls) -> PacketError:
        return cls(ErrCode.UNEXPECTED_EOF, f'Unexpected EOF')

    @classmethod
    def addr_unaligned(cls, exp: int) -> PacketError:
        return cls(ErrCode.ADDR_UNALIGNED, f'Address unaligned, expected {exp}')

    @classmethod
    def size_unaligned(cls, exp: int) -> PacketError:
        return cls(ErrCode.SIZE_UNALIGNED, f'Size unaligned, expected {exp}')

class StopError(Exception):
    pass

class USBAccess:
    def __init__(self, usb: gint.USB, pty: int, size: int) -> None:
        self.usb = usb
        self.pty = pty
        self.left = size
        self.total = size
        self.end_written = False

    def read(self, size: int) -> bytes:
        data = self.usb.read(min(size, self.left))
        self.left -= len(data)
        return data

    def read_exact(self, size: int) -> bytearray:
        if size > self.left: raise PacketError.unexpected_eof()
        buf = bytearray()
        while size:
            data = self.read(size)
            if not data: raise PacketError.unexpected_eof()
            size -= len(data)
            buf.extend(data)
        return buf

    def write(self, data: bytes | bytearray | memoryview):
        self.usb.write(data)

    def set_ok(self, size: int) -> None:
        self.write(struct.pack('>LL', self.pty, size))
        self.end_written = True

    def set_err(self, code: int, msg: str) -> None:
        self.usb.write(code.to_bytes(4, 'big'))
        raw = msg.encode('utf-8')
        self.usb.write(len(raw).to_bytes(4, 'big'))
        self.usb.write(raw)
        self.end_written = True

    def out_stream(self) -> USBOutStream:
        self.write(struct.pack('>LL', STREAM, 0))
        return USBOutStream(self)

    def flush(self) -> None:
        self.usb.flush()

    def consume(self) -> None:
        while self.left: 
            if not self.read(CHUNK_SIZE): break

THRESHOLD = 256

class USBOutStream:
    def __init__(self, usb: USBAccess) -> None:
        self.usb = usb
        self.buf = bytearray()

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.buf.extend(data)
        if len(self.buf) > THRESHOLD:
            self.flush()

    # Empty flushes are allowed, for keepalive maybe?
    def flush(self) -> None:
        self.usb.write(struct.pack('>LL', STREAM, len(self.buf)))
        self.usb.write(self.buf)
        self.usb.flush()
        self.buf = bytearray()  # MicroPython bytearray has no clear()

    def close_ok(self) -> None:
        self.flush()
        self.usb.set_ok(0)
        self.usb.flush()

    def close_err(self, code: int, msg: str) -> None:
        self.flush()
        self.usb.set_err(code, msg)
        self.usb.flush()

def ping(usb: USBAccess):
    echo = usb.read_exact(usb.left)
    usb.set_ok(4 + len(echo))
    usb.write(VERSION.to_bytes(4, 'big'))
    usb.write(echo)
    usb.flush()

def stop(usb: USBAccess):
    usb.set_ok(0)
    usb.flush()
    raise StopError

def exec_(usb: USBAccess):
    code = usb.read_exact(usb.left).decode('utf-8')

    stream = usb.out_stream()
    def _print(*args, sep=' ', end='\n', file=None):
        line = sep.join(str(a) for a in args) + end
        stream.write(line.encode('utf-8'))
        if '\n' in line:
            stream.flush()

    glbls = {'print': _print, 'gint': gint}
    try:
        exec(code, glbls)
    except Exception as e:
        stream.close_err(ErrCode.OTHER, f'{type(e).__name__}: {e}')
    else:
        stream.close_ok()

def status(usb: USBAccess):
    text = usb.read_exact(usb.left).decode('utf-8')
    gint.dclear(gint.C_WHITE)
    gint.dtext(16, 16, gint.C_BLACK, text)
    gint.dupdate()
    usb.set_ok(0)
    usb.flush()

def write(usb: USBAccess, width: int):
    addr = int.from_bytes(usb.read_exact(4), 'big')
    if addr & (width - 1): raise PacketError.addr_unaligned(width)
    if usb.left & (width - 1): raise PacketError.size_unaligned(width)
    while usb.left:
        data = usb.read_exact(min(CHUNK_SIZE, usb.left))
        memx.write(addr, data, width)
        addr += len(data)
    usb.set_ok(0)
    usb.flush()

def write_8 (usb: USBAccess): write(usb, 1)
def write_16(usb: USBAccess): write(usb, 2)
def write_32(usb: USBAccess): write(usb, 4)

# RMW: new = (old & and) ^ xor
def write_masked(usb: USBAccess, mem, width: int):
    if usb.left != 12:
        raise PacketError(ErrCode.INVALID_ARG, 'Expected addr, xor, and')
    addr, xor_, and_ = struct.unpack('>LLL', usb.read_exact(12))
    if addr & (width - 1): raise PacketError.addr_unaligned(width)
    mask = (1 << (8 * width)) - 1
    mem[addr] = ((mem[addr] & and_) ^ xor_) & mask
    new = mem[addr] & mask  # mem32 reads are signed
    usb.set_ok(width)
    usb.write(new.to_bytes(width, 'big'))
    usb.flush()

def mask_8 (usb: USBAccess): write_masked(usb, machine.mem8,  1)
def mask_16(usb: USBAccess): write_masked(usb, machine.mem16, 2)
def mask_32(usb: USBAccess): write_masked(usb, machine.mem32, 4)

def read(usb: USBAccess, width: int):
    addr, size = struct.unpack('>LL', usb.read_exact(8))
    if addr & (width - 1): raise PacketError.addr_unaligned(width)
    if size & (width - 1): raise PacketError.size_unaligned(width)
    buf = bytearray(CHUNK_SIZE)
    usb.set_ok(size)
    while size:
        end = min(len(buf), size)
        view = memoryview(buf)[:end]
        memx.read(view, addr, width)
        usb.write(view)
        addr += end
        size -= end
    usb.flush()

def read_8 (usb: USBAccess): read(usb, 1)
def read_16(usb: USBAccess): read(usb, 2)
def read_32(usb: USBAccess): read(usb, 4)

PACKET_TYPE = {
    PacketType.PING:     (ping,     'ping'),
    PacketType.STOP:     (stop,     'stop'),
    PacketType.EXEC:     (exec_,    'exec'),
    PacketType.STATUS:   (status,   'status'),
    PacketType.WRITE_8:  (write_8,  'write_8'),
    PacketType.WRITE_16: (write_16, 'write_16'),
    PacketType.WRITE_32: (write_32, 'write_32'),
    PacketType.MASK_8:   (mask_8,   'mask_8'),
    PacketType.MASK_16:  (mask_16,  'mask_16'),
    PacketType.MASK_32:  (mask_32,  'mask_32'),
    PacketType.READ_8:   (read_8,   'read_8'),
    PacketType.READ_16:  (read_16,  'read_16'),
    PacketType.READ_32:  (read_32,  'read_32'),
}

def read_packet(usb: gint.USB):
    data = bytearray()
    while len(data) < 8:
        read = usb.read(8 - len(data))
        if not read:
            if not len(data): return
            else: raise EOFError('Header ended to early, desync risk')
        data.extend(read)
    
    ty, size = struct.unpack('>II', data)
    access = USBAccess(usb, ty, size)
    entry = PACKET_TYPE.get(ty, None)
    if entry is None:
        access.consume()
        access.set_err(ErrCode.UNKNOWN, f'Unsupported packet type {ty:08x}')
        access.flush()
        return
    func, _ = entry
    try:
        func(access)
        access.consume()
        return
    except StopError:
        raise
    except MemoryError:
        code, msg = ErrCode.MEMORY, 'Out of memory'
    except PacketError as e:
        code, msg = e.code, e.msg
    except Exception as e:
        code, msg = ErrCode.OTHER, f'{type(e).__name__}: {e}'
    
    access.consume()
    if not access.end_written:
        access.set_err(code, msg)
        access.flush()
    else:
        gint.dtext(16, 16, gint.C_RED, msg)
        gint.dupdate()
        gint.dtext(16, 16, gint.C_WHITE, msg)
        time.sleep(1)

def main(usb: gint.USB):
    while True:
        read_packet(usb)

while True:
    gint.dclear(gint.C_WHITE)
    gint.dtext(16, 16, gint.C_BLACK, 'Open')
    gint.dupdate()
    gint.dtext(16, 16, gint.C_WHITE, 'Open')
    try:
        with gint.USB() as usb:
            main(usb)
    except StopError:
        print('Stopped')
        break
    except Exception as e:
        gint.dtext(16, 16, gint.C_RED, str(e))
        gint.dupdate()
        gint.dtext(16, 16, gint.C_WHITE, str(e))
    time.sleep(5)
