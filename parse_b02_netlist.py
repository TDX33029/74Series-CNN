import json, collections

BASE = r"D:\Document\tempPrj\74Series-CNN\netlist_compare_v2\jlc_netlists"
FILES = ["B02_TIMING__B02_Conn.net", "B02_TIMING__S02_Timing.net"]
POWER = {"GND", "VCC", "+5V", "+VLED", "VDD", "AGND", "DGND", "GNDP", "VCCP"}

def parse_netlist(path):
    comps = {}
    nets = collections.defaultdict(set)
    state = None  # None | "comp" | "net"
    buf = []
    netname = None
    with open(path, "r", errors="ignore") as f:
        for raw in f:
            s = raw.strip()
            if s == "[":
                state = "comp"; buf = []; continue
            if s == "]" and state == "comp":
                if len(buf) >= 4:
                    comps[buf[1].strip()] = buf[3].strip()
                state = None; buf = []; continue
            if state == "comp":
                buf.append(s); continue
            if s == "(":
                state = "net"; netname = None; continue
            if s == ")" and state == "net":
                state = None; netname = None; continue
            if state == "net":
                if netname is None and s:
                    netname = s.split()[0]
                    nets[netname]  # register
                    continue
                if s and netname is not None:
                    tok = s.split()[0]
                    if "-" in tok:
                        d, pin = tok.rsplit("-", 1)
                        if d and pin and (pin.isdigit() or pin.isalnum()):
                            nets[netname].add((d, pin))
                continue
    return comps, dict(nets)

all_comps = {}
all_nets = collections.defaultdict(set)
for fn in FILES:
    c, n = parse_netlist(BASE + "\\" + fn)
    all_comps.update(c)
    for k, v in n.items():
        all_nets[k].update(v)

chips = {d: fp for d, fp in all_comps.items() if d.startswith("U")}
sig_nets = {k: v for k, v in all_nets.items() if k not in POWER and len(v) > 0}

pair_w = collections.Counter()
chip_pin_count = collections.Counter()
jconn = {d for d in all_comps if not d.startswith("U")}
pair_j = collections.Counter()
net_chips = {}
for name, pins in sig_nets.items():
    ds = sorted(set(d for d, _ in pins if d in chips))
    dj = sorted(set(d for d, _ in pins if d in jconn))
    net_chips[name] = ds + dj
    for d in ds:
        chip_pin_count[d] += sum(1 for dd, _ in pins if dd == d)
    for i in range(len(ds)):
        for j in range(i+1, len(ds)):
            pair_w[(ds[i], ds[j])] += 1
    for u in ds:
        for j in dj:
            pair_j[(u, j)] += 1

out = {
    "chips": chips,
    "all_designators": sorted(all_comps.keys()),
    "connector_like": sorted(jconn),
    "signal_net_count": len(sig_nets),
    "pair_weights": [{"a": a, "b": b, "w": w} for (a, b), w in pair_w.most_common()],
    "chip_net_counts": dict(chip_pin_count.most_common()),
    "chip_to_connector": [{"a": a, "b": b, "w": w} for (a, b), w in pair_j.most_common()],
    "net_chips": net_chips,
}
with open(r"D:\Document\tempPrj\74Series-CNN\B02_TIMING_netlist_analysis.json", "w") as f:
    json.dump(out, f, indent=1)
print("chips:", len(chips))
for d in sorted(chips): print(d, chips[d], chip_pin_count.get(d, 0))
print("---top chip pairs---")
for (a, b), w in pair_w.most_common(50): print(a, b, w)
print("---chip-to-conn top---")
for (a, b), w in pair_j.most_common(20): print(a, b, w)
print("---signal nets---")
for name in sorted(sig_nets): print(name, net_chips[name])
