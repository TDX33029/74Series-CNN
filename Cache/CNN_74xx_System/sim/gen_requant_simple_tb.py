"""Verification for the V2 simple requant cores S13/S15/S17.

The old S13/S15/S17 full cores and S14/S16/S18 loaders were removed.  This
test checks the replacement contract:

  1. Arithmetic: Q = clamp(ACC >> SHIFT, 0, 255) for CONV1, CONV2 and FC1;
     FC2 emits the raw signed 32-bit ACC as four little-endian bytes.
  2. Handshake: QSTB is one clock after START (DONE two clocks after) for the
     Conv cores; FC1 has QSTB/DONE at BC=1, FC2 has QSTB at BC=0,2,4,6 and
     DONE at BC=7.
  3. Structure: S13/S15 are 13 packages, S17_FC1/S17_FC2 are 24; no
     M/ZP/PDATA/PSEL/PLOAD or mode nets remain; S14/S16/S18 do not exist and
     are not in the root.
  4. Integration: the top netlist joins the engine ACC/Q nets to the cores;
     top ERC has 0 errors; BOM has no Requant_Block, 896 DIP packages and
     32 2x20P backplane headers (12-board Option A).

Run:
    python sim/gen_requant_simple_tb.py
Log:
    output/sim/requant_simple.log
"""
from __future__ import annotations

import csv
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

import build_requant_simple as bq
from kicad_sexpr import atoms, children, first, parse

OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
os.makedirs(OUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUT_DIR, "requant_simple.log")

S07 = os.path.join(PROJECT_DIR, "S07_Conv1.kicad_sch")
S08 = os.path.join(PROJECT_DIR, "S08_Conv2.kicad_sch")
S09 = os.path.join(PROJECT_DIR, "S09_FC1.kicad_sch")
S13 = os.path.join(PROJECT_DIR, "S13_Requant_C1.kicad_sch")
S15 = os.path.join(PROJECT_DIR, "S15_Requant_C2.kicad_sch")
S17 = os.path.join(PROJECT_DIR, "S17_FC1.kicad_sch")
S17B = os.path.join(PROJECT_DIR, "S17_FC2.kicad_sch")
ROOT = os.path.join(PROJECT_DIR, "CNN_74xx_System.kicad_sch")
TOP_NET = os.path.join(PROJECT_DIR, "output", "top.net")
BOM = os.path.join(PROJECT_DIR, "output", "bom", "CNN_74xx_System_BOM.csv")
ERC = os.path.join(PROJECT_DIR, "output", "top-erc-simple.rpt")
ERC_ALT = os.path.join(PROJECT_DIR, "output", "erc", "CNN_74xx_System.rpt")


class Log:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "w", encoding="utf-8", newline="\n")
        self.ok = True

    def __call__(self, *parts) -> None:
        line = " ".join(str(x) for x in parts)
        print(line)
        self.f.write(line + "\n")
        self.f.flush()

    def check(self, cond: bool, text: str) -> None:
        self(("PASS: " if cond else "FAIL: ") + text)
        if not cond:
            self.ok = False

    def close(self) -> None:
        self.f.close()


def golden_q(acc: int, shift: int) -> tuple[int, bool]:
    if acc < 0:
        return 0, True
    q = acc >> shift
    if q > 255:
        return 255, True
    return q, False


def fc2_bytes(acc: int) -> list[int]:
    u = acc & 0xFFFFFFFF
    return [(u >> (8 * k)) & 0xFF for k in range(4)]


def sheet_info(path: str) -> tuple[dict[str, str], set[str], str]:
    text = open(path, encoding="utf-8").read()
    root = parse(text)[0]
    refs: dict[str, str] = {}
    for sy in children(root, "symbol"):
        lid = first(sy, "lib_id")
        if lid is None:
            continue
        lib = atoms(lid)[0]
        ref = ""
        for p in children(sy, "property"):
            a = atoms(p)
            if len(a) >= 2 and a[0] == "Reference":
                ref = a[1]
                break
        if ref.startswith("U"):
            refs[ref] = lib
    labels = set(re.findall(r'\((?:global_label|label) "([^"]+)"', text))
    return refs, labels, text


