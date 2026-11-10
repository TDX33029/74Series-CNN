"""Build S04_Memories.kicad_sch (27-device memory array + decode + load port).

Run from the tools directory:
    python build_memories.py

Memory map (per-device 64 KB window, ADDR[23:16] = MEM_SEL index):
    0x00xxxx INPUT_SRAM      0x01xxxx CONV1_OUT_SRAM  0x02xxxx POOL1_OUT_SRAM
    0x03xxxx CONV2_OUT_SRAM  0x04xxxx POOL2_OUT_SRAM  0x05xxxx FC1_OUT_SRAM
    0x06xxxx FC2_LOGITS_SRAM
    0x08xxxx W_CONV1         0x09xxxx W_CONV2          0x0Axxxx W_FC1   0x0Bxxxx W_FC2
    (0x0C..0x13: former bias / qparam windows, now reserved and unpopulated)
    0x14xxxx LUT0_LO         0x15xxxx LUT0_HI          0x16xxxx LUT1_LO 0x17xxxx LUT1_HI
    0x18xxxx LUT2_LO         0x19xxxx LUT2_HI          0x1Axxxx LUT3_LO 0x1Bxxxx LUT3_HI

Each device has its own active-low chip select; the 74HC138 decoders are
qualified by MEM_nCE, LOAD_EN and a 74HC688 address-tag comparator, so at most
one device can ever be selected.  MEM_SEL[4:0] is the device index.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"

FOOT = {
    "Device:R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
}

reg = default_registry()
reg.add_library(
    "Connector_Generic",
    r"C:/Program Files/KiCad/10.0/share/kicad/symbols/Connector_Generic.kicad_sym",
)

# ---------------------------------------------------------------------------
# Interface nets (global labels).  Everything else is a sheet-local label.
# ---------------------------------------------------------------------------
GLOBAL = {
    "CLK", "RESET_N",
    "ADDR0", "ADDR1", "ADDR2", "ADDR3", "ADDR4", "ADDR5", "ADDR6", "ADDR7",
    "ADDR8", "ADDR9", "ADDR10", "ADDR11", "ADDR12", "ADDR13", "ADDR14", "ADDR15",
    "ADDR16", "ADDR17", "ADDR18", "ADDR19", "ADDR20", "ADDR21", "ADDR22", "ADDR23",
    "DATA0", "DATA1", "DATA2", "DATA3", "DATA4", "DATA5", "DATA6", "DATA7",
    "MEM_SEL0", "MEM_SEL1", "MEM_SEL2", "MEM_SEL3", "MEM_SEL4",
    "MEM_nCE", "MEM_nOE", "MEM_nWE",
    "LOAD_EN", "LOAD_nOE", "LOAD_nWE",
    "LOAD_DATA0", "LOAD_DATA1", "LOAD_DATA2", "LOAD_DATA3",
    "LOAD_DATA4", "LOAD_DATA5", "LOAD_DATA6", "LOAD_DATA7",
    "IMAGE_DONE_N", "MODEL_DONE_N", "IMAGE_READY", "MODEL_READY",
    "SCORE_ADDR0", "SCORE_ADDR1", "SCORE_ADDR2",
    "SCORE_ADDR3", "SCORE_ADDR4", "SCORE_ADDR5",
    "ARGMAX_BUSY_N",
}
# Option A: one fixed buffer set per engine board.  POOL1/POOL2 and FC1/FC2 are
# separate boards, so each gets its own tri-state merge buffers on S04.
for _p in (1, 2):
    GLOBAL.add(f"POOL{_p}_MEM_WE")
    GLOBAL.add(f"POOL{_p}_BUSY_N")
    GLOBAL.add(f"POOL{_p}_MEM_nCE_OUT")
    for _i in range(13):
        GLOBAL.add(f"POOL{_p}_IN_ADDR{_i}")
    for _i in range(12):
        GLOBAL.add(f"POOL{_p}_OUT_ADDR{_i}")
    for _i in range(8):
        GLOBAL.add(f"POOL{_p}_OUT_DATA{_i}")
# Engine address buses and their address-buffer enables (S07/S08/S09/S17 -> S04).
for _eng in ("C1", "C2", "FC1", "FC2"):
    GLOBAL.add(f"{_eng}_BUSY_N")
    for _i in range(16):
        GLOBAL.add(f"{_eng}_ADDR{_i}")

def is_global(net: str) -> bool:
    return net in GLOBAL

_pwr = 0
def pwr_ref() -> str:
    global _pwr
    _pwr += 1
    return f"#PWR{_pwr:04d}"

def add(sh, lib_id, ref, x, y, unit=1, value=None, desc="", footprint=None):
    return sh.add_symbol(
        lib_id, ref, value, x, y, unit=unit,
        footprint=footprint if footprint is not None else FOOT.get(lib_id, footprint_for(lib_id)),
        description=desc,
    )

def connect(sh, sym, nmap):
    """Connect every visible pin.  nmap is keyed by pin number or pin name."""
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

# The 6264 symbol has VCC/GND on the common (unit 0) body.  The generator
# places one unit at a time, so promote them to unit 1 to have them wired.
_d6264 = reg.get("Memory_RAM:HY6264AxP")
for _p in _d6264.pins:
    _p.unit = 1

# ---------------------------------------------------------------------------
sh = Schematic(
    reg, project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S04_Memories - CNN Memory Array, Chip-Select Decode and Load Port",
    paper="A1",
)
sh.add_text(
    "S04  Memory Array (7x 6264 feature SRAM, 4x 62256 weight SRAM, 8x W27C512 LUT ROM)",
    20, 16, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "Independent chip select and independent 64 KB address window per device; no address multiplexing.\n"
    "Device n occupies 0x{n:02X}0000..0x{n:02X}FFFF; ADDR[15:0] is the window offset and ADDR[23:16] must equal MEM_SEL.\n"
    "MEM_SEL 0..6 = feature SRAM, 8..11 = weights (SRAM, reloaded from SD at power-up), 20..27 = LUT pairs.\n"
    "12..15 (bias) and 16..19 (qparam) are reserved holes: the V2 requant has no bias adder and no zero point.",
    20, 24, size=1.35, justify="left top",
)

# ---------------------------------------------------------------------------
# Row 1: seven 6264 feature SRAMs
# ---------------------------------------------------------------------------
SRAM = [
    ("U1", "INPUT",        "SRAM0_INPUT"),
    ("U2", "CONV1_OUT",    "SRAM1_C1OUT"),
    ("U3", "POOL1_OUT",    "SRAM2_P1OUT"),
    ("U4", "CONV2_OUT",    "SRAM3_C2OUT"),
    ("U5", "POOL2_OUT",    "SRAM4_P2OUT"),
    ("U6", "FC1_OUT",      "SRAM5_FC1OUT"),
    ("U7", "FC2_LOGITS",   "SRAM6_FC2LOG"),
]
CS_SRAM = [
    "nCS_SRAM_INPUT", "nCS_SRAM_C1OUT", "nCS_SRAM_P1OUT", "nCS_SRAM_C2OUT",
    "nCS_SRAM_P2OUT", "nCS_SRAM_FC1OUT", "nCS_SRAM_FC2LOG",
]

def place_6264(ref, x, y, cs, desc):
    s = add(sh, "Memory_RAM:HY6264AxP", ref, x, y, value="6264",
            desc=f"8Kx8 SRAM {desc}")
    m = {
        "~{CS1}": cs,
        "CS2": "+5V",
        "~{OE}": "MEM_nOE_INT",
        "~{WE}": "MEM_nWE_INT",
    }
    for num, p in s.pin_objs.items():
        if p.name.startswith("A") and p.name[1:].isdigit():
            m[num] = f"MADDR{int(p.name[1:])}"
        elif p.name.startswith("I/O") and p.name[3:].isdigit():
            m[num] = f"MEM_D{int(p.name[3:])}"
    connect(sh, s, m)
    return s

for i, (ref, name, desc) in enumerate(SRAM):
    place_6264(ref, 55 + i * 70, 70, CS_SRAM[i], name)

# ---------------------------------------------------------------------------
# Row 2: 4 weight SRAMs (32K x 8, DIP-28)
#
# These are volatile on purpose.  The expansion board reloads them from the SD
# card at every power-up through the J8 load port, so the model is swappable
# without a programmer.  62256 is pin-identical to the 28C256 it replaces
# (1=A14, 20=/CE, 22=/OE, 27=/WE), which is why the netlist does not change.
#
# The bias and qparam banks (former U12..U19) are gone: the V2 requant is
# Q = clamp(ACC >> S, 0, 255) with no bias adder and no zero point, so nothing
# ever read those two banks.  Their MEM_SEL windows (12..15, 16..19) stay
# reserved in the decoder for a future per-channel build.
# ---------------------------------------------------------------------------
WEIGHT_RAM = [
    ("U8",  "W_CONV1", "nCS_W_CONV1"),
    ("U9",  "W_CONV2", "nCS_W_CONV2"),
    ("U10", "W_FC1",   "nCS_W_FC1"),
    ("U11", "W_FC2",   "nCS_W_FC2"),
]

# CY62256 keeps VCC/GND on the common (unit 0) body; promote them so the
# generator places and wires them, same trick as the HY6264 above.
_62256 = reg.get("Memory_RAM:CY62256-70PC")
for _p in _62256.pins:
    _p.unit = 1

def place_62256(ref, x, y, cs, desc):
    s = add(sh, "Memory_RAM:CY62256-70PC", ref, x, y, value="62256",
            desc=f"32Kx8 SRAM {desc}",
            footprint="Package_DIP:DIP-28_W15.24mm")
    m = {"~{CS}": cs, "~{OE}": "MEM_nOE_INT", "~{WE}": "MEM_nWE_INT"}
    for num, p in s.pin_objs.items():
        if p.name.startswith("A") and p.name[1:].isdigit():
            m[num] = f"MADDR{int(p.name[1:])}"
        elif p.name.startswith("Q") and p.name[1:].isdigit():
            m[num] = f"MEM_D{int(p.name[1:])}"
    connect(sh, s, m)
    return s

for i, (ref, name, cs) in enumerate(WEIGHT_RAM):
    place_62256(ref, 55 + i * 70, 160, cs, name)

# ---------------------------------------------------------------------------
# Row 3: 8 LUT ROMs (right)
# ---------------------------------------------------------------------------
LUT = [
    ("U20", "LUT0_LO", "nCS_LUT0_LO", "LUT pair 0 low byte (A*B)[7:0]"),
    ("U21", "LUT0_HI", "nCS_LUT0_HI", "LUT pair 0 high byte (A*B)[15:8]"),
    ("U22", "LUT1_LO", "nCS_LUT1_LO", "LUT pair 1 low byte"),
    ("U23", "LUT1_HI", "nCS_LUT1_HI", "LUT pair 1 high byte"),
    ("U24", "LUT2_LO", "nCS_LUT2_LO", "LUT pair 2 low byte"),
    ("U25", "LUT2_HI", "nCS_LUT2_HI", "LUT pair 2 high byte"),
    ("U26", "LUT3_LO", "nCS_LUT3_LO", "LUT pair 3 low byte"),
    ("U27", "LUT3_HI", "nCS_LUT3_HI", "LUT pair 3 high byte"),
]

def place_27c512(ref, x, y, ce, desc):
    s = add(sh, "Memory_EPROM:27C512", ref, x, y, value="27C512", desc=desc)
    m = {"~{CE}": ce, "~{OE}": "MEM_nOE_INT"}
    for num, p in s.pin_objs.items():
        if p.name.startswith("A") and p.name[1:].isdigit():
            m[num] = f"MADDR{int(p.name[1:])}"
        elif p.name.startswith("D") and p.name[1:].isdigit():
            m[num] = f"MEM_D{int(p.name[1:])}"
    connect(sh, s, m)
    return s

for i, (ref, name, cs, desc) in enumerate(LUT):
    place_27c512(ref, 335 + i * 60, 255, cs, desc)

# ---------------------------------------------------------------------------
# Address / MEM_SEL input buffers (74HCT541 x4)
# ---------------------------------------------------------------------------
U40 = add(sh, "74xx:74HCT541", "U40", 490, 470, value="74HCT541",
          desc="ADDR[7:0] input buffer")
m = {"G1": "GND", "G2": "GND"}
for i in range(8):
    m[f"A{i}"] = f"ADDR{i}"
    m[f"Y{i}"] = f"MADDR{i}"
connect(sh, U40, m)

U41 = add(sh, "74xx:74HCT541", "U41", 590, 470, value="74HCT541",
          desc="ADDR[15:8] input buffer")
m = {"G1": "GND", "G2": "GND"}
for i in range(8):
    m[f"A{i}"] = f"ADDR{8+i}"
    m[f"Y{i}"] = f"MADDR{8+i}"
connect(sh, U41, m)

U42 = add(sh, "74xx:74HCT541", "U42", 690, 470, value="74HCT541",
          desc="ADDR[23:16] input buffer / tag")
m = {"G1": "GND", "G2": "GND"}
for i in range(8):
    m[f"A{i}"] = f"ADDR{16+i}"
    m[f"Y{i}"] = f"MADDR{16+i}"
connect(sh, U42, m)

U43 = add(sh, "74xx:74HCT541", "U43", 785, 470, value="74HCT541",
          desc="MEM_SEL and load-control input buffer")
m = {"G1": "GND", "G2": "GND"}
for i in range(5):
    m[f"A{i}"] = f"MEM_SEL{i}"
    m[f"Y{i}"] = f"MSEL{i}"
m["A5"] = "LOAD_EN"
m["Y5"] = "LOAD_EN_I"
m["A6"] = "LOAD_nWE"
m["Y6"] = "LOAD_nWE_I"
m["A7"] = "LOAD_nOE"
m["Y7"] = "LOAD_nOE_I"
connect(sh, U43, m)

# ---------------------------------------------------------------------------
# Engine address merge buffers (8x 74HCT541)
# The engine sheets drive C1/C2/FC1/FC2_ADDR[15:0] with their own 74HCT541 whose
# OE is the engine BUSY_N.  These second-stage buffers put the active engine's
# address onto the shared ADDR[15:0] net, which U40/U41 then buffer to MADDR.
# ADDR is a tri-state bus: S10 U93/U94 (load) and these eight buffers
# (inference) are mutually exclusive.  U40/U41 remain the only MADDR drivers.
# ---------------------------------------------------------------------------
ENG_BUF = [
    ("U44", "C1", 0, "C1_ADDR", "Segment 1: C1_ADDR[7:0] -> ADDR[7:0]"),
    ("U45", "C1", 8, "C1_ADDR", "Segment 2: C1_ADDR[15:8] -> ADDR[15:8]"),
    ("U46", "C2", 0, "C2_ADDR", "Segment 3: C2_ADDR[7:0] -> ADDR[7:0]"),
    ("U47", "C2", 8, "C2_ADDR", "Segment 4: C2_ADDR[15:8] -> ADDR[15:8]"),
    ("U48", "FC1", 0, "FC1_ADDR", "Segment 5: FC1_ADDR[7:0] -> ADDR[7:0]"),
    ("U49", "FC1", 8, "FC1_ADDR", "Segment 6: FC1_ADDR[15:8] -> ADDR[15:8]"),
    ("U58", "FC2", 0, "FC2_ADDR", "Segment 7: FC2_ADDR[7:0] -> ADDR[7:0]"),
    ("U59", "FC2", 8, "FC2_ADDR", "Segment 8: FC2_ADDR[15:8] -> ADDR[15:8]"),
]
for k, (ref, eng, base, bus, desc) in enumerate(ENG_BUF):
    if ref in ("U58", "U59"):
        # Option-A FC2 pair sits in the free band left of the FC1 pair.
        x = 60 + (k - 6) * 100
        y = 560
    else:
        x = 520 + (k % 3) * 100
        y = 560 + (k // 3) * 60
    u = add(sh, "74xx:74HCT541", ref, x, y, value="74HCT541", desc=desc)
    m = {"G1": f"{eng}_BUSY_N", "G2": f"{eng}_BUSY_N"}
    for i in range(8):
        m[f"A{i}"] = f"{bus}{base + i}"
        m[f"Y{i}"] = f"ADDR{base + i}"
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# Argmax address buffers (2x 74HCT541)
# SCORE_ADDR[5:0] = {class, byte}; zero-extend to the shared ADDR[15:0], then
# U40/U41 buffer it to MADDR.  OE is ARGMAX_BUSY_N, so the buffers are off
# outside the Argmax phase; S01 serializes Argmax after FC2.
# ---------------------------------------------------------------------------
for k, ref in enumerate(("U50", "U51")):
    u = add(sh, "74xx:74HCT541", ref, 820, 560 + k * 60, value="74HCT541",
            desc=f"Argmax SCORE_ADDR[{'5:0' if k == 0 else '15:8'}] address buffer")
    m = {"G1": "ARGMAX_BUSY_N", "G2": "ARGMAX_BUSY_N"}
    for i in range(8):
        bit = 8 * k + i
        m[f"A{i}"] = f"SCORE_ADDR{bit}" if bit < 6 else "GND"
        m[f"Y{i}"] = f"ADDR{bit}"
    connect(sh, u, m)

# ---------------------------------------------------------------------------
# Pool address/data buffers (5x 74HCT541 + 1x 74HC32)
# Read address is enabled while Pool is busy and not writing; write address and
# write data are enabled only during the Pool write transaction (nCE_OUT=0).
# ---------------------------------------------------------------------------
U57 = add(sh, "74xx:74HC32", "U57", 820, 680, unit=1, value="74HC32",
          desc="POOL1 read-buffer OE = POOL1_BUSY_N | POOL1_MEM_WE")
connect(sh, U57, {"1": "POOL1_BUSY_N", "2": "POOL1_MEM_WE",
                  "3": "POOL1_READ_OE"})
U57p = add(sh, "74xx:74HC32", "U57", 860, 680, unit=5, value="74HC32")
connect(sh, U57p, {"7": "GND", "14": "+5V"})

U52 = add(sh, "74xx:74HCT541", "U52", 500, 680, value="74HCT541",
          desc="POOL1 read address [7:0] buffer")
m = {"G1": "POOL1_READ_OE", "G2": "POOL1_READ_OE"}
for i in range(8):
    m[f"A{i}"] = f"POOL1_IN_ADDR{i}"
    m[f"Y{i}"] = f"ADDR{i}"
connect(sh, U52, m)

U53 = add(sh, "74xx:74HCT541", "U53", 590, 680, value="74HCT541",
          desc="POOL1 read address [15:8] buffer")
m = {"G1": "POOL1_READ_OE", "G2": "POOL1_READ_OE"}
for i in range(8):
    bit = 8 + i
    m[f"A{i}"] = f"POOL1_IN_ADDR{bit}" if bit < 13 else "GND"
    m[f"Y{i}"] = f"ADDR{bit}"
connect(sh, U53, m)

U54 = add(sh, "74xx:74HCT541", "U54", 500, 740, value="74HCT541",
          desc="POOL1 write address [7:0] buffer")
m = {"G1": "POOL1_MEM_nCE_OUT", "G2": "POOL1_MEM_nCE_OUT"}
for i in range(8):
    m[f"A{i}"] = f"POOL1_OUT_ADDR{i}"
    m[f"Y{i}"] = f"ADDR{i}"
connect(sh, U54, m)

U55 = add(sh, "74xx:74HCT541", "U55", 590, 740, value="74HCT541",
          desc="POOL1 write address [15:8] buffer")
m = {"G1": "POOL1_MEM_nCE_OUT", "G2": "POOL1_MEM_nCE_OUT"}
for i in range(8):
    bit = 8 + i
    m[f"A{i}"] = f"POOL1_OUT_ADDR{bit}" if bit < 12 else "GND"
    m[f"Y{i}"] = f"ADDR{bit}"
connect(sh, U55, m)

U56 = add(sh, "74xx:74HCT541", "U56", 680, 740, value="74HCT541",
          desc="POOL1 write data buffer")
m = {"G1": "POOL1_MEM_nCE_OUT", "G2": "POOL1_MEM_nCE_OUT"}
for i in range(8):
    m[f"A{i}"] = f"POOL1_OUT_DATA{i}"
    m[f"Y{i}"] = f"DATA{i}"
connect(sh, U56, m)

# ---------------------------------------------------------------------------
# POOL2 buffers (5x 74HCT541 + 1x 74HC32), identical to the POOL1 group.
# POOL1 and POOL2 are separate boards; S01 runs one pool at a time, so the two
# buffer groups never drive ADDR/DATA together.  Each group is enabled by its
# own busy/write controls, exactly like the per-engine address buffers above.
# ---------------------------------------------------------------------------
U65 = add(sh, "74xx:74HC32", "U65", 260, 620, unit=1, value="74HC32",
          desc="POOL2 read-buffer OE = POOL2_BUSY_N | POOL2_MEM_WE")
connect(sh, U65, {"1": "POOL2_BUSY_N", "2": "POOL2_MEM_WE",
                  "3": "POOL2_READ_OE"})
U65p = add(sh, "74xx:74HC32", "U65", 300, 620, unit=5, value="74HC32")
connect(sh, U65p, {"7": "GND", "14": "+5V"})

U60 = add(sh, "74xx:74HCT541", "U60", 60, 620, value="74HCT541",
          desc="POOL2 read address [7:0] buffer")
m = {"G1": "POOL2_READ_OE", "G2": "POOL2_READ_OE"}
for i in range(8):
    m[f"A{i}"] = f"POOL2_IN_ADDR{i}"
    m[f"Y{i}"] = f"ADDR{i}"
connect(sh, U60, m)

U61 = add(sh, "74xx:74HCT541", "U61", 160, 620, value="74HCT541",
          desc="POOL2 read address [15:8] buffer")
m = {"G1": "POOL2_READ_OE", "G2": "POOL2_READ_OE"}
for i in range(8):
    bit = 8 + i
    m[f"A{i}"] = f"POOL2_IN_ADDR{bit}" if bit < 13 else "GND"
    m[f"Y{i}"] = f"ADDR{bit}"
connect(sh, U61, m)

U62 = add(sh, "74xx:74HCT541", "U62", 60, 700, value="74HCT541",
          desc="POOL2 write address [7:0] buffer")
m = {"G1": "POOL2_MEM_nCE_OUT", "G2": "POOL2_MEM_nCE_OUT"}
for i in range(8):
    m[f"A{i}"] = f"POOL2_OUT_ADDR{i}"
    m[f"Y{i}"] = f"ADDR{i}"
connect(sh, U62, m)

U63 = add(sh, "74xx:74HCT541", "U63", 160, 700, value="74HCT541",
          desc="POOL2 write address [15:8] buffer")
m = {"G1": "POOL2_MEM_nCE_OUT", "G2": "POOL2_MEM_nCE_OUT"}
for i in range(8):
    bit = 8 + i
    m[f"A{i}"] = f"POOL2_OUT_ADDR{bit}" if bit < 12 else "GND"
    m[f"Y{i}"] = f"ADDR{bit}"
connect(sh, U63, m)

U64 = add(sh, "74xx:74HCT541", "U64", 260, 700, value="74HCT541",
          desc="POOL2 write data buffer")
m = {"G1": "POOL2_MEM_nCE_OUT", "G2": "POOL2_MEM_nCE_OUT"}
for i in range(8):
    m[f"A{i}"] = f"POOL2_OUT_DATA{i}"
    m[f"Y{i}"] = f"DATA{i}"
connect(sh, U64, m)

sh.add_text(
    "OPTION A BOARD SPLIT: POOL1/POOL2 and FC1/FC2 are separate boards, so "
    "each has its own tri-state merge buffers here.\n"
    "POOL2 group (U60..U65) mirrors the POOL1 group (U52..U57); FC2 pair "
    "(U58/U59) mirrors the FC1 pair (U48/U49).\n"
    "Enables are per engine, so only the active board drives ADDR/DATA.  S01 "
    "serialises the stages; no two groups are enabled together.",
    20, 790, size=1.3, justify="left top",
)

# ---------------------------------------------------------------------------
# 74HC138 chip-select decoders (one per MEM_SEL group of eight)
# ---------------------------------------------------------------------------
DEC = [
    ("U28", 55,  {"~{E0}": "MSEL4", "~{E1}": "MSEL3"},
     ["nCS_SRAM_INPUT", "nCS_SRAM_C1OUT", "nCS_SRAM_P1OUT", "nCS_SRAM_C2OUT",
      "nCS_SRAM_P2OUT", "nCS_SRAM_FC1OUT", "nCS_SRAM_FC2LOG", "NC"]),
    ("U29", 145, {"~{E0}": "MSEL4", "~{E1}": "NOT_MSEL3"},
     ["nCS_W_CONV1", "nCS_W_CONV2", "nCS_W_FC1", "nCS_W_FC2",
      "NC", "NC", "NC", "NC"]),
    ("U30", 235, {"~{E0}": "NOT_MSEL4", "~{E1}": "MSEL3"},
     ["NC", "NC", "NC", "NC",
      "nCS_LUT0_LO", "nCS_LUT0_HI", "nCS_LUT1_LO", "nCS_LUT1_HI"]),
    ("U31", 325, {"~{E0}": "NOT_MSEL4", "~{E1}": "NOT_MSEL3"},
     ["nCS_LUT2_LO", "nCS_LUT2_HI", "nCS_LUT3_LO", "nCS_LUT3_HI",
      "NC", "NC", "NC", "NC"]),
]

for ref, x, enable, outs in DEC:
    s = add(sh, "74xx:74HC138", ref, x, 360, value="74HC138",
            desc="3-to-8 chip-select decoder")
    m = dict(enable)
    m["E2"] = "DEC_EN"
    m["A0"] = "MSEL0"
    m["A1"] = "MSEL1"
    m["A2"] = "MSEL2"
    for i, net in enumerate(outs):
        m[f"~{{Y{i}}}"] = net
    connect(sh, s, m)

# ---------------------------------------------------------------------------
# 74HC688 address-tag comparator: ADDR[23:16] == {000, MEM_SEL[4:0]}
# ---------------------------------------------------------------------------
U32 = add(sh, "74xx:74HC688", "U32", 430, 360, value="74HC688",
          desc="Address tag comparator ADDR[23:16] == MEM_SEL")
m = {"G": "GND", "P=R": "ADDR_TAG_OK_N"}
for i in range(8):
    m[f"P{i}"] = f"MADDR{16+i}"
for i in range(5):
    m[f"R{i}"] = f"MSEL{i}"
for i in range(5, 8):
    m[f"R{i}"] = "GND"
connect(sh, U32, m)

# ---------------------------------------------------------------------------
# Control glue: 74HC04 (inverters), 74HC08 (decode AND), 74HC157 (mux)
# ---------------------------------------------------------------------------
# U33: 1..6 gates, 7 = power
add_gate(sh, "74xx:74HC04", "U33", 1, 55, 405,
         {"1": "MSEL3", "2": "NOT_MSEL3"}, value="74HC04")
add_gate(sh, "74xx:74HC04", "U33", 2, 115, 405,
         {"3": "MSEL4", "4": "NOT_MSEL4"})
add_gate(sh, "74xx:74HC04", "U33", 3, 175, 405,
         {"5": "ADDR_TAG_OK_N", "6": "ADDR_TAG_OK"})
add_gate(sh, "74xx:74HC04", "U33", 4, 235, 405,
         {"9": "DIR_SEL", "8": "READ_DIR"})
add_gate(sh, "74xx:74HC04", "U33", 5, 295, 405,
         {"11": "BOTH_IDLE", "10": "MEM_CE_OK"})
add_gate(sh, "74xx:74HC04", "U33", 6, 355, 405,
         {"13": "GND", "12": "NC"})
add_gate(sh, "74xx:74HC04", "U33", 7, 415, 405,
         {"7": "GND", "14": "+5V"})

# U34: gate1 DEC_EN, gate2 BOTH_IDLE, gates3/4 spare, unit5 power
add_gate(sh, "74xx:74HC08", "U34", 1, 630, 360,
         {"1": "ADDR_TAG_OK", "2": "MEM_CE_OK", "3": "DEC_EN"}, value="74HC08")
add_gate(sh, "74xx:74HC08", "U34", 2, 630, 405,
         {"4": "MEM_nCE", "5": "NOT_LOAD_EN", "6": "BOTH_IDLE"})
add_gate(sh, "74xx:74HC08", "U34", 3, 630, 430,
         {"9": "GND", "10": "GND", "8": "NC"})
add_gate(sh, "74xx:74HC08", "U34", 4, 630, 455,
         {"12": "GND", "13": "GND", "11": "NC"})
add_gate(sh, "74xx:74HC08", "U34", 5, 680, 430,
         {"7": "GND", "14": "+5V"})

# U35: load/run multiplexer
U35 = add(sh, "74xx:74HC157", "U35", 535, 360, value="74HC157",
          desc="nOE/nWE/DIR load-run multiplexer")
connect(sh, U35, {
    "S": "LOAD_EN_I", "E": "GND",
    "I0a": "MEM_nOE", "I1a": "LOAD_nOE_I", "Za": "MEM_nOE_INT",
    "I0b": "MEM_nWE", "I1b": "LOAD_nWE_I", "Zb": "MEM_nWE_INT",
    "I0c": "MEM_nOE", "I1c": "LOAD_nOE_I", "Zc": "DIR_SEL",
    "I0d": "+5V", "I1d": "GND", "Zd": "NOT_LOAD_EN",
})

# System-side data buffer: MEM_D <-> DATA.
# DIR = ~nOE_SEL: read = MEM_D -> DATA, write = DATA -> MEM_D.
U36 = add(sh, "74xx:74HC245", "U36", 55, 470, value="74HC245",
          desc="Memory array data buffer MEM_D <-> DATA")
m = {"A->B": "READ_DIR", "CE": "LOAD_EN_I"}
for i in range(8):
    m[f"A{i}"] = f"MEM_D{i}"
    m[f"B{i}"] = f"DATA{i}"
connect(sh, U36, m)

# Load-port data buffer: LOAD_DATA <-> MEM_D.
# DIR = nOE_SEL: write = LOAD_DATA -> MEM_D, read-back = MEM_D -> LOAD_DATA.
U37 = add(sh, "74xx:74HC245", "U37", 150, 470, value="74HC245",
          desc="Load port data buffer LOAD_DATA <-> MEM_D")
m = {"A->B": "DIR_SEL", "CE": "NOT_LOAD_EN"}
for i in range(8):
    m[f"A{i}"] = f"LOAD_DATA{i}"
    m[f"B{i}"] = f"MEM_D{i}"
connect(sh, U37, m)

# IMAGE_READY / MODEL_READY set-reset latches (D = Q feedback).
U38 = add(sh, "74xx:74HC74", "U38", 245, 470, unit=1, value="74HC74",
          desc="IMAGE_READY set/reset latch")
connect(sh, U38, {"~{R}": "RESET_N", "D": "IMAGE_READY", "C": "CLK",
                  "~{S}": "IMAGE_DONE_N", "Q": "IMAGE_READY", "~{Q}": "NC"})
U38b = add(sh, "74xx:74HC74", "U38", 310, 470, unit=2, value="74HC74",
           desc="MODEL_READY set/reset latch")
connect(sh, U38b, {"~{R}": "RESET_N", "D": "MODEL_READY", "C": "CLK",
                   "~{S}": "MODEL_DONE_N", "Q": "MODEL_READY", "~{Q}": "NC"})
add_gate(sh, "74xx:74HC74", "U38", 3, 275, 435,
         {"7": "GND", "14": "+5V"})

# ---------------------------------------------------------------------------
# Load / programming connector J1 (2x12)
# ---------------------------------------------------------------------------
J1 = add(sh, "Connector_Generic:Conn_02x12_Odd_Even", "J1", 380, 470,
         value="LOAD/PROG", desc="Image / weight load header (companion to J8)",
         footprint="Connector_PinHeader_2.54mm:PinHeader_2x12_P2.54mm_Vertical")
jm = {
    "1": "GND", "2": "GND",
    "3": "LOAD_DATA0", "4": "LOAD_DATA1",
    "5": "LOAD_DATA2", "6": "LOAD_DATA3",
    "7": "LOAD_DATA4", "8": "LOAD_DATA5",
    "9": "LOAD_DATA6", "10": "LOAD_DATA7",
    "11": "LOAD_EN", "12": "LOAD_nWE",
    "13": "LOAD_nOE", "14": "IMAGE_DONE_N",
    "15": "MODEL_DONE_N", "16": "IMAGE_READY",
    "17": "MODEL_READY", "18": "+5V",
    "19": "+5V", "20": "GND",
    "21": "GND", "22": "NC", "23": "NC", "24": "NC",
}
connect(sh, J1, jm)

# ---------------------------------------------------------------------------
# Pull resistors (idle state: MEM_SEL=11111 -> no device, LOAD_EN=0)
# ---------------------------------------------------------------------------
def pull(ref, x, y, net, rail, value="10k"):
    r = add(sh, "Device:R", ref, x, y, value=value,
            desc=f"Pull resistor {net} to {rail}")
    # These nets are global (same names as the interface labels); use a
    # global label here as well so the pull resistor lands on the same net.
    sh.stub_label(r, "1", net, local=False)
    sh.stub_power(r, "2", rail, pwr_ref())

PULLS = [
    ("R1", "MEM_SEL0", "+5V"), ("R2", "MEM_SEL1", "+5V"),
    ("R3", "MEM_SEL2", "+5V"), ("R4", "MEM_SEL3", "+5V"),
    ("R5", "MEM_SEL4", "+5V"), ("R6", "LOAD_EN", "GND"),
    ("R7", "LOAD_nWE", "+5V"), ("R8", "LOAD_nOE", "+5V"),
    ("R9", "IMAGE_DONE_N", "+5V"), ("R10", "MODEL_DONE_N", "+5V"),
]
for i, (ref, net, rail) in enumerate(PULLS):
    pull(ref, 55 + i * 40, 315, net, rail)

# ---------------------------------------------------------------------------
# Power flags and decoupling (one 100 nF per IC)
# ---------------------------------------------------------------------------
for i, (net, x, y) in enumerate((("+5V", 15, 300), ("GND", 15, 330))):
    add(sh, "power:PWR_FLAG", f"FLG{i+1}", x, y, value=net)
    sh.add_wire(x, y, x + 5.08, y)
    sh.add_power(net, x + 5.08, y, pwr_ref())

N_CAPS = 48
for i in range(N_CAPS):
    col, row = i % 21, i // 21
    x, y = 20 + col * 25, 510 + row * 22
    cap = add(sh, "Device:C", f"C{i+1}", x, y, value="100n",
              desc="Decoupling capacitor")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
sh.add_text(
    "Memory map: device window = MEM_SEL x 64 KB (ADDR[23:16] = device index,\n"
    "ADDR[15:0] = offset).  The 74HC688 compares the high byte ADDR[23:16]\n"
    "with MEM_SEL; within a window only the device address pins are decoded.\n"
    "00 INPUT_SRAM 01 CONV1_OUT 02 POOL1_OUT 03 CONV2_OUT 04 POOL2_OUT\n"
    "05 FC1_OUT 06 FC2_LOGITS\n"
    "08 W_CONV1 09 W_CONV2 0A W_FC1 0B W_FC2   (62256, boot-loaded)\n"
    "0C..0F bias, 10..13 qparam: reserved, no device fitted\n"
    "14/15 LUT0 LO/HI 16/17 LUT1 LO/HI\n"
    "18/19 LUT2 LO/HI 1A/1B LUT3 LO/HI\n"
    "07 and 1C..1F are unmapped.  6264 uses ADDR[12:0],\n"
    "62256 ADDR[14:0], W27C512 ADDR[15:0].",
    520, 40, size=1.15, justify="left top",
)
sh.add_text(
    "Chip-select decode: 4x 74HC138 decode MEM_SEL[2:0]; the group\n"
    "enables are MSEL[4:3].  DEC_EN = ADDR_TAG_OK AND MEM_CE_OK,\n"
    "where MEM_CE_OK = NOT(MEM_nCE AND NOT LOAD_EN) and\n"
    "ADDR_TAG_OK = (ADDR[23:16] == {000, MEM_SEL[4:0]}).\n"
    "Exactly one nCS can be low at a time; unmapped indices select\n"
    "nothing.  ADDR[15:0] is a tri-state bus (host U93/U94 or the active\n"
    "engine via U44..U49); no 2:1 address multiplexer is used.\n"
    "Load port J1 carries LOAD_DATA/LOAD_EN/LOAD_nWE/nOE and READY pulses;\n"
    "ADDR[15:0] come from S10 while LOAD_EN=1 and from the active engine's\n"
    "C1/C2/FC_ADDR via U44..U49 while LOAD_EN=0; ADDR[23:16] and MEM_SEL come\n"
    "from S10 (load) or the S11 tag/MEM_SEL buffers (inference).\n"
    "LOAD_EN=1 disables the system data buffer and enables the load buffer.\n"
    "The W27C512 LUTs are programmed once on a bench programmer; they have no\n"
    "in-system write path because their address pins carry A*B, not ADDR.",
    520, 90, size=1.15, justify="left top",
)

sh.write(os.path.join(PROJECT_DIR, "S04_Memories.kicad_sch"))
print("wrote S04_Memories.kicad_sch")
