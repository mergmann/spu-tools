from typing import Callable

from builder import Builder
from line import Match
from register import REGISTERS, Banks, Register, get_reg
from util import get_range, get_signed


def get_reg32_p(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R, Banks.P, Banks.AHI, Banks.ALO, Banks.B, Banks.AEX]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Register {reg} is not supported')

def get_reg32_s(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R, Banks.P, Banks.SYS, Banks.ALO, Banks.AHI, Banks.AEX]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Register {reg} is not supported')

def get_reg20(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R, Banks.PO, Banks.BO]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Register {reg} is not supported')

def get_p4(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    if reg not in Banks.P:
        m.add_error(hole, f'Expected p0..p4, got {reg}')
        return None
    return reg.idx - Banks.P.off

def get_b4(m: Match, reg: Register | None, hole: int | None) -> int | None:
    if reg is None: return None
    if reg not in Banks.B:
        m.add_error(hole, f'Expected b0..b4, got {reg}')
        return None
    return reg.idx - Banks.B.off


GROUPS = {
    'x2': ('a0, a1',         {0: 0, 1: 1}),
    'y2': ('a2, a3',         {2: 0, 3: 1}),
    'x4': ('a0, a1, r0, r1', {0: 0, 1: 1, 4: 2, 5: 3}),
    'y4': ('a2, a3, r2, r3', {2: 0, 3: 1, 6: 2, 7: 3}),
}
def get_small(m: Match, reg: Register | None, grp: str, hole: int | None) -> int | None:
    if reg is None: return None
    names, ints = GROUPS[grp]
    if reg.idx in ints: return ints[reg.idx]
    m.add_error(hole, f'Register {reg} is not supported, expected {names}')


bld = Builder()
bld.import_all(REGISTERS)

@bld.pattern('{register}', 'a{i}.l')
def register_24(m: Match, reg: Register | int | None) -> int | None:
    if isinstance(reg, Register):
        return get_reg20(m, reg, 0)
    regi = get_range(m, reg, 0, 3, 0)
    if regi is not None:
        return regi + 20

@bld.pattern('', '+', '-', '+1', '-1', '+2', '-2', '+O', '-O', '+OM')
def update_3(m: Match) -> int:
    match m.compact:
        case '':         return 0
        case '+1' | '+': return 1
        case '-1' | '-': return 2
        case '+2':       return 3
        case '-2':       return 4
        case '+O':       return 5
        case '-O':       return 6
        case '+OM':      return 7
    raise AssertionError('Unexpected pattern')

@bld.pattern('', '+', '+1', '+O', '+OM')
def update_2(m: Match) -> int:
    match m.compact:
        case '':         return 0
        case '+1' | '+': return 1
        case '+O':       return 2
        case '+OM':      return 3
    raise AssertionError('Unexpected pattern')


def make_dual(name: str, space: str, r2: str, r4: str, get_pointer: Callable):
    @bld.pattern(f'ld {{register}} , {space} [ {{register}} {{update_2}} ] ', name=name + '_ld')
    def dual_ld(m: Match, dst: Register | None, ptr: Register | None, upd: int) -> int | None:
        dsti = get_small(m, dst, r4, 0)
        ptri = get_pointer(m, ptr, 1)
        if dsti is not None and ptri is not None:
            return (dsti << 4) | (ptri << 2) | upd

    @bld.pattern(f'st {space} [ {{register}} {{update_2}} ] , {{register}}', name=name + '_st')
    def dual_st(m: Match, ptr: Register | None, upd: int, dst: Register | None) -> int | None:
        ptri = get_pointer(m, ptr, 0)
        dsti = get_small(m, dst, r2, 2)
        if dsti is not None and ptri is not None:
            return 0x40 | (dsti << 4) | (ptri << 2) | upd

    @bld.pattern('ldi {register} , #{i}', name=name + '_imm')
    def dual_imm(m: Match, dst: Register | None, imm: int | None) -> int | None:
        dsti = get_small(m, dst, r4, 2)
        immi = get_signed(m, imm, 2, 1)
        if dsti is not None and immi is not None:
            return 0x60 | (dsti << 3) | (immi << 1)

    @bld.pattern(f'{{{name + "_ld"}}}', f'{{{name + "_st"}}}', f'{{{name + "_imm"}}}', name=name)
    def dual(m: Match, part: int | None) -> int | None:
        return part

make_dual('dual_x', 'X', 'x2', 'x4', get_p4)
make_dual('dual_y', 'Y', 'y2', 'y4', get_b4)

@bld.export('{dual_x} | {dual_y}', '{dual_y} | {dual_x}')
def dual(m: Match, l: int | None, r: int | None) -> int | None:
    if l is None or r is None: return
    if m.index == 0: return l << 7 | r
    else:            return r << 7 | l


@bld.pattern('sp - {i}')
def stack_slot(m: Match, off: int | None) -> int | None:
    if off is None: return
    if off > 0 and off <= 64:
        return -off + 64
    m.add_error(0, f'Stack slot must be -64..-1, got {off}')

# 0x4000..0x4FFF
@bld.export('ld {register} , X [ {register} {update_3} ]')
def ld_xp(m: Match, dst: Register | None, ptr: Register | None, upd: int) -> int | None:
    dsti = get_reg32_p(m, dst, 0)
    ptri = get_reg(m, ptr, Banks.P, 1)
    if dsti is not None and ptri is not None:
        return 0x4000 | (dsti << 7) | (ptri << 3) | upd


@bld.export('st X [ {register} {update_3} ] , {register}')
def st_xp(m: Match, ptr: Register | None, upd: int, src: Register | None) -> int | None:
    ptri = get_reg(m, ptr, Banks.P, 0)
    srci = get_reg32_p(m, src, 1)
    if srci is not None and ptri is not None:
        return 0x4040 | (srci << 7) | (ptri << 3) | upd

# 0x5000..0x5FFF
@bld.export('lds {register} , X [ {stack_slot} ]')
def ld_stk(m: Match, dst: Register | None, stk: int | None) -> int | None:
    dsti = get_reg32_s(m, dst, 0)
    if dsti is not None and stk is not None:
        return 0x5000 | (dsti << 7) | stk

@bld.export('st X [ {stack_slot} ] , {register}')
def st_stk(m: Match, stk: int | None, src: Register | None) -> int | None:
    srci = get_reg32_s(m, src, 1)
    if srci is not None and stk is not None:
        return 0x5040 | (srci << 7) | stk

# 0x6000..0x6FFF
@bld.export('mv {register} , {register}')
def mv(m: Match, dst: Register | None, src: Register | None) -> int | None:
    if dst is not None and src is not None:
        return 0x6000 | (dst.idx << 6) | src.idx

# 0x7100..0x71FF
@bld.export('ld {register} , L [ {register} {update_3} ]')
def ld_lp(m: Match, dst: Register | None, ptr: Register | None, upd: int) -> int | None:
    dsti = get_reg(m, dst, Banks.A, 0)
    ptri = get_reg(m, ptr, Banks.P, 1)
    if dsti is not None and ptri is not None:
        return 0x7000 | (dsti << 7) | (ptri << 3) | upd

@bld.export('st L [ {register} {update_3} ] , {register}')
def st_lp(m: Match, ptr: Register | None, upd: int, dst: Register | None) -> int | None:
    ptri = get_reg(m, ptr, Banks.P, 0)
    dsti = get_reg(m, dst, Banks.A, 2)
    if dsti is not None and ptri is not None:
        return 0x7040 | (dsti << 7) | (ptri << 3) | upd

# 0x7200..0x72FF
@bld.export('ld {register} , Y [ {register} {update_3} ]')
def ld_yb(m: Match, dst: Register | None, ptr: Register | None, upd: int) -> int | None:
    dsti = get_small(m, dst, 'y4', 0)
    ptri = get_reg(m, ptr, Banks.B, 1)
    if dsti is not None and ptri is not None:
        return 0x7200 | (dsti << 6) | (ptri << 3) | upd

@bld.export('st Y [ {register} {update_3} ] , {register}')
def st_yb(m: Match, ptr: Register | None, upd: int, src: Register | None) -> int | None:
    ptri = get_reg(m, ptr, Banks.B, 0)
    srci = get_small(m, src, 'y4', 2)
    if srci is not None and ptri is not None:
        return 0x7220 | (srci << 6) | (ptri << 3) | upd

# 0x7300..0x73FF
@bld.export('ld {register} , IO [ {register} {update_3} ]')
def ld_iob(m: Match, dst: Register | None, ptr: Register | None, upd: int) -> int | None:
    dsti = get_small(m, dst, 'y4', 0)
    ptri = get_reg(m, ptr, Banks.B, 1)
    if dsti is not None and ptri is not None:
        return 0x7300 | (dsti << 6) | (ptri << 3) | upd

@bld.export('st IO [ {register} {update_3} ] , {register}')
def st_iob(m: Match, ptr: Register | None, upd: int, src: Register | None) -> int | None:
    ptri = get_reg(m, ptr, Banks.B, 0)
    srci = get_small(m, src, 'y4', 2)
    if srci is not None and ptri is not None:
        return 0x7320 | (srci << 6) | (ptri << 3) | upd

# 0x7400..0x75FF
@bld.export('lea {register} , {stack_slot}')
def lea_sp(m: Match, dst: Register | None, stk: int | None) -> int | None:
    dsti = get_reg(m, dst, Banks.P, 0)
    if dsti is not None and stk is not None:
        return 0x7400 | (dsti << 6) | stk

# 0x7600..0x77FF
@bld.export('lea {register} , {register} + {register}')
def lea_po(m: Match, dst: Register | None, src: Register | None, off: Register | None) -> int | None:
    dsti = get_reg(m, dst, Banks.P, 0)
    srci = get_reg(m, src, Banks.P, 1)
    offi = get_reg(m, off, Banks.PO, 2)
    if dsti is not None and srci is not None and offi is not None:
        return 0x7600 | (dsti << 6) | (srci << 3) | offi

# 0x7800..0x79FF
@bld.export('lea {register} , {register} + #{i}')
def lea_pi(m: Match, dst: Register | None, src: Register | None, imm: int | None) -> int | None:
    dsti = get_reg(m, dst, Banks.P, 0)
    srci = get_reg(m, src, Banks.P, 1)
    immi = get_signed(m, imm, 3, 2)
    if dsti is not None and srci is not None and immi is not None:
        return 0x7800 | (dsti << 6) | (srci << 3) | immi

# 0x7A00..0x7CFF
@bld.export('ldi {register_24} , #{i}')
def ldi(m: Match, dst: int | None, imm: int | None) -> int | None:
    immi = get_signed(m, imm, 5, 1)
    if dst is not None and immi is not None:
        return 0x7A00 + (dst << 5) | (immi & 31)

# 0x7D00..0x7D7F
@bld.export('add sp , #{i}')
def add_sp(m: Match, imm: int | None) -> int | None:
    immi = get_signed(m, imm, 7, 0)
    if immi is not None:
        return 0x7D00 | (immi & 127)

# 0x7D80..0x7DFF
@bld.export('lea {register} , {register} + #{i}')
def lea_bi(m: Match, dst: Register | None, src: Register | None, imm: int | None) -> int | None:
    dsti = get_reg(m, dst, Banks.B, 0)
    srci = get_reg(m, src, Banks.B, 1)
    immi = get_signed(m, imm, 3, 2)
    if dsti is not None and srci is not None and immi is not None:
        return 0x7D80 | (dsti << 5) | (srci << 3) | immi

# 0x7E00..0x7E3F
@bld.export('lea {register} , {register} + {register}')
def lea_bm(m: Match, dst: Register | None, src: Register | None, off: Register | None) -> int | None:
    dsti = get_reg(m, dst, Banks.B, 0)
    srci = get_reg(m, src, Banks.B, 1)
    offi = get_reg(m, off, Banks.BO, 2)
    if dsti is not None and srci is not None and offi is not None:
        return 0x7E00 | (dsti << 4) | (srci << 2) | offi

# 0x7E40..0x7E7F
@bld.export('clr X [ {register} {update_3} ]')
def clr_xp(m: Match, ptr: Register | None, upd: int) -> int | None:
    ptri = get_reg(m, ptr, Banks.P, 0)
    if ptri is not None:
        return 0x7E40 | (ptri << 3) | upd

# 0x7E80..0x7EFF
@bld.export('mv.e {register} , {register}')
def mve(m: Match, dst: Register | None, src: Register | None) -> int | None:
    dsti = get_reg(m, dst, Banks.A, 0)
    srci = get_reg(m, src, Banks.A, 1)
    if dsti is not None and srci is not None:
        return 0x7E80 | (dsti << 2) | srci

@bld.export('sub {register} , O')
def sub(m: Match, reg: Register | None) -> int | None:
    dstp = get_reg(m, reg, Banks.P, 0, err=False)
    if dstp is not None:
        return 0x7E90 | dstp
    dstb = get_reg(m, reg, Banks.B, 0, err=False)
    if dstb is not None:
        return 0x7E98 | dstb
    m.add_error(0, f'Register {reg} is not supported, expected p0..7, b0..3')

@bld.export('nop')
def nop(m: Match) -> int:
    return 0x7E9C

MOVE = bld


opt = Builder()
opt.add('move', MOVE)

class _None: pass
_none = _None()

@opt.export('', '|| {move}')
def optmove(m: Match, move: int | None | _None = _none) -> int | None:
    if isinstance(move, _None): return 0x7E9C
    if move is None:            return None
    return move

OPTMOVE = opt
