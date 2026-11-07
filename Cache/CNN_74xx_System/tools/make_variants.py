"""Create the per-layer board variants of the shared engines.

The base builders still generate one shared Pool (S05), one shared FC engine
(S09) and one shared FC requant (S17).  The Option-A board partition needs one
fixed copy per layer:

    S05_Pool1  (POOL_SEL=0)
    S05_Pool2  (POOL_SEL=1)
    S09_FC1    (FC_SEL=0)
    S09_FC2    (FC_SEL=1)
    S17_FC1    (FC_SEL=0)
    S17_FC2    (FC_SEL=1)

The variants are byte copies of the generated sheets with only the
``global_label`` names rewritten.  Local labels, component values and the
verified circuit are untouched.  Every UUID is replaced so KiCad sees a new
sheet, and renumber_refs.py later gives each file its own reference block.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kicad_gen import uid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATE_DIR = os.path.join(PROJECT_DIR, "templates")


def rewrite_label(net: str, variant: str) -> str:
    if variant == "S05_Pool1":
        if net == "POOL_SEL":
            return "GND"
        if net == "P2_START":
            return "GND"
        if net == "P2_DONE":
            return "POOL1_P2_DONE_NC"
        if net == "OUT_WE":
            return "POOL1_OUT_WE_NC"
        if net.startswith("POOL_"):
            return "POOL1_" + net[5:]
        if net.startswith("IN_DATA"):
            return "IN_DATA1" + net[7:]
        return net
    if variant == "S05_Pool2":
        if net == "POOL_SEL":
            return "+5V"
        if net == "P1_START":
            return "GND"
        if net == "P1_DONE":
            return "POOL2_P1_DONE_NC"
        if net == "OUT_WE":
            return "POOL2_OUT_WE_NC"
        if net.startswith("POOL_"):
            return "POOL2_" + net[5:]
        if net.startswith("IN_DATA"):
            return "IN_DATA2" + net[7:]
        return net
    if variant == "S09_FC1":
        if net == "FC_SEL":
            return "GND"
        if net == "FC2_START":
            return "GND"
        if net == "FC2_DONE":
            return "FC1_FC2_DONE_NC"
        if net.startswith("FC_"):
            return "FC1_" + net[3:]
        return net
    if variant == "S09_FC2":
        if net == "FC_SEL":
            return "+5V"
        if net == "FC1_START":
            return "GND"
        if net == "FC1_DONE":
            return "FC2_FC1_DONE_NC"
        if net.startswith("FC_"):
            return "FC2_" + net[3:]
        return net
    if variant == "S17_FC1":
        if net == "FC_SEL":
            return "GND"
        if net.startswith("FC_"):
            return "FC1_" + net[3:]
        return net
    if variant == "S17_FC2":
        if net == "FC_SEL":
            return "+5V"
        if net.startswith("FC_"):
            return "FC2_" + net[3:]
        return net
    raise ValueError(variant)


def make_variant(base: str, out: str, variant: str, title: str) -> None:
    path = os.path.join(TEMPLATE_DIR, base)
    text = open(path, encoding="utf-8").read()

    def repl(m: re.Match) -> str:
        return f'(global_label "{rewrite_label(m.group(1), variant)}"'

    text = re.sub(r'\(global_label "([^"]+)"', repl, text)
    text = re.sub(r'\(uuid "[0-9a-fA-F-]{36}"\)',
                  lambda _m: f'(uuid "{uid()}")', text)
    text = re.sub(r'\(title "[^"]*"', f'(title "{title}"', text, count=1)
    with open(os.path.join(PROJECT_DIR, out), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(text)
    print(f"wrote {out}")


def main() -> int:
    make_variant("S05_Pool.kicad_sch", "S05_Pool1.kicad_sch", "S05_Pool1",
                 "S05_Pool1 - POOL1 fixed board")
    make_variant("S05_Pool.kicad_sch", "S05_Pool2.kicad_sch", "S05_Pool2",
                 "S05_Pool2 - POOL2 fixed board")
    make_variant("S09_FC.kicad_sch", "S09_FC1.kicad_sch", "S09_FC1",
                 "S09_FC1 - FC1 fixed board")
    make_variant("S09_FC.kicad_sch", "S09_FC2.kicad_sch", "S09_FC2",
                 "S09_FC2 - FC2 fixed board")
    make_variant("S17_Requant_FC.kicad_sch", "S17_FC1.kicad_sch", "S17_FC1",
                 "S17_FC1 - FC1 requant fixed board")
    make_variant("S17_Requant_FC.kicad_sch", "S17_FC2.kicad_sch", "S17_FC2",
                 "S17_FC2 - FC2 requant fixed board")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
