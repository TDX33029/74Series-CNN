"""Correct wire-wire junction analysis treating each wire as a polyline.
Finds junction-connected components and the wires bridging unlike nets.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EPS = 5.5


def segs_of(line):
    out = []
    for i in range(0, len(line) - 2, 2):
        out.append((line[i], line[i + 1], line[i + 2], line[i + 3]))
    return out


def dist_point_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    sq = dx * dx + dy * dy
    if sq == 0:
        return (px - x1) ** 2 + (py - y1) ** 2
    t = ((px - x1) * dx + (py - y1) * dy) / sq
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def wires_touch(la, lb):
    sa, sb = segs_of(la), segs_of(lb)
    for x1, y1, x2, y2 in sa:
        for a1, b1, a2, b2 in sb:
            if (dist_point_seg(x1, y1, a1, b1, a2, b2) <= EPS * EPS
                    or dist_point_seg(x2, y2, a1, b1, a2, b2) <= EPS * EPS
                    or dist_point_seg(a1, b1, x1, y1, x2, y2) <= EPS * EPS
                    or dist_point_seg(a2, b2, x1, y1, x2, y2) <= EPS * EPS):
                return True
    return False


def main():
    page = sys.argv[1] if len(sys.argv) > 1 else "b04_conn"
    pg = json.load(open(os.path.join(HERE, f"b046_page_{page}.json"), encoding="utf-8"))
    wires = pg["wires"]
    n = len(wires)
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

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if wires_touch(wires[i]["line"], wires[j]["line"]):
                union(i, j)
                pairs.append((i, j))

    comps = defaultdict(list)
    for i in range(n):
        comps[find(i)].append(i)
    sizes = sorted(((len(v), k) for k, v in comps.items()), reverse=True)
    print(f"page {page}: {n} wires, {len(pairs)} junction pairs, {len(comps)} components")
    print("top:", sizes[:6])

    net_of = [w["net"] or "<empty>" for w in wires]
    for size, root in sizes[:4]:
        members = comps[root]
        nets = defaultdict(int)
        for i in members:
            nets[net_of[i]] += 1
        print(f"\n-- comp size {size}: {dict(sorted(nets.items(), key=lambda x: -x[1])[:12])}")
        if size > 1:
            for i in members[:50]:
                print(f"   {wires[i]['id']} net={net_of[i]!r} {wires[i]['line']}")


if __name__ == "__main__":
    main()
