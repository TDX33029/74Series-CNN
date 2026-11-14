"""Compare the merged EasyEDA 47-board system model against the KiCad
reference netlist (top_20261112c) at pin-connectivity level, restricted to
logic parts (74xx / memory / oscillator).  LED modules and passives added by
the EDA-side expansion are reported separately, not compared.

Usage:
    python compare_eda_vs_kicad.py [--detail]
"""
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "rtl"))
sys.path.insert(0, r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/tools")
import kicad_sexpr as k  # noqa: E402

MERGED = os.path.join(HERE, "merged_system.json")
KICAD = r"D:/Document/tempPrj/74Series-CNN/Simulation/rtl/tmp_netlists/top_20261112c_fixed.net"

# logic part tokens, longest/most specific first (searched in EDA PARTTYPE)
LOGIC_TOKENS = [
    "74HCT273", "74HCT574", "74HCT541", "74HCT245",
    "74HC00", "74HC02", "74HC04", "74HC08", "74HC32",
    "74HC74", "74HC85", "74HC138", "74HC148", "74HC157",
    "74HC161", "74HC238", "74HC283", "74HC688",
    "27C512", "28C256", "62256", "6264", "ASE",
]
# EDA parttype -> logic class token (first token found wins)


def eda_logic_class(parttype):
    up = parttype.upper()
    for tok in LOGIC_TOKENS:
        if tok in up:
            return tok
    return None


def kicad_logic_class(lib, part):
    up = part.upper().replace("74LS", "74HC").replace("74F", "74HC")
    for tok in LOGIC_TOKENS:
        if tok in up:
            return tok
    if lib == "Oscillator":
        return "ASE"
    return None


def load_kicad(path):
    with open(path, encoding="utf-8") as f:
        root = k.parse(f.read())[0]
    comps = {}
    cblock = k.first(root, "components")
    for comp in k.children(cblock, "comp"):
        ref = k.atoms(k.first(comp, "ref"))[0]
        ls = k.first(comp, "libsource")
        lib = k.atoms(k.first(ls, "lib"))[0] if ls is not None else ""
        part = k.atoms(k.first(ls, "part"))[0] if ls is not None else ""
        sheet = ""
        for prop in k.children(comp, "property"):
            nm = k.first(prop, "name")
            if nm is not None and k.atoms(nm)[0] == "Sheetname":
                sheet = k.atoms(k.first(prop, "value"))[0]
        comps[ref] = dict(lib=lib, part=part, sheet=sheet)
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


def main(argv):
    detail = "--detail" in argv
    merged = json.load(open(MERGED, encoding="utf-8"))
    eda_comps = merged["comps"]
    eda_nets = {key: set(tuple(pin.split("|", 1)) for pin in pins)
                for key, pins in merged["nets"].items()}
    # entries are "board|ref.pin"; split back into (board, "ref.pin")
    eda_nets = {key: {(b, rp) for b, rp in v} for key, v in eda_nets.items()}

    kc_comps, kc_nets = load_kicad(KICAD)

    # classify
    kc_class = {ref: kicad_logic_class(c["lib"], c["part"])
                for ref, c in kc_comps.items()}
    eda_class = {ref: eda_logic_class(c["parttype"])
                 for ref, c in eda_comps.items()}

    kc_logic = {r for r, c in kc_class.items() if c}
    # B13_LUT_REF is a standalone LUT reference board, absent from the KiCad
    # functional reference; exclude it from the connectivity comparison.
    eda_logic = {r for r, c in eda_class.items()
                 if c and eda_comps[r]["board"] != "B13_LUT_REF"
                 and r != "U15013"}   # EDA-only C2-requant BUSY1 gate
                                      # (documented A4 pattern), absent from
                                      # the outdated KiCad reference
    # EDA oscillator X10001 (ACH-8.000MHZ-EK, 8-pin can) vs KiCad ASE-xxxMHz
    # (4-pin): add it to the logic set with a pin-number translation.
    OSC_PINMAP = {"1": "1", "4": "2", "5": "3", "8": "4"}   # EDA -> KiCad
    if "X10001" in eda_comps:
        eda_logic.add("X10001")
        eda_class["X10001"] = "ASE"
    if "X10001" in kc_comps:
        kc_class.setdefault("X10001", "ASE")

    print(f"KiCad comps {len(kc_comps)} (logic {len(kc_logic)}), "
          f"EDA comps {len(eda_comps)} (logic {len(eda_logic)})")

    missing = sorted(kc_logic - set(eda_comps))
    extra = sorted(set(eda_comps) - set(kc_comps))
    extra_logic = [r for r in extra if eda_class.get(r)]
    changed = sorted(r for r in (kc_logic & set(eda_logic))
                     if kc_class[r] != eda_class[r])

    print(f"\n=== logic refs missing in EDA ({len(missing)}) ===")
    for r in missing:
        print(f"  - {r:8} {kc_comps[r]['part']:12} {kc_comps[r]['sheet']}")
    print(f"=== EDA-only refs classified as logic ({len(extra_logic)}) ===")
    for r in extra_logic:
        print(f"  + {r:8} {eda_comps[r]['parttype']:30} {eda_comps[r]['board']}")
    print(f"=== logic class mismatches ({len(changed)}) ===")
    for r in changed:
        print(f"  ~ {r:8} {kc_class[r]} vs {eda_class[r]} "
              f"({kc_comps[r]['part']} vs {eda_comps[r]['parttype']})")

    # EDA-only non-logic refs grouped by class
    def eda_kind(ref):
        pt = eda_comps[ref]["parttype"].upper()
        if ref.startswith("LED"):
            return "LED"
        if ref.startswith("Q"):
            return "Q"
        if ref.startswith("RP") or ref.startswith("LEDP"):
            return "RP/LEDP"
        if "X6522" in pt or "CONN" in pt or re.match(r"^J\d", ref):
            return "CONN"
        if ref.startswith("C"):
            return "C"
        if ref.startswith("R"):
            return "R"
        if ref.startswith("SW") or "BUTTON" in pt:
            return "SW"
        return "OTHER:" + pt[:20]

    by_kind = defaultdict(list)
    for r in extra:
        if not eda_class.get(r):
            by_kind[eda_kind(r)].append(r)
    print(f"\n=== EDA-only non-logic refs by kind ===")
    for kind in sorted(by_kind):
        print(f"  {kind:12} {len(by_kind[kind])}")

    # ---- pin connectivity, logic pins only -------------------------------
    # KiCad: net -> {(ref,pin)} restricted to logic refs
    kc_net_logic = defaultdict(set)
    for name, nodes in kc_nets.items():
        for r, p in nodes:
            if r in kc_logic:
                kc_net_logic[name].add((r, p))
    # EDA: net -> {(ref,pin)} restricted to logic refs
    eda_net_logic = defaultdict(set)
    for key, nodes in eda_nets.items():
        for b, rp in nodes:
            r = rp.rsplit(".", 1)[0]
            if r in eda_logic:
                pn = rp.rsplit(".", 1)[1]
                if r == "X10001":
                    pn = OSC_PINMAP.get(pn, pn)
                eda_net_logic[key].add((r, pn))

    # invert: ref.pin -> neighbour logic set
    def neighbours(net_map):
        nb = defaultdict(set)
        for members in net_map.values():
            for rp in members:
                nb[rp] |= members
        for rp, s in nb.items():
            s.discard(rp)
        return nb

    kc_nb = neighbours(kc_net_logic)
    eda_nb = neighbours(eda_net_logic)

    diffs = []
    common = kc_logic & eda_logic
    for r in sorted(common):
        kpins = {p for (rr, p) in kc_nb if rr == r}
        epins = {p for (rr, p) in eda_nb if rr == r}
        for p in sorted(kpins | epins, key=lambda x: (len(x), x)):
            a = kc_nb.get((r, p), set())
            b = eda_nb.get((r, p), set())
            if a != b:
                diffs.append((kc_comps[r]["sheet"], r, p, a - b, b - a))

    print(f"\n=== logic pin connectivity diffs ({len(diffs)}) ===")
    by_sheet = defaultdict(list)
    for sheet, r, p, only_k, only_e in diffs:
        by_sheet[sheet].append((r, p, only_k, only_e))
    shown = 0
    for sheet in sorted(by_sheet):
        rows = by_sheet[sheet]
        print(f"\n-- {sheet} ({len(rows)} pins)")
        for r, p, only_k, only_e in rows[: (12 if not detail else 10 ** 6)]:
            konly = ", ".join(sorted(f"{x}.{y}" for x, y in only_k)) or "-"
            eonly = ", ".join(sorted(f"{x}.{y}" for x, y in only_e)) or "-"
            print(f"  {r}.{p}: kicad_only=[{konly[:120]}] eda_only=[{eonly[:120]}]")
        if not detail and len(rows) > 12:
            print(f"  ... ({len(rows) - 12} more)")
    print(f"\nTOTAL: {len(missing)} missing, {len(changed)} class mismatch, "
          f"{len(diffs)} pin diffs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
