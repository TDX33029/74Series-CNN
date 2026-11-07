"""Build the per-board halves of the former S12_DataAssembly sheet.

S12 used to be one shared sheet with two unrelated jobs:

  * a 74HCT541 that buffered the shared DATA[7:0] byte bus for the shared Pool
    engine (S05), producing IN_DATA[7:0];
  * four 74HCT574 latches plus a 74HC238 that assembled the Argmax 32-bit
    score word from the same DATA bus.

POOL1 and POOL2 are now separate boards, and Argmax sits on its own board, so
the width bridge is split accordingly:

    S12A_PoolLatch1   DATA[7:0] -> IN_DATA1[7:0]   (board B05, POOL1)
    S12A_PoolLatch2   DATA[7:0] -> IN_DATA2[7:0]   (board B07, POOL2)
    S12B_ScoreLatch   DATA[7:0] -> SCORE_DATA[31:0] (board B10, ARGMAX)

The circuits are copied unchanged from the verified S12 sheet; only the net
names and the sheet partition differ.

Run from the tools directory:
    python build_s12_split.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from kicad_gen import default_registry, footprint_for, Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"


def make_registry():
    reg = default_registry()
    reg.add_library(
        "Connector_Generic",
        r"C:/Program Files/KiCad/10.0/share/kicad/symbols/Connector_Generic.kicad_sym",
    )
    return reg


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


def connect(sh, sym, nmap, is_global):
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


def caps(sh, count: int, y: float) -> None:
    for i in range(count):
        cap = add(sh, "Device:C", f"C{i + 1}", 40 + (i % 8) * 45,
                  y + (i // 8) * 27, value="100nF")
        sh.stub_power(cap, "1", "+5V", pwr_ref())
        sh.stub_power(cap, "2", "GND", pwr_ref())


def build_pool_latch(index: int) -> str:
    """One 74HCT541 per Pool board: DATA[7:0] -> IN_DATAn[7:0]."""
    prefix = f"IN_DATA{index}"
    globals_ = {f"DATA{i}" for i in range(8)}
    globals_ |= {f"{prefix}{i}" for i in range(8)}

    def is_global(net: str) -> bool:
        return net in globals_

    sh = Schematic(
        make_registry(), project=PROJECT, instance_path="/__ROOT_UUID__",
        title=f"S12A_PoolLatch{index} - POOL{index} input byte buffer",
        paper="A5",
    )
    sh.add_text(
        f"S12A_POOL LATCH {index}  (DATA[7:0] -> IN_DATA{index}[7:0])",
        15, 12, size=2.4, justify="left top", bold=True,
    )
    sh.add_text(
        "Always-enabled 74HCT541 isolates the shared byte bus from the Pool "
        "engine inputs.\n"
        "One access per byte: S04 drives DATA[7:0], the Pool compares one byte "
        "and advances its address.\n"
        "The buffer is powered from the board's +5V rail and has no control "
        "port on the backplane.",
        15, 19, size=1.2, justify="left top",
    )

    U1 = add(sh, "74xx:74HCT541", "U1", 95, 75, value="74HCT541")
    m = {"G1": "GND", "G2": "GND"}
    for i in range(8):
        m[f"A{i}"] = f"DATA{i}"
        m[f"Y{i}"] = f"{prefix}{i}"
    connect(sh, U1, m, is_global)
    caps(sh, 1, 150)

    path = os.path.join(PROJECT_DIR, f"S12A_PoolLatch{index}.kicad_sch")
    sh.write(path)
    return path


def build_score_latch() -> str:
    """Four byte lanes plus the 74HC238 lane decoder for Argmax."""
    globals_ = {f"DATA{i}" for i in range(8)}
    globals_ |= {f"SCORE_DATA{i}" for i in range(32)}
    globals_ |= {"SCORE_ADDR0", "SCORE_ADDR1", "MEM_ACK"}

    def is_global(net: str) -> bool:
        return net in globals_

    sh = Schematic(
        make_registry(), project=PROJECT, instance_path="/__ROOT_UUID__",
        title="S12B_ScoreLatch - ARGMAX 32-bit score staging",
        paper="A3",
    )
    sh.add_text(
        "S12B  ARGMAX SCORE STAGING (4x 74HCT574 + 74HC238)",
        20, 16, size=3.0, justify="left top", bold=True,
    )
    sh.add_text(
        "Four 74HCT574 latches hold bytes 0..3 of a little-endian signed-32 "
        "score word.\n"
        "74HC238 decodes SCORE_ADDR[1:0] into the four latch clocks while "
        "MEM_ACK is high (S02 data-valid capture).\n"
        "The latches are a staging register, not a second memory: S04 presents "
        "the selected byte on DATA while the decoder output is high.\n"
        "S06 generates the byte address and S04/S02 execute one REQ/ACK "
        "transaction per byte.",
        20, 23, size=1.5, justify="left top",
    )

    ic_symbols = []
    for k in range(4):
        u = add(sh, "74xx:74HCT574", f"U{k + 1}", 90 + k * 80, 100,
                value="74HCT574")
        ic_symbols.append(u)
        m = {"OE": "GND", "Cp": f"SCORE_L{k}"}
        for j in range(8):
            m[f"D{j}"] = f"DATA{j}"
            m[f"Q{j}"] = f"SCORE_DATA{8 * k + j}"
        connect(sh, u, m, is_global)

    U5 = add(sh, "74xx:74HC238", "U5", 430, 100, value="74HC238")
    ic_symbols.append(U5)
    m = {
        "A0": "SCORE_ADDR0", "A1": "SCORE_ADDR1", "A2": "GND",
        "~{E1}": "GND", "~{E2}": "GND", "E3": "MEM_ACK",
    }
    for k in range(4):
        m[f"Y{k}"] = f"SCORE_L{k}"
    for k in range(4, 8):
        m[f"Y{k}"] = "NC"
    connect(sh, U5, m, is_global)

    for k in range(4):
        tp = add(sh, "Connector:TestPoint", f"TP{k + 1}", 90 + k * 80, 175,
                 value=f"SCORE_L{k}")
        sh.stub_label(tp, "1", f"SCORE_L{k}", local=True)

    caps(sh, len({u.ref for u in ic_symbols}), 215)

    path = os.path.join(PROJECT_DIR, "S12B_ScoreLatch.kicad_sch")
    sh.write(path)
    return path


def main() -> int:
    for path in (build_pool_latch(1), build_pool_latch(2), build_score_latch()):
        print("wrote", os.path.basename(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
