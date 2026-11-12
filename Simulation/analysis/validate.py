"""Self-consistency checks on the generated artefacts (run after build_analysis.py)."""
import csv, json, re, sys, collections
sys.path.insert(0, r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/tools")
import kicad_sexpr as k

OUT = r"D:/Document/tempPrj/74Series-CNN/Simulation/analysis"
NETLIST = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/top_20261112c.net"

txt = open(NETLIST, encoding="utf-8").read()
def sect(name, tag):
    b = k.extract_block(txt, "\n\t(" + name)
    r = k.parse(b)[0]
    return [n for n in r[1:] if isinstance(n, list) and n and n[0] == tag]

comps = sect("components", "comp")
nets = sect("nets", "net")
libparts = sect("libparts", "libpart")

def atom(n, t):
    x = k.first(n, t)
    return k.atoms(x)[0] if x and k.atoms(x) else None

ok = True
def check(cond, msg):
    global ok
    print(("PASS  " if cond else "FAIL  ") + msg)
    ok = ok and cond

# --- nets.csv
rows = list(csv.DictReader(open(OUT + "/nets.csv", encoding="utf-8")))
names = [atom(n, "name") for n in nets]
check(len(rows) == len(nets) == 4510, "nets.csv has one row per net (%d)" % len(rows))
check([r["kicad_name"] for r in rows] == names, "nets.csv preserves netlist order and names")
check(len({r["verilog_ident"] for r in rows}) == len(rows), "verilog identifiers unique")
bad = [r for r in rows if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", r["verilog_ident"])]
check(not bad, "verilog identifiers match the identifier regex")
check(all(int(r["node_count"]) == len(k.children(n, "node")) for r, n in zip(rows, nets)),
      "node_count matches the netlist")
check(all(r["is_power"] == ("yes" if r["kicad_name"] in ("+5V", "+3V3") else "no") for r in rows),
      "power flags")
check(all(r["is_ground"] == ("yes" if r["kicad_name"] == "GND" else "no") for r in rows),
      "ground flags")

# --- parts.csv / pins.json
parts = list(csv.DictReader(open(OUT + "/parts.csv", encoding="utf-8")))
pinjson = json.load(open(OUT + "/pins.json", encoding="utf-8"))["parts"]
use = collections.Counter(
    "%s:%s" % (atom(k.first(c, "libsource"), "lib"),
               atom(k.first(c, "libsource"), "part"))
    for c in comps)
modeled = {"%s:%s" % (p["lib"], p["part"]): int(p["count"]) for p in parts}
check(sum(modeled.values()) + 431 == len(comps),
      "modeled (%d) + dropped (431) = components (%d)" % (sum(modeled.values()), len(comps)))
check(all(use[key] == n for key, n in modeled.items()), "per-part counts match the netlist")
check(set(modeled) == set(pinjson), "parts.csv and pins.json cover the same parts")

for key, info in pinjson.items():
    lib, part = key.split(":", 1)
    lp = [x for x in libparts if atom(x, "lib") == lib and atom(x, "part") == part][0]
    refs = [atom(c, "ref") for c in comps if atom(k.first(c, "libsource"), "part") == part]
    pins = {atom(x, "num") for x in k.children(k.first(lp, "pins"), "pin")}
    check(set(info["pins"]) == pins, "%s: pin set complete (%d)" % (key, len(pins)))
    check(len(info["pins"]) == info["pin_count"], "%s: pin_count consistent" % key)
    check(all(p.get("unit", 0) >= 0 for p in info["pins"].values()),
          "%s: every pin has a unit" % key)
    check(all(info["pins"][n]["unit_name"] != "?" for n in info["pins"]),
          "%s: every pin has a unit name" % key)
    check(not info["unit_conflicts"], "%s: unit assignment identical over all %d instances"
          % (key, len(refs)))
    if info["package_pin_count"]:
        check(info["package_pin_count"] == info["pin_count"],
              "%s: %d pins == %s package" % (key, info["pin_count"], info["package"]))
    # every pin name/type equals the netlist libparts entry
    mismatch = [(n, info["pins"][n]["name"], p_name, info["pins"][n]["etype"], p_type)
                for n, p_name, p_type in
                [(atom(x, "num"), atom(x, "name"), atom(x, "type"))
                 for x in k.children(k.first(lp, "pins"), "pin")]
                if info["pins"][n]["name"] != p_name or info["pins"][n]["etype"] != p_type]
    check(not mismatch, "%s: pin names/types identical to netlist libparts" % key)

# --- memories.csv
mem = list(csv.DictReader(open(OUT + "/memories.csv", encoding="utf-8")))
mem_refs = {atom(c, "ref") for c in comps
            if atom(k.first(c, "libsource"), "part") in ("27C512", "28C256", "HY6264AxP")}
check({r["ref"] for r in mem} == mem_refs, "memories.csv covers all %d memory devices" % len(mem_refs))
check(len(mem) == 71, "71 memory rows")
for r in mem:
    w = {"27C512": 16, "28C256": 15, "HY6264AxP": 13}[r["part"]]
    check(r["addr_width"] == str(w), "%s: address width %d" % (r["ref"], w))
    check(int(r["addr_pins_used"]) <= w, "%s: addr_pins_used <= address width" % r["ref"])

print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
