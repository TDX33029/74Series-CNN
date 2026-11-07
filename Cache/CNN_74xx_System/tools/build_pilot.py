"""Build the P0 pilot: one 8x8 LUT multiplier unit and a top-level sheet.

Run from this directory:
    python build_pilot.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import (
    RootSchematic,
    Schematic,
    default_registry,
    footprint_for,
    write_project,
    write_sym_lib_table,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
ROOT_FILE = os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_sch")
SHEET_FILE = os.path.join(PROJECT_DIR, "S_LUT_Mult_1.kicad_sch")

reg = default_registry()

# ---------------------------------------------------------------------------
# Root sheet
# ---------------------------------------------------------------------------
root = RootSchematic(
    reg,
    project=PROJECT,
    instance_path="/__ROOT_UUID__",
    title="CNN 74xx System - Top Level (P0 Pilot)",
    paper="A3",
)
root.add_text(
    "74-Series 28x28 MNIST CNN - Hierarchical Schematic",
    20, 18, size=3.0, justify="left top", bold=True
)
root.add_text(
    "P0 pilot: LUT multiplier unit.  Remaining sheets (supervisor, memories, "
    "timing, CONV1/2, POOL1/2, FC1/2, ARGMAX) are added in P1/P2 after the "
    "architecture contract is approved.",
    20, 27, size=1.6, justify="left top"
)
root.add_sheet("LUT_Mult_1", "S_LUT_Mult_1.kicad_sch", 40, 55, 130, 70, page=2)
root.add_text(
    "Sheet 2: 8x8 LUT multiplier unit\n"
    "2x 27C512 (64Kx8) + 4x 74HCT574\n"
    "LUT_ADDR = {A[7:0], B[7:0]}\n"
    "ROM_LO = (A*B)[7:0], ROM_HI = (A*B)[15:8]",
    40, 132, size=1.4, justify="left top"
)
root.add_text(
    "Global net contract: CLK is the only system clock; LUT control is "
    "active-low where named *_N; all data nets are uint8 unless noted.",
    40, 190, size=1.3, justify="left top"
)
root.write(ROOT_FILE)

# ---------------------------------------------------------------------------
# LUT multiplier unit sheet
# ---------------------------------------------------------------------------
sh = Schematic(
    reg,
    project=PROJECT,
    instance_path="/__ROOT_UUID__/__SHEET_UUID__",
    title="S_LUT_Mult_1 - 8x8 LUT Multiplier Unit",
    paper="A3",
)

sh.add_text(
    "8x8 LUT Multiplier Unit (one of four engine-local units)",
    18, 16, size=2.4, justify="left top", bold=True
)
sh.add_text(
    "Two 27C512 ROMs share the latched 16-bit address {A[7:0],B[7:0]}. "
    "Low ROM returns product[7:0]; high ROM returns product[15:8]. "
    "74HCT574 captures the addresses and the 16-bit product.",
    18, 22, size=1.35, justify="left top"
)

# --- symbols --------------------------------------------------------------
u1 = sh.add_symbol(
    "Memory_EPROM:27C512", "U1", "27C512", 160.02, 100.33,
    footprint=footprint_for("Memory_EPROM:27C512"),
    description="LUT ROM low byte (A*B)[7:0]",
)
u2 = sh.add_symbol(
    "Memory_EPROM:27C512", "U2", "27C512", 160.02, 180.34,
    footprint=footprint_for("Memory_EPROM:27C512"),
    description="LUT ROM high byte (A*B)[15:8]",
)
u3 = sh.add_symbol(
    "74xx:74HCT574", "U3", "74HCT574", 50.8, 88.9,
    footprint=footprint_for("74xx:74HCT574"),
    description="A operand latch",
)
u4 = sh.add_symbol(
    "74xx:74HCT574", "U4", "74HCT574", 50.8, 153.67,
    footprint=footprint_for("74xx:74HCT574"),
    description="B operand latch",
)
u5 = sh.add_symbol(
    "74xx:74HCT574", "U5", "74HCT574", 280.67, 92.71,
    footprint=footprint_for("74xx:74HCT574"),
    description="Product low-byte latch",
)
u6 = sh.add_symbol(
    "74xx:74HCT574", "U6", "74HCT574", 280.67, 172.72,
    footprint=footprint_for("74xx:74HCT574"),
    description="Product high-byte latch",
)

# --- power pins -----------------------------------------------------------
pwr_n = 0
def pwr_ref() -> str:
    global pwr_n
    pwr_n += 1
    return f"#PWR{pwr_n:03d}"

for sym in (u1, u2, u3, u4, u5, u6):
    for num, p in sym.pin_objs.items():
        if p.name == "VCC":
            sh.stub_power(sym, num, "+5V", pwr_ref())
        elif p.name == "GND":
            sh.stub_power(sym, num, "GND", pwr_ref())

# --- U1/U2: address, data, control ---------------------------------------
for sym, is_low in ((u1, True), (u2, False)):
    for num, p in sym.pin_objs.items():
        n = p.name
        if n.startswith("A") and n[1:].isdigit():
            sh.stub_label(sym, num, f"LUT_A{int(n[1:])}", local=True)
        elif n.startswith("D") and n[1:].isdigit():
            prefix = "ROM_L" if is_low else "ROM_H"
            sh.stub_label(sym, num, f"{prefix}{int(n[1:])}", local=True)
        elif n == "~{CE}":
            sh.stub_label(sym, num, "LUT_CE_N")
        elif n == "~{OE}":
            sh.stub_label(sym, num, "LUT_OE_N")

# --- U3: A latch ----------------------------------------------------------
def latch_pins(sym, d_prefix, q_prefix, clock, q_offset=0, tie_oe_to_gnd=True, d_shape="bidirectional", d_local=False, q_local=True):
    for num, p in sym.pin_objs.items():
        n = p.name
        if n == "Cp":
            sh.stub_label(sym, num, clock)
        elif n == "OE":
            if tie_oe_to_gnd:
                sh.stub_power(sym, num, "GND", pwr_ref())
            else:
                sh.stub_label(sym, num, "LUT_OE_N")
        elif n.startswith("D") and n[1:].isdigit():
            sh.stub_label(sym, num, f"{d_prefix}{int(n[1:])}", shape=d_shape, local=d_local)
        elif n.startswith("Q") and n[1:].isdigit():
            sh.stub_label(sym, num, f"{q_prefix}{q_offset + int(n[1:])}", local=q_local)

latch_pins(u3, "A", "LUT_A", "LUT_AB_LATCH", q_offset=0, d_shape="output")

# --- U4: B latch (Q0..Q7 drive LUT address A8..A15) ----------------------
latch_pins(u4, "B", "LUT_A", "LUT_AB_LATCH", q_offset=8, d_shape="output")

# --- U5/U6: product latches ---------------------------------------------
latch_pins(u5, "ROM_L", "PROD", "LUT_PROD_LATCH", q_offset=0, d_local=True, q_local=False)
latch_pins(u6, "ROM_H", "PROD", "LUT_PROD_LATCH", q_offset=8, d_local=True, q_local=False)

# --- decoupling bank ------------------------------------------------------
for i in range(6):
    x = 59.69 + i * 24.13
    cap = sh.add_symbol(
        "Device:C", f"C{i+1}", "100nF", x, 245.11,
        footprint=footprint_for("Device:C"),
        description="Decoupling capacitor",
    )
    # C pin 1 is the top pin, pin 2 the bottom pin.
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# --- test points for control nets ---------------------------------------
for i, net in enumerate(("LUT_AB_LATCH", "LUT_PROD_LATCH", "LUT_CE_N", "LUT_OE_N")):
    tp = sh.add_symbol(
        "Connector:TestPoint", f"TP{i+1}", "TP", 340.36, 55.88 + i * 17.78,
        footprint="TestPoint:TestPoint_Pad_D1.5mm",
        description=f"Test point {net}",
    )
    # TestPoint pin points down (rot 90): the stub and label go below it.
    gx, gy = tp.pins["1"]
    sh.add_wire(gx, gy, gx, gy + 5.08)
    sh.add_wire(gx, gy + 5.08, gx + 12.7, gy + 5.08)
    sh.add_global_label(net, gx + 12.7, gy + 5.08, 0)

# --- power flags (ERC: declare +5V/GND as driven) ------------------------
for i, (net, x) in enumerate((("+5V", 330.2), ("GND", 350.52))):
    flag = sh.add_symbol(
        "power:PWR_FLAG", f"FLG{i+1}", net, x, 245.11,
        footprint="", description=f"Power flag {net}",
    )
    sh.add_wire(x, 245.11, x, 250.19)
    sh.add_power(net, x, 250.19, pwr_ref())

# --- notes ---------------------------------------------------------------

sh.add_text(
    "Address map: LUT_A0..LUT_A7 = latched A[7:0]; LUT_A8..LUT_A15 = latched B[7:0].\n"
    "Data map: ROM_L0..7 -> U5.D, PROD0..7 = U5.Q; ROM_H0..7 -> U6.D, PROD8..15 = U6.Q.\n"
    "Control: LUT_AB_LATCH clocks U3/U4; LUT_PROD_LATCH clocks U5/U6; LUT_CE_N/LUT_OE_N drive both ROMs.",
    18, 215, size=1.3, justify="left top"
)
sh.add_text(
    "Power: +5V +/-5%, one 100nF per IC.  All unused/unconnected pins must be tied or marked NC.\n"
    "This is a pin-level unit schematic; four copies are instantiated in the four compute engines.",
    18, 232, size=1.3, justify="left top"
)

sh.write(SHEET_FILE)

# Patch instance paths now that UUIDs are known.
root_uuid = root.uuid
sheet_uuid = root.subsheets[0]["uuid"]
for path in (ROOT_FILE, SHEET_FILE):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    txt = txt.replace("__ROOT_UUID__", root_uuid).replace("__SHEET_UUID__", sheet_uuid)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)

write_project(os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_pro"), PROJECT)
write_sym_lib_table(os.path.join(PROJECT_DIR, "sym-lib-table"))

print("wrote", ROOT_FILE)
print("wrote", SHEET_FILE)
print("root_uuid", root_uuid, "sheet_uuid", sheet_uuid)
