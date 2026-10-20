from alu import ALUS
from builder import Builder
from control import CONTROLS
from jump import JUMPS
from line import Inst, Match
from mac import MACS
from move import get_small, MOVE
from register import REGISTERS, Banks, Register, get_reg
from util import get_signed, get_unsigned

bld = Builder()
bld.add('move', MOVE)

bld.import_all(REGISTERS)

bld.reexport_all(ALUS)
bld.reexport_all(CONTROLS)
bld.reexport_all(JUMPS)
bld.reexport_all(MACS)


@bld.pattern('X', 'Y')
def space_xy(m: Match) -> int:
    match m.compact:
        case 'X':  return 0
        case 'Y':  return 1
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('X', 'Y', 'L', 'IO')
def space_xylio(m: Match) -> int:
    match m.compact:
        case 'X':  return 0
        case 'Y':  return 1
        case 'L':  return 2
        case 'IO': return 3
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('+ {u}', '- {u}')
def offset(m: Match, val: int | None) -> int | None:
    if val is None: return
    match m.compact:
        case '+': return  val
        case '-': return -val

@bld.pattern('#{i}', '${hu}')
def imm_addr(m: Match, val: int | None) -> int | None:
    return val

@bld.export('LDI {register} , {imm_addr}')
def ldi(m: Match, dst: Register | None, imm: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.X, 0)
    immi = get_signed(m, imm, 20, 1)
    if dsti is not None and immi is not None:
        return Inst(0x30000000 | (dsti << 20) | immi)

@bld.export('STI {space_xylio} [ ${hu} ] , #{i}')
def sti_x(m: Match, space: int, addr: int | None, imm: int | None) -> Inst | None:
    addri = get_unsigned(m, addr, 16, 1)
    immi = get_signed(m, imm, 8, 2)
    if addri is not None and immi is not None:
        return Inst(0x34000000 | (space << 24) | (immi << 16) | addri)


@bld.export('LD {register} , {space_xy} [ ${hu} ]')
def ld_xy(m: Match, dst: Register | None, space: int, addr: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.X, 0)
    addri = get_unsigned(m, addr, 16, 2)
    if dsti is not None and addri is not None:
        return Inst(0x38000000 | (space << 23) | (dsti << 17) | addri)

@bld.export('ST {space_xy} [ ${hu} ] , {register}')
def st_xy(m: Match, space: int, addr: int | None, src: Register | None) -> Inst | None:
    addri = get_unsigned(m, addr, 16, 1)
    srci = get_reg(m, src, Banks.X, 2)
    if srci is not None and addri is not None:
        return Inst(0x38010000 | (space << 23) | (srci << 17) | addri)

@bld.export('LD {register} , L [ ${hu} ]')
def ld_l(m: Match, dst: Register | None, addr: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.A, 0)
    addri = get_unsigned(m, addr, 16, 1)
    if dsti is not None and addri is not None:
        return Inst(0x39000000 | (dsti << 17) | addri)

@bld.export('ST L [ ${hu} ] , {register}')
def st_l(m: Match, addr: int | None, src: Register | None) -> Inst | None:
    addri = get_unsigned(m, addr, 16, 0)
    srci = get_reg(m, src, Banks.A, 1)
    if srci is not None and addri is not None:
        return Inst(0x39010000 | (srci << 17) | addri)

@bld.export('LD {register} , IO [ ${hu} ]')
def ld_io(m: Match, dst: Register | None, addr: int | None) -> Inst | None:
    dsti = get_small(m, dst, 'y4', 0)
    addri = get_unsigned(m, addr, 16, 1)
    if dsti is not None and addri is not None:
        return Inst(0x39800000 | (dsti << 17) | addri)

@bld.export('ST IO [ ${hu} ] , {register}')
def st_io(m: Match, addr: int | None, src: Register | None) -> Inst | None:
    addri = get_unsigned(m, addr, 16, 0)
    srci = get_small(m, src, 'y4', 1)
    if srci is not None and addri is not None:
        return Inst(0x39810000 | (srci << 17) | addri)


@bld.export('LDS {register} , X [ SP {offset} ] ')
def ld_sp(m: Match, dst: Register | None, off: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.X, 0)
    offi = get_signed(m, off, 16, 1)
    if dsti is not None and offi is not None:
        return Inst(0x3A000000 | (dsti << 17) | offi)

@bld.export('STS X [ SP {offset} ] , {register}')
def st_sp(m: Match, off: int | None, src: Register | None) -> Inst | None:
    offi = get_signed(m, off, 16, 0)
    srci = get_reg(m, src, Banks.X, 1)
    if srci is not None and offi is not None:
        return Inst(0x3A010000 | (srci << 17) | offi)

@bld.export('LEA {register} , {register} , #{i}')
def lea(m: Match, dst: Register | None, src: Register | None, off: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.P, 0)
    srci = get_reg(m, src, Banks.P, 1)
    offi = get_signed(m, off, 16, 2)
    if dsti is not None and srci is not None and offi is not None:
        return Inst(0x3A800000 | (dsti << 19) | (srci << 16) | offi)

@bld.export('LDAI {register} , #{i}')
def ldai(m: Match, dst: Register | None, imm: int | None) -> Inst | None:
    dsti = get_reg(m, dst, Banks.A, 0)
    immi = get_signed(m, imm, 20, 1)
    if dsti is not None and immi is not None:
        return Inst(0x3AC00000 | (dsti << 20) | immi)


@bld.export('DUAL {move} || {move}')
def dual(m: Match, mv1: int | None, mv2: int | None) -> Inst | None:
    if mv1 is not None and mv2 is not None:
        return Inst(0x40000000 | (mv2 << 15) | mv1)


INSTRUCTIONS = bld
