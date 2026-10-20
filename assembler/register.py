from __future__ import annotations

from dataclasses import dataclass

from builder import Builder
from line import Match


class Bank:
    @property
    def off(self) -> int: return self._off
    @property
    def num(self) -> int: return self._num
    @property
    def end(self) -> int: return self.off + self.num
    @property
    def name(self) -> str: return self._name

    def __init__(self, off: int, num: int, name: str) -> None:
        self._off = off
        self._num = num
        self._name = name

    def __rsub__(self, other: int) -> int:
        return other - self._off

    def __contains__(self, item: Register | int) -> bool:
        if isinstance(item, Register):
            item = item.idx
        return item >= self.off and item < self.end

    def __str__(self) -> str:
        return f'{self.name}0..{self.name}{self.num-1} (x{self.off}..x{self.off+self.num-1})'

class Banks:
    X   = Bank( 0, 64, 'x' )
    A   = Bank( 0,  4, 'a' )
    R   = Bank( 4,  4, 'r' )
    P   = Bank( 8,  8, 'p' )
    PO  = Bank(16,  8, 'po')
    B   = Bank(24,  4, 'b' )
    BO  = Bank(28,  4, 'bo')
    PM  = Bank(32,  8, 'pm')
    BM  = Bank(40,  4, 'bm')
    SYS = Bank(48,  4, 'sy')
    ALO = Bank(52,  4, 'a' )
    AHI = Bank(56,  4, 'a' )
    AEX = Bank(60,  4, 'a' )

# TODO: sp Bank
SP_IDX = 44
LR_IDX = 48
LI_IDX = 49
FL_IDX = 50
FI_IDX = 51

@dataclass
class Register:
    idx: int

    def get(self, m: Match, bank: Bank, hole: int | None, err: bool = True) -> int | None:
        if not self.idx in bank:
            if err:
                m.add_error(
                    hole,
                    'Expected '
                    f'{bank.name}0..{bank.name}{bank.num-1} '
                    f'(x{bank.off}..x{bank.end-1}), '
                    f'got {self}'
                )
            return None
        return self.idx - bank.off

    def __str__(self) -> str:
        return f'x{self.idx}'

SPECIALS = {'sp': SP_IDX, 'lr': LR_IDX, 'li': LI_IDX, 'fl': FL_IDX, 'fi': FI_IDX}
BANKED = [
    (Banks.A, ''), (Banks.R, ''), (Banks.P, ''), (Banks.PO, ''), (Banks.B, ''), (Banks.BO, ''),
    (Banks.PM, ''), (Banks.BM, ''), (Banks.ALO, '.lo'), (Banks.AHI, '.hi'), (Banks.AEX, '.ex'),
]

def name(idx: int) -> str | None:
    for name, i in SPECIALS.items():
        if i == idx: return name
    for bank, suffix in BANKED:
        if idx in bank: return f'{bank.name}{idx - bank.off}{suffix}'
    return f'x{idx}'

def get_reg(m: Match, reg: Register | None, bank: Bank, hole: int | None, err: bool = True) -> int | None:
    if reg is None: return None
    return reg.get(m, bank, hole, err)

def register_check(m: Match, bank: Bank, idx: int) -> Register | None:
    if idx >= 0 and idx < bank.num:
        return Register(bank.off + idx)
    m.add_error(None, f'{bank.name} registers are {bank}')

bld = Builder()

@bld.regex(r'(?i:sp|lr|li|fl|fi)')
def _register(m: Match) -> Register | None:
    match m.text.lower():
        case 'sp':   return Register(SP_IDX)
        case 'lr':   return Register(LR_IDX)
        case 'li':   return Register(LI_IDX)
        case 'fl':   return Register(FL_IDX)
        case 'fi':   return Register(FI_IDX)

@bld.pattern('x{i}', 'a{i}', 'r{i}', 'p{i}', 'po{i}', 'b{i}', 'bo{i}', 'pm{i}', 'bm{i}', 'a{i}.lo', 'a{i}.hi', 'a{i}.ex')
def _register_i(m: Match, idx: int | None) -> Register | None:
    if idx is None: return None
    match m.compact:
        case 'x':    return register_check(m, Banks.X,   idx)
        case 'a':    return register_check(m, Banks.A,   idx)
        case 'r':    return register_check(m, Banks.R,   idx)
        case 'p':    return register_check(m, Banks.P,   idx)
        case 'po':   return register_check(m, Banks.PO,  idx)
        case 'b':    return register_check(m, Banks.B,   idx)
        case 'bo':   return register_check(m, Banks.BO,  idx)
        case 'pm':   return register_check(m, Banks.PM,  idx)
        case 'bm':   return register_check(m, Banks.BM,  idx)
        case 'a.lo': return register_check(m, Banks.ALO, idx)
        case 'a.hi': return register_check(m, Banks.AHI, idx)
        case 'a.ex': return register_check(m, Banks.AEX, idx)

@bld.export('{_register}', '{_register_i}')
def register(m: Match, val: Register | None) -> Register | None:
    return val

REGISTERS = bld
