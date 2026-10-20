# Instruction groups

```
|31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0|
|-----------------------------------------------------------------------------------------------|
| 0  0  0|                                          --                                          | unused
|-----------------------------------------------------------------------------------------------|
| 0  0  1  0|                count              |                     addr                      | REP
|-----------------------------------------------------------------------------------------------|
| 0  0  1  1  0  0|      reg6       |                           imm20                           | LDI
| 0  0  1  1  0  1| spa |         imm8          |                     addr                      | STI
|-----------------------------------------------------------------------------------------------|
| 0  0  1  1  1  0  0  0|Y |       reg       |st|                     addr                      | MEM X/Y
| 0  0  1  1  1  0  0  1|IO|    ---    | rg2 |st|                     addr                      | MEM L/IO
| 0  0  1  1  1  0  1  0  0|       reg       |st|                    offset                     | MEM S
| 0  0  1  1  1  0  1  0  1  0|   k    |   j    |                    imm16                      | LEA
| 0  0  1  1  1  0  1  0  1  1|  k  |                           imm20                           | LDAL
|-----------------------------------------------------------------------------------------------|
| 0  0  1  1  1  0  1  1|C | typ | --- |  cond  |                     addr                      | JUMP
| 0  0  1  1  1  1 |----|                              control                                  | CTL
|-----------------------------------------------------------------------------------------------|
| 0  1|                   move 2                   |                    move                    | DUAL
|-----------------------------------------------------------------------------------------------|
| 1  0  0  0|   type    |  dst   |   op   |  imm3  |                    move                    | ALU-L
| 1  0  0  1|   type    |  dst   |   op   |  imm3  |                    move                    | ALU-H
| 1  0  1|     type     |  dst   |  op1   |  op2   |                    move                    | ALU-R
|-----------------------------------------------------------------------------------------------|
| 11  | cls |                 mac                  |                    move                    | MAC
|-----------------------------------------------------------------------------------------------|
|31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0|
```

### Hardware repeat
`REP #count, $last`  
Repeats the block after its 2 delay slots until `end` (inclusive), `count` times:
```
$0100 REP #16, $0104
$0101   ... (delay slot)
$0102   ... (delay slot)
$0103   ... (repeated)
$0104   ... (repeated)
$0105   ... (not repeated)
```


### Load immediate
`LDI xN, #imm`
Loads an immediate (sign extended) into any of the 64 register accesses


### Store immediate
`STI X/Y/L/IO[$addr], #imm`  
Stores an immdiate (sign extended) onto the X-bus, Y-bus, IO-bus or stores using long access


### X/Y memory access
`LD xN, X/Y[$addr]`, `ST X/Y[$addr], xN`  
Loads or stores a register from X or Y memory


### L/IO memory access
`LD xN, L/IO[$addr]`, `ST L/IO[$addr], xN`  
Loads or stores a register from IO memory or uses stores using long access


### Load effective address
`LEA pK, pJ + #imm`
Offsets a pointer by a signed immediate


### Load accumulator lower
`LDAL aK, #imm`  
Loads the immediate into a.lo and sign-extends into a.hi, a.ex.  
This is different from LDI in that LDI loads into a.hi.


### Jumps
see [Jumps](jumps.md)


### Control
see [Control](control.md)


### Dual
`DUAL <move> || <move>`  
Performs two [moves](move.md) in one instruction. This uses 2 cycles!
The left move is executed first. The assembler puts the left one in the lower
part of the instruction! This is contrary to other instructions with a parallel move.
But DUAL is special in that it takes 2 cycles, so they run sequentially.  
I don't know what's the use case over 2 seperate `NOP || <move>`, I guess instruction density?  
Apart from being only one instruction it behaves the same as those.


### Arimthetic and logic ops
see [ALU](alu.md)

### Multiply and accumulate
see [MAC](mac.md), see [move field](move.md)


# Pipeline

### Moves
MAC/ALU instructions come with an additional move field that executes in parallel (in the same cycle!).  
Both the operation and move field access the same initial state. For example when writing to r1
and using it as an ALU input, the ALU sees r1 as it was before the instruction.

Writing to a register in both the OP and move is UB. Sometimes one wins, sometimes the results get ORed.
An exception to this is [DUAL](#dual), since it uses 2 cycles. You get the previous result clean in the
second move.

