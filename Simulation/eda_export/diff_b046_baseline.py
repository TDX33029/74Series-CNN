"""Diff the current B04-6_CONV1 export against its 11-12 08:10 baseline
(netlist_compare_v2/jlc_netlists/B04-6_CONV1__b04_conn.net) at pin level.

Baseline is pre-LED-expansion and pre-V19..V26; documented changes on top of
it are expected.  Everything else = damage caused by the LED incident.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_boards import parse_protel2  # noqa: E402

BASE = r"D:/Document/tempPrj/74Series-CNN/netlist_compare_v2/jlc_netlists/B04-6_CONV1__b04_conn.net"
CURR = os.path.join(HERE, "boards", "B04-6_CONV1.txt")


def pin_nets(comps, nets):
    pn = {}
    for name, pins in nets.items():
        for r, p in pins:
            pn.setdefault((r, p), []).append(name)
    return pn


def main():
    bc, bn = parse_protel2(BASE)
    cc, cn = parse_protel2(CURR)
    bp = pin_nets(bc, bn)
    cp = pin_nets(cc, cn)
    print(f"baseline: comps {len(bc)} nets {len(bn)} pins {len(bp)}")
    print(f"current : comps {len(cc)} nets {len(cn)} pins {len(cp)}")

    allp = sorted(set(bp) | set(cp))
    changed = []
    for rp in allp:
        a = set(bp.get(rp, []))
        b = set(cp.get(rp, []))
        if a != b:
            changed.append((rp, sorted(a), sorted(b)))
    print(f"pins with changed net: {len(changed)}")

    out = []
    for (r, p), a, b in changed:
        out.append(dict(ref=r, pin=p, base_nets=a, curr_nets=b))
    json.dump(out, open(os.path.join(HERE, "b046_pin_diffs.json"), "w"),
              indent=1, ensure_ascii=False)

    # summary by current net
    from collections import defaultdict
    by_curr = defaultdict(list)
    for (r, p), a, b in changed:
        by_curr[tuple(b) if b else ("<none>",)].append((r, p, a))
    for curr, rows in sorted(by_curr.items(), key=lambda kv: -len(kv[1])):
        print(f"\n== now on {list(curr)} ({len(rows)} pins)")
        base_nets = defaultdict(int)
        for r, p, a in rows:
            for x in a:
                base_nets[x] += 1
        print(f"   came from: {dict(sorted(base_nets.items(), key=lambda x: -x[1])[:8])}")
        for r, p, a in rows[:12]:
            print(f"   {r}.{p}: base={a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
