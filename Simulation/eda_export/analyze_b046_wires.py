"""Analyse the B04-6_CONV1 schematic wire dump: build the endpoint/T-touch
connectivity graph, find connected components, and locate the wires that
bridge the +5V wires to the GND wires (the collapse culprits).

Schematic wire geometry units: 0.01 inch.  Two wires join when an endpoint
of one lies on the other segment (T junction) or endpoints coincide.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def load(fn):
    return json.load(open(os.path.join(HERE, fn), encoding="utf-8"))


def on_segment(px, py, x1, y1, x2, y2, eps=5.5):
    """Point-to-segment distance <= eps (schematic units, 1 unit = 0.01in)."""
    dx, dy = x2 - x1, y2 - y1
    sq = dx * dx + dy * dy
    if sq == 0:
        return (px - x1) ** 2 + (py - y1) ** 2 <= eps * eps
    t = ((px - x1) * dx + (py - y1) * dy) / sq
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= eps * eps


def main():
    wires = load(sys.argv[1] if len(sys.argv) > 1 else "b046_wires.json")
    n = len(wires)
    segs = []
    for idx, w in enumerate(wires):
        ln = w["line"]
        if not ln or len(ln) < 4:
            continue
        segs.append((idx, ln[0], ln[1], ln[2], ln[3]))

    # union-find
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(segs)):
        _, x1, y1, x2, y2 = segs[i]
        for j in range(i + 1, len(segs)):
            _, a1, b1, a2, b2 = segs[j]
            if (on_segment(x1, y1, a1, b1, a2, b2) or on_segment(x2, y2, a1, b1, a2, b2)
                    or on_segment(a1, b1, x1, y1, x2, y2) or on_segment(a2, b2, x1, y1, x2, y2)):
                union(segs[i][0], segs[j][0])

    comps = defaultdict(list)
    for idx, *_ in segs:
        comps[find(idx)].append(idx)
    sizes = sorted(((len(v), k) for k, v in comps.items()), reverse=True)
    print(f"wires: {n}  components: {len(comps)}")
    print("top components:", sizes[:6])

    net_of = {i: (w["net"] or "") for i, w in enumerate(wires)}
    for size, root in sizes[:3]:
        members = comps[root]
        nets = defaultdict(int)
        for i in members:
            nets[net_of[i] or "<empty>"] += 1
        print(f"\n-- component size {size}: net mix {dict(sorted(nets.items(), key=lambda x: -x[1])[:10])}")
        xs = [wires[i]["line"][0] for i in members] + [wires[i]["line"][2] for i in members]
        ys = [wires[i]["line"][1] for i in members] + [wires[i]["line"][3] for i in members]
        print(f"   bbox x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}")
        if size <= 40 or True:
            # list bridge candidates: wires whose net differs from GND but are
            # in the same component as GND wires
            has_gnd = any(net_of[i] == "GND" for i in members)
            has_p5 = any(net_of[i] == "+5V" for i in members)
            if has_gnd and has_p5:
                bridges = [i for i in members if net_of[i] not in ("GND", "+5V")]
                print(f"   *** merges GND and +5V; {len(bridges)} non-power members")
                for i in sorted(bridges, key=lambda x: net_of[x])[:40]:
                    w = wires[i]
                    print(f"     {w['id']} net={w['net']!r} line={w['line']}")

    # also dump per-wire list of the biggest component for offline review
    if sizes:
        root = sizes[0][1]
        out = [dict(wires[i], comp=str(root)) for i in comps[root]]
        json.dump(out, open(os.path.join(HERE, "b046_giant_component.json"), "w"), indent=1)
        print(f"\nwrote b046_giant_component.json ({len(out)} wires)")


if __name__ == "__main__":
    main()
