# Memory

## IO-memory

The SPU registers are linearly mapped to the IO-memory.  
- `$FF00` on DSP0 is `FE2FFC00 PBANKC0`
- `$FF40` on DSP0 is `FE2FFD00 DSPRST`  

For DSP1 the global SPU registers are simply mirrored to `FE3...`:
- `$FF00` on DSP1 is `FE3FFC00 PBANKC0`
- `$FF40` on DSP1 is `FE3FFD00 DSPRST`
