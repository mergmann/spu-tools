from builder import Builder
from line import Inst, Match
from register import REGISTERS, Banks, Register, get_reg
from util import get_signed, get_unsigned, UTILS


bld = Builder()
bld.import_all(REGISTERS)
bld.import_all(UTILS)


def get_reg8(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Register {reg} is not supported')


@bld.pattern('sp + {i}', 'sp - {i}')
def stack_slot(m: Match, off: int | None) -> int | None:
    if off is None: return
    match m.compact:
        case 'sp+': off2 = off
        case 'sp-': off2 = -off
        case _: raise AssertionError('Unexpected pattern')
    return get_signed(m, off2, 16, 0)

FLAGS = {
    'IE': 2, 'C': 3, 'N': 4, 'Z': 5, 'V': 6, 'S': 11,
    **{ 'FL' + str(i): i for i in range(16) }
}
@bld.regex(r'(?i:IE|C|N|Z|V|S|FL([0-9]|1[0-5]))')
def flag(m: Match) -> int:
    return FLAGS[m.text.upper()]


@bld.export('SWI #{i}')
def swi(m: Match, vec: int | None) -> Inst | None:
    veci = get_unsigned(m, vec, 3, 0)
    if veci is not None:
        return Inst(0x3C000000 | veci)

@bld.export('IDLE {addr}')
def idle_a(m: Match, addr: int | str | None) -> Inst | None:
    addri = 0xDEAD if isinstance(addr, str) else get_unsigned(m, addr, 16, 3)
    if addri is not None:
        ref = addr if isinstance(addr, str) else None
        return Inst(0x3C400000 | addri, ref)

@bld.export('IDLE')
def idle(m: Match) -> Inst:
    return Inst(0x3C800000)

@bld.export('DO {register} , {addr}')
def do(m: Match, reg: Register | None, end: int | str | None) -> Inst | None:
    regi = get_reg8(m, reg, 0)
    endi = 0xDEAD if isinstance(end, str) else get_unsigned(m, end, 16, 1)
    if regi is not None and endi is not None:
        ref = end if isinstance(end, str) else None
        return Inst(0x3CC00000 | (regi << 16) | endi, ref)

@bld.export('LEA {register} , SP + #{stack_slot}')
def lea_sp(m: Match, reg: Register | None, slot: int | None) -> Inst | None:
    regi = get_reg(m, reg, Banks.P, 0)
    if regi is not None and slot is not None:
        return Inst(0x3CC80000 | (regi << 16) | slot)

@bld.export('ADD SP , #{i}')
def add_sp(m: Match, reg: Register | None, imm: int | None) -> Inst | None:
    regi = get_reg(m, reg, Banks.P, 0)
    immi = get_signed(m, imm, 16, 0)
    if regi is not None and immi is not None:
        return Inst(0x3CD00000 | immi)


@bld.export('FSET {flag}')
def fset(m: Match, flag: int) -> Inst | None:
    return Inst(0x3CD80500 | flag)

@bld.export('FCLR {flag}')
def fclr(m: Match, flag: int) -> Inst | None:
    return Inst(0x3CD80600 | flag)

@bld.export('HALT')
def halt(m: Match) -> Inst:
    return Inst(0x3CD80700)


CONTROLS = bld
