"""Insurance cross-check: is today's EDA export the same hardware as the
2026-11-14 export that was already verified?

LED indicator parts are excluded (they were renamed on 11-14 and are skipped
by the DUT generator anyway), so what remains is the logic/power structure.

Levels compared:
  1. component inventory (ref -> parttype, per board)
  2. pin -> net connectivity (neighbour sets, board-qualified)
  3. net membership for global nets
"""
import json
import sys
from collections import defaultdict

OLD = r"D:/Document/tempPrj/74Series-CNN/Simulation/eda_export/merged_system.json"
NEW = r"D:/Document/tempPrj/74Series-CNN/Simulation/eda_export_v1/merged_system_v1.json"


def is_led(ref, rec):
    return ref.upper().startswith("LED") or "LED" in rec.get("parttype", "").upper()


def logic_model(d):
    led = {r for r, rec in d["comps"].items() if is_led(r, rec)}
    pins = {p: k for p, k in d["pins"].items() if p.split("|")[1].split(".")[0] not in led}
    nets = defaultdict(set)
    for p, k in pins.items():
        nets[k].add(p)
    comps = {r: rec for r, rec in d["comps"].items() if r not in led}
    return comps, pins, {k: v for k, v in nets.items()}


def neighbours(pins):
    nb = defaultdict(set)
    netpins = defaultdict(set)
    for p, k in pins.items():
        netpins[k].add(p)
    for ps in netpins.values():
        for p in ps:
            nb[p] |= ps - {p}
    return nb


def main():
    old, new = json.load(open(OLD, encoding="utf-8")), json.load(open(NEW, encoding="utf-8"))
    oc, op, on = logic_model(old)
    nc, np_, nn = logic_model(new)
    print("logic comps: old %d new %d | pins: old %d new %d | nets: old %d new %d"
          % (len(oc), len(nc), len(op), len(np_), len(on), len(nn)))

    only_old = sorted(set(oc) - set(nc))
    only_new = sorted(set(nc) - set(oc))
    changed = sorted(r for r in set(oc) & set(nc)
                     if (oc[r]["parttype"], oc[r]["board"]) != (nc[r]["parttype"], nc[r]["board"]))
    print("\n[inventory] only-11-14 %d, only-11-15 %d, changed %d"
          % (len(only_old), len(only_new), len(changed)))
    for r in only_old[:20]:
        print("  - %-8s %-24s %s" % (r, oc[r]["parttype"], oc[r]["board"]))
    for r in only_new[:20]:
        print("  + %-8s %-24s %s" % (r, nc[r]["parttype"], nc[r]["board"]))
    for r in changed[:20]:
        print("  ~ %-8s %r -> %r" % (r, (oc[r]["parttype"], oc[r]["board"]),
                                     (nc[r]["parttype"], nc[r]["board"])))

    onb, nnb = neighbours(op), neighbours(np_)
    keys = set(op) | set(np_)
    real = []
    for p in sorted(keys):
        a, b = onb.get(p, set()), nnb.get(p, set())
        if a != b:
            real.append((p, a - b, b - a))
    print("\n[connectivity] pins whose neighbour set differs: %d of %d" % (len(real), len(keys)))
    for p, gone, add in real[:80]:
        g = ", ".join(sorted("%s.%s" % (x.split("|")[1].split(".")[0], x.split(".")[-1])
                             for x in gone))[:120]
        n = ", ".join(sorted("%s.%s" % (x.split("|")[1].split(".")[0], x.split(".")[-1])
                             for x in add))[:120]
        print("  %-26s  -[%s]  +[%s]" % (p, g, n))

    # net-level: same membership but renamed == harmless
    oset = {frozenset(v): k for k, v in on.items()}
    nset = {frozenset(v): k for k, v in nn.items()}
    oo = [s for s in oset if s not in nset]
    no = [s for s in nset if s not in oset]
    print("\n[nets] identical membership: %d | old-only %d | new-only %d"
          % (len([s for s in oset if s in nset]), len(oo), len(no)))
    for s in oo[:10]:
        print("  old-only %-40s %d pins" % (oset[s], len(s)))
    for s in no[:10]:
        print("  new-only %-40s %d pins" % (nset[s], len(s)))

    ok = not (only_old or only_new or changed or real)
    print("\nVERDICT: %s" % ("IDENTICAL logic connectivity" if ok else "DIFFERENT"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
