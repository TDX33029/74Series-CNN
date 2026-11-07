"""Build S05_Pool.kicad_sch (2x2 / stride-2 unsigned max pooling engine).

Run from the tools directory:
    python build_pool.py

The sheet is a pin-level 74HC/HCT implementation of one shared POOL engine
used for POOL1 and POOL2 (selected by POOL_SEL).  Internal nets use local
labels, the module boundary uses global labels.  Every pin is connected to a
stub + label, a power symbol, or an explicit no-connect.
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

# Global (cross-module) interface nets from MODULE_SPECS section 1.
GLOBAL = {
    "CLK", "RESET_N", "P1_START", "P2_START", "POOL_SEL",
    "IN_DATA0", "IN_DATA1", "IN_DATA2", "IN_DATA3",
    "IN_DATA4", "IN_DATA5", "IN_DATA6", "IN_DATA7",
    "POOL_IN_ADDR0", "POOL_IN_ADDR1", "POOL_IN_ADDR2", "POOL_IN_ADDR3", "POOL_IN_ADDR4",
    "POOL_IN_ADDR5", "POOL_IN_ADDR6", "POOL_IN_ADDR7", "POOL_IN_ADDR8", "POOL_IN_ADDR9",
    "POOL_IN_ADDR10", "POOL_IN_ADDR11", "POOL_IN_ADDR12",
    "POOL_OUT_DATA0", "POOL_OUT_DATA1", "POOL_OUT_DATA2", "POOL_OUT_DATA3",
    "POOL_OUT_DATA4", "POOL_OUT_DATA5", "POOL_OUT_DATA6", "POOL_OUT_DATA7",
    "POOL_OUT_ADDR0", "POOL_OUT_ADDR1", "POOL_OUT_ADDR2", "POOL_OUT_ADDR3",
    "POOL_OUT_ADDR4", "POOL_OUT_ADDR5", "POOL_OUT_ADDR6", "POOL_OUT_ADDR7",
    "POOL_OUT_ADDR8", "POOL_OUT_ADDR9", "POOL_OUT_ADDR10", "POOL_OUT_ADDR11",
    "OUT_WE", "POOL_BUSY", "P1_DONE", "P2_DONE",
    "MEM_ACK", "MEM_DONE",
    "POOL_MEM_REQ", "POOL_MEM_WE", "POOL_MEM_nCE_IN", "POOL_MEM_nCE_OUT",
    "POOL_BUSY_N",
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
    """Connect every pin of a placed symbol.

    ``nmap`` may be keyed by pin number or pin name.  Unspecified power pins
    default to +5V/GND; any other unspecified pin becomes an explicit NC.
    """
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


# ---------------------------------------------------------------------------
sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S05_Pool - 2x2 Stride-2 Max Pooling Engine (POOL1/POOL2)", paper="A1",
)
sh.add_text(
    "S05  POOL engine: 2x2 window, stride 2, unsigned max (POOL1 / POOL2)",
    20, 14, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "Interface: CLK, RESET_N, P1_START, P2_START, POOL_SEL (0=POOL1, 1=POOL2), "
    "IN_DATA[7:0], POOL_IN_ADDR[12:0], POOL_OUT_DATA[7:0], POOL_OUT_ADDR[11:0], OUT_WE, "
    "POOL_BUSY, P1_DONE, P2_DONE, MEM_ACK, MEM_DONE, POOL_MEM_REQ, "
    "POOL_MEM_WE, POOL_MEM_nCE_IN, POOL_MEM_nCE_OUT, POOL_BUSY_N.\n"
    "POOL_START = P1_START | P2_START (U42a); DONE is page-local POOL_DONE.\n"
    "POOL1: C=8, H=24, W=24 -> 12x12x8 (1152 outputs, 4608 input bytes).  "
    "POOL2: C=16, H=10, W=10 -> 5x5x16 (400 outputs, 1600 input bytes).\n"
    "Read order per output: v0=(2oy,2ox), v1=(2oy,2ox+1), v2=(2oy+1,2ox), "
    "v3=(2oy+1,2ox+1).  POOL_IN_ADDR is held through RD and WT; data is captured "
    "at CP (assumes the S02 controller's 2-wait read).",
    20, 21, size=1.35, justify="left top",
)

ic_list = []


def ic(*args, **kwargs):
    s = add(sh, *args, **kwargs)
    ic_list.append(s)
    return s


# ---------------------------------------------------------------------------
# Counters: output x, output y, channel, and the 2-bit window-value phase.
# ---------------------------------------------------------------------------
U1 = ic("74xx:74HC161", "U1", 55, 65)
connect(sh, U1, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "OX_PE_N", "CEP": "OX_EN", "CET": "OX_EN",
    "Q0": "OX0", "Q1": "OX1", "Q2": "OX2", "Q3": "OX3", "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

U2 = ic("74xx:74HC161", "U2", 145, 65)
connect(sh, U2, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "OY_PE_N", "CEP": "OY_EN", "CET": "OY_EN",
    "Q0": "OY0", "Q1": "OY1", "Q2": "OY2", "Q3": "OY3", "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

U3 = ic("74xx:74HC161", "U3", 235, 65)
connect(sh, U3, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "C_EN", "CET": "C_EN",
    "Q0": "C0", "Q1": "C1", "Q2": "C2", "Q3": "C3", "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

U4 = ic("74xx:74HC161", "U4", 325, 65)
connect(sh, U4, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "S_CP", "CET": "S_CP",
    "Q0": "V0", "Q1": "V1", "Q2": "NC", "Q3": "NC", "TC": "NC",
    "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# Last-index comparators (74HC688 output is active-low equality).
# OW-1 = 11 (POOL1) / 4 (POOL2): bits 0,1,3 = /POOL_SEL, bit2 = POOL_SEL.
# C-1  = 7 (POOL1) / 15 (POOL2): bits 0..2 = 1, bit3 = POOL_SEL.
# ---------------------------------------------------------------------------
U5 = ic("74xx:74HC688", "U5", 420, 65)
connect(sh, U5, {
    "G": "GND", "P=R": "OX_EQ_N",
    "P0": "NPOOL_SEL", "P1": "NPOOL_SEL", "P2": "POOL_SEL", "P3": "NPOOL_SEL",
    "P4": "GND", "P5": "GND", "P6": "GND", "P7": "GND",
    "R0": "OX0", "R1": "OX1", "R2": "OX2", "R3": "OX3",
    "R4": "GND", "R5": "GND", "R6": "GND", "R7": "GND",
    "VCC": "+5V", "GND": "GND",
})

U6 = ic("74xx:74HC688", "U6", 510, 65)
connect(sh, U6, {
    "G": "GND", "P=R": "OY_EQ_N",
    "P0": "NPOOL_SEL", "P1": "NPOOL_SEL", "P2": "POOL_SEL", "P3": "NPOOL_SEL",
    "P4": "GND", "P5": "GND", "P6": "GND", "P7": "GND",
    "R0": "OY0", "R1": "OY1", "R2": "OY2", "R3": "OY3",
    "R4": "GND", "R5": "GND", "R6": "GND", "R7": "GND",
    "VCC": "+5V", "GND": "GND",
})

U7 = ic("74xx:74HC688", "U7", 600, 65)
connect(sh, U7, {
    "G": "GND", "P=R": "C_EQ_N",
    "P0": "+5V", "P1": "+5V", "P2": "+5V", "P3": "POOL_SEL",
    "P4": "GND", "P5": "GND", "P6": "GND", "P7": "GND",
    "R0": "C0", "R1": "C1", "R2": "C2", "R3": "C3",
    "R4": "GND", "R5": "GND", "R6": "GND", "R7": "GND",
    "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# Inverters.
# ---------------------------------------------------------------------------
U8 = ic("74xx:74HC04", "U8", 720, 180, unit=1)
connect(sh, U8, {"1": "POOL_SEL", "2": "NPOOL_SEL"})
U8b = ic("74xx:74HC04", "U8", 720, 205, unit=2)
connect(sh, U8b, {"3": "OX_EQ_N", "4": "OX_LAST"})
U8c = ic("74xx:74HC04", "U8", 720, 230, unit=3)
connect(sh, U8c, {"5": "OY_EQ_N", "6": "OY_LAST"})
U8d = ic("74xx:74HC04", "U8", 720, 255, unit=4)
connect(sh, U8d, {"9": "C_EQ_N", "8": "C_LAST"})
U8e = ic("74xx:74HC04", "U8", 720, 280, unit=5)
connect(sh, U8e, {"11": "V0", "10": "NV0"})
U8f = ic("74xx:74HC04", "U8", 720, 305, unit=6)
connect(sh, U8f, {"13": "V1", "12": "NV1"})
U8p = ic("74xx:74HC04", "U8", 720, 330, unit=7)
connect(sh, U8p, {"7": "GND", "14": "+5V"})

U9 = ic("74xx:74HC04", "U9", 790, 180, unit=1)
connect(sh, U9, {"1": "V_LAST", "2": "NV_LAST"})
U9b = ic("74xx:74HC04", "U9", 790, 205, unit=2)
connect(sh, U9b, {"3": "LAST_PIXEL", "4": "NOT_LAST"})
U9c = ic("74xx:74HC04", "U9", 790, 230, unit=3)
connect(sh, U9c, {"5": "OX_LOAD", "6": "OX_PE_N"})
U9d = ic("74xx:74HC04", "U9", 790, 255, unit=4)
connect(sh, U9d, {"9": "OY_LOAD", "8": "OY_PE_N"})
U9e = ic("74xx:74HC04", "U9", 790, 280, unit=5)
connect(sh, U9e, {"11": "S_DONE", "10": "NOT_S_DONE"})
U9f = ic("74xx:74HC04", "U9", 790, 305, unit=6)
connect(sh, U9f, {"13": "S_INIT", "12": "NOT_INIT"})
U9p = ic("74xx:74HC04", "U9", 790, 330, unit=7)
connect(sh, U9p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Max register (cleared at INIT), output holding register, unsigned comparator.
# ---------------------------------------------------------------------------
U10 = ic("74xx:74HCT273", "U10", 55, 165)
connect(sh, U10, {
    "~{Mr}": "CLR_N", "Cp": "CLK",
    "D0": "MAXD0", "D1": "MAXD1", "D2": "MAXD2", "D3": "MAXD3",
    "D4": "MAXD4", "D5": "MAXD5", "D6": "MAXD6", "D7": "MAXD7",
    "Q0": "MAX0", "Q1": "MAX1", "Q2": "MAX2", "Q3": "MAX3",
    "Q4": "MAX4", "Q5": "MAX5", "Q6": "MAX6", "Q7": "MAX7",
    "VCC": "+5V", "GND": "GND",
})

U11 = ic("74xx:74HCT574", "U11", 145, 165)
connect(sh, U11, {
    "OE": "GND", "Cp": "CLK",
    "D0": "MAX0", "D1": "MAX1", "D2": "MAX2", "D3": "MAX3",
    "D4": "MAX4", "D5": "MAX5", "D6": "MAX6", "D7": "MAX7",
    "Q0": "POOL_OUT_DATA0", "Q1": "POOL_OUT_DATA1", "Q2": "POOL_OUT_DATA2", "Q3": "POOL_OUT_DATA3",
    "Q4": "POOL_OUT_DATA4", "Q5": "POOL_OUT_DATA5", "Q6": "POOL_OUT_DATA6", "Q7": "POOL_OUT_DATA7",
    "VCC": "+5V", "GND": "GND",
})

U12 = ic("74xx:74HC85", "U12", 235, 165)
connect(sh, U12, {
    "A0": "IN_DATA0", "A1": "IN_DATA1", "A2": "IN_DATA2", "A3": "IN_DATA3",
    "B0": "MAX0", "B1": "MAX1", "B2": "MAX2", "B3": "MAX3",
    "Ia>b": "GND", "Ia=b": "+5V", "Ia<b": "GND",
    "Oa>b": "CMP_GT0", "Oa=b": "CMP_EQ0", "Oa<b": "CMP_LT0",
    "VCC": "+5V", "GND": "GND",
})

U13 = ic("74xx:74HC85", "U13", 325, 165)
connect(sh, U13, {
    "A0": "IN_DATA4", "A1": "IN_DATA5", "A2": "IN_DATA6", "A3": "IN_DATA7",
    "B0": "MAX4", "B1": "MAX5", "B2": "MAX6", "B3": "MAX7",
    "Ia>b": "CMP_GT0", "Ia=b": "CMP_EQ0", "Ia<b": "CMP_LT0",
    "Oa>b": "GT", "Oa=b": "NC", "Oa<b": "NC",
    "VCC": "+5V", "GND": "GND",
})

U14 = ic("74xx:74HC157", "U14", 415, 165)
connect(sh, U14, {
    "S": "UPDATE", "E": "GND",
    "I0a": "MAX0", "I1a": "IN_DATA0", "Za": "MAXD0",
    "I0b": "MAX1", "I1b": "IN_DATA1", "Zb": "MAXD1",
    "I0c": "MAX2", "I1c": "IN_DATA2", "Zc": "MAXD2",
    "I0d": "MAX3", "I1d": "IN_DATA3", "Zd": "MAXD3",
    "VCC": "+5V", "GND": "GND",
})

U15 = ic("74xx:74HC157", "U15", 505, 165)
connect(sh, U15, {
    "S": "UPDATE", "E": "GND",
    "I0a": "MAX4", "I1a": "IN_DATA4", "Za": "MAXD4",
    "I0b": "MAX5", "I1b": "IN_DATA5", "Zb": "MAXD5",
    "I0c": "MAX6", "I1c": "IN_DATA6", "Zc": "MAXD6",
    "I0d": "MAX7", "I1d": "IN_DATA7", "Zd": "MAXD7",
    "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# Linear window-base register: WB = c*H*W + 2*oy*W + 2*ox.
# Column step adds 2; row and channel steps add W+2 (H=2OH, W=2OW):
#   POOL1: W+2 = 26 = 0b11010;  POOL2: W+2 = 12 = 0b01100.
# ---------------------------------------------------------------------------
U16 = ic("74xx:74HCT273", "U16", 595, 165)
connect(sh, U16, {
    "~{Mr}": "CLR_N", "Cp": "CLK",
    "D0": "WBN0", "D1": "WBN1", "D2": "WBN2", "D3": "WBN3",
    "D4": "WBN4", "D5": "WBN5", "D6": "WBN6", "D7": "WBN7",
    "Q0": "WB0", "Q1": "WB1", "Q2": "WB2", "Q3": "WB3",
    "Q4": "WB4", "Q5": "WB5", "Q6": "WB6", "Q7": "WB7",
    "VCC": "+5V", "GND": "GND",
})

U17 = ic("74xx:74HCT273", "U17", 685, 165)
connect(sh, U17, {
    "~{Mr}": "CLR_N", "Cp": "CLK",
    "D0": "WBN8", "D1": "WBN9", "D2": "WBN10", "D3": "WBN11",
    "D4": "WBN12", "D5": "GND", "D6": "GND", "D7": "GND",
    "Q0": "WB8", "Q1": "WB9", "Q2": "WB10", "Q3": "WB11",
    "Q4": "WB12", "Q5": "NC", "Q6": "NC", "Q7": "NC",
    "VCC": "+5V", "GND": "GND",
})

# WB increment adder (13 bits) - constant 0 when not stepping.
U18 = ic("74xx:74HC283", "U18", 45, 265)
connect(sh, U18, {
    "A1": "WB0", "A2": "WB1", "A3": "WB2", "A4": "WB3",
    "B1": "GND", "B2": "KC1", "B3": "KC2", "B4": "ROW_STEP",
    "C0": "GND",
    "S1": "WBN0", "S2": "WBN1", "S3": "WBN2", "S4": "WBN3",
    "C4": "WBC0", "VCC": "+5V", "GND": "GND",
})

U19 = ic("74xx:74HC283", "U19", 125, 265)
connect(sh, U19, {
    "A1": "WB4", "A2": "WB5", "A3": "WB6", "A4": "WB7",
    "B1": "KC4", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "WBC0",
    "S1": "WBN4", "S2": "WBN5", "S3": "WBN6", "S4": "WBN7",
    "C4": "WBC1", "VCC": "+5V", "GND": "GND",
})

U20 = ic("74xx:74HC283", "U20", 205, 265)
connect(sh, U20, {
    "A1": "WB8", "A2": "WB9", "A3": "WB10", "A4": "WB11",
    "B1": "GND", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "WBC1",
    "S1": "WBN8", "S2": "WBN9", "S3": "WBN10", "S4": "WBN11",
    "C4": "WBC2", "VCC": "+5V", "GND": "GND",
})

U21 = ic("74xx:74HC283", "U21", 285, 265)
connect(sh, U21, {
    "A1": "WB12", "A2": "GND", "A3": "GND", "A4": "GND",
    "B1": "GND", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "WBC2",
    "S1": "WBN12", "S2": "NC", "S3": "NC", "S4": "NC",
    "C4": "NC", "VCC": "+5V", "GND": "GND",
})

# Read-address adder: POOL_IN_ADDR = WB + offset(V).
# offset = 0, 1, W, W+1; W = 24 (POOL1) / 10 (POOL2).
U22 = ic("74xx:74HC283", "U22", 375, 265)
connect(sh, U22, {
    "A1": "WB0", "A2": "WB1", "A3": "WB2", "A4": "WB3",
    "B1": "V0", "B2": "OFF1", "B3": "GND", "B4": "V1",
    "C0": "GND",
    "S1": "POOL_IN_ADDR0", "S2": "POOL_IN_ADDR1", "S3": "POOL_IN_ADDR2", "S4": "POOL_IN_ADDR3",
    "C4": "ADC0", "VCC": "+5V", "GND": "GND",
})

U23 = ic("74xx:74HC283", "U23", 455, 265)
connect(sh, U23, {
    "A1": "WB4", "A2": "WB5", "A3": "WB6", "A4": "WB7",
    "B1": "OFF4", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "ADC0",
    "S1": "POOL_IN_ADDR4", "S2": "POOL_IN_ADDR5", "S3": "POOL_IN_ADDR6", "S4": "POOL_IN_ADDR7",
    "C4": "ADC1", "VCC": "+5V", "GND": "GND",
})

U24 = ic("74xx:74HC283", "U24", 535, 265)
connect(sh, U24, {
    "A1": "WB8", "A2": "WB9", "A3": "WB10", "A4": "WB11",
    "B1": "GND", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "ADC1",
    "S1": "POOL_IN_ADDR8", "S2": "POOL_IN_ADDR9", "S3": "POOL_IN_ADDR10", "S4": "POOL_IN_ADDR11",
    "C4": "ADC2", "VCC": "+5V", "GND": "GND",
})

U25 = ic("74xx:74HC283", "U25", 615, 265)
connect(sh, U25, {
    "A1": "WB12", "A2": "GND", "A3": "GND", "A4": "GND",
    "B1": "GND", "B2": "GND", "B3": "GND", "B4": "GND",
    "C0": "ADC2",
    "S1": "POOL_IN_ADDR12", "S2": "NC", "S3": "NC", "S4": "NC",
    "C4": "NC", "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# Output address counter: one increment per write, 12 bits.
# ---------------------------------------------------------------------------
U26 = ic("74xx:74HC161", "U26", 45, 365)
connect(sh, U26, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "NEXT_DONE", "CET": "NEXT_DONE",
    "Q0": "POOL_OUT_ADDR0", "Q1": "POOL_OUT_ADDR1", "Q2": "POOL_OUT_ADDR2", "Q3": "POOL_OUT_ADDR3",
    "TC": "OAC0", "VCC": "+5V", "GND": "GND",
})

U27 = ic("74xx:74HC161", "U27", 135, 365)
connect(sh, U27, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "NEXT_DONE", "CET": "OAC0",
    "Q0": "POOL_OUT_ADDR4", "Q1": "POOL_OUT_ADDR5", "Q2": "POOL_OUT_ADDR6", "Q3": "POOL_OUT_ADDR7",
    "TC": "OAC1", "VCC": "+5V", "GND": "GND",
})

U28 = ic("74xx:74HC161", "U28", 225, 365)
connect(sh, U28, {
    "~{MR}": "CLR_N", "CP": "CLK",
    "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
    "~{PE}": "+5V", "CEP": "NEXT_DONE", "CET": "OAC1",
    "Q0": "POOL_OUT_ADDR8", "Q1": "POOL_OUT_ADDR9", "Q2": "POOL_OUT_ADDR10", "Q3": "POOL_OUT_ADDR11",
    "TC": "NC", "VCC": "+5V", "GND": "GND",
})

# ---------------------------------------------------------------------------
# One-hot FSM (8 states), run flag, and glue.
# IDLE is the all-zero state; RUN is set by POOL_START and cleared at S_DONE.
# ---------------------------------------------------------------------------
U29 = ic("74xx:74HCT273", "U29", 315, 365)
connect(sh, U29, {
    "~{Mr}": "RESET_N", "Cp": "CLK",
    "D0": "D_INIT", "D1": "D_RD", "D2": "D_WT", "D3": "D_CP",
    "D4": "D_OUTLD", "D5": "D_NEXT", "D6": "D_DONE", "D7": "D_WAIT",
    "Q0": "S_INIT", "Q1": "S_RD", "Q2": "S_WT", "Q3": "S_CP",
    "Q4": "S_OUTLD", "Q5": "S_NEXT", "Q6": "S_DONE", "Q7": "S_WAIT",
    "VCC": "+5V", "GND": "GND",
})

U30 = ic("74xx:74HC74", "U30", 405, 365, unit=1)
connect(sh, U30, {
    "~{R}": "RESET_N", "D": "D_RUN", "C": "CLK", "~{S}": "+5V",
    "Q": "RUN", "~{Q}": "NC",
})
U30b = ic("74xx:74HC74", "U30", 455, 365, unit=2)
connect(sh, U30b, {
    "~{R}": "RESET_N", "D": "GND", "C": "GND", "~{S}": "+5V",
    "Q": "NC", "~{Q}": "NC",
})
U30p = ic("74xx:74HC74", "U30", 505, 365, unit=3)
connect(sh, U30p, {"VCC": "+5V", "GND": "GND"})

# OR gates: IN_RD, D_WAIT, IDLE, K1 on U31; D_RD/D_RUN on U32.
U31 = ic("74xx:74HC32", "U31", 545, 365, unit=1)
connect(sh, U31, {"1": "S_RD", "2": "S_WT", "3": "IN_RD"})
U31b = ic("74xx:74HC32", "U31", 545, 390, unit=2)
connect(sh, U31b, {"4": "S_DONE", "5": "WAIT_HOLD", "6": "D_WAIT"})
U31c = ic("74xx:74HC32", "U31", 545, 415, unit=3)
connect(sh, U31c, {"9": "RUN", "10": "S_WAIT", "8": "IDLE_OR"})
U31d = ic("74xx:74HC32", "U31", 545, 440, unit=4)
connect(sh, U31d, {"12": "OX_EN", "13": "KC4", "11": "KC1"})
U31p = ic("74xx:74HC32", "U31", 585, 365, unit=5)
connect(sh, U31p, {"7": "GND", "14": "+5V"})

U32 = ic("74xx:74HC32", "U32", 625, 365, unit=1)
connect(sh, U32, {"1": "S_INIT", "2": "NEXT_VALUE", "3": "D_RD_A"})
U32b = ic("74xx:74HC32", "U32", 625, 390, unit=2)
connect(sh, U32b, {"4": "GND", "5": "GND", "6": "NC"})
U32c = ic("74xx:74HC32", "U32", 625, 415, unit=3)
connect(sh, U32c, {"9": "BUSY_I", "10": "D_INIT", "8": "D_RUN"})
U32d = ic("74xx:74HC32", "U32", 625, 440, unit=4)
connect(sh, U32d, {"12": "IS_V0", "13": "GT", "11": "UPDATE_TERM"})
U32p = ic("74xx:74HC32", "U32", 665, 365, unit=5)
connect(sh, U32p, {"7": "GND", "14": "+5V"})

# AND gates.
U33 = ic("74xx:74HC08", "U33", 705, 365, unit=1)
connect(sh, U33, {"1": "S_CP", "2": "UPDATE_TERM", "3": "UPDATE"})
U33b = ic("74xx:74HC08", "U33", 705, 390, unit=2)
connect(sh, U33b, {"4": "NEXT_DONE", "5": "NOT_LAST", "6": "STEP"})
U33c = ic("74xx:74HC08", "U33", 705, 415, unit=3)
connect(sh, U33c, {"9": "NEXT_DONE", "10": "OX_EQ_N", "8": "OX_EN"})
U33d = ic("74xx:74HC08", "U33", 705, 440, unit=4)
connect(sh, U33d, {"12": "NEXT_DONE", "13": "OX_LAST", "11": "OX_LOAD"})
U33p = ic("74xx:74HC08", "U33", 745, 365, unit=5)
connect(sh, U33p, {"7": "GND", "14": "+5V"})

U34 = ic("74xx:74HC08", "U34", 45, 455, unit=1)
connect(sh, U34, {"1": "OX_LOAD", "2": "OY_LAST", "3": "OY_LOAD"})
U34b = ic("74xx:74HC08", "U34", 45, 480, unit=2)
connect(sh, U34b, {"4": "OX_LOAD", "5": "OY_EQ_N", "6": "OY_EN"})
U34c = ic("74xx:74HC08", "U34", 45, 505, unit=3)
connect(sh, U34c, {"9": "OY_LOAD", "10": "C_EQ_N", "8": "C_EN"})
U34d = ic("74xx:74HC08", "U34", 45, 530, unit=4)
connect(sh, U34d, {"12": "STEP", "13": "OX_LAST", "11": "ROW_STEP"})
# KC3 is ROW_STEP itself (bit 3 of W+2 is always 1).
U34p = ic("74xx:74HC08", "U34", 85, 455, unit=5)
connect(sh, U34p, {"7": "GND", "14": "+5V"})

U35 = ic("74xx:74HC08", "U35", 125, 455, unit=1)
connect(sh, U35, {"1": "ROW_STEP", "2": "POOL_SEL", "3": "KC2"})
U35b = ic("74xx:74HC08", "U35", 125, 480, unit=2)
connect(sh, U35b, {"4": "ROW_STEP", "5": "NPOOL_SEL", "6": "KC4"})
U35c = ic("74xx:74HC08", "U35", 125, 505, unit=3)
connect(sh, U35c, {"9": "V1", "10": "POOL_SEL", "8": "OFF1"})
U35d = ic("74xx:74HC08", "U35", 125, 530, unit=4)
connect(sh, U35d, {"12": "V1", "13": "NPOOL_SEL", "11": "OFF4"})
U35p = ic("74xx:74HC08", "U35", 165, 455, unit=5)
connect(sh, U35p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Pool start pulse: POOL_START = P1_START | P2_START (74HC32, new package U42).
# S01 drives P1_START/P2_START as global stage pulses; the Pool engine has a
# single local start net, so the two stage pulses are OR-ed here.
# ---------------------------------------------------------------------------
U42 = ic("74xx:74HC32", "U42", 545, 455, unit=1)
connect(sh, U42, {"1": "P1_START", "2": "P2_START", "3": "POOL_START"})
U42b = ic("74xx:74HC32", "U42", 545, 480, unit=2)
connect(sh, U42b, {"4": "S_CP", "5": "WT_HOLD", "6": "D_WT"})
U42c = ic("74xx:74HC32", "U42", 545, 505, unit=3)
connect(sh, U42c, {"9": "S_RD", "10": "S_CP", "8": "READ_A"})
U42d = ic("74xx:74HC32", "U42", 545, 530, unit=4)
connect(sh, U42d, {"12": "READ_A", "13": "S_WT", "11": "READ_PHASE"})
U42p = ic("74xx:74HC32", "U42", 585, 455, unit=5)
connect(sh, U42p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Memory handshake decode (added for the S11/S02 shared bus).
# RD waits for MEM_ACK, CP captures, WT waits for MEM_DONE, NEXT waits for the
# write MEM_DONE.  The read phase keeps POOL_MEM_REQ/nCE_IN active; NEXT keeps
# POOL_MEM_REQ/WE/nCE_OUT active.
# ---------------------------------------------------------------------------
U43 = ic("74xx:74HC08", "U43", 760, 365, unit=1)
connect(sh, U43, {"1": "S_RD", "2": "MEM_ACK", "3": "D_CP"})
U43b = ic("74xx:74HC08", "U43", 800, 365, unit=2)
connect(sh, U43b, {"4": "WT_DONE", "5": "NV_LAST", "6": "NEXT_VALUE"})
U43c = ic("74xx:74HC08", "U43", 760, 395, unit=3)
connect(sh, U43c, {"9": "WT_DONE", "10": "V_LAST", "8": "D_OUTLD"})
U43d = ic("74xx:74HC08", "U43", 800, 395, unit=4)
connect(sh, U43d, {"12": "S_RD", "13": "NMEM_ACK", "11": "RD_HOLD"})
U43p = ic("74xx:74HC08", "U43", 830, 365, unit=5)
connect(sh, U43p, {"7": "GND", "14": "+5V"})

U44 = ic("74xx:74HC32", "U44", 760, 425, unit=1)
connect(sh, U44, {"1": "STEP", "2": "RD_HOLD", "3": "D_RD_B"})
U44b = ic("74xx:74HC32", "U44", 800, 425, unit=2)
connect(sh, U44b, {"4": "D_RD_A", "5": "D_RD_B", "6": "D_RD"})
U44c = ic("74xx:74HC32", "U44", 760, 455, unit=3)
connect(sh, U44c, {"9": "READ_PHASE", "10": "S_NEXT", "8": "POOL_MEM_REQ_INT"})
U44d = ic("74xx:74HC32", "U44", 800, 455, unit=4)
connect(sh, U44d, {"12": "S_OUTLD", "13": "NEXT_HOLD", "11": "D_NEXT"})
U44p = ic("74xx:74HC32", "U44", 830, 425, unit=5)
connect(sh, U44p, {"7": "GND", "14": "+5V"})

U45 = ic("74xx:74HC04", "U45", 600, 340, unit=1)
connect(sh, U45, {"1": "MEM_ACK", "2": "NMEM_ACK"})
U45b = ic("74xx:74HC04", "U45", 630, 340, unit=2)
connect(sh, U45b, {"3": "MEM_DONE", "4": "NMEM_DONE"})
U45c = ic("74xx:74HC04", "U45", 660, 340, unit=3)
connect(sh, U45c, {"5": "READ_PHASE", "6": "NREAD_PHASE"})
U45d = ic("74xx:74HC04", "U45", 690, 340, unit=4)
connect(sh, U45d, {"9": "S_NEXT", "8": "NS_NEXT"})
U45e = ic("74xx:74HC04", "U45", 720, 340, unit=5)
connect(sh, U45e, {"11": "BUSY_I", "10": "POOL_BUSY_N_INT"})
U45f = ic("74xx:74HC04", "U45", 750, 340, unit=6)
connect(sh, U45f, {"13": "GND", "12": "NC"})
U45p = ic("74xx:74HC04", "U45", 780, 340, unit=7)
connect(sh, U45p, {"7": "GND", "14": "+5V"})

U36 = ic("74xx:74HC08", "U36", 205, 455, unit=1)
connect(sh, U36, {"1": "POOL_START", "2": "IDLE", "3": "D_INIT"})
U36b = ic("74xx:74HC08", "U36", 205, 480, unit=2)
connect(sh, U36b, {"4": "RUN", "5": "NOT_S_DONE", "6": "BUSY_I"})
U36c = ic("74xx:74HC08", "U36", 205, 505, unit=3)
connect(sh, U36c, {"9": "NEXT_DONE", "10": "LAST_PIXEL", "8": "D_DONE"})
U36d = ic("74xx:74HC08", "U36", 205, 530, unit=4)
connect(sh, U36d, {"12": "GND", "13": "GND", "11": "NC"})
U36p = ic("74xx:74HC08", "U36", 245, 455, unit=5)
connect(sh, U36p, {"7": "GND", "14": "+5V"})

U37 = ic("74xx:74HC08", "U37", 285, 455, unit=1)
connect(sh, U37, {"1": "S_WT", "2": "MEM_DONE", "3": "WT_DONE"})
U37b = ic("74xx:74HC08", "U37", 285, 480, unit=2)
connect(sh, U37b, {"4": "S_WAIT", "5": "POOL_START", "6": "WAIT_HOLD"})
U37c = ic("74xx:74HC08", "U37", 285, 505, unit=3)
connect(sh, U37c, {"9": "OX_LAST", "10": "OY_LAST", "8": "LAST_ROW"})
U37d = ic("74xx:74HC08", "U37", 285, 530, unit=4)
connect(sh, U37d, {"12": "LAST_ROW", "13": "C_LAST", "11": "LAST_PIXEL"})
U37p = ic("74xx:74HC08", "U37", 325, 455, unit=5)
connect(sh, U37p, {"7": "GND", "14": "+5V"})

U38 = ic("74xx:74HC08", "U38", 365, 455, unit=1)
connect(sh, U38, {"1": "RESET_N", "2": "NOT_INIT", "3": "CLR_N"})
U38b = ic("74xx:74HC08", "U38", 365, 480, unit=2)
connect(sh, U38b, {"4": "V0", "5": "V1", "6": "V_LAST"})
U38c = ic("74xx:74HC08", "U38", 365, 505, unit=3)
connect(sh, U38c, {"9": "NV0", "10": "NV1", "8": "IS_V0"})
U38d = ic("74xx:74HC08", "U38", 365, 530, unit=4)
connect(sh, U38d, {"12": "S_NEXT", "13": "MEM_DONE", "11": "NEXT_DONE"})
U38p = ic("74xx:74HC08", "U38", 405, 455, unit=5)
connect(sh, U38p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# IDLE = NOR(RUN, S_WAIT) (74HC02).
# ---------------------------------------------------------------------------
U40 = ic("74xx:74HC02", "U40", 670, 200, unit=1)
connect(sh, U40, {"2": "RUN", "3": "S_WAIT", "1": "IDLE"})
U40b = ic("74xx:74HC02", "U40", 670, 225, unit=2)
connect(sh, U40b, {"5": "GND", "6": "GND", "4": "NC"})
U40c = ic("74xx:74HC02", "U40", 670, 250, unit=3)
connect(sh, U40c, {"8": "GND", "9": "GND", "10": "NC"})
U40d = ic("74xx:74HC02", "U40", 670, 275, unit=4)
connect(sh, U40d, {"11": "GND", "12": "GND", "13": "NC"})
U40p = ic("74xx:74HC02", "U40", 670, 300, unit=5)
connect(sh, U40p, {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Output buffers (74HCT541): OUT_WE and POOL_BUSY are module-boundary nets.
# Y1 drives the page-local POOL_DONE that feeds the P1_DONE/P2_DONE gates.
# ---------------------------------------------------------------------------
U39 = ic("74xx:74HCT541", "U39", 445, 455)
connect(sh, U39, {
    "G1": "GND", "G2": "GND",
    "A0": "S_NEXT", "A1": "S_DONE", "A2": "BUSY_I",
    "A3": "POOL_MEM_REQ_INT", "A4": "S_NEXT", "A5": "NREAD_PHASE",
    "A6": "NS_NEXT", "A7": "POOL_BUSY_N_INT",
    "Y0": "OUT_WE", "Y1": "POOL_DONE", "Y2": "POOL_BUSY",
    "Y3": "POOL_MEM_REQ", "Y4": "POOL_MEM_WE", "Y5": "POOL_MEM_nCE_IN",
    "Y6": "POOL_MEM_nCE_OUT", "Y7": "POOL_BUSY_N",
    "VCC": "+5V", "GND": "GND",
})

# Stage-specific done pulses for the supervisor: POOL_SEL is stable for the
# whole run, so P1_DONE = POOL_DONE & ~POOL_SEL and P2_DONE = POOL_DONE & POOL_SEL.
U41 = ic("74xx:74HC08", "U41", 700, 455, unit=1)
connect(sh, U41, {"1": "POOL_DONE", "2": "NPOOL_SEL", "3": "P1_DONE"})
U41b = ic("74xx:74HC08", "U41", 700, 480, unit=2)
connect(sh, U41b, {"4": "POOL_DONE", "5": "POOL_SEL", "6": "P2_DONE"})
U41c = ic("74xx:74HC08", "U41", 700, 505, unit=3)
connect(sh, U41c, {"9": "S_NEXT", "10": "NMEM_DONE", "8": "NEXT_HOLD"})
U41d = ic("74xx:74HC08", "U41", 700, 530, unit=4)
connect(sh, U41d, {"12": "S_WT", "13": "NMEM_DONE", "11": "WT_HOLD"})
U41p = ic("74xx:74HC08", "U41", 740, 455, unit=5)
connect(sh, U41p, {"7": "GND", "14": "+5V"})

# Test point for the internal read-request strobe (keeps the net observable).
TP1 = add(sh, "Connector:TestPoint", "TP1", 690, 470, value="IN_RD")
sh.stub_label(TP1, "1", "IN_RD", local=True)

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
for i, (net, x, y) in enumerate((("+5V", 790, 110), ("GND", 790, 140))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, y, value=net)
    sh.add_wire(x, y, x, y + 5.08)
    sh.add_power(net, x, y + 5.08, pwr_ref())

# ---------------------------------------------------------------------------
# Notes.
# ---------------------------------------------------------------------------
sh.add_text(
    "Four-value read order (per output pixel): v0=(2oy,2ox), v1=(2oy,2ox+1), "
    "v2=(2oy+1,2ox), v3=(2oy+1,2ox+1).\n"
    "Linear input address: WB = c*H*W + 2*oy*W + 2*ox; v0..v3 add 0, 1, W, W+1.\n"
    "Column step adds 2.  Because H=2*OH and W=2*OW, both a row step and a "
    "channel step add W+2 to WB (POOL1: 26, POOL2: 12).",
    20, 552, size=1.3, justify="left top",
)
sh.add_text(
    "Unsigned max rule: MAX is cleared in INIT.  At the first value of every "
    "window (V=0) the max register is force-loaded with v0 (UPDATE = CP & "
    "(IS_V0 | GT)); v1..v3 are accepted only when IN_DATA > MAX (74HC85 "
    "cascade, strict greater).  Equal values keep the current MAX value.  "
    "POOL_SEL must be stable for the whole run.\n"
    "FSM states: IDLE -> INIT -> {RD -> WT -> CP} x4 -> OUTLD -> NEXT -> "
    "(RD | DONE) -> WAIT; RUN is set by POOL_START and cleared at S_DONE.  OUT_WE is "
    "asserted in NEXT, after POOL_OUT_DATA has been loaded in OUTLD.",
    20, 566, size=1.3, justify="left top",
)
sh.add_text(
    "POOL1: 12x12x8, POOL_OUT_ADDR 0..1151, input 24x24x8 (13-bit address).  "
    "POOL2: 5x5x16, POOL_OUT_ADDR 0..399, input 10x10x16 (11-bit address).  "
    "Address bits above the used range are still computed to 0 because the "
    "window base is cleared in INIT and only legal steps are applied.",
    20, 580, size=1.3, justify="left top",
)

TEMPLATE_DIR = os.path.join(PROJECT_DIR, "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)
sh.write(os.path.join(TEMPLATE_DIR, "S05_Pool.kicad_sch"))
print("wrote templates/S05_Pool.kicad_sch")
print("ICs:", len(ic_list), "caps:", n_caps)
