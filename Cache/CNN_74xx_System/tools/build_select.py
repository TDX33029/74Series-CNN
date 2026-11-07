"""Build S11A_EngineMerge.kicad_sch (per-layer engines -> shared fabric slot).

S11 was verified with one FC engine slot and one POOL engine slot.  Option A
duplicates the engines (FC1/FC2, POOL1/POOL2) but keeps the S11 map ROM,
master encoder and REQ/WE merge untouched, so the two engines of a pair are
multiplexed back into the single slot they used to share:

    FC1_*  / FC2_*    -> FC_*    selected by FC2_BUSY
    POOL1_* / POOL2_* -> POOL_*  selected by POOL2_BUSY

A mux, not an OR/AND merge, is required: the engine 74HC138 region decoders
are qualified only by the shared MEM_nCE, so an idle engine still asserts a
region code while another engine owns the bus.  Gating with the engine's own
BUSY would fix that too, but that would edit the verified engine sheets; the
mux keeps every engine byte-identical to the reviewed design.

Only one engine of each pair runs at a time (S01 serialises the CNN stages),
so the select is stable for the whole transaction.  The unselected engine's
outputs are ignored, and the merged nets feed S11 exactly as before.

Run from the tools directory:
    python build_select.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"

REGIONS = ("IN", "W", "OUT", "B", "Q", "MC")

GLOBAL = {
    "FC1_MEM_REQ", "FC1_MEM_WE", "FC1_BUSY_N", "FC2_MEM_REQ", "FC2_MEM_WE",
    "FC2_BUSY_N", "FC2_BUSY",
    "FC_MEM_REQ", "FC_MEM_WE", "FC_BUSY_N",
    "POOL1_MEM_REQ", "POOL1_MEM_WE", "POOL1_MEM_nCE_IN",
    "POOL1_MEM_nCE_OUT", "POOL1_BUSY", "POOL1_BUSY_N",
    "POOL2_MEM_REQ", "POOL2_MEM_WE", "POOL2_MEM_nCE_IN",
    "POOL2_MEM_nCE_OUT", "POOL2_BUSY", "POOL2_BUSY_N",
    "POOL_MEM_REQ", "POOL_MEM_WE", "POOL_MEM_nCE_IN", "POOL_MEM_nCE_OUT",
    "POOL_BUSY", "POOL_BUSY_N",
}
for _r in REGIONS:
    GLOBAL.add(f"FC1_MEM_nCE_{_r}")
    GLOBAL.add(f"FC2_MEM_nCE_{_r}")
    GLOBAL.add(f"FC_MEM_nCE_{_r}")


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


def mux(sh, ref, x, y, sel, pairs):
    """Place one 74HC157 package.

    ``pairs`` is a list of (I0, I1, Z) for units a..d; None leaves the unit
    unused (inputs tied low, output no-connect).
    """
    u = add(sh, "74xx:74HC157", ref, x, y, value="74HC157")
    m = {"S": sel, "E": "GND"}
    for k, unit in enumerate(("a", "b", "c", "d")):
        if k < len(pairs) and pairs[k] is not None:
            i0, i1, z = pairs[k]
            m[f"I0{unit}"] = i0
            m[f"I1{unit}"] = i1
            m[f"Z{unit}"] = z
        else:
            m[f"I0{unit}"] = "GND"
            m[f"I1{unit}"] = "GND"
            m[f"Z{unit}"] = "NC"
    connect(sh, u, m)
    return u


sh = Schematic(
    default_registry(), project=PROJECT, instance_path="/__ROOT_UUID__",
    title="S11A_EngineMerge - FC1/FC2 and POOL1/POOL2 Bus Merge", paper="A2",
)
sh.add_text(
    "S11A  ENGINE MERGE (PER-LAYER ENGINES -> SHARED S11 SLOT)",
    20, 16, size=3.0, justify="left top", bold=True,
)
sh.add_text(
    "FC1 and FC2 are separate boards with identical engines; POOL1 and POOL2 "
    "likewise.  S01 serialises the stages, so at most one engine of each pair "
    "is running at a time.\n"
    "This sheet multiplexes each pair back onto the single FC_* / POOL_* slot "
    "that S11 was verified against: FC2_BUSY selects FC2 when high, and "
    "POOL2_BUSY selects POOL2 when high.\n"
    "A mux is required instead of an OR/AND merge because the engine 74HC138 "
    "region decoders are qualified only by MEM_nCE: an idle engine still "
    "drives a region code while another engine owns the bus.\n"
    "The selected engine's region/REQ/WE/BUSY reach S11 unchanged; the "
    "unselected engine's outputs are simply ignored.  No engine sheet changes.",
    20, 24, size=1.5, justify="left top",
)

# ---------------------------------------------------------------------------
# FC pair: six region lines + REQ/WE + BUSY_N.
# ---------------------------------------------------------------------------
mux(sh, "U1", 80, 80, "FC2_BUSY", [
    ("FC1_MEM_nCE_IN", "FC2_MEM_nCE_IN", "FC_MEM_nCE_IN"),
    ("FC1_MEM_nCE_W", "FC2_MEM_nCE_W", "FC_MEM_nCE_W"),
    ("FC1_MEM_nCE_OUT", "FC2_MEM_nCE_OUT", "FC_MEM_nCE_OUT"),
    ("FC1_MEM_nCE_B", "FC2_MEM_nCE_B", "FC_MEM_nCE_B"),
])
mux(sh, "U2", 80, 170, "FC2_BUSY", [
    ("FC1_MEM_nCE_Q", "FC2_MEM_nCE_Q", "FC_MEM_nCE_Q"),
    ("FC1_MEM_nCE_MC", "FC2_MEM_nCE_MC", "FC_MEM_nCE_MC"),
    ("FC1_MEM_REQ", "FC2_MEM_REQ", "FC_MEM_REQ"),
    ("FC1_MEM_WE", "FC2_MEM_WE", "FC_MEM_WE"),
])
mux(sh, "U3", 80, 260, "FC2_BUSY", [
    ("FC1_BUSY_N", "FC2_BUSY_N", "FC_BUSY_N"),
])

# ---------------------------------------------------------------------------
# POOL pair: two region lines + REQ/WE + BUSY/BUSY_N.
# ---------------------------------------------------------------------------
mux(sh, "U4", 330, 80, "POOL2_BUSY", [
    ("POOL1_MEM_nCE_IN", "POOL2_MEM_nCE_IN", "POOL_MEM_nCE_IN"),
    ("POOL1_MEM_nCE_OUT", "POOL2_MEM_nCE_OUT", "POOL_MEM_nCE_OUT"),
    ("POOL1_MEM_REQ", "POOL2_MEM_REQ", "POOL_MEM_REQ"),
    ("POOL1_MEM_WE", "POOL2_MEM_WE", "POOL_MEM_WE"),
])
mux(sh, "U5", 330, 170, "POOL2_BUSY", [
    ("POOL1_BUSY", "POOL2_BUSY", "POOL_BUSY"),
    ("POOL1_BUSY_N", "POOL2_BUSY_N", "POOL_BUSY_N"),
])

sh.add_text(
    "Select timing: S01 sets FC_SEL/POOL_SEL before asserting the matching "
    "*_START, and the engine raises BUSY for the whole run.\n"
    "FC2_BUSY / POOL2_BUSY therefore switch the mux before the first memory "
    "transaction and hold it until DONE.  The map ROM still sees FC_SEL / "
    "POOL_SEL from S01, so both sides agree on the weight/output window.",
    80, 340, size=1.2, justify="left top",
)
sh.add_text(
    "Unused mux units are tied low with no-connect outputs.  All five packages "
    "are 74HC157 (quad 2:1, non-inverting); no bus buffers are added here "
    "because the engines drive the backplane directly and S04 owns the "
    "tri-state ADDR/DATA merge buffers.",
    80, 365, size=1.2, justify="left top",
)

# One 100 nF per package.
for i in range(5):
    cap = add(sh, "Device:C", f"C{i + 1}", 80 + i * 45, 400, value="100nF")
    sh.stub_power(cap, "1", "+5V", pwr_ref())
    sh.stub_power(cap, "2", "GND", pwr_ref())

sh.write(os.path.join(PROJECT_DIR, "S11A_EngineMerge.kicad_sch"))
print("wrote S11A_EngineMerge.kicad_sch")
