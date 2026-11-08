"""Targeted static audit of the three structural findings.

1. 74HC688 P=R is active-low.  Find comparators whose output reaches a 27C512
   address pin directly, or through a 74HC157, with no inversion.
2. A 688 only compares 8 bits.  If its R pins are the low 8 bits of a 74HC161
   counter that has higher Q bits, the terminal count is truncated.
3. Which H_A bits actually reach a connector pin.

This is a targeted check for the findings in ../VERIFICATION_REPORT.md, not a
general-purpose linter.

Run:
    python audit_structure.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.abspath(os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, ANALYSIS)

import build_analysis as ba  # noqa: E402

P_PINS = ("2", "4", "6", "8", "11", "13", "15", "17")
R_PINS = ("3", "5", "7", "9", "12", "14", "16", "18")
ROM_ADDR_PINS = {str(p) for p in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                                  21, 23, 24, 25, 26, 27)}
MUX_IN = {"2": "4", "3": "4", "5": "7", "6": "7",
          "11": "9", "10": "9", "14": "12", "13": "12"}


def pin(ref, num):
    return ba.PIN_NET.get(ref, {}).get(num)


def short(net):
    return net.split("/")[-1] if net else ""


def nodes(net):
    return next((n for n in ba.NET if n["name"] == net), {"nodes": []})["nodes"]


def main() -> int:
    print("=== 74HC688 outputs feeding a ROM/mux 'last' input ===")
    hits = []
    for ref in sorted(ba.COMP, key=ba.pin_sort_key):
        c = ba.COMP[ref]
        if c["part"] != "74HC688":
            continue
        out = pin(ref, "19")
        on_rom = any(ba.COMP[n["ref"]]["part"] == "27C512"
                     and n["pin"] in ROM_ADDR_PINS for n in nodes(out))
        via157 = []
        for n in nodes(out):
            cc = ba.COMP[n["ref"]]
            if cc["part"] == "74HC157" and n["pin"] in MUX_IN:
                z = pin(n["ref"], MUX_IN[n["pin"]])
                if short(z).endswith("_INDEX_LAST"):
                    via157.append(f"{n['ref']}.{MUX_IN[n['pin']]}->{short(z)}")
        if on_rom:
            hits.append((ref, c["sheet"], short(out), "direct 27C512 address"))
        elif via157:
            hits.append((ref, c["sheet"], short(out), "; ".join(via157)))
    for ref, sheet, name, how in hits:
        print(f"  {ref:6} {sheet:22} {name:20} {how}")
    print(f"  total flagged: {len(hits)}")

    print("\n=== 74HC688 width: counter Q bits above bit 7 ignored ===")
    width = []
    for ref in sorted(ba.COMP, key=ba.pin_sort_key):
        c = ba.COMP[ref]
        if c["part"] != "74HC688":
            continue
        rnets = [pin(ref, p) for p in R_PINS]
        stems = {re.sub(r"\d+$", "", short(n)) for n in rnets if n}
        for stem in stems:
            hi = []
            for n in ba.NET:
                m = re.fullmatch(re.escape(stem) + r"(\d+)", short(n["name"]))
                if not m or int(m.group(1)) < 8:
                    continue
                for nd in n["nodes"]:
                    cc = ba.COMP[nd["ref"]]
                    if cc["part"] == "74HC161" and nd["pin"] in ("11", "12", "13", "14"):
                        hi.append(int(m.group(1)))
            if not hi or short(pin(ref, "19")).startswith("MATCH"):
                continue
            const = sum(1 << i for i, p in enumerate(P_PINS)
                        if pin(ref, p) in ("+5V", "+3V3"))
            name = short(pin(ref, "19"))
            m = re.search(r"(\d+)$", name)
            named_big = bool(m and int(m.group(1)) > 255)
            if named_big or name.endswith("SP_LAST"):
                width.append((ref, c["sheet"], name, stem, const, max(hi)))
    for ref, sheet, name, stem, const, top in width:
        print(f"  {ref:6} {sheet:22} {name:20} P=0x{const:02X}({const}) "
              f"compares {stem}0..7, counter has {stem}{top}")
    print(f"  total flagged: {len(width)}")

    print("\n=== H_A bits on connectors ===")
    host = {}
    for ref in sorted(ba.COMP, key=ba.pin_sort_key):
        c = ba.COMP[ref]
        if not c["part"].startswith("Conn_"):
            continue
        bits = sorted({int(m.group(1)) for n in ba.PIN_NET.get(ref, {}).values()
                       if (m := re.search(r"/H_A(\d+)$", n))})
        if bits:
            host[ref] = bits
    for ref, bits in host.items():
        print(f"  {ref}: H_A{min(bits)}..H_A{max(bits)} ({len(bits)} bits)")
    allbits = set().union(*host.values()) if host else set()
    print(f"  missing on every header: {[i for i in range(24) if i not in allbits]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
