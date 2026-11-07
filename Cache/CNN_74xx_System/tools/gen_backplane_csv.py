"""Generate the final backplane pinout from output/top.net.

The module builders write a local pinout CSV with the un-renumbered J1..Jn
labels.  This script reads the exported netlist, finds every component with
Value=BACKPLANE, reads its Sheetname property and its pin-to-net map, and
writes one authoritative CSV plus a per-board summary.

Run from the project directory after the top-level netlist export:
    python tools/gen_backplane_csv.py [output/top.net]
"""
from __future__ import annotations

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUTDIR = os.path.join(PROJECT_DIR, "output", "backplane")

POWER_PINS = set(range(1, 15))
SIGNAL_PINS = list(range(15, 41))


def parse_components(text: str) -> dict[str, dict]:
    comps: dict[str, dict] = {}
    for m in re.finditer(r'\(comp\s*\n\s*\(ref "([^"]+)"\)\s*\n'
                         r'\s*\(value "([^"]+)"\)', text):
        ref, value = m.group(1), m.group(2)
        if value != "BACKPLANE":
            continue
        tail = text[m.end():m.end() + 2500]
        sm = re.search(r'\(name "Sheetname"\)\s*\n\s*\(value "([^"]+)"\)', tail)
        comps[ref] = {"value": value,
                      "sheet": sm.group(1) if sm else "?"}
    return comps


def parse_nets(text: str) -> dict[str, dict[str, str]]:
    pinmap: dict[str, dict[str, str]] = {}
    for block in re.split(r"\n\t\t\(net\n", text)[1:]:
        m = re.search(r'\(name "([^"]+)"\)', block)
        if not m:
            continue
        net = m.group(1)
        for ref, pin in re.findall(
                r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', block):
            pinmap.setdefault(ref, {})[pin] = net
    return pinmap


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        PROJECT_DIR, "output", "top.net")
    text = open(path, encoding="utf-8").read()
    comps = parse_components(text)
    pinmap = parse_nets(text)
    if not comps:
        print("no BACKPLANE components found")
        return 1

    os.makedirs(OUTDIR, exist_ok=True)
    rows = []
    summary: dict[str, dict] = {}
    for ref in sorted(comps, key=lambda r: (comps[r]["sheet"], r)):
        sheet = comps[ref]["sheet"]
        pins = pinmap.get(ref, {})
        info = summary.setdefault(sheet, {"headers": 0, "signals": 0})
        info["headers"] += 1
        for pin in range(1, 41):
            net = pins.get(str(pin), "")
            if pin in POWER_PINS:
                role = "power"
            elif net.startswith("unconnected-"):
                net = ""
                role = "nc"
            else:
                role = "signal"
                info["signals"] += 1
            rows.append((sheet, ref, pin, net, role))

    out = os.path.join(OUTDIR, "backplane_pinout.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "connector", "pin", "net", "role"])
        w.writerows(rows)

    summary_path = os.path.join(OUTDIR, "backplane_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "headers", "signal_pins"])
        for sheet in sorted(summary):
            w.writerow([sheet, summary[sheet]["headers"],
                        summary[sheet]["signals"]])

    # Net-centric view: every board/pin that carries each signal.  This is the
    # table the backplane designer uses to route a net between slots.
    net_rows: dict[str, list[tuple[str, str, int]]] = {}
    for sheet, ref, pin, net, role in rows:
        if role == "signal" and net:
            net_rows.setdefault(net, []).append((sheet, ref, pin))
    nets_path = os.path.join(OUTDIR, "backplane_nets.csv")
    with open(nets_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["net", "sheet", "connector", "pin"])
        for net in sorted(net_rows):
            for sheet, ref, pin in sorted(net_rows[net]):
                w.writerow([net, sheet, ref, pin])

    print(f"wrote {out}: {len(comps)} headers, {len(rows)} pins")
    print(f"wrote {nets_path}: {len(net_rows)} nets")
    for sheet in sorted(summary):
        print(f"  {sheet:22s} {summary[sheet]['headers']} headers, "
              f"{summary[sheet]['signals']} signal pins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
