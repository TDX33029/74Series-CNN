"""Build S12_DataAssembly.kicad_sch.

S12 is the byte-width bridge between the shared 8-bit DATA bus and the two
consumers that need wider or registered inputs:

  * Pool (S05) reads one byte per access.  A 74HCT541 is used as the input
    isolation buffer: DATA[7:0] -> IN_DATA[7:0], always enabled.
  * Argmax (S06) consumes a 32-bit little-endian score word.  Four 74HCT574
    latches assemble the four byte lanes.  A 74HC238 decodes SCORE_ADDR[1:0]
    into the four latch clocks, qualified by MEM_ACK.

The latches are a staging register, not a second memory: S04 must present the
selected byte on DATA while the corresponding decoder output is high.  The
address/REQ sequencing of the four byte reads is part of the Argmax/S04
transaction and is intentionally kept outside this data-width sheet.

Run from the tools directory:
    python build_s12.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"

reg = default_registry()

GLOBAL = {
    "DATA0", "DATA1", "DATA2", "DATA3",
    "DATA4", "DATA5", "DATA6", "DATA7",
    "IN_DATA0", "IN_DATA1", "IN_DATA2", "IN_DATA3",
    "IN_DATA4", "IN_DATA5", "IN_DATA6", "IN_DATA7",
    "SCORE_DATA0", "SCORE_DATA1", "SCORE_DATA2", "SCORE_DATA3",
    "SCORE_DATA4", "SCORE_DATA5", "SCORE_DATA6", "SCORE_DATA7",
    "SCORE_DATA8", "SCORE_DATA9", "SCORE_DATA10", "SCORE_DATA11",
    "SCORE_DATA12", "SCORE_DATA13", "SCORE_DATA14", "SCORE_DATA15",
    "SCORE_DATA16", "SCORE_DATA17", "SCORE_DATA18", "SCORE_DATA19",
    "SCORE_DATA20", "SCORE_DATA21", "SCORE_DATA22", "SCORE_DATA23",
    "SCORE_DATA24", "SCORE_DATA25", "SCORE_DATA26", "SCORE_DATA27",
    "SCORE_DATA28", "SCORE_DATA29", "SCORE_DATA30", "SCORE_DATA31",
    "SCORE_ADDR0", "SCORE_ADDR1", "SCORE_RD", "MEM_ACK",
}


def is_global(net: str) -> bool:
    return net in GLOBAL


pwr_n = 0


def pwr_ref() -> str:
    global pwr_n
    pwr_n += 1
    return f"#PWR{pwr_n:03d}"


def add(sh, lib_id, ref, x, y, unit=1, value=None, footprint=None):
    return sh.add_symbol(
        lib_id, ref, value, x, y, unit=unit,
        footprint=footprint if footprint is not None else footprint_for(lib_id),
    )


def connect(sh, sym, nmap):
    for num, p in sym.pin_objs.items():
        net = nmap.get(num, nmap.get(p.name))
        if net is None:
            if p.name in ("VCC", "Vdd"):
                net = "+5V"
            elif p.name == "GND":
                net = "GND"
            elif p.etype == "no_connect":
                continue
            else:
                net = "NC"
        if net == "NC":
            sh.stub_nc(sym, num)
        elif net in ("+5V", "GND"):
            sh.stub_power(sym, num, net, pwr_ref())
        else:
            sh.stub_label(sym, num, net, local=not is_global(net))


sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S12_DataAssembly - Byte-to-Word Data Assembly", paper="A2",
)
sh.add_text("S12  DATA ASSEMBLY (POOL BYTE BUFFER, ARGMAX 32-BIT STAGING LATCH)", 20, 16,
            size=3.0, justify="left top", bold=True)
sh.add_text(
    "Pool: 74HCT541 isolates/redrives the shared DATA[7:0] byte bus as "
    "IN_DATA[7:0]; the pool compares one byte per access.\n"
    "Argmax: four 74HCT574 latches hold bytes 0..3 of a little-endian score "
    "word; 74HC238 decodes SCORE_ADDR[1:0] into the four latch clocks while "
    "MEM_ACK is high (S02 data-valid capture).\n"
    "S12 is a width/staging bridge; S06 generates the byte address and S04/S02 "
    "execute one REQ/ACK transaction per byte.",
    20, 23, size=1.5, justify="left top",
)

# ---------------------------------------------------------------------------
# Pool input buffer: shared DATA -> module-local IN_DATA.
# ---------------------------------------------------------------------------
ic_symbols = []
U1 = add(sh, "74xx:74HCT541", "U1", 95, 85, value="74HCT541")
ic_symbols.append(U1)
m = {"G1": "GND", "G2": "GND"}
for i in range(8):
    m[f"A{i}"] = f"DATA{i}"
    m[f"Y{i}"] = f"IN_DATA{i}"
connect(sh, U1, m)

# ---------------------------------------------------------------------------
# Argmax score staging latches: four byte lanes -> 32-bit SCORE_DATA.
# ---------------------------------------------------------------------------
for k in range(4):
    u = add(sh, "74xx:74HCT574", f"U{2 + k}", 90 + k * 80, 145, value="74HCT574")
    ic_symbols.append(u)
    m = {"OE": "GND", "Cp": f"SCORE_L{k}"}
    for j in range(8):
        m[f"D{j}"] = f"DATA{j}"
        m[f"Q{j}"] = f"SCORE_DATA{8 * k + j}"
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# Byte-lane address decode: SCORE_ADDR[1:0] -> one of four latch clocks,
# qualified by MEM_ACK (active high).  Y4..Y7 are unused.
# ---------------------------------------------------------------------------
U6 = add(sh, "74xx:74HC238", "U6", 430, 85, value="74HC238")
ic_symbols.append(U6)
m = {
    "A0": "SCORE_ADDR0", "A1": "SCORE_ADDR1", "A2": "GND",
    "~{E1}": "GND", "~{E2}": "GND", "E3": "MEM_ACK",
}
for k in range(4):
    m[f"Y{k}"] = f"SCORE_L{k}"
for k in range(4, 8):
    m[f"Y{k}"] = "NC"
connect(sh, U6, m)

# Test points keep the four lane clocks visible on the sheet.
for k in range(4):
    tp = add(sh, "Connector:TestPoint", f"TP{k + 1}", 90 + k * 80, 195,
             value=f"SCORE_L{k}")
    sh.stub_label(tp, "1", f"SCORE_L{k}", local=True)

# ---------------------------------------------------------------------------
# Decoupling: one 100 nF per IC package.
# ---------------------------------------------------------------------------
for i, _ref in enumerate(sorted({u.ref for u in ic_symbols}, key=lambda r: int(r[1:]))):
    x = 40 + (i % 8) * 45
    y = 240 + (i // 8) * 27
    cap = add(sh, "Device:C", f"C{i + 1}", x, y, value="100nF")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# Power flags are supplied by the root sheet; no PWR_FLAG here.
# SUPERSEDED by build_s12_split.py in the 12-board (Option A) partition.  The
# combined sheet is kept under legacy/ for provenance only; it is not part of
# the hierarchy anymore.
LEGACY_DIR = os.path.join(PROJECT_DIR, "legacy")
os.makedirs(LEGACY_DIR, exist_ok=True)
sh.write(os.path.join(LEGACY_DIR, "S12_DataAssembly.kicad_sch"))
print("wrote legacy/S12_DataAssembly.kicad_sch (superseded)")
print("IC packages:", len({u.ref for u in ic_symbols}))
