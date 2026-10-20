from builder import Builder
from line import Inst, Match
from move import OPTMOVE
from register import REGISTERS, Banks, Register
from util import get_signed, get_unsigned


bld = Builder()
bld.import_all(OPTMOVE)
bld.import_all(REGISTERS)


def get_regar(m: Match, reg: Register | None, hole: int) -> int | None:
    if reg is None: return None
    off = 0
    for bank in [Banks.A, Banks.R]:
        if reg in bank:
            return reg.idx - bank + off
        off += bank.num
    m.add_error(hole, f'Expected register a0..a3, r0..r3')


def make_alu_imm(name: str, code: int, signed: bool = True):
    @bld.export(f'{name} {{register}} , {{register}} , #{{i}} {{optmove}}', name=name.lower().replace('.', '_'))
    def alu_imm(m: Match, dst: Register | None, src: Register | None, imm: int | None, mv: int | None) -> Inst | None:
        dsti = get_regar(m, dst, 0)
        srci = get_regar(m, src, 1)
        immi = get_signed(m, imm, 3, 2) if signed else get_unsigned(m, imm, 3, 2)
        if dsti is not None and srci is not None and immi is not None and mv is not None:
            return Inst((code << 24) | (dsti << 21) | (srci << 18) | (immi << 15) | mv)

def make_alu_reg3(name: str, code: int):
    @bld.export(f'{name} {{register}} , {{register}} , {{register}} {{optmove}}', name=name.lower().replace('.', '_'))
    def alu_l(m: Match, dst: Register | None, op1: Register | None, op2: Register | None, mv: int | None) -> Inst | None:
        dsti = get_regar(m, dst, 0)
        op1i = get_regar(m, op1, 1)
        op2i = get_regar(m, op2, 2)
        if dsti is not None and op1i is not None and op2i is not None and mv is not None:
            return Inst((code << 24) | (dsti << 21) | (op1i << 18) | (op2i << 15) | mv)

def make_alu_reg2(name: str, code: int):
    @bld.export(f'{name} {{register}} , {{register}} {{optmove}}', name=name.lower().replace('.', '_'))
    def alu_reg2(m: Match, dst: Register | None, op2: Register | None, mv: int | None) -> Inst | None:
        dsti = get_regar(m, dst, 0)
        op2i = get_regar(m, op2, 1)
        if dsti is not None and op2i is not None and mv is not None:
            return Inst((code << 24) | (dsti << 21) | (op2i << 15) | mv)

def make_alu_cmp(name: str, code: int):
    @bld.export(f'{name} {{register}} , #{{i}} {{optmove}}', name=name.lower().replace('.', '_'))
    def alu_cmp(m: Match, src: Register | None, imm: int | None, mv: int | None) -> Inst | None:
        srci = get_regar(m, src, 0)
        immi = get_signed(m, imm, 3, 1)
        if srci is not None and immi is not None and mv is not None:
            return Inst((code << 24) | (srci << 18) | (immi << 15) | mv)

make_alu_imm('ADDL',   0x80) # aD = aX + imm3, 56bit
make_alu_imm('ADDL.E', 0x81) # aD = aX + imm3, 48bit
make_alu_cmp('CMPL',   0x82)
make_alu_cmp('CMPLU',  0x83)
make_alu_imm('ANDL',   0x88) # aD = aX & ext(imm3), 56bit
make_alu_imm('ORL',    0x89) # aD = aX | ext(imm3), 56bit
make_alu_imm('XORL',   0x8A) # aD = aX ^ ext(imm3), 56bit

@bld.export('MOVL {register} , #{i} {optmove}')
def movl(m: Match, dst: Register | None, imm: int | None, mv: int | None) -> Inst | None:
    dsti = get_regar(m, dst, 0)
    immi = get_signed(m, imm, 6, 1)
    if dsti is not None and immi is not None and mv is not None:
        return Inst(0x8B000000 | (dsti << 21) | (immi << 15) | mv)

