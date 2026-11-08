"""Build S02_Timing.kicad_sch (generic SRAM/ROM timing controller)."""
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
    "CLK", "RESET_N", "REQ", "WE",
    "WAIT_READ0", "WAIT_READ1", "WAIT_READ2", "WAIT_READ3",
    "WAIT_WRITE0", "WAIT_WRITE1", "WAIT_WRITE2", "WAIT_WRITE3",
    "MEM_nCE", "MEM_nOE", "MEM_nWE", "MEM_ACK", "MEM_DONE", "MEM_BUSY",
}

def is_global(net: str) -> bool:
    return net in GLOBAL

pwr_n = 0
def pwr_ref() -> str:
    global pwr_n
    pwr_n += 1
    return f"#PWR{pwr_n:03d}"

def add(sh, lib_id, ref, x, y, unit=1, value=None):
    return sh.add_symbol(lib_id, ref, value, x, y, unit=unit,
                         footprint=footprint_for(lib_id))

def connect(sh, sym, nmap, local=True):
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

sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S02_Timing - SRAM/ROM Timing Controller", paper="A1",
)
sh.add_text(
    "S02  Memory Timing Controller (read/write wait-state sequencer)",
    20, 16, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "T_IDLE -> T_SETUP -> T_WAIT(n) -> T_CAPTURE(read)/T_HOLD(write) -> T_RELEASE -> T_DONE.\n"
    "nCE/nOE/nWE are active-low.  DONE is issued only after the final hold cycle.  "
    "WAIT_READ/WAIT_WRITE are 4-bit inputs.",
    20, 23, size=1.5, justify="left top",
)

# --- microcode ROM --------------------------------------------------------
U1 = add(sh, "Memory_EPROM:27C512", "U1", 80, 65)
m = {"VCC": "+5V", "GND": "GND", "~{CE}": "GND", "~{OE}": "GND"}
# V9: the controller stays level-sensitive so the burst clients (POOL,
# ARGMAX) can hold REQ high for back-to-back transfers.  The engine microcode
# now drops MEM_REQ at MEM_ACK instead of MEM_DONE, so REQ_S is already low
# when the controller returns to IDLE; otherwise MEM_REQ (plus the one-cycle
# REQ_S latch and control-register skew) started a second, spurious transfer.
ADDR = ["TS0", "TS1", "TS2", "REQ_S", "WAIT_MATCH", "WE_S"]
for i in range(6):
    m[f"A{i}"] = ADDR[i]
for i in range(6, 16):
    m[f"A{i}"] = "GND"
for i in range(8):
    m[f"D{i}"] = f"MC{i}"
connect(sh, U1, m, local=True)

