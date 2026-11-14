"""Rebuild the correct Protel2 netlist for B04-6: every pin's net = the label
of the stub wire touching it (the geometry labels are verified correct); the
engine's stored net table carries a stale +5V/+VLED->GND merge record, so the
exported blocks for {+5V blob, +5VX, GND, +VLED} are rebuilt from the pin ->
wire -> label map.  All other blocks pass through unchanged.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def segs_of(line):
    return [(line[i], line[i + 1], line[i + 2], line[i + 3])
            for i in range(0, len(line) - 2, 2)]


def d2(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    sq = dx * dx + dy * dy
    if sq == 0:
        return (px - x1) ** 2 + (py - y1) ** 2
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / sq))
    cx, cy = x1 + t * dx, y1 + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def parse_blocks(text):
    """-> list of (name, [pin_tokens]) preserving order."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = []
    state = 0
    cur = None
    for ln in lines:
        s = ln.strip()
        if s == "(":
            state = 1
            cur = None
        elif s == ")":
            state = 0
        elif state == 1:
            cur = s
            state = 2
            blocks.append([cur, []])
        elif state == 2 and s:
            blocks[-1][1].append(s)
    return blocks


def main():
    src = open(os.path.join(HERE, "surgery_src.txt"), encoding="utf-8").read()
    blocks = parse_blocks(src)
    print(f"src blocks: {len(blocks)}")

    # pin -> stub label from the fetched page data
    pin_label = {}
    for page in ("s07_conv1", "b04_conn"):
        pg = json.load(open(os.path.join(HERE, f"b046_page_{page}.json"),
                            encoding="utf-8"))
        for p in pg["pins"]:
            key = (p["designator"], p["pinNumber"], p["x"], p["y"])
            labels = set()
            for w in pg["wires"]:
                for (x1, y1, x2, y2) in segs_of(w["line"]):
                    if d2(p["x"], p["y"], x1, y1, x2, y2) <= 30.25:
                        labels.add(w["net"] or "")
                        break
            if len(labels) == 1:
                pin_label[key] = next(iter(labels))
            elif len(labels) > 1:
                pin_label[key] = "MULTI:" + ",".join(sorted(labels))

    # classify the pins currently inside the merged blocks
    MERGED = {"+5V", "+5VX", "GND", "+VLED"}
    new_blocks = []
    fixed = {"+5V": [], "+VLED": [], "GND": []}
    unresolvable = []
    for name, pins in blocks:
        if name not in MERGED:
            new_blocks.append((name, pins))
            continue
        for tok in pins:
            rp = tok.split()[0]
            k = rp.index("-")
            ref, num = rp[:k], rp[k + 1:]
            # find pin coords from page data
            coord = None
            for page in ("s07_conv1", "b04_conn"):
                pg = json.load(open(os.path.join(HERE, f"b046_page_{page}.json"),
                                    encoding="utf-8"))
                for p in pg["pins"]:
                    if p["designator"] == ref and p["pinNumber"] == num:
                        coord = (ref, num, p["x"], p["y"])
                        break
                if coord:
                    break
            if coord is None:
                unresolvable.append(tok)
                continue
            lab = pin_label.get(coord, "?")
            if lab in ("+5V", "+VLED", "GND"):
                fixed[lab].append(tok)
            else:
                unresolvable.append((tok, lab))

    for lab in ("+5V", "+VLED", "GND"):
        if fixed[lab]:
            new_blocks.append((lab, fixed[lab]))
        print(f"{lab}: {len(fixed[lab])} pins")
    if unresolvable:
        print("UNRESOLVED:")
        for u in unresolvable[:15]:
            print("   ", u)

    # emit Protel2
    out = ["PROTEL NETLIST 2.0"]
    for name, pins in blocks:
        if name in MERGED:
            continue
        out.append("[")
        # component blocks are embedded in src as [...] too - handled below
    # We must preserve the component section: easiest is textual surgery on
    # the source: keep everything up to the first "(" net block, then emit
    # corrected net blocks.
    first_net = src.replace("\r\n", "\n").index("\n(\n")
    head = src.replace("\r\n", "\n")[:first_net + 1]
    body = [head]
    for name, pins in new_blocks:
        body.append("(\n" + name + "\n")
        for tok in pins:
            body.append(tok + "\n")
        body.append(")\n")
    result = "".join(body)
    open(os.path.join(HERE, "surgery_fixed.txt"), "w", encoding="utf-8",
         newline="").write(result)
    print("written surgery_fixed.txt, length", len(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