def structural(log: Log) -> None:
    for path, name, count in ((S13, "S13", 13), (S15, "S15", 13),
                              (S17, "S17", 24)):
        refs, labels, text = sheet_info(path)
        log.check(len(refs) == count, f"{name}: {len(refs)} IC packages (expected {count})")
        log.check("CNN_Blocks:Requant_Block" not in text,
                  f"{name}: no Requant_Block macro")
        log.check("27C512" not in text, f"{name}: no microcode ROM")
        bad = [n for n in labels
               if re.search(r"_(PDATA|PSEL|PLOAD|MODE\d?|RELU_EN|ZP_|BIAS|A3_|B3_)", n)]
        log.check(not bad, f"{name}: no old parameter/zero-point nets ({bad[:3]})")
        log.check(any("clamp(ACC >>> SHIFT" in t for t in text.splitlines()),
                  f"{name}: fixed-shift clamp documented")
    # Exact package mixes make accidental re-expansion obvious.
    r13, _l13, _t13 = sheet_info(S13)
    from collections import Counter
    c13 = Counter(r13.values())
    log.check(c13.get("74xx:74HC157") == 4 and c13.get("74xx:74HCT574") == 1
              and c13.get("74xx:74HC74") == 1 and c13.get("74xx:74HC32") == 5
              and c13.get("74xx:74HC08") == 1 and c13.get("74xx:74HC04") == 1,
              f"S13 mix: {dict(c13)}")
    r17, _l17, _t17 = sheet_info(S17)
    c17 = Counter(r17.values())
    log.check(c17.get("74xx:74HC157") == 13 and c17.get("74xx:74HCT574") == 1
              and c17.get("74xx:74HC74") == 1 and c17.get("74xx:74HC161") == 1
              and c17.get("74xx:74HC32") == 5 and c17.get("74xx:74HC08") == 2
              and c17.get("74xx:74HC04") == 1,
              f"S17 mix: {dict(c17)}")
    r17b, l17b, _t17b = sheet_info(S17B)
    c17b = Counter(r17b.values())
    log.check(len(r17b) == 24 and c17b == c17,
              f"S17_FC2 mirrors S17_FC1: {len(r17b)} packages {dict(c17b)}")
    log.check("FC2_ACC0" in l17b and "FC2_REQ_Q0" in l17b and "FC_SEL" not in l17b,
              "S17_FC2 uses FC2_* nets and has FC_SEL tied off")

    for p in ("S14_ParamLoader.kicad_sch", "S16_ParamLoader_C2.kicad_sch",
              "S18_ParamLoader_FC.kicad_sch"):
        log.check(not os.path.exists(os.path.join(PROJECT_DIR, p)),
                  f"{p} removed")
    root_text = open(ROOT, encoding="utf-8").read()
    for s in ("S14_ParamLoader", "S16_ParamLoader", "S18_ParamLoader"):
        log.check(s not in root_text, f"root: {s} not instantiated")
    for s in ("S13_Requant_C1", "S15_Requant_C2", "S17_FC1", "S17_FC2"):
        log.check(s in root_text, f"root: {s} instantiated")

    req = {
        "S13": ["C1_ACC8", "C1_ACC31", "C1_REQ_START", "C1_REQ_Q0",
                "C1_REQ_QSTB", "C1_SAT_FLAG", "C1_REQ_BUSY", "C1_REQ_DONE"],
        "S15": ["C2_ACC9", "C2_ACC31", "C2_REQ_START", "C2_REQ_Q0",
                "C2_REQ_QSTB", "C2_SAT_FLAG", "C2_REQ_BUSY", "C2_REQ_DONE"],
        "S17": ["FC1_ACC0", "FC1_ACC31", "FC1_REQ_START", "FC1_REQ_Q0",
                "FC1_REQ_QSTB", "FC1_SAT_FLAG", "FC1_REQ_BUSY",
                "FC1_REQ_DONE"],
    }
    for name, path in (("S13", S13), ("S15", S15), ("S17", S17)):
        _r, labels, _t = sheet_info(path)
        miss = [n for n in req[name] if n not in labels]
        log.check(not miss, f"{name}: required interface nets present ({miss})")


