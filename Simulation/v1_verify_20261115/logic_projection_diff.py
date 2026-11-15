"""Project both netlists onto logic-device pins only and compare net by net.

Difference between 11-14 and 11-15 exports is confined to the LED indicator
block (Q9/R13 orphaned).  This script proves that no net that carries a logic
pin changed membership once non-logic parts (LED / transistor / resistor) are
projected away.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(os.path.dirname(HERE), "eda_export", "merged_system.json")
NEW = os.path.join(os.path.dirname(HERE), "eda_export_v1", "merged_system_v1.json")

LOGIC_PREF = ("74", "27C512", "28C256", "6264", "62256", "HY6264", "OSC")


def is_logic(pt):
    p = pt.upper()
    return any(k in p for k in LOGIC_PREF)


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    comps = d["comps"]
    nets = d["nets"]
    proj = {}
    for k, members in nets.items():
        keep = set()
        for m in members:
            tail = m.split("|")[-1]
            ref = tail.split(".")[0]
            c = comps.get(ref)
            if c and is_logic(c["parttype"]):
                keep.add(m)
        if keep:
            proj[k] = keep
    return proj, len(nets)


def main():
    old, nold = load(OLD)
    new, nnew = load(NEW)
    print("nets: old %d new %d | logic-only nets: old %d new %d" %
          (nold, nnew, len(old), len(new)))
    keys = set(old) | set(new)
    same = sum(1 for k in keys if old.get(k) == new.get(k))
    bad = [k for k in keys if old.get(k) != new.get(k)]
    print("logic-projected nets identical: %d / %d" % (same, len(keys)))
    for k in bad:
        o = old.get(k, set())
        n = new.get(k, set())
        print("  DIFF %s  -%s +%s" % (k, sorted(o - n), sorted(n - o)))
    print("VERDICT:", "PASS (no logic pin moved)" if not bad else "FAIL")


if __name__ == "__main__":
    main()
