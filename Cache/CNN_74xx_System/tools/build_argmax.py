"""Build S06_Argmax.kicad_sch (10-class signed-32 argmax).

Run from the tools directory:
    python build_argmax.py

Scores are read as four bytes per class on the shared DATA bus; S12
assembles them into SCORE_DATA[31:0].  SCORE_ADDR[5:0] = {class, byte}, so
the byte address is class*4+byte.  Each SCORE_RD is one S02 REQ/ACK read.  Class 0 initializes MAX; classes 1..9 use
a signed 32-bit compare.  Only a strict greater-than updates MAX and INDEX,
therefore ties keep the lower class number.
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
    "CLK", "RESET_N", "ARGMAX_START",
    "SCORE_DATA0", "SCORE_DATA1", "SCORE_DATA2", "SCORE_DATA3",
    "SCORE_DATA4", "SCORE_DATA5", "SCORE_DATA6", "SCORE_DATA7",
    "SCORE_DATA8", "SCORE_DATA9", "SCORE_DATA10", "SCORE_DATA11",
    "SCORE_DATA12", "SCORE_DATA13", "SCORE_DATA14", "SCORE_DATA15",
    "SCORE_DATA16", "SCORE_DATA17", "SCORE_DATA18", "SCORE_DATA19",
    "SCORE_DATA20", "SCORE_DATA21", "SCORE_DATA22", "SCORE_DATA23",
    "SCORE_DATA24", "SCORE_DATA25", "SCORE_DATA26", "SCORE_DATA27",
    "SCORE_DATA28", "SCORE_DATA29", "SCORE_DATA30", "SCORE_DATA31",
    "SCORE_ADDR0", "SCORE_ADDR1", "SCORE_ADDR2", "SCORE_ADDR3",
    "SCORE_ADDR4", "SCORE_ADDR5", "SCORE_RD",
    "RESULT_IN0", "RESULT_IN1", "RESULT_IN2", "RESULT_IN3",
    "ARGMAX_RESULT_VALID", "ARGMAX_BUSY", "ARGMAX_BUSY_N", "ARGMAX_DONE",
    "MEM_ACK", "MEM_DONE",
}


def is_global(net: str) -> bool:
    return net in GLOBAL


pwr_n = 0


def pwr_ref() -> str:
    global pwr_n
    pwr_n += 1
    return f"#PWR{pwr_n:03d}"


def add(sh: Schematic, lib_id: str, ref: str, x: float, y: float,
        unit: int = 1, value=None):
    return sh.add_symbol(
        lib_id, ref, value, x, y, unit=unit, footprint=footprint_for(lib_id)
    )


def connect(sh: Schematic, sym, nmap, local: bool = True) -> None:
    for num, p in sym.pin_objs.items():
        net = nmap.get(num)
        if net is None:
            net = nmap.get(p.name)
        if net is None:
            if p.name == "VCC":
                net = "+5V"
            elif p.name == "GND":
                net = "GND"
            else:
                net = "NC"
        if net == "NC":
            sh.stub_nc(sym, num)
        elif net in ("+5V", "GND"):
            sh.stub_power(sym, num, net, pwr_ref())
        else:
            sh.stub_label(sym, num, net, local=local and not is_global(net))


SD = [f"SCORE_DATA{i}" for i in range(32)]
SC = [f"SCORE{i}" for i in range(32)]
MX = [f"MAX{i}" for i in range(32)]
MD = [f"MAXD{i}" for i in range(32)]
CL = [f"CLASS{i}" for i in range(4)]
RS = [f"RESULT_IN{i}" for i in range(4)]
IX = [f"IDXD{i}" for i in range(4)]

# ---------------------------------------------------------------------------
sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S06_Argmax - 10-class signed-32 Argmax", paper="A1",
)
sh.add_text(
    "S06  ARGMAX: 10 signed-32 scores -> 4-bit class index",
    20, 14, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "Interface: CLK, RESET_N, ARGMAX_START, SCORE_DATA[31:0], SCORE_ADDR[5:0], "
    "SCORE_RD, RESULT[3:0], RESULT_VALID, BUSY, DONE.\n"
    "Each class is four little-endian bytes at SCORE_ADDR = class*4+byte; "
    "MEM_ACK latches the byte lane in S12 and each read is one S02 transaction.  "
    "Class 0 initializes MAX/INDEX; classes 1..9 are compared with a signed "
    "32-bit magnitude comparator.  UPDATE only on strict greater-than: ties "
    "keep the lower class number.  RESULT_VALID is held until the next ARGMAX_START.",
    20, 21, size=1.35, justify="left top",
)

ic_list = []


def ic(*args, **kwargs):
    s = add(sh, *args, **kwargs)
    ic_list.append(s)
    return s


# ---------------------------------------------------------------------------
# 32-bit score registers (4x 74HCT574, 8 bits each).
# ---------------------------------------------------------------------------
for k in range(4):
    u = ic("74xx:74HCT574", f"U{4+k}", 55 + k * 90, 60)
    m = {"OE": "GND", "Cp": "CLK"}
    for j in range(8):
        bit = 8 * k + j
        m[f"D{j}"] = SD[bit]
        m[f"Q{j}"] = SC[bit]
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# 32-bit MAX registers (4x 74HCT574, 8 bits each).
# ---------------------------------------------------------------------------
for k in range(4):
    u = ic("74xx:74HCT574", f"U{8+k}", 430 + k * 90, 60)
    m = {"OE": "GND", "Cp": "CLK"}
    for j in range(8):
        bit = 8 * k + j
        m[f"D{j}"] = MD[bit]
        m[f"Q{j}"] = MX[bit]
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# 32-bit signed magnitude comparator: 8x 74HC85, MSB of both operands
# inverted (two's complement -> offset binary).  Oa>b is strict greater.
# ---------------------------------------------------------------------------
for k in range(8):
    u = ic("74xx:74HC85", f"U{14+k}", 55 + k * 85, 155)
    m = {}
    for j in range(4):
        bit = 4 * k + j
        m[f"A{j}"] = SC[bit]
        m[f"B{j}"] = MX[bit]
    if k == 0:
        m["Ia>b"] = "GND"
        m["Ia=b"] = "+5V"
        m["Ia<b"] = "GND"
    else:
        m["Ia>b"] = f"GT{k-1}"
        m["Ia=b"] = f"EQ{k-1}"
        m["Ia<b"] = f"LT{k-1}"
    if k == 7:
        m["A3"] = "S31_INV"
        m["B3"] = "M31_INV"
        m["Oa>b"] = "GT"
        m["Oa=b"] = "NC"
        m["Oa<b"] = "NC"
    else:
        m["Oa>b"] = f"GT{k}"
        m["Oa=b"] = f"EQ{k}"
        m["Oa<b"] = f"LT{k}"
    m["VCC"] = "+5V"
    m["GND"] = "GND"
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# 32-bit MAX update mux (8x 74HC157, 4 bits each).
# ---------------------------------------------------------------------------
for k in range(8):
    u = ic("74xx:74HC157", f"U{22+k}", 55 + k * 85, 250)
    m = {"S": "UPDATE", "E": "GND", "VCC": "+5V", "GND": "GND"}
    for j, n in enumerate(("a", "b", "c", "d")):
        bit = 4 * k + j
        m[f"I0{n}"] = MX[bit]
        m[f"I1{n}"] = SC[bit]
        m[f"Z{n}"] = MD[bit]
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# Class counter, class==9 comparator, index register/mux.
# ---------------------------------------------------------------------------
U1 = ic("74xx:74HC161", "U1", 55, 345)
connect(sh, U1, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "S_NEXT", "CET": "S_NEXT",
    "Q0": CL[0], "Q1": CL[1], "Q2": CL[2], "Q3": CL[3], "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

U2 = ic("74xx:74HC688", "U2", 145, 345)
connect(sh, U2, {
    "G": "GND", "P=R": "EQ9_N",
    "P0": "+5V", "P1": "GND", "P2": "GND", "P3": "+5V",
    "P4": "GND", "P5": "GND", "P6": "GND", "P7": "GND",
    "R0": CL[0], "R1": CL[1], "R2": CL[2], "R3": CL[3],
    "R4": "GND", "R5": "GND", "R6": "GND", "R7": "GND",
    "VCC": "+5V", "GND": "GND",
})

U12 = ic("74xx:74HCT574", "U12", 250, 345)
connect(sh, U12, {
    "OE": "GND", "Cp": "CLK",
    "D0": IX[0], "D1": IX[1], "D2": IX[2], "D3": IX[3],
    "D4": "GND", "D5": "GND", "D6": "GND", "D7": "GND",
    "Q0": RS[0], "Q1": RS[1], "Q2": RS[2], "Q3": RS[3],
    "Q4": "NC", "Q5": "NC", "Q6": "NC", "Q7": "NC",
    "VCC": "+5V", "GND": "GND",
})

U13 = ic("74xx:74HC157", "U13", 340, 345)
connect(sh, U13, {
    "S": "UPDATE", "E": "GND",
    "I0a": RS[0], "I1a": CL[0], "Za": IX[0],
    "I0b": RS[1], "I1b": CL[1], "Zb": IX[1],
    "I0c": RS[2], "I1c": CL[2], "Zc": IX[2],
    "I0d": RS[3], "I1d": CL[3], "Zd": IX[3],
    "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# FSM: IDLE -> INIT -> {RD -> WT -> BYDONE -> BYNEXT} x4 -> LD0/CMP
#      -> NEXT -> ... -> DONE -> WAIT -> IDLE
# BYDONE waits for S02 DONE; BYNEXT advances the 2-bit byte counter.
# ---------------------------------------------------------------------------
U30 = ic("74xx:74HCT273", "U30", 430, 345)
connect(sh, U30, {
    "~{Mr}": "RESET_N", "Cp": "CLK",
    "D0": "D_INIT", "D1": "D_RD", "D2": "D_WT", "D3": "D_LD0",
    "D4": "D_NEXT", "D5": "D_CMP", "D6": "GND", "D7": "GND",
    "Q0": "S_INIT", "Q1": "S_RD", "Q2": "S_WT", "Q3": "S_LD0",
    "Q4": "S_NEXT", "Q5": "S_CMP", "Q6": "NC", "Q7": "NC",
    "VCC": "+5V", "GND": "GND",
})

U31 = ic("74xx:74HCT273", "U31", 520, 345)
connect(sh, U31, {
    "~{Mr}": "RESET_N", "Cp": "CLK",
    "D0": "D_DONE", "D1": "D_WAIT", "D2": "D_BYTE_DONE", "D3": "BYTE_INC",
    "D4": "GND", "D5": "GND", "D6": "GND", "D7": "GND",
    "Q0": "S_DONE", "Q1": "S_WAIT", "Q2": "S_BYTE_DONE", "Q3": "S_BYTE_NEXT",
    "Q4": "NC", "Q5": "NC", "Q6": "NC", "Q7": "NC",
    "VCC": "+5V", "GND": "GND",
})

U32 = ic("74xx:74HC74", "U32", 610, 345, unit=1)
connect(sh, U32, {
    "~{R}": "RESET_N", "D": "D_RUN", "C": "CLK", "~{S}": "+5V",
    "Q": "RUN", "~{Q}": "NC",
})
# FIRST is set by INIT and cleared by LD0; it selects LD0 vs CMP after byte 3.
U32b = ic("74xx:74HC74", "U32", 660, 345, unit=2)
connect(sh, U32b, {
    "~{R}": "NOT_LD0", "D": "+5V", "C": "GND", "~{S}": "NOT_INIT",
    "Q": "FIRST", "~{Q}": "NC",
})
U32p = ic("74xx:74HC74", "U32", 610, 450, unit=3)
connect(sh, U32p, {"VCC": "+5V", "GND": "GND"})

# ---------------------------------------------------------------------------
# Inverters: EQ9_N->EQ9, score31/max31 MSB inversion, clear/run/idle.
# ---------------------------------------------------------------------------
U3 = ic("74xx:74HC04", "U3", 430, 430, unit=1)
connect(sh, U3, {"1": "EQ9_N", "2": "EQ9"})
U3b = ic("74xx:74HC04", "U3", 430, 455, unit=2)
connect(sh, U3b, {"3": SC[31], "4": "S31_INV"})
U3c = ic("74xx:74HC04", "U3", 430, 480, unit=3)
connect(sh, U3c, {"5": MX[31], "6": "M31_INV"})
U3d = ic("74xx:74HC04", "U3", 500, 430, unit=4)
connect(sh, U3d, {"9": "S_INIT", "8": "NOT_INIT"})
U3e = ic("74xx:74HC04", "U3", 500, 455, unit=5)
connect(sh, U3e, {"11": "S_DONE", "10": "NOT_S_DONE"})
U3f = ic("74xx:74HC04", "U3", 500, 480, unit=6)
connect(sh, U3f, {"13": "IDLE_OR", "12": "IDLE"})
U3p = ic("74xx:74HC04", "U3", 570, 430, unit=7)
connect(sh, U3p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# OR gates.
# ---------------------------------------------------------------------------
U33 = ic("74xx:74HC32", "U33", 55, 440, unit=1)
connect(sh, U33, {"1": "S_LD0", "2": "S_CMP", "3": "D_NEXT"})
U33b = ic("74xx:74HC32", "U33", 55, 465, unit=2)
connect(sh, U33b, {"4": "S_LD0", "5": "UPDATE_A", "6": "UPDATE"})
U33c = ic("74xx:74HC32", "U33", 55, 490, unit=3)
connect(sh, U33c, {"9": "BUSY_I", "10": "D_INIT", "8": "D_RUN"})
U33d = ic("74xx:74HC32", "U33", 55, 515, unit=4)
connect(sh, U33d, {"12": "S_DONE", "13": "WAIT_HOLD", "11": "D_WAIT"})
U33p = ic("74xx:74HC32", "U33", 95, 440, unit=5)
connect(sh, U33p, {"7": "GND", "14": "+5V"})

U34 = ic("74xx:74HC32", "U34", 145, 440, unit=1)
connect(sh, U34, {"1": "S_RD", "2": "S_WT", "3": "SCORE_RD"})
U34b = ic("74xx:74HC32", "U34", 145, 465, unit=2)
connect(sh, U34b, {"4": "S_INIT", "5": "S_BYTE_NEXT", "6": "RD_START"})
U34c = ic("74xx:74HC32", "U34", 145, 490, unit=3)
connect(sh, U34c, {"9": "RD_START", "10": "D_RD_A", "8": "D_RD"})
U34d = ic("74xx:74HC32", "U34", 145, 515, unit=4)
connect(sh, U34d, {"12": "S_DONE", "13": "S_WAIT", "11": "ARGMAX_RESULT_VALID"})
U34p = ic("74xx:74HC32", "U34", 185, 440, unit=5)
connect(sh, U34p, {"7": "GND", "14": "+5V"})

U35 = ic("74xx:74HC32", "U35", 235, 440, unit=1)
connect(sh, U35, {"1": "RUN", "2": "S_WAIT", "3": "IDLE_OR"})
U35b = ic("74xx:74HC32", "U35", 235, 465, unit=2)
connect(sh, U35b, {"4": "S_INIT", "5": "S_LD0", "6": "BC1"})
U35c = ic("74xx:74HC32", "U35", 235, 490, unit=3)
connect(sh, U35c, {"9": "BC1", "10": "S_NEXT", "8": "BYTE_CLR"})
U35d = ic("74xx:74HC32", "U35", 235, 515, unit=4)
connect(sh, U35d, {"12": "GND", "13": "GND", "11": "NC"})
U35p = ic("74xx:74HC32", "U35", 275, 440, unit=5)
connect(sh, U35p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# AND gates.
# ---------------------------------------------------------------------------
U36 = ic("74xx:74HC08", "U36", 325, 440, unit=1)
connect(sh, U36, {"1": "S_CMP", "2": "GT", "3": "UPDATE_A"})
U36b = ic("74xx:74HC08", "U36", 325, 465, unit=2)
connect(sh, U36b, {"4": "ARGMAX_START", "5": "IDLE", "6": "D_INIT"})
U36c = ic("74xx:74HC08", "U36", 325, 490, unit=3)
connect(sh, U36c, {"9": "RUN", "10": "NOT_S_DONE", "8": "BUSY_I"})
U36d = ic("74xx:74HC08", "U36", 325, 515, unit=4)
connect(sh, U36d, {"12": "S_NEXT", "13": "EQ9_N", "11": "D_RD_A"})
U36p = ic("74xx:74HC08", "U36", 365, 440, unit=5)
connect(sh, U36p, {"7": "GND", "14": "+5V"})

U37 = ic("74xx:74HC08", "U37", 415, 440, unit=1)
connect(sh, U37, {"1": "S_NEXT", "2": "EQ9", "3": "D_DONE"})
U37b = ic("74xx:74HC08", "U37", 415, 465, unit=2)
connect(sh, U37b, {"4": "S_WAIT", "5": "ARGMAX_START", "6": "WAIT_HOLD"})
U37c = ic("74xx:74HC08", "U37", 415, 490, unit=3)
connect(sh, U37c, {"9": "RESET_N", "10": "NOT_INIT", "8": "CLR_N"})
U37d = ic("74xx:74HC08", "U37", 415, 515, unit=4)
connect(sh, U37d, {"12": "RESET_N", "13": "NOT_BYTE_CLR", "11": "BYTE_CLR_N"})
U37p = ic("74xx:74HC08", "U37", 455, 440, unit=5)
connect(sh, U37p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Byte counter and ACK/DONE sequencer.
# ---------------------------------------------------------------------------
U39 = ic("74xx:74HC161", "U39", 55, 425)
connect(sh, U39, {
    "~{MR}": "BYTE_CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "BYTE_INC", "CET": "BYTE_INC",
    "Q0": "BYTE0", "Q1": "BYTE1", "Q2": "NC", "Q3": "NC", "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

U40 = ic("74xx:74HC08", "U40", 550, 440, unit=1)
connect(sh, U40, {"1": "BYTE0", "2": "BYTE1", "3": "BYTE3"})
U40b = ic("74xx:74HC08", "U40", 550, 465, unit=2)
connect(sh, U40b, {"4": "S_BYTE_DONE", "5": "MEM_DONE", "6": "BYTE_DONE_P"})
U40c = ic("74xx:74HC08", "U40", 550, 490, unit=3)
connect(sh, U40c, {"9": "BYTE_DONE_P", "10": "NOT_BYTE3", "8": "BYTE_INC"})
U40d = ic("74xx:74HC08", "U40", 550, 515, unit=4)
connect(sh, U40d, {"12": "BYTE_DONE_P", "13": "BYTE3", "11": "BYTE_LAST"})
U40p = ic("74xx:74HC08", "U40", 590, 440, unit=5)
connect(sh, U40p, {"7": "GND", "14": "+5V"})

U42 = ic("74xx:74HC04", "U42", 620, 440, unit=1)
connect(sh, U42, {"1": "BYTE3", "2": "NOT_BYTE3"})
U42b = ic("74xx:74HC04", "U42", 620, 465, unit=2)
connect(sh, U42b, {"3": "FIRST", "4": "NOT_FIRST"})
U42c = ic("74xx:74HC04", "U42", 620, 490, unit=3)
connect(sh, U42c, {"5": "BYTE_CLR", "6": "NOT_BYTE_CLR"})
U42d = ic("74xx:74HC04", "U42", 620, 515, unit=4)
connect(sh, U42d, {"9": "S_LD0", "8": "NOT_LD0"})
U42e = ic("74xx:74HC04", "U42", 680, 440, unit=5)
connect(sh, U42e, {"11": "ARGMAX_BUSY", "10": "ARGMAX_BUSY_N"})
U42f = ic("74xx:74HC04", "U42", 680, 465, unit=6)
connect(sh, U42f, {"13": "MEM_ACK", "12": "NOT_MEM_ACK"})
U42p = ic("74xx:74HC04", "U42", 680, 490, unit=7)
connect(sh, U42p, {"7": "GND", "14": "+5V"})

U45 = ic("74xx:74HC08", "U45", 720, 440, unit=1)
connect(sh, U45, {"1": "BYTE_LAST", "2": "FIRST", "3": "D_LD0"})
U45b = ic("74xx:74HC08", "U45", 720, 465, unit=2)
connect(sh, U45b, {"4": "BYTE_LAST", "5": "NOT_FIRST", "6": "D_CMP"})
U45c = ic("74xx:74HC08", "U45", 720, 490, unit=3)
connect(sh, U45c, {"9": "S_WT", "10": "MEM_ACK", "8": "D_BYTE_DONE_SET"})
U45d = ic("74xx:74HC08", "U45", 720, 515, unit=4)
connect(sh, U45d, {"12": "S_BYTE_DONE", "13": "NOT_MEM_DONE", "11": "BD_HOLD"})
U45p = ic("74xx:74HC08", "U45", 760, 440, unit=5)
connect(sh, U45p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Read-state hold logic: WT waits for ACK, BYDONE waits for DONE.
# ---------------------------------------------------------------------------
U46 = ic("74xx:74HC32", "U46", 780, 440, unit=1)
connect(sh, U46, {"1": "S_RD", "2": "WT_HOLD", "3": "D_WT"})
U46b = ic("74xx:74HC32", "U46", 780, 465, unit=2)
connect(sh, U46b, {"4": "D_BYTE_DONE_SET", "5": "BD_HOLD", "6": "D_BYTE_DONE"})
U46c = ic("74xx:74HC32", "U46", 780, 490, unit=3)
connect(sh, U46c, {"9": "GND", "10": "GND", "8": "NC"})
U46d = ic("74xx:74HC32", "U46", 780, 515, unit=4)
connect(sh, U46d, {"12": "GND", "13": "GND", "11": "NC"})
U46p = ic("74xx:74HC32", "U46", 820, 440, unit=5)
connect(sh, U46p, {"7": "GND", "14": "+5V"})

U47 = ic("74xx:74HC04", "U47", 860, 440, unit=1)
connect(sh, U47, {"1": "MEM_DONE", "2": "NOT_MEM_DONE"})
U47b = ic("74xx:74HC04", "U47", 860, 465, unit=2)
connect(sh, U47b, {"3": "GND", "4": "NC"})
U47c = ic("74xx:74HC04", "U47", 860, 490, unit=3)
connect(sh, U47c, {"5": "GND", "6": "NC"})
U47d = ic("74xx:74HC04", "U47", 860, 515, unit=4)
connect(sh, U47d, {"9": "GND", "8": "NC"})
U47e = ic("74xx:74HC04", "U47", 900, 440, unit=5)
connect(sh, U47e, {"11": "GND", "10": "NC"})
U47f = ic("74xx:74HC04", "U47", 900, 465, unit=6)
connect(sh, U47f, {"13": "GND", "12": "NC"})
U47p = ic("74xx:74HC04", "U47", 900, 490, unit=7)
connect(sh, U47p, {"7": "GND", "14": "+5V"})

U48 = ic("74xx:74HC08", "U48", 940, 440, unit=1)
connect(sh, U48, {"1": "S_WT", "2": "NOT_MEM_ACK", "3": "WT_HOLD"})
U48b = ic("74xx:74HC08", "U48", 940, 465, unit=2)
connect(sh, U48b, {"4": "GND", "5": "GND", "6": "NC"})
U48c = ic("74xx:74HC08", "U48", 940, 490, unit=3)
connect(sh, U48c, {"9": "GND", "10": "GND", "8": "NC"})
U48d = ic("74xx:74HC08", "U48", 940, 515, unit=4)
connect(sh, U48d, {"12": "GND", "13": "GND", "11": "NC"})
U48p = ic("74xx:74HC08", "U48", 980, 440, unit=5)
connect(sh, U48p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Output buffer: SCORE_ADDR[5:0], DONE and BUSY.
# SCORE_ADDR = class number (0..9); upper two bits grounded.
# ---------------------------------------------------------------------------
U38 = ic("74xx:74HCT541", "U38", 700, 345)
connect(sh, U38, {
    "G1": "GND", "G2": "GND",
    "A0": "BYTE0", "A1": "BYTE1", "A2": CL[0], "A3": CL[1],
    "A4": CL[2], "A5": CL[3], "A6": "S_DONE", "A7": "BUSY_I",
    "Y0": "SCORE_ADDR0", "Y1": "SCORE_ADDR1",
    "Y2": "SCORE_ADDR2", "Y3": "SCORE_ADDR3",
    "Y4": "SCORE_ADDR4", "Y5": "SCORE_ADDR5",
    "Y6": "ARGMAX_DONE", "Y7": "ARGMAX_BUSY",
    "VCC": "+5V", "GND": "GND",
})

# Test point for the internal signed-compare result.
TP1 = add(sh, "Connector:TestPoint", "TP1", 660, 440, value="GT")
sh.stub_label(TP1, "1", "GT", local=True)

# ---------------------------------------------------------------------------
# Decoupling bank: one 100 nF per IC package.
# ---------------------------------------------------------------------------
n_caps = len({s.ref for s in ic_list})
for i in range(n_caps):
    x = 40 + (i % 20) * 40
    y = 505 + (i // 20) * 27
    cap = add(sh, "Device:C", f"C{i+1}", x, y, value="100nF")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# Power flags.
for i, (net, x, y) in enumerate((("+5V", 700, 430), ("GND", 700, 460))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, y, value=net)
    sh.add_wire(x, y, x, y + 5.08)
    sh.add_power(net, x, y + 5.08, pwr_ref())

# ---------------------------------------------------------------------------
# Notes.
# ---------------------------------------------------------------------------
sh.add_text(
    "Signed compare: two's-complement operands are converted to offset binary "
    "by inverting bit 31 of SCORE and MAX; the 8x 74HC85 cascade then performs "
    "an unsigned magnitude compare.  GT (Oa>b) is strict greater-than.\n"
    "Tie rule: GT=0 for equal scores, so MAX and INDEX are not updated; the "
    "first (lowest-numbered) class wins.  Class 0 is loaded unconditionally in "
    "LD0.  Do not compare these scores as uint32.",
    20, 552, size=1.3, justify="left top",
)
sh.add_text(
    "Read sequence: INIT clears CLASS and BYTE; for each class BYTE=0..3: "
    "RD -> WT (wait MEM_ACK) -> BYDONE (wait MEM_DONE) -> BYNEXT.  "
    "SCORE_ADDR = {CLASS,BYTE} = class*4+byte; SCORE_RD is high in RD/WT.\n"
    "After BYTE=3: class 0 -> LD0 (load MAX/INDEX), classes 1..9 -> CMP; "
    "NEXT increments CLASS and clears BYTE until CLASS=9, then DONE.  "
    "FSM: IDLE -> INIT -> ... -> DONE -> WAIT -> IDLE.  RUN is set by "
    "ARGMAX_START and cleared at DONE; BUSY=RUN&~DONE.  RESULT_VALID=DONE|WAIT.",
    20, 566, size=1.3, justify="left top",
)
sh.add_text(
    "S12 latches DATA[7:0] into the four byte lanes on MEM_ACK; SCORE_DATA is "
    "the assembled little-endian 32-bit word.  Each byte is one S02 REQ/ACK "
    "transaction at byte address class*4+byte in FC2_LOGITS.  RESULT is the "
    "4-bit class index (0..9), held valid until the next ARGMAX_START.",
    20, 580, size=1.3, justify="left top",
)

sh.write(os.path.join(PROJECT_DIR, "S06_Argmax.kicad_sch"))
print("wrote S06_Argmax.kicad_sch")
print("IC units:", len(ic_list), "packages:", n_caps)