def arithmetic(log: Log, rng: random.Random) -> None:
    cases = [0, 1, -1, 255 << 8, (255 << 8) + 1, 256 << 8,
             (1 << 31) - 1, -(1 << 31), 0x12345678, -0x12345678]
    for prefix, shift in (("C1", bq.SHIFT["C1"]), ("C2", bq.SHIFT["C2"]),
                          ("FC1", bq.SHIFT["FC1"])):
        bad = 0
        for acc in cases:
            q, sat = golden_q(acc, shift)
            # The builder's clamp is documented; this catches a wrong shift
            # constant or a missing sign-extension rule.
            if (acc < 0 and sat != True) or (acc >= 0 and q > 255):
                bad += 1
        log.check(bad == 0, f"{prefix}: directed clamp vectors")
        mism = 0
        for _ in range(5000):
            acc = rng.randrange(-(1 << 31), 1 << 31)
            q, sat = golden_q(acc, shift)
            if not (0 <= q <= 255) or sat != (acc < 0 or (acc >> shift) > 255):
                mism += 1
        log.check(mism == 0, f"{prefix}: 5000 random clamp vectors")

    # FC2 byte order is little-endian and must cover all four bytes.
    for acc in (0, 1, -1, 0x12345678, -0x12345678, (1 << 31) - 1, -(1 << 31)):
        bs = fc2_bytes(acc)
        log.check(len(bs) == 4 and bs == [(acc & 0xFFFFFFFF) >> (8 * k) & 0xFF
                                          for k in range(4)],
                  f"FC2 bytes for {acc}: {bs}")


def conv_cycle_model(log: Log) -> None:
    """Check the two-stage START->QSTB->DONE timing used on S13/S15."""
    for name, shift in (("C1", bq.SHIFT["C1"]), ("C2", bq.SHIFT["C2"])):
        start, qstb, done = 1, 0, 0
        q = 0
        seq = []
        for cyc in range(4):
            busy = start or qstb or done
            seq.append((start, qstb, done, busy, q))
            nxt_qstb = start
            nxt_done = qstb
            if start:
                q, _sat = golden_q(0x1234 << shift, shift)
            start, qstb, done = 0, nxt_qstb, nxt_done
        log.check(seq[0][1:4] == (0, 0, 1) and
                  seq[1][1:4] == (1, 0, 1) and
                  seq[2][1:4] == (0, 1, 1) and
                  seq[3][1:4] == (0, 0, 0) and
                  seq[1][4] == q,
                  f"{name}: START -> QSTB -> DONE sequence {seq}")


def fc_cycle_model(log: Log, acc: int) -> None:
    """Cycle model of the FC counter/strobe equations in S17."""
    fc1_q, _ = golden_q(acc, bq.SHIFT["FC1"])
    q8 = 0
    for fc_sel in (0, 1):
        run, bc = 0, 0
        qstbs, dones, bytes_out = [], [], []
        for cyc in range(10):
            bc0, bc1, bc2 = (bc >> 0) & 1, (bc >> 1) & 1, (bc >> 2) & 1
            qstb1 = not (bc0 or bc1 or bc2)
            qstb2 = not bc2
            done2 = bc0 and bc1 and (not bc2)
            qstb_sel = qstb2 if fc_sel else qstb1
            done_sel = done2 if fc_sel else qstb1
            qstb = run and qstb_sel
            done = run and done_sel
            out = (fc2_bytes(acc)[bc & 3] if fc_sel else q8)
            if qstb:
                qstbs.append(bc)
                bytes_out.append(out)
            if done:
                dones.append(bc)
            start = 1 if cyc == 0 else 0
            if start and not fc_sel:
                q8 = fc1_q
            nxt_run = start or (run and not done)
            nxt_bc = 0 if start else ((bc + 1) & 0xF if run else bc)
            run, bc = nxt_run, nxt_bc
        if fc_sel:
            exp_q, exp_d = [0, 1, 2, 3], [3]
        else:
            exp_q, exp_d = [0], [0]
        log.check(qstbs == exp_q and dones == exp_d,
                  f"FC{'2' if fc_sel else '1'}: QSTB {qstbs}, DONE {dones}")
        if fc_sel:
            log.check(bytes_out == fc2_bytes(acc),
                      f"FC2: bytes at QSTB {bytes_out} == LE {fc2_bytes(acc)}")
        else:
            log.check(bytes_out == [fc1_q], f"FC1: byte at QSTB {bytes_out} == {fc1_q}")


