"""Independent acceptance check of the H1 XOR3 fix + PCB-sync-era schematic
state, straight from the freshly re-exported 47-board netlists.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_boards import parse_protel2  # noqa: E402

BOARDS = os.path.join(HERE, "boards")

XOR_BOARDS = [
    ("B04-2_CONV1", "U7186", "U7088", "/B04_S07_CONV1/C1_S12_16",
     "/B04_S07_CONV1/C1_S12_C4", "/B04_S07_CONV1/C1_S12_X1",
     "/B04_S07_CONV1/C1_P1_15", "/B04_S07_CONV1/C1_P2_15"),
    ("B04-1_CONV1", "U7187", "U7092", "/B04_S07_CONV1/C1_S34_16",
     "/B04_S07_CONV1/C1_S34_C4", "/B04_S07_CONV1/C1_S34_X1",
     "/B04_S07_CONV1/C1_P3_15", "/B04_S07_CONV1/C1_P4_15"),
    ("B06-2_CONV2", "U8186", "U8089", "/B06_S08_CONV2/C2_S12_16",
     "/B06_S08_CONV2/C2_S12_C4", "/B06_S08_CONV2/C2_S12_X1",
     "/B06_S08_CONV2/C2_P1_15", "/B06_S08_CONV2/C2_P2_15"),
    ("B06-1_CONV2", "U8187", "U8093", "/B06_S08_CONV2/C2_S34_16",
     "/B06_S08_CONV2/C2_S34_C4", "/B06_S08_CONV2/C2_S34_X1",
     "/B06_S08_CONV2/C2_P3_15", "/B06_S08_CONV2/C2_P4_15"),
    ("B08-3_FC1", "U9186", "U9074", "/B08_S09_FC1/FC_S12_16",
     "/B08_S09_FC1/FC_S12_C4", "/B08_S09_FC1/FC_S12_X1",
     "/B08_S09_FC1/FC_P1_15", "/B08_S09_FC1/FC_P2_15"),
    ("B08-2_FC1", "U9187", "U9078", "/B08_S09_FC1/FC_S34_16",
     "/B08_S09_FC1/FC_S34_C4", "/B08_S09_FC1/FC_S34_X1",
     "/B08_S09_FC1/FC_P3_15", "/B08_S09_FC1/FC_P4_15"),
    ("B09-3_FC2", "U9340", "U9274", "/B09_S09_FC2/FC_S12_16",
     "/B09_S09_FC2/FC_S12_C4", "/B09_S09_FC2/FC_S12_X1",
     "/B09_S09_FC2/FC_P1_15", "/B09_S09_FC2/FC_P2_15"),
    ("B09-2_FC2", "U9341", "U9278", "/B09_S09_FC2/FC_S34_16",
     "/B09_S09_FC2/FC_S34_C4", "/B09_S09_FC2/FC_S34_X1",
     "/B09_S09_FC2/FC_P3_15", "/B09_S09_FC2/FC_P4_15"),
]


def main():
    all_ok = True
    for board, chip, adder, out_net, c4_net, x1_net, pa_net, pb_net in XOR_BOARDS:
        comps, nets = parse_protel2(os.path.join(BOARDS, board + ".txt"))
        errs = []
        pt = comps.get(chip, {}).get("parttype", "")
        if "74HC86" not in pt.upper():
            errs.append(f"chip {chip} parttype={pt!r}")
        pin_net = {}
        for name, pins in nets.items():
            for (r, p) in pins:
                if r == chip:
                    pin_net.setdefault(p, set()).add(name)
        expect = {"1": pa_net, "2": pb_net, "3": x1_net, "4": x1_net,
                  "5": c4_net, "6": out_net, "7": "GND", "9": "+5V",
                  "10": "+5V", "12": "+5V", "13": "+5V", "14": "+5V"}
        for p, want in expect.items():
            got = pin_net.get(p, set())
            if got != {want}:
                errs.append(f"{chip}.{p}: want {want}, got {sorted(got)}")
        for p in ("8", "11"):
            if p in pin_net:
                errs.append(f"{chip}.{p} should be NC, got {pin_net[p]}")
        a9 = [name for name, pins in nets.items() if (adder, "9") in pins]
        if a9 != [c4_net]:
            errs.append(f"{adder}.9 nets={a9}, want [{c4_net}]")
        if (chip, "6") not in nets.get(out_net, set()):
            errs.append(f"OUT net lacks {chip}-6")
        # board health
        bad_gnd = [f"{r}.{p}" for (r, p) in nets.get("GND", set())
                   if "-VCC" in p.upper() or "-VDD" in p.upper()]
        if bad_gnd:
            errs.append(f"GND has VCC pins: {bad_gnd[:5]}")
        bad_vled = [f"{r}.{p}" for (r, p) in nets.get("+VLED", set())
                    if r.startswith("U")]
        if bad_vled:
            errs.append(f"+VLED has U pins: {bad_vled[:5]}")
        status = "OK" if not errs else "FAIL"
        if errs:
            all_ok = False
        print(f"{board:14} {status}")
        for e in errs:
            print(f"    !! {e}")

    comps, nets = parse_protel2(os.path.join(BOARDS, "B04-6_CONV1.txt"))
    errs = []
    if not nets.get("+5V"):
        errs.append("+5V net missing")
    elif ("J20306", "5") not in nets["+5V"]:
        errs.append("J20306-5 not on +5V")
    bad_gnd = [f"{r}.{p}" for (r, p) in nets.get("GND", set())
               if "-VCC" in p.upper() or "-VDD" in p.upper()]
    if bad_gnd:
        errs.append(f"GND has VCC pins: {bad_gnd[:5]}")
    bad_vled = [f"{r}.{p}" for (r, p) in nets.get("+VLED", set()) if r.startswith("U")]
    if bad_vled:
        errs.append(f"+VLED has U pins: {bad_vled[:5]}")
    print(f"{'B04-6_CONV1':14} {'OK' if not errs else 'FAIL'}")
    for e in errs:
        all_ok = False
        print(f"    !! {e}")

    comps, nets = parse_protel2(os.path.join(BOARDS, "B08-5_FC1.txt"))
    errs = []
    a = [name for name, pins in nets.items() if ("U9093", "7") in pins]
    if a != ["/B08_S09_FC1/FC_ACCSUM_C3"]:
        errs.append(f"U9093.7 nets={a}")
    j = [name for name, pins in nets.items() if ("J20705", "11") in pins]
    if j != ["/B08_S09_FC1/FC_ACCSUM_C3"]:
        errs.append(f"J20705.11 nets={j}")
    bad_vled = [f"{r}.{p}" for (r, p) in nets.get("+VLED", set()) if r.startswith("U")]
    if bad_vled:
        errs.append(f"+VLED has U pins: {bad_vled[:5]}")
    print(f"{'B08-5_FC1':14} {'OK' if not errs else 'FAIL'}")
    for e in errs:
        all_ok = False
        print(f"    !! {e}")

    print("\nACCEPTANCE:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
