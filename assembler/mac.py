# Disclaimer:
# This—file—was—written—by——AI——

from dataclasses import dataclass
from typing import Callable

from builder import Builder
from line import Inst, Match
from move import OPTMOVE
from register import REGISTERS, Banks, Register, get_reg


bld = Builder()
bld.import_all(REGISTERS)
bld.import_all(OPTMOVE)


# Products are 2 * x * y of r0..r3 into a0..a3, MPY: aD := +-P, MAC: aD += +-P
@dataclass
class Product:
    dst: int
    rst: bool
    sub: bool
    kind: str              # 'ss', 'su' (s * u), 'uu' (49 bit) or 'pre'
    regs: tuple[int, ...]  # (x, y), 'pre': (y, xa, xb) = y * (xa +- xb)
    pre_sub: bool = False

def get_pair(m: Match, idx: int, base: int, name: str, hole: int) -> int | None:
    if idx - base in (0, 1): return idx - base
    m.add_error(hole, f'Expected {name}{base}..{name}{base + 1}, got {name}{idx}')

def get_factors(m: Match, p: Product, fits: Callable[[int, int], bool], what: str, hole: int) -> tuple[int, int] | None:
    if p.kind != 'ss':
        m.add_error(hole, 'Only a single product can be .SU, .UU or use the pre-adder')
        return
    x, y = p.regs
    if fits(x, y): return x, y
    if fits(y, x): return y, x
    m.add_error(hole, f'Factors must be {what}')


@bld.pattern('MPY', 'MAC')
def mulop(m: Match) -> bool:
    match m.compact:
        case 'MPY': return True
        case 'MAC': return False
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('', '.SU', '.UU')
def mulkind(m: Match) -> str:
    match m.compact:
        case '':    return 'ss'
        case '.SU': return 'su'
        case '.UU': return 'uu'
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('', '-')
def neg(m: Match) -> bool:
    return m.compact == '-'

@bld.pattern('+', '-')
def preop(m: Match) -> bool:
    return m.compact == '-'

@bld.pattern('{mulop}{mulkind} {register} , {neg}{register} , {register}')
def mul(m: Match, rst: bool, kind: str, dst: Register | None, sub: bool, x: Register | None, y: Register | None) -> Product | None:
    dsti = get_reg(m, dst, Banks.A, 2)
    xi = get_reg(m, x, Banks.R, 4)
    yi = get_reg(m, y, Banks.R, 5)
    if dsti is not None and xi is not None and yi is not None:
        return Product(dsti, rst, sub, kind, (xi, yi))

@bld.pattern('{mulop} {register} , {neg}{register} , {register} {preop} {register}')
def premul(m: Match, rst: bool, dst: Register | None, sub: bool, y: Register | None, xa: Register | None, pre_sub: bool, xb: Register | None) -> Product | None:
    dsti = get_reg(m, dst, Banks.A, 1)
    yi = get_reg(m, y, Banks.R, 3)
    xai = get_reg(m, xa, Banks.R, 4)
    xbi = get_reg(m, xb, Banks.R, 6)
    if dsti is not None and yi is not None and xai is not None and xbi is not None:
        return Product(dsti, rst, sub, 'pre', (yi, xai, xbi), pre_sub)

@bld.pattern('{mul}', '{premul}')
def product(m: Match, p: Product | None) -> Product | None:
    return p


# Acc-op and C8 pair-op: ADD d, x, y / SUB d, y, x (y - x) / HADD / HSUB
@bld.regex(r'(?i:HADD|HSUB|ADD|SUB)')
def acc3_op(m: Match) -> int:
    match m.text.upper():
        case 'ADD':  return 0
        case 'SUB':  return 1
        case 'HADD': return 2
        case 'HSUB': return 3
        case _: raise AssertionError('Unexpected pattern')

@bld.pattern('{acc3_op} {register} , {register} , {register}')
def acc3(m: Match, op: int, dst: Register | None, src: Register | None, op2: Register | None) -> tuple[int, int, int, int] | None:
    dsti = get_reg(m, dst, Banks.A, 1)
    srci = get_reg(m, src, Banks.A, 2)
    op2i = get_reg(m, op2, Banks.A, 3)
    if dsti is not None and srci is not None and op2i is not None:
        return op, dsti, srci, op2i

