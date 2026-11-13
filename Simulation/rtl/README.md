# 74Series-CNN structural simulation (ModelSim ASE)

This directory rebuilds the 12-board design as a flat, pin-accurate Verilog
netlist and runs a host/board-level testbench against it.

## What is modelled

- every 74xx / memory **package** from `Cache/CNN_74xx_System/output/top.net`
  (897 packages), connected by the exact KiCad symbol pin numbers;
- every signal net (3809 wires), rails as `1'b1` / `1'b0`;
- 10k/100k pulls as `pullup`/`pulldown`, series resistors as `assign`,
  the fitted **JP1 1-2 shunt** as `OSC_OUT -> CLK_SEL`;
- 27C512 images from the project `model/` tree;
- U2001 timing microcode is **reconstructed** (the project has no image for it),
  see `gen_timing_rom.py`.

Passives with no logic role (decoupling caps, LEDs, test points, connectors,
power flags) and the push button are not modelled; the testbench drives
`RESET_RAW`, `START_RAW`, `LOAD_EN` and the host bus directly.

## Run

```bat
cd /d D:\Document\tempPrj\74Series-CNN\Simulation\rtl
run.bat
```

or manually:

```bat
python gen_models.py
python gen_timing_rom.py
python gen_rtl.py
set PATH=C:\intelFPGA\18.0\modelsim_ase\win32aloem;%PATH%
vlib work
vlog -sv models.v cnn74_top.v tb_cnn74.v
vsim -c -voptargs=+acc tb_cnn74 -do "run -all; quit -f"
```

`gen_rtl.py` imports `analysis/build_analysis.py`, which re-parses
`output/top.net` and refreshes `analysis/*.csv|json`; that is expected.

## Static audit

```bat
python audit_structure.py
```

Prints the comparators whose active-low `P=R` output reaches a ROM/mux "last"
input without inversion, the comparators that only see the low 8 bits of a
wider counter, and the host address bits that never reach a connector.
See `../VERIFICATION_REPORT.md` section 8 for the expected output.

## Expected result

The bench passes reset, clock, SRAM/EEPROM load+readback and the READY
handshake. It then runs the supervisor chain. With the current netlist it ends
with `TB RESULT: FAIL` for one reason: **FC2 never returns DONE** (S01 stays in
`FC2_WAIT` until the 300k-cycle timeout). C1/C2/FC1 also finish far too early.
These are real design findings, documented in `../VERIFICATION_REPORT.md`
(V1..V6), not testbench bugs.

## Modelling notes

- 74HCT574 has no async clear; its model starts at 0 so the supervisor ROM
  address is defined before the first stage writes the register. Real devices
  power up unknown.
- ROM/SRAM address bits that are X are read as 0 (X-optimistic decode). Real
  hardware has a definite level; this only prevents a 4-state X-lock between
  DONE flags and the fully-decoded microcode ROMs.
- Unconnected model ports produce ModelSim warnings 3017/3722. They were
  audited: they are unused gate outputs/inputs of spare units.

## Parallel regression (one vector per core, ~4.5 min for 8 vectors)

    bash run_par.sh          # 8 vsim processes: +nvec=1 +vfirst=K each
    python compare_par.py    # bitwise layer compare vs weights/x28s/vectors

Requires tb_numeric plus-args +vfirst=K (vector index) and +wbase=S
(absolute weights prefix); both default to the old single-process behavior.
