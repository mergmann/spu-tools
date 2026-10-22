# SPU Tools

# Prerequisites

- Python 3.14 with pyusb
- A CP-400, CG-50 or 90+E calculator
- A dev build of PythonExtra on the calculator  
  - For the CP-400, you can grab one [here](https://github.com/TheRainbowPhoenix/PythonExtra/actions)
  - For the CG-50 or 90+E there's no pipeline, you have to build it yourself
- `server.py` on the calculator
- (Linux) A udev rule to access the calculator (USB `07cf:6102`) from your user


# Demo

0. Make sure the [prerequisites](#prerequisites) are met
0. Assemble the DSP programs:
    - CP-400: `python assembler.py programs/rend400.spu`
    - CG-50/90+E: `python assembler.py programs/rend50.spu`
0. Run the demo:
    - CP-400: `python run_demo.py programs/out/rend400.bin data/points.csv`
    - CG-50/90+E: `python run_demo.py programs/out/rend50.bin data/points.csv`
0. The calculator should show the rendered points on screen
0. To stop `server.py` on the calculator, run `python run_demo.py --stop`
0. You can change the model (`points.csv`) and view matrix (in `run_demo.py`)
    - Make sure the model points are in the range -2..2 or change the `SCALE` constant
    - Matrix parameters are -1..1, Z translation must be -0.5..0.5


# Assembler

Run the assembler with `python assembler/main.py <input file> [output file]`.  
It shows an error where the syntax is incorrect.  
Currently it doesn't show an error/warning for non-syntax errors like pipeline conflicts.


# USB interface

The USB interface consists of the device-side `server.py` and PC-side `usbclient.py`.  
It can be used to easily access memory and run python scripts on the calculator, without
recompiling or copying over files!  
Make sure you know what you're doing with raw memory access, you can easily crash the device.  
For example accessing SPU registers as 1, or 2 byte units instead of 4 will freeze the calculator.

There is also a wrapper for drawing things on screen using `draw.py`.
It batches up draw commands and sends them to the device at once.

And `spu.py` for more easy access to the DSP cores.

Modify `run_demo.py` to try out things yourself
