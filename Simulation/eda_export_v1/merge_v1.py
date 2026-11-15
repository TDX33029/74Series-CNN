"""Merge the freshly exported 2026-11-15 board netlists into one system model.

Same semantics as Simulation/eda_export/merge_boards.py: global (named) nets
merge across boards (backplane = same-name join), $-auto nets stay board-local,
and every pin is board-qualified.

Output: merged_system_v1.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = os.path.join(HERE, "boards")
OUT = os.path.join(HERE, "merged_system_v1.json")


def parse_protel2(path):
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    lines = text.split("\n")
    comps, nets = {}, {}
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "[":
            rec = {}
            j = i + 1
            while j < n and lines[j].strip() != "]":
                key = lines[j].strip()
                val = lines[j + 1].strip() if j + 1 < n else ""
                if key in ("DESIGNATOR", "PARTTYPE", "FOOTPRINT") and key not in rec:
                    rec[key] = val
                j += 2
            ref = rec.get("DESIGNATOR", "")
            if ref:
                comps[ref] = {"parttype": rec.get("PARTTYPE", ""),
                              "footprint": rec.get("FOOTPRINT", "")}
            i = j + 1
        elif s == "(":
            name = lines[i + 1].strip() if i + 1 < n else ""
            j = i + 2
            pins = set()
            while j < n and lines[j].strip() != ")":
                tok = lines[j].strip().split()
                if tok and "-" in tok[0]:
                    rp = tok[0]
                    k = rp.index("-")
                    pins.add((rp[:k], rp[k + 1:]))
                j += 1
            if name:
                nets.setdefault(name, set()).update(pins)
            i = j + 1
        else:
            i += 1
    return comps, nets


def net_key(board, name):
    if name.startswith("$"):
        return "%s::%s" % (board, name)
    return "G::" + name


def main():
    files = sorted(f for f in os.listdir(BOARDS) if f.endswith(".txt"))
    comps, dup_refs, nets = {}, [], {}
    for fn in files:
        board = fn[:-4]
        bc, bn = parse_protel2(os.path.join(BOARDS, fn))
        for ref, rec in bc.items():
            if ref in comps:
                dup_refs.append((ref, board))
                continue
            comps[ref] = dict(rec, board=board)
        for name, pins in bn.items():
            key = net_key(board, name)
            nets.setdefault(key, set()).update((board, r, p) for r, p in pins)

    pin_net, dups = {}, []
    for key, pins in nets.items():
        for bp in pins:
            if bp in pin_net:
                dups.append((bp, pin_net[bp], key))
            pin_net[bp] = key
    ghosts = [bp for bp in pin_net if bp[1] not in comps]
    out = {
        "boards": [f[:-4] for f in files],
        "comps": comps,
        "dup_refs": sorted(set(r for r, _ in dup_refs)),
        "pins": {"%s|%s.%s" % (b, r, p): k for (b, r, p), k in sorted(pin_net.items())},
        "nets": {k: sorted("%s|%s.%s" % (b, r, p) for b, r, p in v)
                 for k, v in sorted(nets.items())},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("boards: %d" % len(files))
    print("comps: %d  dup_refs: %d  nets: %d  pins: %d  ghosts: %d  dup_pins: %d"
          % (len(comps), len(set(r for r, _ in dup_refs)), len(nets), len(pin_net),
             len(ghosts), len(dups)))
    print("global nets: %d" % len([k for k in nets if k.startswith("G::")]))
    if dups:
        for d in dups[:10]:
            print("  dup pin %s in %s and %s" % d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
