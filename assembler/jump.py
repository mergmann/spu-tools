from builder import Builder
from line import Inst, Match
from register import REGISTERS, Banks, Register, get_reg
from util import get_range, get_unsigned


bld = Builder()
bld.import_all(REGISTERS)

def get_reg8(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Register {reg} is not supported')


@bld.pattern('${hu}', '{n}')
def addr(m: Match, val: int | str | None) -> int | str | None:
    return val


@bld.regex(r'(?i:NV|AL|EQ|NE|LT|GE|LE|GT)')
def jcond(m: Match) -> int:
    match m.text.upper():
        case 'NV': return 0
        case 'AL': return 1
        case 'EQ': return 2
        case 'NE': return 3
        case 'LT': return 4
        case 'GE': return 5
        case 'LE': return 6
        case 'GT': return 7
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('', '.D')
def nodelay(m: Match) -> bool:
    match m.compact:
        case '':   return True
        case '.D': return False
        case _: raise AssertionError('Unexpected pattern')


@bld.export('JMP{nodelay} {addr}')
def jump(m: Match, nodelay: bool, addr: int | str | None) -> Inst | None:
    addri = 0xDEAD if isinstance(addr, str) else get_unsigned(m, addr, 16, 3)
    if addri is not None:
        ref = addr if isinstance(addr, str) else None
        return Inst(0x3B000000 | (nodelay << 21) | addri, ref)

@bld.export('J{jcond}{nodelay} {addr}')
def jumpc(m: Match, cond: int, nodelay: bool, addr: int | str | None) -> Inst | None:
    addri = 0xDEAD if isinstance(addr, str) else get_unsigned(m, addr, 16, 3)
    if addri is not None:
        ref = addr if isinstance(addr, str) else None
        return Inst(0x3B400000 | (nodelay << 21) | (cond << 16) | addri, ref)

@bld.export('CALL.D {addr}')
def call(m: Match, addr: int | str | None) -> Inst | None:
    addri = 0xDEAD if isinstance(addr, str) else get_unsigned(m, addr, 16, 3)
    if addri is not None:
        ref = addr if isinstance(addr, str) else None
        return Inst(0x3B800000 | addri, ref)


@bld.export('REP #{i} , {addr}')
def rep(m: Match, count: int | None, end: int | str | None) -> Inst | None:
    counti = get_range(m, count, 1, 4096, 0)
    endi = 0xDEAD if isinstance(end, str) else get_unsigned(m, end, 16, 1)
    if counti is not None and endi is not None:
        ref = end if isinstance(end, str) else None
        return Inst(0x20000000 | ((counti & 4095) << 16) | endi, ref)

@bld.export('DO {register} , {addr}')
def do(m: Match, reg: Register | None, end: int | str | None) -> Inst | None:
    regi = get_reg8(m, reg, 0)
    endi = 0xDEAD if isinstance(end, str) else get_unsigned(m, end, 16, 1)
    if regi is not None and endi is not None:
        ref = end if isinstance(end, str) else None
        return Inst(0x3CC00000 | (regi << 16) | endi, ref)


@bld.export('JMPI.D {register}')
def jumpi(m: Match, reg: Register | None) -> Inst | None:
    regi = get_reg(m, reg, Banks.P, 0)
    if regi is not None:
        return Inst(0x3CD80000 | regi)

@bld.export('J{jcond}I.D {register}')
def jumpci(m: Match, cond: int, reg: Register | None) -> Inst | None:
    regi = get_reg(m, reg, Banks.P, 1)
    if regi is not None:
        return Inst(0x3CD80100 | (cond << 3) | regi)

@bld.export('CALLI.D {register}')
def calli(m: Match, reg: Register | None) -> Inst | None:
    regi = get_reg(m, reg, Banks.P, 0)
    if regi is not None:
        return Inst(0x3CD80200 | regi)

@bld.export('RTS.D')
def rts(m: Match) -> Inst:
    return Inst(0x3CD80300)

@bld.export('RTI')
def rti(m: Match) -> Inst:
    return Inst(0x3CD80400)

@bld.export('RTI.D')
def rtid(m: Match) -> Inst:
    return Inst(0x3CD80800)

JUMPS = bld