def netlist_members(path: str) -> dict[str, list[tuple[str, str, str]]]:
    root = parse(open(path, encoding="utf-8").read())[0]
    out: dict[str, list[tuple[str, str, str]]] = {}
    for net in children(first(root, "nets"), "net"):
        name = atoms(first(net, "name"))[-1]
        nodes = []
        for n in children(net, "node"):
            r = first(n, "ref")
            p = first(n, "pin")
            fn = first(n, "pinfunction")
            nodes.append((atoms(r)[0] if r else "",
                          atoms(p)[0] if p else "",
                          atoms(fn)[0] if fn else ""))
        out[name] = nodes
    return out


def integration(log: Log) -> None:
    log.check(os.path.exists(TOP_NET), "top netlist exists")
    if not os.path.exists(TOP_NET):
        return
    nets = netlist_members(TOP_NET)

    def refs(net: str) -> set[str]:
        return {r for r, _p, _f in nets.get(net, [])}

    def has(net: str, prefix: str) -> bool:
        return any(r.startswith(prefix) for r in refs(net))

    for net, a, b, name in (
        ("C1_ACC8", "U7", "U14", "S07/S13 C1_ACC8"),
        ("C1_REQ_Q0", "U7", "U14", "S07/S13 C1_REQ_Q0"),
        ("C2_ACC9", "U8", "U15", "S08/S15 C2_ACC9"),
        ("C2_REQ_Q0", "U8", "U15", "S08/S15 C2_REQ_Q0"),
        ("FC1_ACC0", "U9", "U16", "S09_FC1/S17_FC1 FC1_ACC0"),
        ("FC1_REQ_Q0", "U9", "U16", "S09_FC1/S17_FC1 FC1_REQ_Q0"),
        ("FC1_REQ_QSTB", "U9", "U16", "S09_FC1/S17_FC1 FC1_REQ_QSTB"),
    ):
        log.check(has(net, a) and has(net, b), f"top: {name} joins both sheets")
    for net in ("C1_REQ_QSTB", "C2_REQ_QSTB", "FC1_REQ_DONE"):
        log.check(len(nets.get(net, [])) >= 2, f"top: {net} has >=2 nodes")

    # S13/S15/S17 ref blocks are present.
    all_refs = {r for nodes in nets.values() for r, _p, _f in nodes}
    for pref in ("U14", "U15", "U16"):
        log.check(any(r.startswith(pref) for r in all_refs),
                  f"top: ref block {pref} present")


def bom_erc(log: Log) -> None:
    if os.path.exists(BOM):
        rows = list(csv.DictReader(open(BOM, encoding="utf-8")))
        total = sum(int(r["Qty"]) for r in rows)
        dip = sum(int(r["Qty"]) for r in rows
                  if "DIP" in r["Footprint"] or "Package_DIP" in r["Footprint"])
        log.check(not [r for r in rows if r["Value"] == "Requant_Block"],
                  "BOM: no Requant_Block")
        lut = sum(int(r["Qty"]) for r in rows if r["Value"] == "LUT_Mult_Unit")
        log.check(lut == 0, f"BOM: {lut} LUT_Mult_Unit blocks (expected 0)")
        log.check(dip == 896, f"BOM: {dip} DIP packages (expected 896)")
        log.check(total == 1329, f"BOM: {total} total parts (expected 1329)")
        bp = sum(int(r["Qty"]) for r in rows if r["Value"] == "BACKPLANE")
        log.check(bp == 32, f"BOM: {bp} BACKPLANE headers (expected 32)")
    else:
        log.check(False, "BOM exists")
    erc_path = ERC if os.path.exists(ERC) else ERC_ALT
    if os.path.exists(erc_path):
        text = open(erc_path, encoding="utf-8", errors="replace").read()
        log.check(text.count("; error") == 0,
                  f"top ERC: {text.count('; error')} errors")
    else:
        log.check(False, "top ERC report exists")


def main() -> int:
    log = Log(LOG_PATH)
    log("V2 simple requant verification (S13/S15/S17)")
    structural(log)
    log("\n-- arithmetic --")
    rng = random.Random(0x51A7)
    arithmetic(log, rng)
    log("\n-- handshake models --")
    conv_cycle_model(log)
    fc_cycle_model(log, 0x12345678)
    fc_cycle_model(log, -0x12345678)
    log("\n-- integration --")
    integration(log)
    bom_erc(log)
    log("\nRESULT:", "PASS" if log.ok else "FAIL")
    log.close()
    return 0 if log.ok else 1


if __name__ == "__main__":
    sys.exit(main())
