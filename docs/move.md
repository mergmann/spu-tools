# Parallel move field

I want to make the name "bointer" for the Y/IO (b0..b3) pointers official

```
|14 13 12 11 10  9  8  7  6  5  4  3  2  1  0|
|--------------------------------------------|
| 0|       X-half       |       Y-half       | DUAL-XY
|--------------------------------------------|
| 1  0  0|     reg5     |st|  ptr   |  upd3  | MEM-X
| 1  0  1|     reg5     |st|      slot       | MEM-STK
| 1  1  0|       dst       |       src       | REG-MOVE
|--------------------------------------------|
| 1  1  1  0  0  0| acc |st|  ptr   |  upd3  | MEM-L
| 1  1  1  0  0  1|sp|regY |st| btr |  upd3  | MEM-YIO
| 1  1  1  0  1  0|  ptr   |      slot       | LEA-STK
| 1  1  1  0  1  1|  dptr  |  sptr  |  off   | LEA-OFF
| 1  1  1  1  0  0|  dptr  |  sptr  |  imm3  | LEA-IMM
|--------------------------------------------|
| 1  1  1  1  1  0  1  0|        imm7        | ADD-STK
| 1  1  1  1  1  0  1  1|dbtr |sbtr |  imm3  | LEA-BIMM
|--------------------------------------------|
| 1  1  1  1  1  1|--| 0  0|dbtr |sbtr |boff | LEA-BOFF
| 1  1  1  1  1  1|--| 0  1|   ptr  |  upd3  | MEM-CLR
| 1  1  1  1  1  1|--| 1| --- | 0|dacc |sacc | ACC-MOVE
| 1  1  1  1  1  1|--| 1| --- | 1  0|  ptr   | SUB-PTR
| 1  1  1  1  1  1|--| 1| --- | 1  1  0| btr | SUB-BTR
| 1  1  1  1  1  1|--| 1| --- | 1  1  1| --- | NOP
|--------------------------------------------|
|14 13 12 11 10  9  8  7  6  5  4  3  2  1  0|
```


## Legend

| reg5     | 0..3   | 4..7   | 8..15  | 16..19       | 20..23       | 24..27 | 28..31       |
|----------|--------|--------|--------|--------------|--------------|--------|--------------|
| register | a0..a3 | r0..r3 | p0..p7 | a0.hi..a3.hi | a0.lo..a3.lo | b0..b3 | a0.ex..a3.ex |

---

| upd3   | 000  | 001 | 010 | 011 | 100 | 101 | 110 | 111  |
|--------|------|-----|-----|-----|-----|-----|-----|------|
| effect | none | +=1 | -=1 | +=2 | -=2 | +=O | -=O | mode |

The update field changes how the pointer gets update after access.  
O means the corresponding offset register,
mode means the behaviour depends on the mode register.

- `acc`: a0..a3
- `ptr`: p0..p7
- `btr`: b0..b3
- `regX`: a0, a1, r0, r1
- `regY`: a2, a3, r2, r3
- `st`: `0`: load, `1`: store
- `slot`: Stack slot `SP - 64 + slot`

## Description

### Dual X and Y
// TODO


### X memory access
`ld reg5, X[ptr(upd3)]`, `st X[ptr(upd3)], reg5`  
Access X-memory by a pointer with pointer update


### Stack memory access
`ld reg5, X[sp - 64 + slot]`, `st X[sp - 64 + slot], reg5`  
Access X-memory by a stack slot. This encoding can access X[SP-64]..X[SP-1]


### Register-Register move
`mv dst, src`  
Move from any of the 64 register views to any other


### Long memory access
`ld acc, L[ptr(upd3)]`, `st L[ptr(upd3)], acc`  
Access X-memory and Y-memory simultaneously.
a.hi is in Y-memory and a.lo in X-memory.


### Y/IO access
`ld regY, Y/IO[btr(upd3)]`, `st Y/IO[btr(upd3)], regY`  
Access Y-memory or [IO-memory](memory.md#io-memory) with a bointer.


### Load effective address (X)
`lea ptr, sp - 64 + slot`  
Set a pointer to a stack offset

`lea dptr, sptr + off`  
Offset a pointer by an offset register (po0..po7)

`lea dptr, sptr + #imm3`  
Offset a pointer by an immediate (signed)


### Change stack pointer
`add sp, #imm7`  
Move the stack pointer by an immediate (signed)


### Load effective address (Y)
`lea dbtr, sbtr + #imm3`  
Offset a bointer by an immediate (signed)

`lea dbtr, sbtr + off`  
Offset a bointer by an offset register (bo0..bo7)


### Clear memory cell
`clr X[ptr(upd3)]`
Set the memory cell to 0 and do the pointer update


### Accumulator move
`mv.e dacc, sacc`  
Move an accumulator and sign-extend into its guard bits (48-bit extend mode)


### Decrease pointer
`sub ptr, o`  
Decrease the pointer by its corresponding offset register

`sub btr, o`  
Decrease the bointer by its corresponding offset register


### No move
`nop`  
Does nothing
