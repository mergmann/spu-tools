# Registers

## Overview

The DSP has 64 register slots, but only 49 physical registers.
Some accesses read these registers differently.  
Signed registers sign-extend when loaded

| ID       | Name         | Size | Usage
|----------|--------------|------|------
| x0..x3   | a0..a3       | 56s  | 56-bit Accumulator
| x4..x7   | r0..r3       | 24s  | 24-bit Data
| x8..x15  | p0..p7       | 16u  | X-bus pointer
| x16..x23 | po0..po7     | 16s  | Increment for p0..p7
| x24..x27 | b0..b3       | 16u  | Y-bus bointer
| x28..x31 | bo0..bo3     | 16s  | Increment for b0..b3
| x32..x39 | pm0..pm7     | 15u  | Increment mode for p0..p7
| x40..x43 | bm0..bm3     | 15u  | Increment mode for b0..b3
| x44..x47 | sp           | 16u  | Stack pointer (same physical register)
| x48      | lr           | 16u  | Call return PC
| x49      | li           | 16u  | Interrupt return PC
| x50      | fl           | 16u  | status / flags
| x51      | fi           | 16u  | Interrupt return status / flags
| x52..x55 | a0.lo..a3.lo | 8s   | Lower 24 bits of a0..a3
| x56..x59 | a0.hi..a3.hi | 8s   | Middle 24 (data) bits of a0..a3
| x60..x63 | a0.ex..a3.ex | 8s   | Upper 8 (guard) bits of a0..a3


## Accumulator (a0..a3)

The 4 56-bit accumulators are mainly used for ALU operations.

The most important part is the middle (a.hi):  
Writing to accumulator into its a0..a3 alias writes the value to a.hi,  
sign extends into the extension (a.ex) and clears the lower part (a.lo).  
Reading from an accumulator from its a0..a3 alias behaves differently based
on the flag register (see below).


## Data register (r0..r3)

The 4 24-bit data registers can be used for ALU operations and as multiply inputs


## Flag / Status register (fl)

| Bit  | Name | Usage
|------|------|------
| 1..0 | R    | Rounding mode for a0..a3
| 2    | IE   | Enables interrutps
| 3    | C    | Carry
| 4    | N    | Negative/sign
| 5    | Z    | Zero
| 6    | V    | oVerflow
| 

| Value | Effect
|-------|-------
| 00    | Truncate
| 01    | 
