from builder import Builder
from line import Match


bld = Builder()

def get_range(m: Match, i: int | None, min: int, max: int, hole: int) -> int | None:
    if i is None: return
    if i < min or i > max:
        m.add_error(hole, f'Value must be {min}..{max}, got {i}')
        return
    return i

def get_signed(m: Match, i: int | None, bits: int, hole: int) -> int | None:
    if i is None: return
    if i < -(1 << (bits - 1)) or i > (1 << (bits - 1)) - 1:
        m.add_error(hole, f'Value must be {bits} bits signed')
        return
    return i & ((1 << bits) - 1)

def get_unsigned(m: Match, i: int | None, bits: int, hole: int) -> int | None:
    if i is None: return
    if i < 0 or i > (1 << bits) - 1:
        m.add_error(hole, f'Value must be {bits} bits unsigned')
        return
    return i & ((1 << bits) - 1)


@bld.export('${hu}', '{n}')
def addr(m: Match, val: int | str | None) -> int | str | None:
    return val

UTILS = bld
