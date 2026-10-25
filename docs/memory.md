# Memory

## IO-memory

The SPU registers are linearly mapped to the IO-memory.  
- `$FF00` on DSP0 is `FE2FFC00 PBANKC0`
- `$FF40` on DSP0 is `FE2FFD00 DSPRST`  

For DSP1 the global SPU registers are simply mirrored to `FE3...`:
- `$FF00` on DSP1 is `FE3FFC00 PBANKC0`
- `$FF40` on DSP1 is `FE3FFD00 DSPRST`


### Bus through

- `BTADRU`: Upper 16-bit of the target address
- `BTADRL`: Lower 16-bit of the target address
- `WDATU`: Upper 16-bit of the data to write
- `WDATL`: Lower 16-bit of the data to write
- `RDATU`: Upper 16-bit of the read data
- `RDATL`: Lower 16-bit of the read data

| BTCTRL | Name  | Usage |
|--------|-------|-------|
| 13..12 | width | Transfer width, `00`: 32bit, `01`: 16bit, `10`: 8bit
| 4      | write | Set `1` to start write, poll until `0` for completion
| 0      | read  | Set `1` to start read, poll until `0` for completion

The bus-through engine runs asynchronously.

```py
# Split the address into 16-bit
# Note that addr must be the physical address
BTADRU = addr >> 16
BTADRL = addr & 0xFFFF

# Write a 32bit value
WDATU = data >> 16
WDATL = data & 0xFFFF
BTCTRL = 0x0010
# ... Do things asynchronously ...
# Poll completion
while BTCTRL & 0x10: pass

# Write an 8bit value
WDATL = data
BTCTRL = 0x2010
# ... Do things asynchronously ...
while BTCTRL & 0x10: pass

# Read a 16bit value
BTCTRL = 0x1001
# ... Do things asynchronously ...
while BTCTRL & 0x01: pass
data = RDATL
```
