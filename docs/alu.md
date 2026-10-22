# Overview

The ALU operates on
the 56-bit [Accumulators (a0..a3)](registers.md#accumulator-a0a3)
and 24-bit [Data registers (r0..r3)](registers.md#data-register-r0r3).  
Behaviour of data registers:
- As input: `r0..r3` get extended to `[sign:8][input:24][000000:24]`.
- As output: `r0..r3` get truncated as `[:8][output:24][:24]`.

## Instructions

- `.E` are 48-bit versions of their 56-bit counterpart.  
  They extend their 48-bit result into the ex bits.
- `imm3` is a 3-bit **signed** immediate (-4..3).  
- `imm6` is a 6-bit **signed** immdeate (-32..31)
- `umm3` is a 3-bit **unsigned** immediate

Signed immediates are sign-extended to 56 bits before being passed to the operation:  
`XORL D, X, #-1` flips all bits in the input => `D = ~X`

### Low-immediate

These instructions use the immediate on the lower part of the accumulator

| Major | Mnemonic | Operation
|-------|----------|-----------|
| 80    | `ADDL D, X, #imm3`   | `D = X + imm3`
| 81    | `ADDL.E D, X, #imm3` | `D = X + imm3`
| 82    | `CMPL X, #imm3`      | `fl = iflags(X - imm3)`
| 83    | `CMPLU X, #imm3`     | `fl = uflags(X - imm3)`
| 88    | `ANDL D, X, #imm3`   | `D = X & imm3`
| 89    | `ORL D, X, #imm3`    | `D = X \| imm3`
| 8A    | `XORL D, X, #imm3`   | `D = X ^ imm3`
| 8B    | `MOVL D, #imm6`      | `D = imm6`

### High-immediate

These instructions use the immediate on the middle part of the accumulator (imm << 24)

| Major | Mnemonic | Operation
|-------|----------|-----------|
| 90    | `ADDH D, X, #imm3`   | `D = X + (imm3 << 24)`
| 91    | `ADDH.E D, X, #imm3` | `D = X + (imm3 << 24)`
| 92    | `CMPH X, #imm3`      | `fl = iflags(X - (imm3 << 24))`
| 93    | `CMPHU X, #imm3`     | `fl = uflags(X - (imm3 << 24))`
| 94    | `SHLH D, X, #umm3`   | `D = X << umm3`
| 95    | `SHLH.E D, X, #umm3` | `D = X << umm3`
| 96    | `SHRH D, X, #umm3`   | `D = (X as i56) >> umm3` (arithmetic)
| 97    | `SHRH.E D, X, #umm3` | `D = (X as u48) >> umm3` (logic)
| 98    | `ANDH D, X, #imm3`   | `D = X & (imm3 << 24)`
| 99    | `ORH D, X, #imm3`    | `D = X \| (imm3 << 24)`
| 9A    | `XORH D, X, #imm3`   | `D = X ^ (imm3 << 24)`
| 9B    | `MOVH D, #imm6`      | `D = (imm6 << 24)`

### Two-register

| Major | Mnemonic | Operation
|-------|----------|----------|
| A0    | `ADD D, X, Y`   | `D = X + Y`
| A1    | `ADD.E D, X, Y` | `D = X + Y`
| A2    | `CMP X, Y`      | `fl = iflags(X - Y)`
| A3    | `CMPU X, Y`     | `fl = uflags(X - Y)`
| A4    | `SHL D, X, Y`   | `D = X << (Y.hi & 63)`
| A5    | `SHL.E D, X, Y` | `D = X << (Y.hi & 63)`
| A6    | `SHR D, X, Y`   | `D = (X as i56) >> (Y.hi & 63)` (arithmetic)
| A7    | `SHR.E D, X, Y` | `D = (X as u48) >> (Y.hi & 63)` (logic)
| A8    | `AND D, X, Y`   | `D = X & (imm3 << 24)`
| A9    | `OR D, X, Y`    | `D = X \| (imm3 << 24)`
| AA    | `XOR D, X, Y`   | `D = X ^ (imm3 << 24)`
| AB    | `MOV D, Y`      | `D = Y`
| AE    | `HADD D, X, Y`  | `D = (X + Y) >> 1` (average of X, Y)
| AF    | `HSUB D, X, Y`  | `D = (X - Y) >> 1`
| B0    | `SUB D, X, Y`   | `D = X - Y`
| B1    | `SUB.E D, X, Y` | `D = X - Y`
| B2    | `MAX D, X, Y`   | `D = max(X, Y)`
| B3    | `MIN D, X, Y`   | `D = min(X, Y)`
| B4    | `DIVS D, X, Y`  | non-restoring divide step
| B5    | `NOP`           | nop operation
| B8    | `NEG, D, Y`     | `D = -Y`
| B9    | `NORM, D, Y`    | [see below](#norm-instruction)
| BA    | `ABS, D, Y`     | `D = \|Y\|`

// TODO: Conditional operations

#### `NORM` instruction

This instruction counts the leading zeros/ones - 9.  
The sign bit (bit 55) determines whether leading zeros or ones are counted.  
This is presumably used to normalize Q23 numbers.  
For 48-bit numbers think of it as "how much do I have to shift Y left until bit 47 and 46 differ".  
It is similar to the PDMSB instruction from SH4DSP

The result is -8..47

- `Y < 0`: `D = 47 - bitlen(~Y)`
- `Y = 0`: `D = 0`
- `Y > 0`: `D = 47 - bitlen(Y)`

If your input fits in 48 bits, you can simply use the result as an input into SHL.  
If it doesn't fit (overflows into a.ex), the result can be negative and SHL alone would be wrong.
