"""Check the 12-board backplane pinout against the board partition.

Inputs:
    output/backplane/backplane_pinout.csv   (final, renumbered J refs)
    output/boards/backplane_nets.csv        (net -> boards)
    the module .kicad_sch global labels     (source of truth)

Checks:
  1. every board's connector signal pins equal its computed external net list;
  2. each net appears on exactly the boards listed in backplane_nets.csv;
  3. no net is pinned twice on one board;
  4. every header has the fixed power map 1-4 +5V, 5-8 +3V3, 9-14 GND;
  5. internal nets (ACC/REQ pairs, IN_DATA1/2, SCORE_DATA) never reach a pin;
  6. the total is 32 headers / 1280 pins.

Run:
    python sim/check_backplane.py
"""
from __future__ import annotations

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

from backplane import POWER_NETS  # noqa: E402
from build_boards import BOARDS, compute_external  # noqa: E402

PINOUT = os.path.join(PROJECT_DIR, "output", "backplane", "backplane_pinout.csv")
NETS = os.path.join(PROJECT_DIR, "output", "boards", "backplane_nets.csv")

POWER_MAP = {**{p: "+5V" for p in range(1, 5)},
             **{p: "+3V3" for p in range(5, 9)},
             **{p: "GND" for p in range(9, 15)}}


class Log:
    def __init__(self) -> None:
        self.ok = True

    def check(self, cond: bool, text: str) -> None:
        print(("PASS: " if cond else "FAIL: ") + text)
        if not cond:
            self.ok = False


def main() -> int:
    log = Log()
    if not os.path.exists(PINOUT):
        print("missing pinout; run build_boards.py + gen_backplane_csv.py")
        return 1
    rows = list(csv.DictReader(open(PINOUT, encoding="utf-8-sig")))
    log.check(len({r["connector"] for r in rows}) == 32,
              "32 headers in pinout")
    log.check(len(rows) == 32 * 40, f"{len(rows)} pins (expected 1280)")

    # Board id from the connector sheet name, e.g. B05_Conn -> 05.
    bad_sheet = [r["sheet"] for r in rows
                 if not re.fullmatch(r"B\d\d_Conn", r["sheet"])]
    log.check(not bad_sheet,
              f"connector sheet names are Bxx_Conn ({bad_sheet[:3]})")

    sig: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        if r["role"] != "signal" or not r["net"]:
            continue
        bid = r["sheet"][1:3]
        sig.setdefault(bid, {}).setdefault(r["net"], []).append(r["pin"])

    dup = [(b, n, p) for b, nets in sig.items() for n, p in nets.items()
           if len(p) > 1]
    log.check(not dup, f"no net pinned twice on a board ({dup[:3]})")

    external, net_boards = compute_external(BOARDS)
    for bid, _name, _func, _sheets, _stage in BOARDS:
        want = set(external[bid])
        got = set(sig.get(bid, {}))
        log.check(want == got,
                  f"B{bid}: connector nets match ({len(got)} pins, "
                  f"missing={sorted(want - got)[:3]}, extra={sorted(got - want)[:3]})")

    # Net -> boards from the pinout must equal the computed matrix.
    pin_boards: dict[str, set[str]] = {}
    for bid, nets in sig.items():
        for n in nets:
            pin_boards.setdefault(n, set()).add(bid)
    interboard = {n for n, bs in net_boards.items()
                  if len(bs) >= 2 and n not in POWER_NETS}
    log.check(set(pin_boards) == interboard,
              f"pinout net set matches ({len(pin_boards)} nets)")
    mism = [n for n, bs in pin_boards.items() if bs != net_boards[n]]
    log.check(not mism, f"net -> board sets match ({mism[:5]})")

    # Fixed power map on every header.
    power_bad = []
    for r in rows:
        p = int(r["pin"])
        if p <= 14 and (r["role"] != "power" or r["net"] != POWER_MAP[p]):
            power_bad.append((r["connector"], p, r["net"], r["role"]))
    log.check(not power_bad, f"power pins 1-14 fixed ({power_bad[:3]})")

    # Internal nets never appear on a pin.
    internal = []
    for bid, _name, _func, sheets, _stage in BOARDS:
        own = set()
        for s in sheets:
            text = open(os.path.join(PROJECT_DIR, s), encoding="utf-8").read()
            own |= set(re.findall(r'\(global_label "([^"]+)"', text))
        internal.extend(n for n in own - set(external[bid]) - POWER_NETS
                        if n in pin_boards)
    log.check(not internal, f"no internal net on a pin ({internal[:5]})")

    # No header may be empty; every net has at least one signal pin somewhere.
    log.check(len(sig) == 12, f"all 12 boards have connectors ({len(sig)})")
    print("\nRESULT:", "PASS" if log.ok else "FAIL")
    return 0 if log.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
