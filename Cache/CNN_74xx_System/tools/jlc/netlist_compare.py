#!/usr/bin/env python3
"""Compare KiCad kicadsexpr netlist with EasyEDA Protel2 netlist by pin connectivity.

Usage:
  python -I netlist_compare.py <kicad.net> <eda_protel.txt> [report.json]

Exit code 0 if the pin partitions match (net names ignored), 1 otherwise.
"""
import json
import re
import sys


def parse_kicad(path):
    s = open(path, encoding="utf-8").read()
    nets = {}
    for m in re.finditer(r'\(net\s+\(code "[^"]*"\)\s+\(name "([^"]*)"\)(.*?)\n\t\t\)', s, re.S):
        name = m.group(1)
        if name.startswith("unconnected-") or name.startswith("unconnected_"):
            continue
        pins = set()
        for n in re.finditer(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins.add("%s.%s" % (n.group(1), n.group(2)))
        if pins:
            nets[name] = pins
    return nets


def parse_protel(path):
    lines = open(path, encoding="utf-8").read().replace("\r\n", "\n").splitlines()
    nets = {}
    i = 0
    idx = 0
    while i < len(lines):
        if lines[i].strip() == "(":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            name = lines[j].strip() if j < len(lines) else ""
            pins = set()
            j += 1
            while j < len(lines) and lines[j].strip() != ")":
                m = re.match(r'^(\S+)-(\d+)\s', lines[j].strip())
                if m:
                    pins.add("%s.%s" % (m.group(1), m.group(2)))
                j += 1
            if pins:
                if not name:
                    name = "NET_%d" % idx
                nets[name] = pins
            idx += 1
            i = j
        i += 1
    return nets


def compare(knets, enets):
    kp = {p: frozenset(s) for s in knets.values() for p in s}
    ep = {p: frozenset(s) for s in enets.values() for p in s}
    all_pins = set(kp) | set(ep)
    common = set(kp) & set(ep)
    only_k = sorted(set(kp) - set(ep))
    only_e = sorted(set(ep) - set(kp))
    mism = []
    for p in sorted(common):
        ks = frozenset(kp[p] & common)
        es = frozenset(ep[p] & common)
        if ks != es:
            mism.append({"pin": p, "kicad_net": sorted(ks), "eda_net": sorted(es)})
    # net-name warnings: for each matching partition, compare names
    name_warn = []
    kname = {frozenset(s): n for n, s in knets.items()}
    for n, s in enets.items():
        fs = frozenset(s & common)
        if fs in kname and kname[fs] != n:
            name_warn.append({"kicad": kname[fs], "eda": n})
    return {
        "kicad_nets": len(knets),
        "eda_nets": len(enets),
        "kicad_pins": len(kp),
        "eda_pins": len(ep),
        "common_pins": len(common),
        "only_kicad": only_k[:200],
        "only_eda": only_e[:200],
        "only_kicad_count": len(only_k),
        "only_eda_count": len(only_e),
        "mismatch_count": len(mism),
        "mismatch_sample": mism[:50],
        "name_warnings": name_warn[:50],
        "name_warning_count": len(name_warn),
    }


def main():
    k = parse_kicad(sys.argv[1])
    e = parse_protel(sys.argv[2])
    r = compare(k, e)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if len(sys.argv) > 3:
        json.dump(r, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = r["mismatch_count"] == 0 and r["only_kicad_count"] == 0 and r["only_eda_count"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
