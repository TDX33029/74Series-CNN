"""B04-6 damage analysis: map each damaged pin (baseline net != current net,
current net == the GND blob) to the wires touching it, and list suspicious
long wires on both pages.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DAMAGED = json.load(open(os.path.join(HERE, "b046_pin_diffs.json"), encoding="utf-8"))
BASE = json.load(open(os.path.join(HERE, "..", "..", "b046_baseline_pins.json"), encoding="utf-8")) if False else None


def load_page(name):
    return json.load(open(os.path.join(HERE, f"b046_page_{name}.json"), encoding="utf-8"))


def touches(line, px, py, eps=5.5):
    """True if point (px,py) touches the polyline (x1,y1,x2,y2,...)."""
    if not line or len(line) < 4 or len(line) % 2:
        return False
    for i in range(0, len(line) - 2, 2):
        x1, y1, x2, y2 = line[i], line[i + 1], line[i + 2], line[i + 3]
        dx, dy = x2 - x1, y2 - y1
        sq = dx * dx + dy * dy
        if sq == 0:
            if (px - x1) ** 2 + (py - y1) ** 2 <= eps * eps:
                return True
            continue
        t = ((px - x1) * dx + (py - y1) * dy) / sq
        t = max(0.0, min(1.0, t))
        cx, cy = x1 + t * dx, y1 + t * dy
        if (px - cx) ** 2 + (py - cy) ** 2 <= eps * eps:
            return True
    return False


def main():
    damage = {(d["ref"], d["pin"]): d for d in DAMAGED
              if d["curr_nets"] == ["GND"] or (len(d["curr_nets"]) == 1 and d["curr_nets"][0] == "GND")}
    print(f"damaged pins (now on GND): {len(damage)}")

    for page in ("s07_conv1", "b04_conn"):
        pg = load_page(page)
        wires = pg["wires"]
        pins = pg["pins"]
        print(f"\n===== page {page}: {len(wires)} wires, {len(pins)} pins =====")

        # suspicious long wires (span > 300 units)
        long_wires = [(w["id"], w["net"], w["line"]) for w in wires
                      if abs(w["line"][0] - w["line"][2]) + abs(w["line"][1] - w["line"][3]) > 300]
        print(f"long wires (>300 span): {len(long_wires)}")
        for wid, net, line in long_wires[:15]:
            print(f"   {wid} net={net!r} line={line}")

        # map damaged pins of this page to touching wires
        byref = defaultdict(list)
        for p in pins:
            byref[p["designator"]].append(p)
        n_mapped = 0
        for (ref, pin), d in sorted(damage.items()):
            cand = [p for p in byref.get(ref, []) if p["pinNumber"] == pin]
            if not cand:
                continue
            p = cand[0]
            tw = [(w["id"], w["net"], w["line"]) for w in wires if touches(w["line"], p["x"], p["y"])]
            n_mapped += 1
            if n_mapped <= 25 or page == "b04_conn":
                print(f"   {ref}.{pin} @({p['x']},{p['y']}) pinnet={p['net']!r} base={d['base_nets']}")
                for wid, net, line in tw[:6]:
                    print(f"      wire {wid} net={net!r} {line}")
        print(f"   mapped {n_mapped} damaged pins on this page")


if __name__ == "__main__":
    main()
