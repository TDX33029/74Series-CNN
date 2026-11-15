"""Per-board statistics of today's export, for the verification report."""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "eda_export_v1"))
from merge_v1 import parse_protel2  # noqa: E402

BOARDS = os.path.join(os.path.dirname(HERE), "eda_export_v1", "boards")
OUT = os.path.join(HERE, "board_stats.csv")


def main():
    rows = []
    total = Counter()
    for fn in sorted(os.listdir(BOARDS)):
        if not fn.endswith(".txt"):
            continue
        comps, nets = parse_protel2(os.path.join(BOARDS, fn))
        parts = Counter()
        for r, v in comps.items():
            p = v["parttype"].upper()
            if "74HC" in p or "74HCT" in p or "74LS" in p:
                parts["74xx"] += 1
            elif "27C512" in p:
                parts["27C512"] += 1
            elif "28C256" in p:
                parts["28C256"] += 1
            elif "6264" in p:
                parts["6264"] += 1
            elif "62256" in p:
                parts["62256"] += 1
            elif p.startswith("LED") or "HLMP" in p:
                parts["LED"] += 1
            elif r.upper().startswith("Q"):
                parts["Q"] += 1
            elif p.startswith("R"):
                parts["R"] += 1
            else:
                parts["other"] += 1
        pins = sum(len(v) for v in nets.values())
        row = {"board": fn[:-4], "components": len(comps), "nets": len(nets),
               "pins": pins}
        row.update(parts)
        rows.append(row)
        for k in ("components", "nets", "pins"):
            total[k] += len(comps) if k == "components" else (len(nets) if k == "nets" else pins)
        total.update(parts)
    keys = ["board", "components", "74xx", "27C512", "28C256", "6264", "62256",
            "LED", "Q", "R", "other", "nets", "pins"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, 0) for k in keys})
    print("wrote %s (%d boards)" % (OUT, len(rows)))
    print("TOTAL:", dict(total))


if __name__ == "__main__":
    main()
