"""Build S10_Top_IO.kicad_sch (clock, reset, start, load port, status I/O).

Run from the tools directory:
    python build_top_io.py

Contents:
  * 8.000 MHz active oscillator + external-clock connector and select jumper
  * RC + 74HC04 power-on reset supervisor with push button
  * START two-stage synchronizer (74HC74)
  * combined image / parameter load port (J_IMG 2x16, J_PARAM 2x20) with
    74HCT541 address/control buffers and a 74HCT245 data transceiver
  * status buffers (74HCT541 x2), LEDs and J_STATUS header
  * power entry, bulk/decoupling capacitors, test points
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
KICAD_SYMBOLS = r"C:/Program Files/KiCad/10.0/share/kicad/symbols"

reg = default_registry()
reg.add_library("Connector_Generic", KICAD_SYMBOLS + "/Connector_Generic.kicad_sym")
reg.add_library("Switch", KICAD_SYMBOLS + "/Switch.kicad_sym")
reg.add_library("Oscillator", KICAD_SYMBOLS + "/Oscillator.kicad_sym")
# 74HCT245 is pin-compatible with the 74HC245 symbol and is missing from the
# stock library; derive it the same way the project derives other HC parts.
reg.add_alias("74xx", "74xx", "74HC245", "74HCT245")

# Switch:SW_Push has its pins on the common (unit 0) body.
for _p in reg.get("Switch:SW_Push").pins:
    _p.unit = 1

GLOBAL = {
    "CLK", "RESET_N", "START",
    "IMAGE_READY", "MODEL_READY",
    "BUSY", "DONE", "RESULT_VALID", "ERROR",
    "RESULT0", "RESULT1", "RESULT2", "RESULT3",
    "ERROR_CODE0", "ERROR_CODE1", "ERROR_CODE2", "ERROR_CODE3",
    "ADDR0", "ADDR1", "ADDR2", "ADDR3", "ADDR4", "ADDR5", "ADDR6", "ADDR7",
    "ADDR8", "ADDR9", "ADDR10", "ADDR11", "ADDR12", "ADDR13", "ADDR14", "ADDR15",
    "ADDR16", "ADDR17", "ADDR18", "ADDR19", "ADDR20", "ADDR21", "ADDR22", "ADDR23",
    "LOAD_DATA0", "LOAD_DATA1", "LOAD_DATA2", "LOAD_DATA3",
    "LOAD_DATA4", "LOAD_DATA5", "LOAD_DATA6", "LOAD_DATA7",
    "MEM_SEL0", "MEM_SEL1", "MEM_SEL2", "MEM_SEL3", "MEM_SEL4",
    "LOAD_EN", "LOAD_nOE", "LOAD_nWE",
    "IMAGE_DONE_N", "MODEL_DONE_N",
}

def is_global(net: str) -> bool:
    return net in GLOBAL

_pwr = 0
def pwr_ref() -> str:
    global _pwr
    _pwr += 1
    return f"#PWR{_pwr:04d}"

FOOT = {
    "Connector_Generic:Conn_01x02": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "Connector_Generic:Conn_01x03": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    "Connector_Generic:Conn_02x02_Odd_Even": "Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical",
    "Connector_Generic:Conn_02x10_Odd_Even": "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical",
    "Connector_Generic:Conn_02x16_Odd_Even": "Connector_PinHeader_2.54mm:PinHeader_2x16_P2.54mm_Vertical",
    "Connector_Generic:Conn_02x20_Odd_Even": "Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical",
    "Connector_Generic:Conn_02x32_Odd_Even": "Connector_PinHeader_2.54mm:PinHeader_2x32_P2.54mm_Vertical",
    "Connector:TestPoint": "TestPoint:TestPoint_Pad_D1.5mm",
    "Switch:SW_Push": "Button_Switch_THT:SW_PUSH_6mm",
    "Oscillator:ASE-xxxMHz": "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
    "Device:R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
    "Device:R_Network08": "Resistor_THT:R_Array_SIP9",
    "Device:LED": "LED_THT:LED_D5.0mm",
    "Device:C": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
    "74xx:74HCT245": "Package_DIP:DIP-20_W7.62mm",
}

def add(sh, lib_id, ref, x, y, unit=1, value=None, desc=""):
    return sh.add_symbol(
        lib_id, ref, value, x, y, unit=unit,
        footprint=FOOT.get(lib_id, footprint_for(lib_id)), description=desc,
    )

def connect(sh, sym, nmap):
    for num, p in sym.pin_objs.items():
        net = nmap.get(num, nmap.get(p.name))
        if net is None:
            if p.name in ("VCC", "Vdd", "VCC"):
                net = "+5V"
            elif p.name == "GND":
                net = "GND"
            elif p.etype == "no_connect":
                continue
            else:
                net = "NC"
        if net == "SKIP":
            continue
        if net == "NC":
            sh.stub_nc(sym, num)
        elif net in ("+5V", "GND"):
            sh.stub_power(sym, num, net, pwr_ref())
        else:
            sh.stub_label(sym, num, net, local=not is_global(net))

def add_gate(sh, lib_id, ref, unit, x, y, nmap, value=None):
    s = add(sh, lib_id, ref, x, y, unit=unit, value=value)
    connect(sh, s, nmap)
    return s

def resistor(sh, ref, x, y, net_top, net_bottom, value="10k", desc=""):
    r = add(sh, "Device:R", ref, x, y, value=value, desc=desc or f"Resistor {ref}")
    for pin, net in (("1", net_top), ("2", net_bottom)):
        if net in ("+5V", "GND"):
            sh.stub_power(r, pin, net, pwr_ref())
        else:
            sh.stub_label(r, pin, net, local=not is_global(net))
    return r

# ---------------------------------------------------------------------------
sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S10_Top_IO - Clock, Reset, Load Port and Status I/O",
    paper="A1",
)
sh.add_text(
    "S10  Top-Level I/O: 8 MHz clock, reset supervisor, START, load/program port, status",
    20, 16, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "CLK = 8.000 MHz from X1 (ASE-xxxMHz) or an external clock at J_CLK, selected by JP1.\n"
    "RESET_N is generated by the R1/C90 power-on network and SW1/J_RESET; U70A/B square it up.\n"
    "JP1 must always be fitted: 1-2 = internal oscillator, 2-3 = external clock.",
    20, 24, size=1.35, justify="left top",
)

# ---------------------------------------------------------------------------
# Clock generation and selection
# ---------------------------------------------------------------------------
X1 = add(sh, "Oscillator:ASE-xxxMHz", "X1", 60, 70, value="8.000MHz",
         desc="8.000 MHz active oscillator")
connect(sh, X1, {"EN": "+5V", "GND": "GND", "OUT": "OSC_OUT", "Vdd": "+5V"})

JP1 = add(sh, "Connector_Generic:Conn_01x03", "JP1", 150, 55,
          value="CLK_SEL", desc="Clock select jumper")
connect(sh, JP1, {"1": "OSC_OUT", "2": "CLK_SEL", "3": "EXT_CLK_IN"})

J_CLK = add(sh, "Connector_Generic:Conn_01x02", "J4", 150, 95,
            value="EXT_CLK", desc="External clock input")
connect(sh, J_CLK, {"1": "EXT_CLK_IN", "2": "GND"})

resistor(sh, "R3", 105, 55, "CLK_SEL", "GND", desc="CLK_SEL pull-down")
resistor(sh, "R4", 105, 95, "EXT_CLK_IN", "GND", desc="EXT_CLK_IN pull-down")

add_gate(sh, "74xx:74HC04", "U70", 5, 230, 70,
         {"11": "CLK_SEL", "10": "CLK_BUF"}, value="74HC04")
resistor(sh, "R5", 300, 70, "CLK_BUF", "CLK", value="33",
         desc="Clock series damping resistor")

# ---------------------------------------------------------------------------
# Reset supervisor (RC + 74HC04 + push button + external reset header)
# ---------------------------------------------------------------------------
resistor(sh, "R1", 60, 140, "+5V", "RESET_RAW", value="100k",
         desc="Reset RC pull-up")
C90 = add(sh, "Device:C", "C90", 100, 140, value="1u",
          desc="Reset RC capacitor")
sh.stub_label(C90, "1", "RESET_RAW", local=True)
sh.stub_power(C90, "2", "GND", pwr_ref())

SW1 = add(sh, "Switch:SW_Push", "SW1", 60, 175, value="RESET",
          desc="Manual reset button")
connect(sh, SW1, {"1": "RESET_RAW", "2": "GND"})

J_RESET = add(sh, "Connector_Generic:Conn_01x02", "J3", 150, 175,
              value="RESET", desc="External reset input")
connect(sh, J_RESET, {"1": "RESET_RAW", "2": "GND"})

add_gate(sh, "74xx:74HC04", "U70", 1, 230, 140,
         {"1": "RESET_RAW", "2": "RESET_RAW_H"})
add_gate(sh, "74xx:74HC04", "U70", 2, 300, 140,
         {"3": "RESET_RAW_H", "4": "RESET_N"})

# ---------------------------------------------------------------------------
# START input and two-stage synchronizer
# ---------------------------------------------------------------------------
J_START = add(sh, "Connector_Generic:Conn_01x02", "J2", 60, 220,
              value="START", desc="Start input")
connect(sh, J_START, {"1": "START_RAW", "2": "GND"})
resistor(sh, "R2", 110, 220, "START_RAW", "GND", desc="START pull-down")

U91 = add(sh, "74xx:74HC74", "U91", 210, 220, unit=1, value="74HC74",
          desc="START synchronizer stage 1")
connect(sh, U91, {"~{R}": "RESET_N", "D": "START_RAW", "C": "CLK",
                  "~{S}": "+5V", "Q": "START_S1", "~{Q}": "NC"})
U91b = add(sh, "74xx:74HC74", "U91", 290, 220, unit=2, value="74HC74",
           desc="START synchronizer stage 2")
connect(sh, U91b, {"~{R}": "RESET_N", "D": "START_S1", "C": "CLK",
                   "~{S}": "+5V", "Q": "START", "~{Q}": "NC"})
add_gate(sh, "74xx:74HC74", "U91", 3, 360, 220,
         {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Load/program buffers: data (74HCT245), address and control (74HCT541 x4)
# ---------------------------------------------------------------------------
U92 = add(sh, "74xx:74HCT245", "U92", 230, 330, value="74HCT245",
          desc="Load-port data transceiver H_D <-> LOAD_DATA")
m = {"A->B": "LOAD_nOE", "CE": "NOT_LOAD_EN"}
for i in range(8):
    m[f"A{i}"] = f"H_D{i}"
    m[f"B{i}"] = f"LOAD_DATA{i}"
connect(sh, U92, m)

U93 = add(sh, "74xx:74HCT541", "U93", 330, 330, value="74HCT541",
          desc="Load address buffer A[7:0]")
m = {"G1": "NOT_LOAD_EN", "G2": "NOT_LOAD_EN"}
for i in range(8):
    m[f"A{i}"] = f"H_A{i}"
    m[f"Y{i}"] = f"ADDR{i}"
connect(sh, U93, m)

U94 = add(sh, "74xx:74HCT541", "U94", 430, 330, value="74HCT541",
          desc="Load address buffer A[15:8]")
m = {"G1": "NOT_LOAD_EN", "G2": "NOT_LOAD_EN"}
for i in range(8):
    m[f"A{i}"] = f"H_A{8+i}"
    m[f"Y{i}"] = f"ADDR{8+i}"
connect(sh, U94, m)

U95 = add(sh, "74xx:74HCT541", "U95", 530, 330, value="74HCT541",
          desc="Load address tag buffer ADDR[23:16] = {GND,GND,GND,MEM_SEL[4:0]}")
m = {"G1": "NOT_LOAD_EN", "G2": "NOT_LOAD_EN"}
for i in range(5):
    m[f"A{i}"] = f"MEM_SEL{i}"
    m[f"Y{i}"] = f"ADDR{16+i}"
for i in range(5, 8):
    m[f"A{i}"] = "GND"
    m[f"Y{i}"] = f"ADDR{16+i}"
connect(sh, U95, m)

U96 = add(sh, "74xx:74HCT541", "U96", 630, 330, value="74HCT541",
          desc="Load MEM_SEL and WE/OE buffer")
m = {"G1": "NOT_LOAD_EN", "G2": "NOT_LOAD_EN"}
for i in range(5):
    m[f"A{i}"] = f"H_MEM_SEL{i}"
    m[f"Y{i}"] = f"MEM_SEL{i}"
m["A5"] = "H_LOAD_nWE"
m["Y5"] = "LOAD_nWE"
m["A6"] = "H_LOAD_nOE"
m["Y6"] = "LOAD_nOE"
m["A7"] = "GND"
m["Y7"] = "NC"
connect(sh, U96, m)

add_gate(sh, "74xx:74HC04", "U70", 3, 380, 140,
         {"5": "LOAD_EN", "6": "NOT_LOAD_EN"})
add_gate(sh, "74xx:74HC04", "U70", 4, 450, 140,
         {"9": "GND", "8": "NC"})
add_gate(sh, "74xx:74HC04", "U70", 6, 520, 140,
         {"13": "GND", "12": "NC"})
add_gate(sh, "74xx:74HC04", "U70", 7, 590, 140,
         {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Expansion-board port J8 (2x32, one IDC ribbon)
#
# Replaces the former J5 (image, 2x16), J6 (params, 2x20) and J7 (status, 2x10)
# trio.  The three old headers carried the same H_D[7:0] bus and the same
# LOAD_EN / LOAD_nWE / LOAD_nOE control lines, so merging them keeps every
# function and only removes the duplicated pins.  Address grows from 15 to 16
# bits (A15 was already buffered by U94), and START/RESET move here from their
# separate 1x02/2x02 headers so the expansion board needs a single cable.
#
#   1,2      GND
#   3..10    H_D0..H_D7
#   11..26   H_A0..H_A15
#   27..31   H_MEM_SEL0..4
#   32       LOAD_EN          (host drives 1 to isolate the system)
#   33       H_LOAD_nWE
#   34       H_LOAD_nOE
#   35       IMAGE_DONE_N      (pulse low after the 784-byte image is written)
#   36       MODEL_DONE_N      (pulse low after the weight images are written)
#   37       START_RAW         (same node as J2, synchronised by U91)
#   38       RESET_RAW         (same node as SW1/J3; drive open-drain)
#   39       ST_BUSY
#   40       ST_DONE
#   41       ST_RESULT_VALID
#   42       ST_ERROR
#   43..46   ST_RESULT0..3
#   47..50   ST_ERROR_CODE0..3
#   51       ST_IMAGE_READY
#   52       ST_MODEL_READY
#   53..56   +5V
#   57..64   GND
# ---------------------------------------------------------------------------
J8 = add(sh, "Connector_Generic:Conn_02x32_Odd_Even", "J8", 70, 360,
         value="EXPANSION", desc="Expansion-board port: load, start, reset, status")
jm = {"1": "GND", "2": "GND"}
for i in range(8):
    jm[str(3 + i)] = f"H_D{i}"
for i in range(16):
    jm[str(11 + i)] = f"H_A{i}"
for i in range(5):
    jm[str(27 + i)] = f"H_MEM_SEL{i}"
jm.update({
    "32": "LOAD_EN", "33": "H_LOAD_nWE", "34": "H_LOAD_nOE",
    "35": "IMAGE_DONE_N", "36": "MODEL_DONE_N",
    "37": "START_RAW", "38": "RESET_RAW",
    "39": "ST_BUSY", "40": "ST_DONE", "41": "ST_RESULT_VALID", "42": "ST_ERROR",
    "43": "ST_RESULT0", "44": "ST_RESULT1", "45": "ST_RESULT2", "46": "ST_RESULT3",
    "47": "ST_ERROR_CODE0", "48": "ST_ERROR_CODE1",
    "49": "ST_ERROR_CODE2", "50": "ST_ERROR_CODE3",
    "51": "ST_IMAGE_READY", "52": "ST_MODEL_READY",
    "53": "+5V", "54": "+5V", "55": "+5V", "56": "+5V",
    "57": "GND", "58": "GND", "59": "GND", "60": "GND",
    "61": "GND", "62": "GND", "63": "GND", "64": "GND",
})
connect(sh, J8, jm)

# ---------------------------------------------------------------------------
# Host-side pull resistors
# ---------------------------------------------------------------------------
resistor(sh, "R6", 480, 440, "LOAD_EN", "GND", desc="LOAD_EN pull-down")
resistor(sh, "R7", 520, 440, "+5V", "H_LOAD_nWE", desc="H_LOAD_nWE pull-up")
resistor(sh, "R8", 560, 440, "+5V", "H_LOAD_nOE", desc="H_LOAD_nOE pull-up")
resistor(sh, "R9", 600, 440, "+5V", "IMAGE_DONE_N", desc="IMAGE_DONE_N pull-up")
resistor(sh, "R10", 640, 440, "+5V", "MODEL_DONE_N", desc="MODEL_DONE_N pull-up")
for i in range(5):
    resistor(sh, f"R{11+i}", 690 + i * 28, 440, f"H_MEM_SEL{i}", "GND",
             desc=f"H_MEM_SEL{i} pull-down")

# 16 host address pull-downs (H_A0..H_A15), two bussed 10k networks to GND.
# The upper tag byte is generated on-board from MEM_SEL, so it is not a host
# input and needs no pull-down network.
for k, rn in enumerate(("RN1", "RN2")):
    r = add(sh, "Device:R_Network08", rn, 250 + k * 80, 430, value="10k",
            desc=f"Host address pull-down network A[{8*k+7}:{8*k}]")
    sh.stub_power(r, "1", "GND", pwr_ref())
    for j in range(8):
        sh.stub_label(r, str(2 + j), f"H_A{8*k + j}", local=True)

# ---------------------------------------------------------------------------
# Status buffers, LEDs and status header
# ---------------------------------------------------------------------------
U97 = add(sh, "74xx:74HCT541", "U97", 450, 230, value="74HCT541",
          desc="BUSY/DONE/RESULT status buffer")
m = {"G1": "GND", "G2": "GND",
     "A0": "BUSY", "A1": "DONE", "A2": "RESULT_VALID", "A3": "ERROR",
     "A4": "RESULT0", "A5": "RESULT1", "A6": "RESULT2", "A7": "RESULT3",
     "Y0": "ST_BUSY", "Y1": "ST_DONE", "Y2": "ST_RESULT_VALID", "Y3": "ST_ERROR",
     "Y4": "ST_RESULT0", "Y5": "ST_RESULT1", "Y6": "ST_RESULT2", "Y7": "ST_RESULT3"}
connect(sh, U97, m)

U98 = add(sh, "74xx:74HCT541", "U98", 550, 230, value="74HCT541",
          desc="ERROR_CODE/READY status buffer")
m = {"G1": "GND", "G2": "GND",
     "A0": "ERROR_CODE0", "A1": "ERROR_CODE1", "A2": "ERROR_CODE2", "A3": "ERROR_CODE3",
     "A4": "IMAGE_READY", "A5": "MODEL_READY", "A6": "GND", "A7": "GND",
     "Y0": "ST_ERROR_CODE0", "Y1": "ST_ERROR_CODE1",
     "Y2": "ST_ERROR_CODE2", "Y3": "ST_ERROR_CODE3",
     "Y4": "ST_IMAGE_READY", "Y5": "ST_MODEL_READY", "Y6": "NC", "Y7": "NC"}
connect(sh, U98, m)

# The former J7 status header is merged into J8 (pins 39..52); the ST_* nets
# still drive the LEDs below.

LEDS = [
    ("D1", "PWR",         None),
    ("D2", "BUSY",        "ST_BUSY"),
    ("D3", "DONE",        "ST_DONE"),
    ("D4", "RESULT_VALID","ST_RESULT_VALID"),
    ("D5", "ERROR",       "ST_ERROR"),
    ("D6", "IMAGE_READY", "ST_IMAGE_READY"),
    ("D7", "MODEL_READY", "ST_MODEL_READY"),
]
for i, (ref, name, net) in enumerate(LEDS):
    y = 45 + i * 20
    rr = f"R{16+i}"
    r = add(sh, "Device:R", rr, 620, y, value="470",
            desc=f"{name} LED resistor")
    if net is None:
        sh.stub_power(r, "1", "+5V", pwr_ref())
        sh.stub_label(r, "2", "LED_PWR", local=True)
        anode_net = "LED_PWR"
    else:
        sh.stub_label(r, "1", net, local=True)
        sh.stub_label(r, "2", f"LED_{name}", local=True)
        anode_net = f"LED_{name}"
    led = add(sh, "Device:LED", ref, 680, y, value=name.lower(),
              desc=f"{name} indicator")
    sh.stub_label(led, "2", anode_net, local=True)
    sh.stub_power(led, "1", "GND", pwr_ref())

# ---------------------------------------------------------------------------
# Power entry, bulk capacitors and power flags
# ---------------------------------------------------------------------------
J_PWR = add(sh, "Connector_Generic:Conn_02x02_Odd_Even", "J1", 70, 510,
            value="+5V", desc="Power entry")
connect(sh, J_PWR, {"1": "+5V", "2": "GND", "3": "+5V", "4": "GND"})

for ref, x, val, desc in (
    ("C91", 150, "10u", "Bulk capacitor"),
    ("C92", 190, "100n", "Bulk decoupling"),
):
    c = add(sh, "Device:C", ref, x, 510, value=val, desc=desc)
    sh.stub_power(c, "1", "+5V", pwr_ref())
    sh.stub_power(c, "2", "GND", pwr_ref())

for i, (net, x, y) in enumerate((("+5V", 230, 500), ("GND", 260, 500))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, y, value=net)
    sh.add_wire(x, y, x, y + 5.08)
    sh.add_power(net, x, y + 5.08, pwr_ref())

# One 100 nF decoupling capacitor per IC (10 ICs: X1, U70, U91, U92..U98).
for i in range(10):
    x, y = 310 + i * 48, 510
    cap = add(sh, "Device:C", f"C{i+1}", x, y, value="100n",
              desc="Decoupling capacitor")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# ---------------------------------------------------------------------------
# Test points
# ---------------------------------------------------------------------------
TP_NETS = ["CLK", "RESET_N", "START", "IMAGE_READY", "MODEL_READY",
           "BUSY", "DONE", "RESULT_VALID", "ERROR", "LOAD_EN"]
for i, net in enumerate(TP_NETS):
    tp = add(sh, "Connector:TestPoint", f"TP{i+1}", 790, 275 + i * 15,
             value="TP", desc=f"Test point {net}")
    gx, gy = tp.pins["1"]
    sh.add_wire(gx, gy, gx, gy + 5.08)
    sh.add_wire(gx, gy + 5.08, gx + 15.24, gy + 5.08)
    sh.add_global_label(net, gx + 15.24, gy + 5.08, 0)

# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
sh.add_text(
    "Expansion port J8 (2x32) carries image load, weight load, START, RESET and status.\n"
    "LOAD_EN=1 tri-states the system path and enables U92..U96.\n"
    "U92 DIR = LOAD_nOE: 1 = host write, 0 = host read-back.  U93/U94 drive ADDR[15:0];\n"
    "U95 drives ADDR[23:16] = {GND,GND,GND,MEM_SEL[4:0]} so the S04 tag check always sees\n"
    "the memory select the host requested.  U96 drives MEM_SEL[4:0] and LOAD_nWE/nOE.\n"
    "H_A[15:0] have 10k pull-downs (RN1/RN2); H_MEM_SEL[4:0] pull-downs; controls idle high.\n"
    "J8 pin 38 is RESET_RAW (same node as SW1/J3): drive it open-drain, never push-pull.\n"
    "J8 pin 37 is START_RAW (same node as J2); U91 synchronises it to CLK.",
    20, 540, size=1.15, justify="left top",
)
sh.add_text(
    "Status: BUSY/DONE/RESULT_VALID/ERROR/RESULT[3:0]/ERROR_CODE[3:0] and the READY flags are\n"
    "buffered by U97/U98 to J_STATUS and the LEDs.  IMAGE_READY/MODEL_READY are generated in S04;\n"
    "S10 only monitors them.  Test points TP1..TP10 are on the named global nets.\n"
    "Power: +5 V from J_PWR, 10 uF + 100 nF bulk, one 100 nF per IC.",
    20, 558, size=1.15, justify="left top",
)

sh.write(os.path.join(PROJECT_DIR, "S10_Top_IO.kicad_sch"))
print("wrote S10_Top_IO.kicad_sch")
