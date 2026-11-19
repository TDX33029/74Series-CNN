import re, json
from collections import defaultdict
path = r"D:\Document\tempPrj\74Series-CNN\netlist_compare_v2\jlc_netlists\B03-4_MEMORY__B03-4_MEMORY.net"
text = open(path, encoding="utf-8", errors="replace").read()
POWER = {"GND", "VCC", "+5V", "+VLED", "VDD", "VSS", "AGND", "DGND", "+3.3V", "+12V", "-12V", "VPP"}
comps = {}
for m in re.finditer(r"^\[\r?\nDESIGNATOR\r?\n(.+?)\r?\nFOOTPRINT\r?\n(.+?)\r?\n", text, re.M):
    comps[m.group(1).strip()] = m.group(2).strip()
nets = {}
for m in re.finditer(r"^\(\r?\n(.+?)\r?\n(.*?)^\)", text, re.M | re.S):
    name = m.group(1).strip()
    body = m.group(2)
    pins = [t[0] + "-" + t[1] for t in re.findall(r"^([A-Za-z][\w+\-\.]*)-(\d+)\s", body, re.M)]
    nets[name] = pins
u_designators = sorted([d for d in comps if d.startswith("U")], key=lambda s: (len(s), s))
pair = defaultdict(int)
deg = defaultdict(int)
for name, pins in nets.items():
    if name in POWER:
        continue
    us = sorted(set(p.split("-", 1)[0] for p in pins if p.split("-", 1)[0].startswith("U")))
    for u in us:
        deg[u] += 1
    for i in range(len(us)):
        for j in range(i+1, len(us)):
            pair[(us[i], us[j])] += 1
out = {
    "comps_total": len(comps),
    "U": {d: comps[d] for d in u_designators},
    "nets_total": len(nets),
    "power_nets": sorted(set(nets) & POWER),
    "degree": dict(deg),
    "pairs": {f"{a}|{b}": w for (a, b), w in pair.items() if w >= 2},
}
json.dump(out, open(r"D:\Document\tempPrj\74Series-CNN\tools_b034\net_summary.json", "w"), indent=1)
print("components total:", len(comps))
print("U components:", len(u_designators))
for d in u_designators:
    print("  ", d, "|", comps[d], "| degree:", deg.get(d, 0))
print("nets total:", len(nets))
print("power nets found:", sorted(set(nets) & POWER))
print()
print("pair weights >=2:")
for (a, b), w in sorted(pair.items(), key=lambda kv: (-kv[1], kv[0])):
    if w >= 2:
        print(f"  {a} - {b}: {w}")
print()
print("singles (degree 0-1):", [d for d in u_designators if deg.get(d, 0) <= 1])