def get_accop(m: Match, acc: tuple[int, int, int, int], hole: int) -> tuple[int, int] | None:
    op, dst, src, op2 = acc
    x, y = (op2, src) if op & 1 else (src, op2)
    dsti = get_pair(m, dst, 2, 'a', hole)
    yi = get_pair(m, y, 2, 'a', hole)
    if dsti is not None and yi is not None:
        return ((op >> 1) << 20) | ((op & 1) << 19) | (dsti << 18) | (yi << 16), x


# E row ALU op on accumulators, value = bits 27:25 << 1 | twin bit 17
E_OPS = {
    'ADD':  0, 'ADD.E': 1, 'CMP':   2, 'CMPU':  3, 'SUB':  4, 'SUB.E': 5, 'MAX':  6, 'MIN':    7,
    'AND':  8, 'OR':    9, 'HADD': 10, 'HSUB': 11, 'NEG': 12, 'NORM': 13, 'ABS': 14, 'MOV.E': 15,
}

@bld.regex(r'(?i:CMPU|CMP)', name='e_cmp')
@bld.regex(r'(?i:MOV\.E|NORM|NEG|ABS)', name='e_rr')
@bld.regex(r'(?i:ADD\.E|SUB\.E|HADD|HSUB|ADD|SUB|MAX|MIN|AND|OR)', name='e_rrr')
def e_op(m: Match) -> int:
    return E_OPS[m.text.upper()]

def get_ealu(m: Match, op: int, dst: Register | None, src: Register | None, op2: Register | None, holes: tuple[int, int, int]) -> tuple[int, int] | None:
    dsti = get_reg(m, dst, Banks.A, holes[0])
    srci = get_reg(m, src, Banks.A, holes[1])
    op2i = get_reg(m, op2, Banks.A, holes[2])
    if dsti is None or srci is None or op2i is None: return
    dsti = get_pair(m, dsti, 0, 'a', holes[0])
    srci = get_pair(m, srci, 0, 'a', holes[1])
    if dsti is not None and srci is not None:
        bits = ((op >> 1) << 25) | (dsti << 24) | ((op2i >> 1) << 23) | (srci << 22) | ((op2i & 1) << 21) | ((op & 1) << 17)
        return bits, op2i

@bld.pattern('{e_rrr} {register} , {register} , {register}')
def ealu_rrr(m: Match, op: int, dst: Register | None, src: Register | None, op2: Register | None) -> tuple[int, int] | None:
    return get_ealu(m, op, dst, src, op2, (1, 2, 3))

@bld.pattern('{e_cmp} {register} , {register}')
def ealu_cmp(m: Match, op: int, src: Register | None, op2: Register | None) -> tuple[int, int] | None:
    return get_ealu(m, op, Register(0), src, op2, (1, 1, 2))

@bld.pattern('{e_rr} {register} , {register}')
def ealu_rr(m: Match, op: int, dst: Register | None, op2: Register | None) -> tuple[int, int] | None:
    return get_ealu(m, op, dst, Register(0), op2, (1, 1, 2))

@bld.pattern('{ealu_rrr}', '{ealu_cmp}', '{ealu_rr}')
def ealu(m: Match, val: tuple[int, int] | None) -> tuple[int, int] | None:
    return val


# 0xC0..0xC7: product into a0/a1 + acc-op
@bld.export('{product} | {acc3} {optmove}')
def mac_c0(m: Match, p: Product | None, acc: tuple[int, int, int, int] | None, mv: int | None) -> Inst | None:
    if p is None or acc is None or mv is None: return
    xy = get_factors(m, p, lambda x, y: x < 2, 'r0..r1 * r0..r3', 0)
    dsti = get_pair(m, p.dst, 0, 'a', 0)
    accw = get_accop(m, acc, 1)
    if xy is not None and dsti is not None and accw is not None:
        (x, y), (bits, ax) = xy, accw
        return Inst(
            0xC0000000 | ((y >> 1) << 26) | (x << 25) | ((y & 1) << 24) | (p.rst << 23) | (p.sub << 22) | (dsti << 21)
                       | bits | ((ax < 2) << 17) | ((ax & 1) << 15) | mv
        )

