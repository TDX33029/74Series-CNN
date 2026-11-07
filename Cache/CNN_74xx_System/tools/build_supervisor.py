"""Build S01_Supervisor.kicad_sch (global supervisor FSM).

Run from the tools directory:
    python build_supervisor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic, write_project, write_sym_lib_table

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"

reg = default_registry()

GLOBAL = {
    "CLK", "RESET_N", "START", "IMAGE_READY", "MODEL_READY",
    "C1_DONE", "P1_DONE", "C2_DONE", "P2_DONE", "FC1_DONE", "FC2_DONE", "ARGMAX_DONE",
    "C1_START", "P1_START", "C2_START", "P2_START", "FC1_START", "FC2_START", "ARGMAX_START",
    "BUSY", "DONE", "RESULT_VALID", "ERROR",
    "ERROR_CODE0", "ERROR_CODE1", "ERROR_CODE2", "ERROR_CODE3",
    "RESULT0", "RESULT1", "RESULT2", "RESULT3",
    "RESULT_IN0", "RESULT_IN1", "RESULT_IN2", "RESULT_IN3",
    "POOL_SEL", "FC_SEL",
}

def is_global(net: str) -> bool:
    return net in GLOBAL

pwr_n = 0
def pwr_ref() -> str:
    global pwr_n
    pwr_n += 1
    return f"#PWR{pwr_n:03d}"

def connect(sh: Schematic, sym, nmap, local=True):
    """Connect every pin. nmap may be keyed by pin number or pin name."""
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

def add(sh, lib_id, ref, x, y, unit=1, value=None):
    return sh.add_symbol(
        lib_id, ref, value, x, y, unit=unit,
        footprint=footprint_for(lib_id),
    )

# ---------------------------------------------------------------------------
sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S01_Supervisor - Global Supervisor FSM", paper="A1",
)
sh.add_text(
    "S01  Global Supervisor FSM (GLOBAL_SUPERVISOR_FSM)",
    20, 16, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "16-bit microcode: state[4:0] + 11 condition inputs -> next state + control.\n"
    "State sequence: C1 -> P1 -> C2 -> P2 -> FC1 -> FC2 -> ARGMAX.  "
    "START is synchronized; BUSY/DONE/ERROR are registered outputs.",
    20, 23, size=1.5, justify="left top",
)

# --- microcode ROMs -------------------------------------------------------
ADDR = ["ST0", "ST1", "ST2", "ST3", "ST4", "START_S", "IMG_RDY_S", "MDL_RDY_S",
        "C1_DONE", "P1_DONE", "C2_DONE", "P2_DONE", "FC1_DONE", "FC2_DONE",
        "ARGMAX_DONE", "TIMEOUT_I"]

def rom_map(prefix: str):
    m = {}
    for i in range(16):
        m[f"A{i}"] = ADDR[i]
    for i in range(8):
        m[f"D{i}"] = f"{prefix}{i}"
    m["~{CE}"] = "GND"
    m["~{OE}"] = "GND"
    m["VCC"] = "+5V"
    m["GND"] = "GND"
    return m

U1 = add(sh, "Memory_EPROM:27C512", "U1", 70, 65)
connect(sh, U1, rom_map("MC"), local=True)

U2 = add(sh, "Memory_EPROM:27C512", "U2", 150, 65)
m2 = rom_map("MC")
for i in range(8):
    m2[f"D{i}"] = f"MC{8+i}"
connect(sh, U2, m2, local=True)

# --- state register -------------------------------------------------------
U3 = add(sh, "74xx:74HCT273", "U3", 240, 65)
m = {"~{Mr}": "RESET_N", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(5):
    m[f"D{i}"] = f"MC{i}"
    m[f"Q{i}"] = f"ST{i}"
for i in range(5, 8):
    m[f"D{i}"] = "GND"
    m[f"Q{i}"] = "NC"
connect(sh, U3, m, local=True)

# --- output registers -----------------------------------------------------
U4 = add(sh, "74xx:74HCT574", "U4", 320, 65)
m = {"OE": "GND", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(8):
    m[f"D{i}"] = f"MC{i}"
    m[f"Q{i}"] = f"MCR{i}"
m["Q5"] = "BUSY_I"
m["Q6"] = "DONE_I"
m["Q7"] = "RESULT_VALID_SET"
connect(sh, U4, m, local=True)

U5 = add(sh, "74xx:74HCT574", "U5", 400, 65)
m = {"OE": "GND", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(8):
    m[f"D{i}"] = f"MC{8+i}"
    m[f"Q{i}"] = f"MCR{8+i}"
m["Q0"] = "ERROR_I"
m["Q4"] = "TIMEOUT_CLR"
# Spare microcode bits 13/14 (U5 Q5/Q6) carry the pool/FC phase selects.
# POOL_SEL=1 during P2 (states 9/10); FC_SEL=1 during FC2 (states 13/14).
m["Q5"] = "POOL_SEL"
m["Q6"] = "FC_SEL"
connect(sh, U5, m, local=True)

# --- stage decoder --------------------------------------------------------
U6 = add(sh, "74xx:74HC238", "U6", 70, 160)
m = {"A0": "MCR9", "A1": "MCR10", "A2": "MCR11",
     "~{E1}": "GND", "~{E2}": "GND", "E3": "+5V",
     "VCC": "+5V", "GND": "GND"}
m["Y0"] = "NC"
for i in range(1, 8):
    m[f"Y{i}"] = f"STG{i}"
connect(sh, U6, m, local=True)

# --- error-code mux -------------------------------------------------------
U7 = add(sh, "74xx:74HC157", "U7", 150, 160)
m = {"S": "TIMEOUT_I", "E": "GND", "VCC": "+5V", "GND": "GND",
     "I0a": "+5V", "I0b": "GND", "I0c": "GND", "I0d": "GND",
     "I1a": "GND", "I1b": "+5V", "I1c": "GND", "I1d": "GND",
     "Za": "ERRCODE0", "Zb": "ERRCODE1", "Zc": "ERRCODE2", "Zd": "ERRCODE3"}
connect(sh, U7, m, local=True)

# --- stage/status buffers -------------------------------------------------
U8 = add(sh, "74xx:74HCT541", "U8", 230, 160)
m = {"G1": "GND", "G2": "GND", "VCC": "+5V", "GND": "GND"}
for i in range(7):
    m[f"A{i}"] = f"STG{i+1}"
    m[f"Y{i}"] = ["C1_START", "P1_START", "C2_START", "P2_START",
                  "FC1_START", "FC2_START", "ARGMAX_START"][i]
m["A7"] = "GND"
m["Y7"] = "NC"
connect(sh, U8, m, local=True)

U9 = add(sh, "74xx:74HCT541", "U9", 310, 160)
m = {"G1": "GND", "G2": "GND", "VCC": "+5V", "GND": "GND",
     "A0": "BUSY_I", "A1": "DONE_I", "A2": "RESULT_VALID_I", "A3": "ERROR_I",
     "A4": "ERRCODE0", "A5": "ERRCODE1", "A6": "ERRCODE2", "A7": "ERRCODE3",
     "Y0": "BUSY", "Y1": "DONE", "Y2": "RESULT_VALID", "Y3": "ERROR",
     "Y4": "ERROR_CODE0", "Y5": "ERROR_CODE1", "Y6": "ERROR_CODE2", "Y7": "ERROR_CODE3"}
connect(sh, U9, m, local=True)

# --- result latch ---------------------------------------------------------
U10 = add(sh, "74xx:74HCT574", "U10", 390, 160)
m = {"OE": "GND", "Cp": "CLK", "VCC": "+5V", "GND": "GND"}
for i in range(4):
    m[f"D{i}"] = f"RESULT_IN{i}"
    m[f"Q{i}"] = f"RESULT{i}"
for i in range(4, 8):
    m[f"D{i}"] = "GND"
    m[f"Q{i}"] = "NC"
connect(sh, U10, m, local=True)

# --- synchronizers and result-valid DFF ----------------------------------
U11 = add(sh, "74xx:74HC74", "U11", 480, 160, unit=1)
connect(sh, U11, {"~{R}": "RESET_N", "D": "START", "C": "CLK", "~{S}": "+5V",
                  "Q": "START_S1", "~{Q}": "NC"}, local=True)
U11b = add(sh, "74xx:74HC74", "U11", 480, 195, unit=2)
connect(sh, U11b, {"~{R}": "RESET_N", "D": "START_S1", "C": "CLK", "~{S}": "+5V",
                   "Q": "START_S", "~{Q}": "NC"}, local=True)
U11p = add(sh, "74xx:74HC74", "U11", 520, 160, unit=3)
connect(sh, U11p, {"VCC": "+5V", "GND": "GND"}, local=True)

U12 = add(sh, "74xx:74HC74", "U12", 70, 250, unit=1)
connect(sh, U12, {"~{R}": "RESET_N", "D": "IMAGE_READY", "C": "CLK", "~{S}": "+5V",
                  "Q": "IMG_RDY_S", "~{Q}": "NC"}, local=True)
U12b = add(sh, "74xx:74HC74", "U12", 70, 285, unit=2)
connect(sh, U12b, {"~{R}": "RESET_N", "D": "MODEL_READY", "C": "CLK", "~{S}": "+5V",
                   "Q": "MDL_RDY_S", "~{Q}": "NC"}, local=True)
U12p = add(sh, "74xx:74HC74", "U12", 110, 250, unit=3)
connect(sh, U12p, {"VCC": "+5V", "GND": "GND"}, local=True)

U13 = add(sh, "74xx:74HC74", "U13", 150, 250, unit=1)
# D = Q feedback makes this a sticky SR latch: set by G_FINISH, cleared only
# by an accepted START or RESET_N.  D=+5V would re-set on the next clock.
connect(sh, U13, {"~{R}": "RESULT_VALID_CLEAR_N", "D": "RESULT_VALID_I", "C": "CLK",
                  "~{S}": "NOT_RESULT_VALID_SET", "Q": "RESULT_VALID_I", "~{Q}": "NC"},
        local=True)
U13b = add(sh, "74xx:74HC74", "U13", 150, 285, unit=2)
connect(sh, U13b, {"~{R}": "+5V", "D": "GND", "C": "GND", "~{S}": "+5V",
                   "Q": "NC", "~{Q}": "NC"}, local=True)
U13p = add(sh, "74xx:74HC74", "U13", 190, 250, unit=3)
connect(sh, U13p, {"VCC": "+5V", "GND": "GND"}, local=True)

# --- gates ----------------------------------------------------------------
U14 = add(sh, "74xx:74HC08", "U14", 240, 250, unit=1)
connect(sh, U14, {"1": "IMG_RDY_S", "2": "MDL_RDY_S", "3": "READY_I"}, local=True)
U14b = add(sh, "74xx:74HC08", "U14", 240, 275, unit=2)
connect(sh, U14b, {"4": "IDLE_MATCH", "5": "START_S", "6": "ACCEPT_A"}, local=True)
U14c = add(sh, "74xx:74HC08", "U14", 240, 300, unit=3)
connect(sh, U14c, {"9": "ACCEPT_A", "10": "READY_I", "8": "ACCEPT_I"}, local=True)
U14d = add(sh, "74xx:74HC08", "U14", 240, 325, unit=4)
connect(sh, U14d, {"12": "NOT_ACCEPT", "13": "RESET_N", "11": "RESULT_VALID_CLEAR_N"}, local=True)
U14p = add(sh, "74xx:74HC08", "U14", 280, 250, unit=5)
connect(sh, U14p, {"7": "GND", "14": "+5V"}, local=True)

U15 = add(sh, "74xx:74HC32", "U15", 320, 250, unit=1)
connect(sh, U15, {"1": "MATCH0", "2": "MATCH1", "3": "TIMEOUT_A"}, local=True)
U15b = add(sh, "74xx:74HC32", "U15", 320, 275, unit=2)
connect(sh, U15b, {"4": "TIMEOUT_A", "5": "MATCH2", "6": "TIMEOUT_N"}, local=True)
U15c = add(sh, "74xx:74HC32", "U15", 320, 300, unit=3)
connect(sh, U15c, {"9": "GND", "10": "GND", "8": "NC"}, local=True)
U15d = add(sh, "74xx:74HC32", "U15", 320, 325, unit=4)
connect(sh, U15d, {"12": "GND", "13": "GND", "11": "NC"}, local=True)
U15p = add(sh, "74xx:74HC32", "U15", 360, 250, unit=5)
connect(sh, U15p, {"7": "GND", "14": "+5V"}, local=True)

U16 = add(sh, "74xx:74HC04", "U16", 400, 250, unit=1)
connect(sh, U16, {"1": "RESULT_VALID_SET", "2": "NOT_RESULT_VALID_SET"}, local=True)
U16b = add(sh, "74xx:74HC04", "U16", 400, 275, unit=2)
connect(sh, U16b, {"3": "ACCEPT_I", "4": "NOT_ACCEPT"}, local=True)
U16c = add(sh, "74xx:74HC04", "U16", 400, 300, unit=3)
connect(sh, U16c, {"5": "RESET_N", "6": "NOT_RESET_N"}, local=True)
U16d = add(sh, "74xx:74HC04", "U16", 400, 325, unit=4)
connect(sh, U16d, {"9": "TIMEOUT_CLR", "8": "NOT_TIMEOUT_CLR"}, local=True)
U16e = add(sh, "74xx:74HC04", "U16", 400, 350, unit=5)
connect(sh, U16e, {"11": "TIMEOUT_N", "10": "TIMEOUT_I"}, local=True)
U16f = add(sh, "74xx:74HC04", "U16", 400, 375, unit=6)
connect(sh, U16f, {"13": "IDLE_N", "12": "IDLE_MATCH"}, local=True)
U16p = add(sh, "74xx:74HC04", "U16", 440, 250, unit=7)
connect(sh, U16p, {"7": "GND", "14": "+5V"}, local=True)

# --- state == G_IDLE comparator ------------------------------------------
U17 = add(sh, "74xx:74HC688", "U17", 480, 250)
m = {"G": "GND", "P=R": "IDLE_N", "VCC": "+5V", "GND": "GND",
     "P0": "GND", "P1": "+5V"}
for i in range(2, 8):
    m[f"P{i}"] = "GND"
for i in range(5):
    m[f"R{i}"] = f"ST{i}"
for i in range(5, 8):
    m[f"R{i}"] = "GND"
connect(sh, U17, m, local=True)

# --- 24-bit timeout counter ----------------------------------------------
COUNTERS = []
for i in range(6):
    x = 70 + i * 70
    u = add(sh, "74xx:74HC161", f"U{18+i}", x, 400)
    m = {"~{MR}": "RESET_N", "CP": "CLK", "~{PE}": "NOT_TIMEOUT_CLR",
         "CEP": "BUSY_I", "VCC": "+5V", "GND": "GND"}
    for b in range(4):
        m[f"D{b}"] = "GND"
        m[f"Q{b}"] = f"TC{4*i+b}"
    if i == 0:
        m["CET"] = "BUSY_I"
    else:
        m["CET"] = f"TC_CARRY{i-1}"
    if i < 5:
        m["TC"] = f"TC_CARRY{i}"
    else:
        m["TC"] = "NC"
    connect(sh, u, m, local=True)
    COUNTERS.append(u)

# --- 24-bit timeout comparators ------------------------------------------
for i in range(3):
    x = 500 + i * 80
    u = add(sh, "74xx:74HC688", f"U{24+i}", x, 400)
    m = {"G": "GND", "P=R": f"MATCH{i}", "VCC": "+5V", "GND": "GND"}
    for b in range(8):
        m[f"P{b}"] = "+5V"
        m[f"R{b}"] = f"TC{8*i+b}"
    connect(sh, u, m, local=True)

# --- decoupling bank ------------------------------------------------------
for i in range(27):
    x = 35 + (i % 14) * 55
    y = 480 + (i // 14) * 40
    cap = add(sh, "Device:C", f"C{i+1}", x, y)
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# --- test points ----------------------------------------------------------
for i, net in enumerate(("CLK", "RESET_N", "START", "BUSY", "DONE", "ERROR", "RESULT_VALID")):
    tp = add(sh, "Connector:TestPoint", f"TP{i+1}", 700, 60 + i * 25, value="TP")
    gx, gy = tp.pins["1"]
    sh.add_wire(gx, gy, gx, gy + 5.08)
    sh.add_wire(gx, gy + 5.08, gx + 15.24, gy + 5.08)
    sh.add_global_label(net, gx + 15.24, gy + 5.08, 0)

# --- power flags ----------------------------------------------------------
for i, (net, x) in enumerate((("+5V", 700), ("GND", 760))):
    flag = add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, 500, value=net)
    sh.add_wire(x, 500, x, 505.08)
    sh.add_power(net, x, 505.08, pwr_ref())

# --- notes ---------------------------------------------------------------

sh.add_text(
    "State table (5-bit): 0 RESET, 1 WAIT_READY, 2 IDLE, 3 C1_START, 4 C1_WAIT, "
    "5 P1_START, 6 P1_WAIT, 7 C2_START, 8 C2_WAIT, 9 P2_START, 10 P2_WAIT, "
    "11 FC1_START, 12 FC1_WAIT, 13 FC2_START, 14 FC2_WAIT, 15 ARGMAX_START, "
    "16 ARGMAX_WAIT, 17 FINISH, 18 WAIT_START_LOW, 19 ERROR.",
    20, 540, size=1.3, justify="left top",
)
sh.add_text(
    "Microcode address: A[4:0]=state, A5=START_S, A6=IMAGE_READY_S, A7=MODEL_READY_S, "
    "A8..A14=C1/P1/C2/P2/FC1/FC2/ARGMAX done, A15=TIMEOUT.\n"
    "Microcode data: [4:0]=next state, 5=BUSY, 6=DONE, 7=RESULT_VALID_SET, 8=ERROR, "
    "[11:9]=STAGE_CODE, 12=TIMEOUT_CLR, 13=POOL_SEL, 14=FC_SEL, 15=spare.\n"
    "POOL_SEL is high in P2 (states 9/10); FC_SEL is high in FC2 (states 13/14); "
    "both are held through the matching WAIT state so S05/S09 keep the phase.\n"
    "TIMEOUT_CLR is active-high in microcode; U16D inverts it for the 74HC161 ~PE input.\n"
    "The 74HC688 outputs are active-low: U16E/U16F convert TIMEOUT_N and IDLE_N to active-high TIMEOUT_I/IDLE_MATCH.",
    20, 550, size=1.3, justify="left top",
)
sh.add_text(
    "Timeout: 24-bit counter (U18..U23) counts while BUSY; compares to 0xFFFFFF with "
    "U24..U26.  At 8 MHz the limit is ~2.1 s for the whole inference; a per-stage "
    "limit can be obtained by splitting TIMEOUT_CLR per stage.",
    20, 565, size=1.3, justify="left top",
)

sh.write(os.path.join(PROJECT_DIR, "S01_Supervisor.kicad_sch"))
print("wrote S01_Supervisor.kicad_sch")
