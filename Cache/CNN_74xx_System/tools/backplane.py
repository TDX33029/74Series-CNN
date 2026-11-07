"""Add 2x20P backplane headers to a module schematic.

The project is being split into boards that plug into a passive backplane.
Every board gets one or more 2x20P headers.  The power pins are identical on
every header so the backplane can feed any slot:

    pin 1..4   +5V
    pin 5..8   +3V3 (reserved; the current logic is 5 V only)
    pin 9..14  GND
    pin 15..40 signals (26 per header)

A 2x20P header only has 26 signal pins after the 14 power pins.  The large
boards carry far more than 26 inter-module nets (S04 has 151), so they get
J1..Jn; every header keeps the same power pinout.  The signal assignment is
per board: the user explicitly allowed arbitrary signal positions and will
route the backplane per slot.  A machine-readable pinout is written to
output/backplane/ and the final (renumbered) pinout is produced by
tools/gen_backplane_csv.py from output/top.net.

Run from a builder:
    from backplane import place_backplane
    place_backplane(sh, "S07_Conv1")
"""
from __future__ import annotations

import csv
import os
import re
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

HEADER_LIB = "Connector_Generic:Conn_02x20_Odd_Even"
HEADER_FOOTPRINT = (
    "Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical"
)

POWER_PINS = {
    1: "+5V", 2: "+5V", 3: "+5V", 4: "+5V",
    5: "+3V3", 6: "+3V3", 7: "+3V3", 8: "+3V3",
    9: "GND", 10: "GND", 11: "GND", 12: "GND", 13: "GND", 14: "GND",
}
SIGNAL_PINS = list(range(15, 41))
POWER_NETS = {"+5V", "GND", "+3V3", "+3.3V"}

PAPER_MM = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
    "A5": (210.0, 148.0),
}


def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def net_rank(name: str) -> int:
    """Group related nets so each header carries a coherent slice of the bus."""
    if name in ("CLK", "RESET_N"):
        return 0
    if (name in ("START", "BUSY", "DONE", "ERROR",
                 "IMAGE_READY", "MODEL_READY", "MODEL_DONE_N",
                 "IMAGE_DONE_N", "RESULT_VALID")
            or name.startswith("ERROR_CODE")
            or name.startswith("RESULT")):
        return 1
    if (re.match(r"^(C1|C2|FC1|FC2|P1|P2|ARGMAX)_(START|DONE)$", name)
            or name in ("FC_SEL", "POOL_SEL")):
        return 2
    if (name.startswith("DATA") or name.startswith("ADDR")
            or name in ("MEM_nCE", "MEM_nOE", "MEM_nWE",
                        "MEM_ACK", "MEM_DONE", "MEM_BUSY", "REQ", "WE")):
        return 3
    if name.startswith("LOAD_") or name.startswith("MEM_SEL"):
        return 4
    if name.startswith("C1_"):
        return 5
    if name.startswith("C2_"):
        return 6
    if name.startswith("FC_"):
        return 7
    if name.startswith("POOL_") or name.startswith("IN_DATA"):
        return 8
    if name.startswith("SCORE_") or name.startswith("ARGMAX_"):
        return 9
    return 10


def collect_global_nets(sh) -> list[str]:
    """Unique non-power global labels already placed on the sheet."""
    nets: list[str] = []
    seen: set[str] = set()
    for item in sh.items:
        for m in re.finditer(r'\(global_label "([^"]+)"', item):
            net = m.group(1)
            if net in POWER_NETS or net in seen:
                continue
            seen.add(net)
            nets.append(net)
    return nets


def content_bbox(sh) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for sym in sh.symbols:
        for (x, y) in sym.pins.values():
            xs.append(x)
            ys.append(y)
    for item in sh.items:
        for m in re.finditer(
                r"\((?:at|xy|start|end)\s+(-?\d+(?:\.\d+)?)\s+"
                r"(-?\d+(?:\.\d+)?)", item):
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def _existing_j_refs(sh) -> set[int]:
    used: set[int] = set()
    for sym in sh.symbols:
        m = re.fullmatch(r"J(\d+)", sym.ref)
        if m:
            used.add(int(m.group(1)))
    return used


def _write_csv(sheet_name: str, rows: Iterable[tuple[str, int, str, str]]) -> str:
    outdir = os.path.join(PROJECT_DIR, "output", "backplane")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{sheet_name}_backplane.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "connector", "pin", "net", "role"])
        for row in rows:
            w.writerow(row)
    return path


def place_backplane(sh, sheet_name: str, x: float | None = None,
                    y: float = 60.0, pitch: float = 60.0,
                    note: bool = True,
                    nets: Iterable[str] | None = None) -> int:
    """Place the board's 2x20P headers and return the header count.

    ``nets`` overrides the auto-collected global labels.  This is used by the
    board connector sheets: they expose a deliberate subset of the module
    nets (the backplane interface), not every global label on the sheet.
    """
    if nets is None:
        net_list = collect_global_nets(sh)
    else:
        net_list = sorted({n for n in nets if n not in POWER_NETS})
    nets = sorted(net_list,
                  key=lambda n: (net_rank(n), natural_key(n)))
    if not nets:
        return 0
    chunks = [nets[i:i + len(SIGNAL_PINS)]
              for i in range(0, len(nets), len(SIGNAL_PINS))]

    minx, miny, maxx, maxy = content_bbox(sh)
    if x is None:
        x = maxx + 40.0

    used = _existing_j_refs(sh)
    start_ref = (max(used) + 1) if used else 1
    rows: list[tuple[str, int, str, str]] = []

    for ci, chunk in enumerate(chunks):
        ref = f"J{start_ref + ci}"
        cy = y + ci * pitch
        sym = sh.add_symbol(
            HEADER_LIB, ref, "BACKPLANE", x, cy,
            footprint=HEADER_FOOTPRINT,
            description=f"2x20P backplane connector {sheet_name} {ref}",
        )
        for pin, net in POWER_PINS.items():
            sh.stub_label(sym, str(pin), net, length=3.81, local=False)
            rows.append((sheet_name, f"J{start_ref + ci}", pin, net, "power"))
        for pin, net in zip(SIGNAL_PINS, chunk):
            sh.stub_label(sym, str(pin), net, length=3.81, local=False)
            rows.append((sheet_name, f"J{start_ref + ci}", pin, net, "signal"))
        for pin in SIGNAL_PINS[len(chunk):]:
            sh.stub_nc(sym, str(pin))
            rows.append((sheet_name, f"J{start_ref + ci}", pin, "", "nc"))

    _write_csv(sheet_name, rows)

    if note:
        refs = (f"J{start_ref}" if len(chunks) == 1
                else f"J{start_ref}..J{start_ref + len(chunks) - 1}")
        sh.add_text(
            f"BACKPLANE {sheet_name}: {refs} "
            f"({len(nets)} signals).\n"
            "2x20P pinout: 1-4 +5V, 5-8 +3V3 (reserved), 9-14 GND, 15-40 signals.\n"
            "Signal positions are per board; see output/backplane/ for the pinout.",
            x - 5.08, y - 45.0, size=0.95, justify="left top",
        )

    # Extend the page so the connector strip is inside the frame.
    std_w, std_h = PAPER_MM.get(sh.paper, (maxx + 200.0, maxy + 200.0))
    width = max(std_w, x + 120.0, maxx + 60.0)
    height = max(std_h, maxy + 40.0,
                 y + len(chunks) * pitch + 10.0)
    sh.paper = "User"
    sh.paper_w = width
    sh.paper_h = height
    return len(chunks)
