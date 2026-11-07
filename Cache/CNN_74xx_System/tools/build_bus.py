"""Build S11_BusFabric.kicad_sch (shared engine <-> memory bus fabric).

The fabric connects the three compute engines to the single S02 timing
controller and the S04 memory array:

  * 74HC148 master encoder: C1/C2/FC busy -> MASTER[1:0]
  * 74HC148 region encoders: engine Cx_MEM_nCE_IN..MC -> REGION[2:0]
  * 74HC157 region mux: selects the active engine's region code
  * 27C512 map ROM: {FC_SEL, MASTER, REGION, 0} -> MEM_SEL[4:0]
  * 74HCT541 tag buffer: MEM_SEL -> ADDR[23:16] = {000, MEM_SEL}
  * 74HCT541 MEM_SEL buffer: map ROM -> shared MEM_SEL[4:0]
  * 74HC32/74HC08: REQ/WE merge for S02
  * MEM_ACK/MEM_DONE/MEM_BUSY remain global labels consumed by S07-S09.

The host owns the buses while LOAD_EN=1; the fabric output buffers use
active-low OE=LOAD_EN, enabled during inference (LOAD_EN=0), exactly
complementary to the S10 load buffers (OE=NOT_LOAD_EN).

Run from the tools directory:
    python build_bus.py
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

REGION_SUFFIX = ("IN", "W", "OUT", "B", "Q", "MC")

GLOBAL = {
    "LOAD_EN", "REQ", "WE",
    "MEM_ACK", "MEM_DONE", "MEM_BUSY",
    "MEM_SEL0", "MEM_SEL1", "MEM_SEL2", "MEM_SEL3", "MEM_SEL4",
    "ADDR16", "ADDR17", "ADDR18", "ADDR19",
    "ADDR20", "ADDR21", "ADDR22", "ADDR23",
    "FC_SEL",
    "C1_BUSY_N", "C2_BUSY_N", "FC_BUSY_N", "ARGMAX_BUSY_N",
    "SCORE_RD",
    "C1_MEM_REQ", "C1_MEM_WE", "C2_MEM_REQ", "C2_MEM_WE",
    "FC_MEM_REQ", "FC_MEM_WE",
    "POOL_SEL", "POOL_BUSY", "POOL_BUSY_N",
    "POOL_MEM_REQ", "POOL_MEM_WE", "POOL_MEM_nCE_IN", "POOL_MEM_nCE_OUT",
}
for _eng in ("C1", "C2", "FC"):
    for _r in REGION_SUFFIX:
        GLOBAL.add(f"{_eng}_MEM_nCE_{_r}")


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
    """Connect every visible pin; nmap is keyed by pin number or pin name."""
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
    title="S11_BusFabric - Engine/Memory Bus Fabric", paper="A1",
)
sh.add_text("S11  BUS FABRIC (MASTER / REGION ENCODE, MAP ROM, TAG + MEM_SEL)",
            20, 16, size=3.0, justify="left top", bold=True)
sh.add_text(
    "MASTER = {C1,C2,FC} busy priority (74HC148); REGION = active engine's "
    "Cx_MEM_nCE_IN/W/OUT/B/Q/MC one-hot code (74HC148 per engine).\n"
    "27C512 map ROM address A[6:0] = {FC_SEL, MASTER[1:0], REGION[2:0], 0}; "
    "D[4:0] = MEM_SEL[4:0]; unused addresses = 0x1F (no device).\n"
    "Fabric outputs are enabled by active-low LOAD_EN (LOAD_EN=0, inference); "
    "S10 owns MEM_SEL/ADDR while LOAD_EN=1.",
    20, 23, size=1.5, justify="left top",
)

# ---------------------------------------------------------------------------
# Master encoder (74HC148): priority C1 > C2 > FC
# ---------------------------------------------------------------------------
U1 = add(sh, "74xx:74LS148", "U1", 90, 75, value="74HC148",
        footprint="Package_DIP:DIP-16_W7.62mm")
connect(sh, U1, {
    "EI": "GND",
    "I7": "+5V", "I6": "C1_BUSY_N", "I5": "C2_BUSY_N", "I4": "FC_BUSY_N",
    "I3": "ARGMAX_BUSY_N", "I2": "POOL_BUSY_N", "I1": "+5V", "I0": "+5V",
    "S2": "MASTER2", "S1": "MASTER1", "S0": "MASTER0",
    "GS": "NC", "EO": "NC",
})

# ---------------------------------------------------------------------------
# Region encoders: one 74HC148 per engine.  The engine 74HC138 is qualified by
# the shared MEM_nCE, so at most one region input is low during a transaction;
# no memory operation reads as REGION=7.
# ---------------------------------------------------------------------------
REGION_ENC = [
    ("U2", "C1", 90, 165),
    ("U3", "C2", 90, 255),
    ("U4", "FC", 90, 345),
]
for ref, eng, x, y in REGION_ENC:
    u = add(sh, "74xx:74LS148", ref, x, y, value="74HC148",
            footprint="Package_DIP:DIP-16_W7.62mm")
    m = {
        "EI": "GND",
        "I7": f"{eng}_MEM_nCE_IN", "I6": f"{eng}_MEM_nCE_W",
        "I5": f"{eng}_MEM_nCE_OUT", "I4": f"{eng}_MEM_nCE_B",
        "I3": f"{eng}_MEM_nCE_Q", "I2": f"{eng}_MEM_nCE_MC",
        "I1": "+5V", "I0": "+5V",
        "S2": f"{eng}_REG2", "S1": f"{eng}_REG1", "S0": f"{eng}_REG0",
        "GS": "NC", "EO": "NC",
    }
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# Region mux (2x 74HC157): C1 > C2 > FC, same priority as the master encoder.
#   stage 1: S = C1_BUSY_N -> selects C1 when low, C2 otherwise
#   stage 2: S = ANY_CONV_N (C1_BUSY_N & C2_BUSY_N) -> conv region when low,
#            FC region otherwise (FC idle gives REGION=7).
# ---------------------------------------------------------------------------
U6 = add(sh, "74xx:74HC157", "U6", 430, 70, value="74HC157")
connect(sh, U6, {
    "S": "C1_BUSY_N", "E": "GND",
    "I0a": "C1_REG0", "I1a": "C2_REG0", "Za": "RMUX0",
    "I0b": "C1_REG1", "I1b": "C2_REG1", "Zb": "RMUX1",
    "I0c": "C1_REG2", "I1c": "C2_REG2", "Zc": "RMUX2",
    "I0d": "GND", "I1d": "GND", "Zd": "NC",
})
U7 = add(sh, "74xx:74HC157", "U7", 430, 150, value="74HC157")
connect(sh, U7, {
    "S": "ANY_CONV_N", "E": "GND",
    "I0a": "RMUX0", "I1a": "FC_REG0", "Za": "REGION_PRE0",
    "I0b": "RMUX1", "I1b": "FC_REG1", "Zb": "REGION_PRE1",
    "I0c": "RMUX2", "I1c": "FC_REG2", "Zc": "REGION_PRE2",
    "I0d": "GND", "I1d": "GND", "Zd": "NC",
})
U13 = add(sh, "74xx:74HC157", "U13", 700, 230, value="74HC157")
connect(sh, U13, {
    "S": "POOL_BUSY", "E": "GND",
    "I0a": "REGION_PRE0", "I1a": "GND", "Za": "REGION0",
    "I0b": "REGION_PRE1", "I1b": "POOL_MEM_nCE_IN", "Zb": "REGION1",
    "I0c": "REGION_PRE2", "I1c": "GND", "Zc": "REGION2",
    "I0d": "GND", "I1d": "GND", "Zd": "NC",
})

# ---------------------------------------------------------------------------
# Map ROM 27C512: address {FC_SEL, MASTER1, MASTER0, REGION2..0, 0}
# ---------------------------------------------------------------------------
U5 = add(sh, "Memory_EPROM:27C512", "U5", 250, 105, value="27C512",
        footprint="Package_DIP:DIP-28_W15.24mm")
m = {"~{CE}": "GND", "~{OE}": "GND",
     "A0": "GND", "A1": "REGION0", "A2": "REGION1", "A3": "REGION2",
     "A4": "MASTER0", "A5": "MASTER1", "A6": "FC_SEL", "A7": "MASTER2",
     "A8": "POOL_SEL"}
for i in range(9, 16):
    m[f"A{i}"] = "GND"
for i in range(5):
    m[f"D{i}"] = f"MAP_SEL{i}"
for i in range(5, 8):
    m[f"D{i}"] = "NC"
connect(sh, U5, m)

# ---------------------------------------------------------------------------
# Address tag buffer: ADDR[23:16] = {000, MEM_SEL[4:0]}
# OE is active-low LOAD_EN: enabled while LOAD_EN=0 (inference), disabled while
# the S10 host buffers (OE = NOT_LOAD_EN = ~LOAD_EN) own the bus.
# ---------------------------------------------------------------------------
U8 = add(sh, "74xx:74HCT541", "U8", 590, 70, value="74HCT541")
m = {"G1": "LOAD_EN", "G2": "LOAD_EN"}
for i in range(5):
    m[f"A{i}"] = f"MAP_SEL{i}"
    m[f"Y{i}"] = f"ADDR{16 + i}"
for i in range(5, 8):
    m[f"A{i}"] = "GND"
    m[f"Y{i}"] = f"ADDR{16 + i}"
connect(sh, U8, m)

# ---------------------------------------------------------------------------
# MEM_SEL output buffer (engine mode only, OE = active-low LOAD_EN)
# ---------------------------------------------------------------------------
U9 = add(sh, "74xx:74HCT541", "U9", 590, 160, value="74HCT541")
m = {"G1": "LOAD_EN", "G2": "LOAD_EN"}
for i in range(5):
    m[f"A{i}"] = f"MAP_SEL{i}"
    m[f"Y{i}"] = f"MEM_SEL{i}"
for i in range(5, 8):
    m[f"A{i}"] = "GND"
    m[f"Y{i}"] = "NC"
connect(sh, U9, m)

# ---------------------------------------------------------------------------
# REQ/WE merge: S01 only runs one engine at a time, so a combinational merge
# is sufficient (no latch / arbiter).
# ---------------------------------------------------------------------------
U10 = add(sh, "74xx:74HC32", "U10", 430, 240, unit=1, value="74HC32")
connect(sh, U10, {"1": "C1_MEM_REQ", "2": "C2_MEM_REQ", "3": "REQ_A"})
U10b = add(sh, "74xx:74HC32", "U10", 480, 240, unit=2)
connect(sh, U10b, {"4": "FC_MEM_REQ", "5": "SCORE_RD", "6": "REQ_B"})
U12 = add(sh, "74xx:74HC32", "U12", 530, 240, unit=1, value="74HC32")
connect(sh, U12, {"1": "GND", "2": "GND", "3": "NC"})
U12b = add(sh, "74xx:74HC32", "U12", 530, 285, unit=2, value="74HC32")
connect(sh, U12b, {"4": "REQ_B", "5": "POOL_MEM_REQ", "6": "REQ_C"})
U12c = add(sh, "74xx:74HC32", "U12", 580, 285, unit=3, value="74HC32")
connect(sh, U12c, {"9": "REQ_A", "10": "REQ_C", "8": "REQ"})
U12d = add(sh, "74xx:74HC32", "U12", 630, 285, unit=4, value="74HC32")
connect(sh, U12d, {"12": "WE3", "13": "WE4", "11": "WE34"})
U12p = add(sh, "74xx:74HC32", "U12", 580, 240, unit=5, value="74HC32")
connect(sh, U12p, {"7": "GND", "14": "+5V"})
U10c = add(sh, "74xx:74HC32", "U10", 430, 285, unit=3)
connect(sh, U10c, {"9": "WE1", "10": "WE2", "8": "WE12"})
U10d = add(sh, "74xx:74HC32", "U10", 480, 285, unit=4)
connect(sh, U10d, {"12": "WE12", "13": "WE34", "11": "WE"})
U10p = add(sh, "74xx:74HC32", "U10", 530, 240, unit=5)
connect(sh, U10p, {"7": "GND", "14": "+5V"})

U11 = add(sh, "74xx:74HC08", "U11", 430, 335, unit=1, value="74HC08")
connect(sh, U11, {"1": "C1_MEM_REQ", "2": "C1_MEM_WE", "3": "WE1"})
U11b = add(sh, "74xx:74HC08", "U11", 480, 335, unit=2)
connect(sh, U11b, {"4": "C2_MEM_REQ", "5": "C2_MEM_WE", "6": "WE2"})
U11c = add(sh, "74xx:74HC08", "U11", 430, 380, unit=3)
connect(sh, U11c, {"9": "FC_MEM_REQ", "10": "FC_MEM_WE", "8": "WE3"})
U11d = add(sh, "74xx:74HC08", "U11", 480, 380, unit=4)
connect(sh, U11d, {"12": "C1_BUSY_N", "13": "C2_BUSY_N", "11": "ANY_CONV_N"})
U11p = add(sh, "74xx:74HC08", "U11", 530, 335, unit=5)
connect(sh, U11p, {"7": "GND", "14": "+5V"})

U14 = add(sh, "74xx:74HC08", "U14", 580, 335, unit=1, value="74HC08")
connect(sh, U14, {"1": "POOL_MEM_REQ", "2": "POOL_MEM_WE", "3": "WE4"})
U14p = add(sh, "74xx:74HC08", "U14", 630, 335, unit=5)
connect(sh, U14p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Handshake visibility: MEM_ACK/DONE/BUSY are global labels; S07-S09 consume
# them directly.  These test points keep the handshake visible on S11.
# ---------------------------------------------------------------------------
for i, net in enumerate(("MEM_ACK", "MEM_DONE", "MEM_BUSY")):
    tp = add(sh, "Connector:TestPoint", f"TP{i+1}", 720, 300 + i * 30, value="TP")
    gx, gy = tp.pins["1"]
    sh.add_wire(gx, gy, gx, gy + 5.08)
    sh.add_wire(gx, gy + 5.08, gx + 12.7, gy + 5.08)
    sh.add_global_label(net, gx + 12.7, gy + 5.08, 0)

# ---------------------------------------------------------------------------
# Decoupling and power flags (flags removed by strip_pwr_flags.py)
# ---------------------------------------------------------------------------
for i in range(14):
    x = 60 + (i % 6) * 45
    y = 500 + (i // 6) * 30
    cap = add(sh, "Device:C", f"C{i+1}", x, y, value="100n")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

for i, (net, x) in enumerate((("+5V", 760), ("GND", 800))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, 500, value=net)
    sh.add_wire(x, 500, x + 5.08, 500)
    sh.add_power(net, x + 5.08, 500, pwr_ref())

# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
sh.add_text(
    "Master code: 0=none/host, 1=C1, 2=C2, 3=FC, 4=ARGMAX.  Region code: 0=IN, 1=W, 2=OUT, "
    "3=B, 4=Q, 5=MC, 7=none.\n"
    "The three 74HC148 region encoders are mutually exclusive in time; U6/U7 "
    "select the active engine's code with the same C1>C2>FC priority as U1.\n"
    "Map ROM contents: model/busmap/bus_map.bin (tools/gen_bus_map.py).",
    600, 400, size=1.2, justify="left top",
)
sh.add_text(
    "REQ = C1_REQ | C2_REQ | FC_REQ | SCORE_RD.  "
    "WE = (C1_REQ & C1_WE) | (C2_REQ & C2_WE) | (FC_REQ & FC_WE).\n"
    "S02 nCE/nOE/nWE drive S04 directly; MEM_ACK/DONE/BUSY fan out to all "
    "three engines as global labels.\n"
    "Tag buffer drives ADDR[23:16]={000,MEM_SEL}; MEM_SEL and tag buffers use "
    "active-low OE=LOAD_EN, complementary to the S10 load buffers (OE=NOT_LOAD_EN).",
    600, 430, size=1.2, justify="left top",
)

out = os.path.join(PROJECT_DIR, "S11_BusFabric.kicad_sch")
sh.write(out)
print("wrote", out)