make_alu_imm('ADDH',   0x90) # aD = aX + (imm3 << 24), 56bit
make_alu_imm('ADDH.E', 0x91) # aD = aX + (imm3 << 24), 48bit
make_alu_cmp('CMPH',   0x92)
make_alu_cmp('CMPHU',  0x93)
make_alu_imm('SHLH',   0x94, signed=False) # aD = aX << umm3 56bit
make_alu_imm('SHLH.E', 0x95, signed=False) # aD = aX << umm3 48bit
make_alu_imm('SHRH',   0x96, signed=False) # aD = aX >> umm3 56bit
make_alu_imm('SHRH.E', 0x97, signed=False) # aD = aX >> umm3 48bit
make_alu_imm('ANDH',   0x98) # aD = aX & (imm3 << 24), 56bit
make_alu_imm('ORH',    0x99) # aD = aX | (imm3 << 24), 56bit
make_alu_imm('XORH',   0x9A) # aD = aX ^ (imm3 << 24), 56bit

@bld.export('MOVH {register} , #{i} {optmove}')
def movh(m: Match, dst: Register | None, imm: int | None, mv: int | None) -> Inst | None:
    dsti = get_regar(m, dst, 0)
    immi = get_signed(m, imm, 6, 1)
    if dsti is not None and immi is not None and mv is not None:
        return Inst(0x9B000000 | (dsti << 21) | (immi << 15) | mv)

make_alu_reg3('ADD',    0xA0) # aD = aX + aY, 56bit
make_alu_reg3('ADD.E',  0xA1) # aD = aX + aY, 48bit

@bld.export('CMP {register} , {register} {optmove}')
def cmp(m: Match, op1: Register | None, op2: Register | None, mv: int | None) -> Inst | None:
    op1i = get_regar(m, op1, 0)
    op2i = get_regar(m, op2, 1)
    if op1i is not None and op2i is not None and mv is not None:
        return Inst(0xA2000000 | (op1i << 18) | (op2i << 15) | mv)

@bld.export('CMPU {register} , {register} {optmove}')
def cmp_e(m: Match, op1: Register | None, op2: Register | None, mv: int | None) -> Inst | None:
    op1i = get_regar(m, op1, 0)
    op2i = get_regar(m, op2, 1)
    if op1i is not None and op2i is not None and mv is not None:
        return Inst(0xA3000000 | (op1i << 18) | (op2i << 15) | mv)

make_alu_reg3('SHL',   0xA4) # aD = aX << rY, 56bit
make_alu_reg3('SHL.E', 0xA5) # aD = aX << rY, 48bit
make_alu_reg3('SHR',   0xA6) # aD = aX >> rY, 56bit
make_alu_reg3('SHR.E', 0xA7) # aD = aX >> rY, 48bit
make_alu_reg3('AND',   0xA8) # aD = aX & aY, 56bit
make_alu_reg3('OR',    0xA9) # aD = aX | aY, 56bit
make_alu_reg3('XOR',   0xAA) # aD = aX ^ aY, 56bit
make_alu_reg3('HADD',  0xAE) # aD = (aX + aY) >> 1, 56bit
make_alu_reg3('HSUB',  0xAF) # aD = (aX - aY) >> 1, 56bit

make_alu_reg3('SUB',   0xB0) # aD = aX - aY, 56bit
make_alu_reg3('SUB.E', 0xB1) # aD = aX - aY, 48bit
make_alu_reg3('MAX',   0xB2) # aD = max(aX, aY), 56bit
make_alu_reg3('MIN',   0xB3) # aD = min(aX, aY), 56bit
make_alu_reg3('DIVS',  0xB4) # Divide step

@bld.export('NOP {optmove}') # Does NOPthing by itself
def nop(m: Match, mv: int | None) -> Inst | None:
    if mv is not None:
        return Inst(0xB5000000 | mv)

make_alu_reg2('MOV',    0xB7) # aD = aY, 56bit
make_alu_reg2('NEG',    0xB8) # aD = -aY, 56bit
make_alu_reg2('NORM',   0xB9) # aD = 47 - bitlen(aY >= 0 ? Y : ~Y)
make_alu_reg2('ABS',    0xBA) # aD = |aY|, 56bit
make_alu_reg2('MOV.E',  0xBB) # aD = aY, 48bit

ALUS = bld
