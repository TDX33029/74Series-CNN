"""Pin-level diff between two KiCad netlists (old -> new).

Used to produce the EasyEDA sync change list.  Compares electrical
connectivity per component pin, not net names:

  * components added / removed
  * pins whose neighbour set changed (old net, new net, both node sets)
  * nets renamed while keeping exactly the same nodes

Usage:
    python diff_netlist.py OLD.net NEW.net [--detail]
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/tools"
sys.path.insert(0, TOOLS)
import kicad_sexpr as k  # noqa: E402


def load(path: str):
    with open(path, encoding="utf-8") as f:
        root = k.parse(f.read())[0]
    comps = {}
    cblock = k.first(root, "components")
    for comp in k.children(cblock, "comp"):
        ref = k.atoms(k.first(comp, "ref"))[0]
        value = k.atoms(k.first(comp, "value"))[0]
        lib = part = ""
        ls = k.first(comp, "libsource")
        if ls is not None:
            lib = k.atoms(k.first(ls, "lib"))[0]
            part = k.atoms(k.first(ls, "part"))[0]
        sheet = ""
        for prop in k.children(comp, "property"):
            nm = k.first(prop, "name")
            if nm is not None and k.atoms(nm)[0] == "Sheetname":
                sheet = k.atoms(k.first(prop, "value"))[0]
        comps[ref] = dict(value=value, lib=lib, part=part, sheet=sheet)
    nets = {}
    nblock = k.first(root, "nets")
    for net in k.children(nblock, "net"):
        name = k.atoms(k.first(net, "name"))[0]
        nodes = frozenset(
            (k.atoms(k.first(n, "ref"))[0], k.atoms(k.first(n, "pin"))[0])
            for n in k.children(net, "node")
        )
        nets[name] = nodes
    return comps, nets


def pin_index(nets):
    idx = {}
    for name, nodes in nets.items():
        for p in nodes:
            idx[p] = name
    return idx


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    old_path, new_path = argv[1], argv[2]
    detail = "--detail" in argv
    oc, on = load(old_path)
    nc, nn = load(new_path)
    op, np_ = pin_index(on), pin_index(nn)

    added = sorted(set(nc) - set(oc), key=lambda r: (nc[r]["sheet"], r))
    removed = sorted(set(oc) - set(nc), key=lambda r: (oc[r]["sheet"], r))
    common = sorted(set(oc) & set(nc), key=lambda r: (nc[r]["sheet"], r))

    # components
    if added or removed:
        print("=== components added ===")
        for r in added:
            c = nc[r]
            print(f"  + {r:8} {c['part']:10} {c['value']:20} {c['sheet']}")
        print("=== components removed ===")
        for r in removed:
            c = oc[r]
            print(f"  - {r:8} {c['part']:10} {c['value']:20} {c['sheet']}")

    changed_part = [(r, oc[r], nc[r]) for r in common
                    if (oc[r]["part"], oc[r]["value"]) != (nc[r]["part"], nc[r]["value"])]
    if changed_part:
        print("=== components with changed part/value (same ref) ===")
        for r, a, b in changed_part:
            print(f"  ~ {r:8} {b['sheet']:20} {a['part']:10} -> {b['part']:10}")

    # pinned connectivity changes
    by_sheet = defaultdict(list)
    renamed = []
    for r in common:
        sheet = nc[r]["sheet"]
        pins = {p for (rr, p) in op if rr == r} | {p for (rr, p) in np_ if rr == r}
        for p in sorted(pins, key=lambda x: (len(x), x)):
            a = op.get((r, p))
            b = np_.get((r, p))
            if a == b:
                continue
            na = on.get(a, frozenset())
            nb = nn.get(b, frozenset())
            if a and b and na == nb:
                renamed.append((a, b, r, p))
                continue
            by_sheet[sheet].append((r, p, a, b, na, nb))

    # net renames (same nodes, different name)
    if renamed:
        seen = {}
        for a, b, r, p in renamed:
            seen.setdefault((a, b), []).append(f"{r}.{p}")
        print("=== nets renamed (connectivity unchanged) ===")
        for (a, b), pins in sorted(seen.items()):
            print(f"  {a}  ->  {b}   ({len(pins)} pins: {', '.join(pins[:6])}"
                  f"{'...' if len(pins) > 6 else ''})")

    print("=== pin connectivity changes by sheet ===")
    for sheet in sorted(by_sheet):
        rows = by_sheet[sheet]
        print(f"\n-- {sheet} ({len(rows)} pins)")
        for r, p, a, b, na, nb in rows:
            print(f"  {r}.{p}: {a or '<none>'}  ->  {b or '<none>'}")
            if detail:
                print(f"      old nodes: {', '.join(f'{x}.{y}' for x, y in sorted(na))}")
                print(f"      new nodes: {', '.join(f'{x}.{y}' for x, y in sorted(nb))}")
    print(f"\nsummary: +{len(added)} -{len(removed)} components, "
          f"{sum(len(v) for v in by_sheet.values())} changed pins, "
          f"{len(renamed)} renamed pin attachments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
