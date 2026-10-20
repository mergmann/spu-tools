from builder import Builder
from line import Inst, Match


bld = Builder()


@bld.export('IDLE')
def idle(m: Match) -> Inst:
    return Inst(0x3C800000)

@bld.export('HALT')
def halt(m: Match) -> Inst:
    return Inst(0x3CD80700)


CONTROLS = bld