# 0xC8..0xCF: pair-op into a0/a1 + product into a2/a3
@bld.export('{acc3} | {product} {optmove}')
def mac_c8(m: Match, pair: tuple[int, int, int, int] | None, p: Product | None, mv: int | None) -> Inst | None:
    if pair is None or p is None or mv is None: return
    op, dst, src, op2 = pair
    dsti = get_pair(m, dst, 0, 'a', 0)
    srci = get_pair(m, src, 0, 'a', 0)
    xy = get_factors(m, p, lambda x, y: y >= 2, 'r0..r3 * r2..r3', 1)
    pdsti = get_pair(m, p.dst, 2, 'a', 1)
    if dsti is not None and srci is not None and xy is not None and pdsti is not None:
        x, y = xy
        if x < 2: prod = (1 << 20) | ((y - 2) << 19) | (x << 18) # r0..r1 * r2..r3
        else:     prod = ((x - 2) << 19) | ((y - 2) << 18)       # r2..r3 * r2..r3
        return Inst(
            0xC8000000 | (op << 25) | (dsti << 24) | ((op2 >> 1) << 23) | (srci << 22) | ((op2 & 1) << 21)
                       | prod | (p.rst << 17) | (p.sub << 16) | (pdsti << 15) | mv
        )

# 0xD0..0xD7: one product, any registers
@bld.export('{product} {optmove}')
def mac_d0(m: Match, p: Product | None, mv: int | None) -> Inst | None:
    if p is None or mv is None: return
    if p.kind == 'pre':
        y, xa, xb = p.regs
        def fits(xa: int, xb: int) -> int | None:
            if xa <  2 and xb >= 2:             return ((y & 1) << 24) | (xa << 23) | ((xb - 2) << 22) | ((y >> 1) << 21)
            if  y <  2 and xa >= 2 and xb >= 2: return (y << 24) | ((xa - 2) << 23) | ((xb - 2) << 22) | (1 << 20)
            if  y >= 2 and xa <  2 and xb <  2: return ((y - 2) << 24) | (xa << 23) | (xb << 22) | (1 << 21) | (1 << 20)
        prod = fits(xa, xb)
        if prod is None and not p.pre_sub: prod = fits(xb, xa)
        if prod is None:
            m.add_error(0, 'Pre-adder needs r0..r1 +- r2..r3, or both on the other half from y')
            return
        prod |= (1 << 25) | (p.pre_sub << 19)
    else:
        x, y = p.regs
        prod = ((p.kind == 'su') << 24) | ((p.kind == 'uu') << 23) | (x << 21) | (y << 19)
    return Inst(0xD0000000 | prod | (p.rst << 18) | (p.sub << 17) | (p.dst << 15) | mv)

# 0xD8..0xDF: two products, into a0/a1 and a2/a3
@bld.export('{product} | {product} {optmove}')
def mac_d8(m: Match, p1: Product | None, p2: Product | None, mv: int | None) -> Inst | None:
    if p1 is None or p2 is None or mv is None: return
    xy1 = get_factors(m, p1, lambda x, y: x < 2, 'r0..r1 * r0..r3', 0)
    dst1 = get_pair(m, p1.dst, 0, 'a', 0)
    dst2 = get_pair(m, p2.dst, 2, 'a', 1)
    if xy1 is None or dst1 is None or dst2 is None: return
    b23 = xy1[1] >= 2 # also selects p2's second factor from r0..r1
    xy2 = get_factors(m, p2, lambda x, y: x >= 2 and (y < 2) == b23, f'r2..r3 * {"r0..r1" if b23 else "r2..r3"}', 1)
    if xy2 is not None:
        (x1, y1), (x2, y2) = xy1, xy2
        return Inst(
            0xD8000000 | (p1.rst << 26) | (p1.sub << 25) | (dst1 << 24) | (b23 << 23) | (x1 << 22) | ((y1 & 1) << 21)
                       | (p2.rst << 20) | (p2.sub << 19) | (dst2 << 18) | ((x2 - 2) << 16) | ((y2 & 1) << 15) | mv
        )

# 0xE0..0xEF: ALU op on a0..a3 + acc-op, acc-op x is a0..a1 iff ALU op2 is a2..a3
@bld.export('{ealu} | {acc3} {optmove}')
def mac_e0(m: Match, alu: tuple[int, int] | None, acc: tuple[int, int, int, int] | None, mv: int | None) -> Inst | None:
    if alu is None or acc is None or mv is None: return
    (bits, op2), accw = alu, get_accop(m, acc, 1)
    if accw is None: return
    accbits, ax = accw
    if (ax < 2) != (op2 >= 2):
        m.add_error(1, f'Acc-op operand must be {"a0..a1" if op2 >= 2 else "a2..a3"} with ALU op2 a{op2}')
        return
    return Inst(0xE0000000 | bits | accbits | ((ax & 1) << 15) | mv)


MACS = bld