# --- state register ------------------------------------------------------
U2 = add(sh, "74xx:74HCT273", "U2", 170, 65)
m = {"~{Mr}": "RESET_N", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(3):
    m[f"D{i}"] = f"MC{i}"
    m[f"Q{i}"] = f"TS{i}"
for i in range(3, 8):
    m[f"D{i}"] = "GND"
    m[f"Q{i}"] = "NC"
connect(sh, U2, m, local=True)

# --- output register -----------------------------------------------------
U3 = add(sh, "74xx:74HCT574", "U3", 260, 65)
m = {"OE": "GND", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(8):
    m[f"D{i}"] = f"MC{i}"
for i in range(3):
    m[f"Q{i}"] = f"MC_REG{i}"
m["Q3"] = "nCE_I"
m["Q4"] = "nOE_I"
m["Q5"] = "nWE_I"
m["Q6"] = "ACK_I"
m["Q7"] = "DONE_I"
connect(sh, U3, m, local=True)

# --- state decoder -------------------------------------------------------
U4 = add(sh, "74xx:74HC138", "U4", 350, 65)
# The 74HC138 symbol names its outputs ~{Y0}..~{Y7}, so address by pin number.
m = {"A0": "TS0", "A1": "TS1", "A2": "TS2",
     "4": "GND", "5": "GND", "6": "+5V",
     "15": "IDLE_N", "14": "SETUP_N", "13": "WAIT_N",
     "12": "CAPTURE_N", "11": "HOLD_N", "10": "RELEASE_N",
     "9": "DONE_ST_N", "7": "NC", "VCC": "+5V", "GND": "GND"}
connect(sh, U4, m, local=True)

# --- control output buffer ----------------------------------------------
U5 = add(sh, "74xx:74HCT541", "U5", 440, 65)
m = {"G1": "GND", "G2": "GND", "VCC": "+5V", "GND": "GND",
     "A0": "nCE_I", "A1": "nOE_I", "A2": "nWE_I", "A3": "ACK_I",
     "A4": "DONE_I", "A5": "IDLE_N", "A6": "GND", "A7": "GND",
     "Y0": "MEM_nCE", "Y1": "MEM_nOE", "Y2": "MEM_nWE", "Y3": "MEM_ACK",
     "Y4": "MEM_DONE", "Y5": "MEM_BUSY", "Y6": "NC", "Y7": "NC"}
connect(sh, U5, m, local=True)

# --- wait counter --------------------------------------------------------
U6 = add(sh, "74xx:74HC161", "U6", 80, 175)
m = {"~{MR}": "CNT_CLR_N", "CP": "CLK", "CEP": "+5V", "CET": "+5V",
     "~{PE}": "+5V", "VCC": "+5V", "GND": "GND",
     "D0": "GND", "D1": "GND", "D2": "GND", "D3": "GND",
     "Q0": "CNT0", "Q1": "CNT1", "Q2": "CNT2", "Q3": "CNT3", "TC": "NC"}
connect(sh, U6, m, local=True)

# --- wait value mux ------------------------------------------------------
# Default wait values: READ=3 (worst-case 28C256), WRITE=2 (6264).
# Replace these four ties with a configuration latch/DIP switch if per-device
# tuning is required; the global WAIT_READ/WRITE nets were left unconnected in
# the standalone sheet and are intentionally tied here for system integration.
U7 = add(sh, "74xx:74HC157", "U7", 170, 175)
m = {"S": "WE_S", "E": "GND", "VCC": "+5V", "GND": "GND",
     "I0a": "+5V", "I1a": "GND", "Za": "WAITV0",
     "I0b": "+5V", "I1b": "+5V", "Zb": "WAITV1",
     "I0c": "GND", "I1c": "GND", "Zc": "WAITV2",
     "I0d": "GND", "I1d": "GND", "Zd": "WAITV3"}
connect(sh, U7, m, local=True)

# --- wait comparator -----------------------------------------------------
U8 = add(sh, "74xx:74HC688", "U8", 260, 175)
m = {"G": "GND", "P=R": "WAIT_MATCH_N", "VCC": "+5V", "GND": "GND"}
for i in range(4):
    m[f"P{i}"] = f"WAITV{i}"
    m[f"R{i}"] = f"CNT{i}"
for i in range(4, 8):
    m[f"P{i}"] = "GND"
    m[f"R{i}"] = "GND"
connect(sh, U8, m, local=True)

# --- request/write-enable synchronizers ---------------------------------
U9 = add(sh, "74xx:74HC74", "U9", 350, 175, unit=1)
connect(sh, U9, {"~{R}": "RESET_N", "D": "REQ", "C": "CLK", "~{S}": "+5V",
                 "Q": "REQ_S", "~{Q}": "NC"}, local=True)
U9b = add(sh, "74xx:74HC74", "U9", 350, 215, unit=2)
connect(sh, U9b, {"~{R}": "RESET_N", "D": "WE", "C": "CLK", "~{S}": "+5V",
                  "Q": "WE_S", "~{Q}": "NC"}, local=True)
U9p = add(sh, "74xx:74HC74", "U9", 395, 175, unit=3)
connect(sh, U9p, {"VCC": "+5V", "GND": "GND"}, local=True)


# --- data path -----------------------------------------------------------
# There is no data transceiver on this sheet.  S04 U36 (74HC245) is the single
# MEM_D <-> DATA buffer; its direction is controlled by MEM_nOE via the S04
# load/run mux, so a second 245 in S02 would only duplicate (and fight) it.
# REQ and WE are driven by S11, which merges the three engine requests.

# --- glue gates ----------------------------------------------------------
U11 = add(sh, "74xx:74HC08", "U11", 80, 270, unit=1)
connect(sh, U11, {"1": "SETUP_N", "2": "RESET_N", "3": "CNT_CLR_N"}, local=True)
U11p = add(sh, "74xx:74HC08", "U11", 120, 270, unit=5)
connect(sh, U11p, {"7": "GND", "14": "+5V"}, local=True)

U12 = add(sh, "74xx:74HC04", "U12", 160, 270, unit=1)
connect(sh, U12, {"1": "WE_S", "2": "READ_I"}, local=True)
U12b = add(sh, "74xx:74HC04", "U12", 160, 295, unit=2)
connect(sh, U12b, {"3": "WAIT_MATCH_N", "4": "WAIT_MATCH"}, local=True)
U12p = add(sh, "74xx:74HC04", "U12", 205, 270, unit=7)
connect(sh, U12p, {"7": "GND", "14": "+5V"}, local=True)

# --- decoupling ----------------------------------------------------------
# U1..U12 minus U10 (removed): 11 packages, one 100 nF each.
for i in range(11):
    x = 290 + (i % 6) * 55
    y = 260 + (i // 6) * 40
    cap = add(sh, "Device:C", f"C{i+1}", x, y)
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# --- power flags ---------------------------------------------------------
for i, (net, x) in enumerate((("+5V", 680), ("GND", 720))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, 270, value=net)
    sh.add_wire(x, 270, x, 275.08)
    sh.add_power(net, x, 275.08, pwr_ref())

# --- test points ---------------------------------------------------------
TP_NETS = ["CLK", "REQ", "WE", "MEM_nCE", "MEM_nOE", "MEM_nWE",
           "MEM_ACK", "MEM_DONE", "MEM_BUSY"]
for i, net in enumerate(TP_NETS):
    tp = add(sh, "Connector:TestPoint", f"TP{i+1}", 650, 60 + i * 22, value="TP")
    gx, gy = tp.pins["1"]
    sh.add_wire(gx, gy, gx, gy + 5.08)
    sh.add_wire(gx, gy + 5.08, gx + 12.7, gy + 5.08)
    sh.add_global_label(net, gx + 12.7, gy + 5.08, 0)

# --- notes ---------------------------------------------------------------
sh.add_text(
    "State: 0 T_IDLE, 1 T_SETUP, 2 T_WAIT, 3 T_CAPTURE (read), 4 T_HOLD (write), "
    "5 T_RELEASE, 6 T_DONE.\n"
    "Read: SETUP asserts nCE/nOE; WAIT until counter==WAIT_READ; CAPTURE latches data "
    "and asserts ACK; HOLD releases nOE; RELEASE releases nCE; DONE.\n"
    "Write: SETUP asserts nCE/nWE; WAIT until counter==WAIT_WRITE; HOLD raises nWE "
    "and asserts ACK; RELEASE raises nCE; DONE.  No nOE during write.",
    20, 350, size=1.3, justify="left top",
)
sh.add_text(
    "Wait-state formula: WAIT_READ = ceil((max(tAA,tCE,tOE)+margin)/Tclk); "
    "WAIT_WRITE = ceil((tWP+tDH+margin)/Tclk).\n"
    "Default examples: 6264 read/write = 2/2; 28C256 read = 3; 27C512 read = 2. "
    "The 74HC161 free-runs and is cleared in T_SETUP; the 74HC688 compares the "
    "count with the WE-selected wait value.  Its P=R output is active-low, so U12B "
    "inverts WAIT_MATCH_N to the active-high WAIT_MATCH used by the microcode ROM. "
    "The 74HC688 outputs are active-low.  S02 is the only timing controller; "
    "REQ/WE are driven by the S11 bus fabric.  The MEM_DATA <-> DATA data path is "
    "provided by S04 U36 (74HC245), so this sheet no longer has a data transceiver.",
    20, 365, size=1.3, justify="left top",
)

sh.write(os.path.join(PROJECT_DIR, "S02_Timing.kicad_sch"))
print("wrote S02_Timing.kicad_sch")
