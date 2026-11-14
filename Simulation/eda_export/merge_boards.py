"""Parse the 47 exported EasyEDA Protel2 board netlists, merge them into one
system-level connectivity model (global net names merge across boards,
sheet-local and $-auto names stay board-local), and dump JSON.

Output: eda_export/merged_system.json
  comps:  ref -> {board, parttype, footprint}
  pins:   "ref.pin" -> net key
  nets:   net key -> ["ref.pin", ...]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = os.path.join(HERE, "boards")
OUT = os.path.join(HERE, "merged_system.json")


def parse_protel2(path):
    """Return (comps, nets) for one Protel2 netlist file.

    comps: ref -> {parttype, footprint}
    nets:  name -> set("ref.pin")
    """
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    lines = text.split("\n")
    comps = {}
    nets = {}
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "[":
            # component block
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
            # net block: next line = name, then "ref-pin part-pintype" lines
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
    # Auto-generated $-net names are per-page unique -> board-local.
    # Everything else (including /Sheet/name labels) merges by full name:
    # the 47 physical boards are schematic-independent and their same-named
    # fragment nets are joined by the backplane (same net name = same node).
    if name.startswith("$"):
        return f"{board}::{name}"
    return f"G::{name}"


def main():
    files = sorted(f for f in os.listdir(BOARDS) if f.endswith(".txt"))
    comps = {}
    dup_refs = set()
    nets = {}
    for fn in files:
        board = fn[:-4]
        bc, bn = parse_protel2(os.path.join(BOARDS, fn))
        for ref, rec in bc.items():
            if ref in comps:
                dup_refs.add(ref)
                # keep first occurrence's part record; board attribute of the
                # FIRST board wins, duplicates tracked separately
                continue
            comps[ref] = dict(rec, board=board)
        for name, pins in bn.items():
            key = net_key(board, name)
            # board-qualify every pin so cross-board ref collisions
            # (LED modules, per-board R numbering) cannot short together
            nets.setdefault(key, set()).update((board, r, p) for r, p in pins)

    # pin -> net index (board-qualified)
    pin_net = {}
    for key, pins in nets.items():
        for bp in pins:
            if bp in pin_net:
                print(f"!! pin {bp} on multiple nets: {pin_net[bp]} and {key}")
            pin_net[bp] = key

    ghosts = [bp for bp in pin_net if bp[1] not in comps]
    out = {
        "comps": comps,
        "dup_refs": sorted(dup_refs),
        "pins": {f"{b}|{r}.{p}": k for (b, r, p), k in sorted(pin_net.items())},
        "nets": {k: sorted(f"{b}|{r}.{p}" for b, r, p in v)
                 for k, v in sorted(nets.items())},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"comps: {len(comps)}  dup_refs: {len(dup_refs)}  "
          f"nets: {len(nets)}  pins: {len(pin_net)}  ghosts: {len(ghosts)}")
    g = [k for k in nets if k.startswith("G::")]
    print(f"global nets: {len(g)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
