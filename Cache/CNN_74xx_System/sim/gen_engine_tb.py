"""Address-sequence and MAC-count verification for CONV1, CONV2, FC1/FC2.

Three independent checks are run for every engine:

1. Python golden model: nested loop order, address formulas, MAC counts and
   address bounds.
2. Python 74HC161-style counter model: synchronous zero-load at the terminal
   value, enable chaining, one MAC per clock.  Its loop indices must match the
   golden model for every one of the 115200 (or 13120) MAC steps.
3. SPICE behavioral model (ngspice from KiCad): step = floor(time/Tclk),
   addresses computed from the same formulas with floor/mod arithmetic.  The
   complete MAC sequence is simulated and every sampled step is compared with
   the golden model; .meas gives the address extrema.

Logs:  output/sim/conv1_engine.log
       output/sim/conv2_engine.log
       output/sim/fc_engine.log
Run:   python sim/gen_engine_tb.py
"""
from __future__ import annotations

import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

from ngspice_runner import NgSpice

SIM_DIR = os.path.join(PROJECT_DIR, "sim")
OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
os.makedirs(OUT_DIR, exist_ok=True)

TCLK_NS = 100.0


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


# ---------------------------------------------------------------------------
# Golden models
# ---------------------------------------------------------------------------
@dataclass
class Step:
    oc: int
    oy: int
    ox: int
    ky: int
    kx: int
    ic: int
    ina: int
    wa: int
    oa: int


def golden_conv1() -> List[Step]:
    rows: List[Step] = []
    for oc in range(8):
        for oy in range(24):
            for ox in range(24):
                for ky in range(5):
                    for kx in range(5):
                        rows.append(Step(
                            oc, oy, ox, ky, kx, 0,
                            (oy + ky) * 28 + (ox + kx),
                            oc * 25 + ky * 5 + kx,
                            oc * 576 + oy * 24 + ox,
                        ))
    return rows


def golden_conv2() -> List[Step]:
    rows: List[Step] = []
    for oc in range(16):
        for oy in range(10):
            for ox in range(10):
                for ic in range(8):
                    for ky in range(3):
                        for kx in range(3):
                            rows.append(Step(
                                oc, oy, ox, ky, kx, ic,
                                ic * 144 + (oy + ky) * 12 + (ox + kx),
                                oc * 72 + ic * 9 + ky * 3 + kx,
                                oc * 100 + oy * 10 + ox,
                            ))
    return rows


def golden_fc() -> Tuple[List[Step], List[Tuple[int, int, int]]]:
    rows: List[Step] = []
    for neuron in range(32):
        for index in range(400):
            rows.append(Step(neuron, 0, 0, 0, 0, 0, index,
                             neuron * 400 + index, neuron))
    for neuron in range(10):
        for index in range(32):
            rows.append(Step(neuron, 1, 0, 0, 0, 0, index,
                             neuron * 32 + index, neuron * 4))
    writes: List[Tuple[int, int, int]] = []
    for neuron in range(32):
        writes.append((neuron, 0, neuron))
    for neuron in range(10):
        for b in range(4):
            writes.append((neuron, b, neuron * 4 + b))
    return rows, writes


# ---------------------------------------------------------------------------
# 74HC161-style counter models (synchronous zero-load at terminal value)
# ---------------------------------------------------------------------------
def hw_conv1(log: Log, golden: Sequence[Step]) -> None:
    oc = oy = ox = ky = kx = 0
    for i, g in enumerate(golden):
        assert (oc, oy, ox, ky, kx) == (g.oc, g.oy, g.ox, g.ky, g.kx)
        kx_last = kx == 4
        ky_last = ky == 4
        ox_last = ox == 23
        oy_last = oy == 23
        oc_last = oc == 7
        # next-state with synchronous zero-load (the ~PE NAND terms)
        n_kx = 0 if kx_last else kx + 1
        n_ky = 0 if (kx_last and ky_last) else (ky + 1 if kx_last else ky)
        n_ox = 0 if (kx_last and ky_last and ox_last) else (
            ox + 1 if (kx_last and ky_last) else ox)
        n_oy = 0 if (kx_last and ky_last and ox_last and oy_last) else (
            oy + 1 if (kx_last and ky_last and ox_last) else oy)
        n_oc = 0 if (kx_last and ky_last and ox_last and oy_last and oc_last) else (
            oc + 1 if (kx_last and ky_last and ox_last and oy_last) else oc)
        oc, oy, ox, ky, kx = n_oc, n_oy, n_ox, n_ky, n_kx
    log.check(True, "CONV1 74HC161 counter model matches golden indices for all "
                    f"{len(golden)} MACs")
    log.check((oc, oy, ox, ky, kx) == (0, 0, 0, 0, 0),
              "CONV1 counters wrap to (oc,oy,ox,ky,kx)=0 after the final MAC")


def hw_conv2(log: Log, golden: Sequence[Step]) -> None:
    oc = oy = ox = ic = ky = kx = 0
    for g in golden:
        assert (oc, oy, ox, ic, ky, kx) == (g.oc, g.oy, g.ox, g.ic, g.ky, g.kx)
        kx_last = kx == 2
        ky_last = ky == 2
        ic_last = ic == 7
        ox_last = ox == 9
        oy_last = oy == 9
        oc_last = oc == 15
        n_kx = 0 if kx_last else kx + 1
        n_ky = 0 if (kx_last and ky_last) else (ky + 1 if kx_last else ky)
        n_ic = 0 if (kx_last and ky_last and ic_last) else (
            ic + 1 if (kx_last and ky_last) else ic)
        n_ox = 0 if (kx_last and ky_last and ic_last and ox_last) else (
            ox + 1 if (kx_last and ky_last and ic_last) else ox)
        n_oy = 0 if (kx_last and ky_last and ic_last and ox_last and oy_last) else (
            oy + 1 if (kx_last and ky_last and ic_last and ox_last) else oy)
        n_oc = 0 if (kx_last and ky_last and ic_last and ox_last and oy_last and oc_last) else (
            oc + 1 if (kx_last and ky_last and ic_last and ox_last and oy_last) else oc)
        oc, oy, ox, ic, ky, kx = n_oc, n_oy, n_ox, n_ic, n_ky, n_kx
    log.check(True, "CONV2 74HC161 counter model matches golden indices for all "
                    f"{len(golden)} MACs")
    log.check((oc, oy, ox, ic, ky, kx) == (0, 0, 0, 0, 0, 0),
              "CONV2 counters wrap to 0 after the final MAC")


def hw_fc(log: Log, golden: Sequence[Step]) -> None:
    # FC1 phase
    neuron = index = 0
    for g in golden[:12800]:
        assert (neuron, index) == (g.oc, g.ina)
        n_index = 0 if index == 399 else index + 1
        n_neuron = 0 if (index == 399 and neuron == 31) else (
            neuron + 1 if index == 399 else neuron)
        neuron, index = n_neuron, n_index
    log.check((neuron, index) == (0, 0), "FC1 neuron/index counters wrap after 12800 MACs")
    # FC2 phase
    neuron = index = 0
    for g in golden[12800:]:
        assert (neuron, index) == (g.oc, g.ina)
        n_index = 0 if index == 31 else index + 1
        n_neuron = 0 if (index == 31 and neuron == 9) else (
            neuron + 1 if index == 31 else neuron)
        neuron, index = n_neuron, n_index
    log.check((neuron, index) == (0, 0), "FC2 neuron/index counters wrap after 320 MACs")
    log.check(True, "FC 74HC161 counter model matches golden indices for all 13120 MACs")


# ---------------------------------------------------------------------------
# SPICE netlist builders
# ---------------------------------------------------------------------------
def spice_conv1(total: int) -> str:
    lines = [
        "* CONV1 full address/MAC sequence (behavioral counter)",
        "Bstep step 0 V = floor(time/100n)",
        "Bpt pt 0 V = floor(V(step)/25)",
        "Bm m 0 V = V(step)-25*V(pt)",
        "Bky ky 0 V = floor(V(m)/5)",
        "Bkx kx 0 V = V(m)-5*V(ky)",
        "Boc oc 0 V = floor(V(pt)/576)",
        "Brem rem 0 V = V(pt)-576*V(oc)",
        "Boy oy 0 V = floor(V(rem)/24)",
        "Box ox 0 V = V(rem)-24*V(oy)",
        "Bina ina 0 V = (V(oy)+V(ky))*28+(V(ox)+V(kx))",
        "Bwa wa 0 V = V(oc)*25+V(ky)*5+V(kx)",
        "Boa oa 0 V = V(oc)*576+V(oy)*24+V(ox)",
        "Bactive act 0 V = (V(step) < %d) ? 1 : 0" % total,
        f".tran 100n {total * TCLK_NS / 1e6:.6f}m",
        ".meas tran in_max max V(ina)",
        ".meas tran in_min min V(ina)",
        ".meas tran w_max max V(wa)",
        ".meas tran w_min min V(wa)",
        ".meas tran out_max max V(oa)",
        ".meas tran out_min min V(oa)",
        ".meas tran step_max max V(step)",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def spice_conv2(total: int) -> str:
    lines = [
        "* CONV2 full address/MAC sequence (behavioral counter)",
        "Bstep step 0 V = floor(time/100n)",
        "Bpt pt 0 V = floor(V(step)/72)",
        "Bm m 0 V = V(step)-72*V(pt)",
        "Bic ic 0 V = floor(V(m)/9)",
        "Bmm mm 0 V = V(m)-9*V(ic)",
        "Bky ky 0 V = floor(V(mm)/3)",
        "Bkx kx 0 V = V(mm)-3*V(ky)",
        "Boc oc 0 V = floor(V(pt)/100)",
        "Brem rem 0 V = V(pt)-100*V(oc)",
        "Boy oy 0 V = floor(V(rem)/10)",
        "Box ox 0 V = V(rem)-10*V(oy)",
        "Bina ina 0 V = V(ic)*144+(V(oy)+V(ky))*12+(V(ox)+V(kx))",
        "Bwa wa 0 V = V(oc)*72+V(ic)*9+V(ky)*3+V(kx)",
        "Boa oa 0 V = V(oc)*100+V(oy)*10+V(ox)",
        f".tran 100n {total * TCLK_NS / 1e6:.6f}m",
        ".meas tran in_max max V(ina)",
        ".meas tran in_min min V(ina)",
        ".meas tran w_max max V(wa)",
        ".meas tran w_min min V(wa)",
        ".meas tran out_max max V(oa)",
        ".meas tran out_min min V(oa)",
        ".meas tran step_max max V(step)",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def spice_fc(total: int) -> str:
    lines = [
        "* FC1+FC2 full address/MAC sequence (behavioral counter)",
        "Bstep step 0 V = floor(time/100n)",
        f"Bsel sel 0 V = (V(step) < 12800) ? 0 : 1",
        "Bs1 s1 0 V = V(step)",
        "Bs2 s2 0 V = V(step)-12800",
        "Bn1 n1 0 V = floor(V(s1)/400)",
        "Bi1 i1 0 V = V(s1)-400*V(n1)",
        "Bn2 n2 0 V = floor(V(s2)/32)",
        "Bi2 i2 0 V = V(s2)-32*V(n2)",
        "Bn n 0 V = (V(sel) < 0.5) ? V(n1) : V(n2)",
        "Bi idx 0 V = (V(sel) < 0.5) ? V(i1) : V(i2)",
        "Bina ina 0 V = V(idx)",
        "Bwa wa 0 V = (V(sel) < 0.5) ? V(n)*400+V(idx) : V(n)*32+V(idx)",
        "Boa oa 0 V = (V(sel) < 0.5) ? V(n) : V(n)*4",
        f".tran 100n {total * TCLK_NS / 1e6:.6f}m",
        ".meas tran in_max max V(ina)",
        ".meas tran in_min min V(ina)",
        ".meas tran w_max max V(wa)",
        ".meas tran w_min min V(wa)",
        ".meas tran out_max max V(oa)",
        ".meas tran out_min min V(oa)",
        ".meas tran step_max max V(step)",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def parse_wrdata(path: str, nvec: int = 4) -> Dict[int, Tuple[float, ...]]:
    """Return step -> vector tuple, keeping one row per integer step."""
    rows: Dict[int, Tuple[float, ...]] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2 * nvec:
                continue
            try:
                t = float(parts[0])
                vals = tuple(float(parts[1 + 2 * i]) for i in range(nvec))
            except ValueError:
                continue
            step = int(math.floor(t / (TCLK_NS * 1e-9) + 1e-6))
            rows.setdefault(step, vals)
    return rows


def run_spice(log: Log, name: str, netlist: str, total: int,
              golden: Sequence[Step]) -> None:
    cir = os.path.join(SIM_DIR, f"tb_{name}_eng.cir")
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(netlist)
    log(f"NGSPICE COMMAND: python tools/ngspice_runner.py {os.path.relpath(cir, PROJECT_DIR)}")
    ng = NgSpice()
    rc = ng.run_file(cir)
    log(f"ngspice load rc={rc}")
    run_rc = ng.command("run")
    txt = ng.text()
    keep = [ln for ln in txt.splitlines()
            if re.search(r"(meas|Error|error|Warning|warning|step_max|in_max|in_min|"
                         r"w_max|w_min|out_max|out_min)", ln)
            and "--ready--" not in ln]
    for ln in keep[-40:]:
        log("NGSPICE:", ln.strip())
    log(f"ngspice run rc={run_rc}")
    wave = os.path.join(OUT_DIR, f"{name}_eng_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command("wrdata " + wave.replace("\\", "/") + " v(step) v(ina) v(wa) v(oa)")
    rows = parse_wrdata(wave)
    log(f"SPICE samples: {len(rows)} steps (expected {total})")
    log.check(len(rows) >= total, f"{name}: SPICE produced at least {total} MAC steps")
    bad = 0
    first_bad = None
    for i, g in enumerate(golden):
        v = rows.get(i)
        if v is None:
            bad += 1
            first_bad = first_bad or (i, "missing", None)
            continue
        got = (int(round(v[1])), int(round(v[2])), int(round(v[3])))
        exp = (g.ina, g.wa, g.oa)
        if got != exp:
            bad += 1
            first_bad = first_bad or (i, got, exp)
    log.check(bad == 0, f"{name}: SPICE address sequence equals golden for every step"
                        + ("" if not bad else f" (bad={bad}, first={first_bad})"))
    # .meas extrema against the golden extrema
    ina = [g.ina for g in golden]
    wa = [g.wa for g in golden]
    oa = [g.oa for g in golden]
    log(f"{name}: golden address bounds IN {min(ina)}..{max(ina)}, "
        f"W {min(wa)}..{max(wa)}, OUT {min(oa)}..{max(oa)}")
    # Extrema measured directly from the SPICE waveform (wrdata).
    s_ina = [int(round(v[1])) for v in rows.values()]
    s_wa = [int(round(v[2])) for v in rows.values()]
    s_oa = [int(round(v[3])) for v in rows.values()]
    # Ignore the one extra row at t=N*Tclk (step == N).
    s_ina = s_ina[:total]
    s_wa = s_wa[:total]
    s_oa = s_oa[:total]
    log(f"{name}: SPICE measured bounds IN {min(s_ina)}..{max(s_ina)}, "
        f"W {min(s_wa)}..{max(s_wa)}, OUT {min(s_oa)}..{max(s_oa)}")
    log.check((min(s_ina), max(s_ina), min(s_wa), max(s_wa), min(s_oa), max(s_oa))
              == (min(ina), max(ina), min(wa), max(wa), min(oa), max(oa)),
              f"{name}: SPICE extrema equal golden extrema")
    log.check(max(ina) < 2048 and max(wa) < 16384 and max(oa) < 8192,
              f"{name}: all addresses stay inside their documented ranges")
    log.check(len(golden) == total, f"{name}: MAC count {len(golden)} == {total}")


# ---------------------------------------------------------------------------
# Engine drivers
# ---------------------------------------------------------------------------
def verify_conv1(log: Log) -> None:
    golden = golden_conv1()
    log("=== CONV1 ===")
    log("Loop: oc(0..7) -> oy(0..23) -> ox(0..23) -> ky(0..4) -> kx(0..4), ic=0")
    log("Expected MAC: 8*24*24*5*5 = 115200")
    log(f"Golden MAC count: {len(golden)}")
    log.check(len(golden) == 115200, "CONV1 MAC count = 115200")
    log.check(sum(1 for g in golden if (g.ky, g.kx) == (0, 0)) == 8 * 24 * 24,
              "CONV1 points = 8*24*24 = 4608")
    ina = [g.ina for g in golden]
    wa = [g.wa for g in golden]
    oa = [g.oa for g in golden]
    log.check((min(ina), max(ina)) == (0, 783), f"CONV1 IN_ADDR bounds 0..783 (got {min(ina)}..{max(ina)})")
    log.check((min(wa), max(wa)) == (0, 199), f"CONV1 W_ADDR bounds 0..199 (got {min(wa)}..{max(wa)})")
    log.check((min(oa), max(oa)) == (0, 4607), f"CONV1 OUT_ADDR bounds 0..4607 (got {min(oa)}..{max(oa)})")
    # boundary points
    last = golden[-1]
    log.check((last.oc, last.oy, last.ox, last.ky, last.kx) == (7, 23, 23, 4, 4),
              "CONV1 last MAC at oc=7,oy=23,ox=23,ky=4,kx=4")
    log.check((last.ina, last.wa, last.oa) == (783, 199, 4607),
              "CONV1 last addresses = (783,199,4607)")
    hw_conv1(log, golden)
    run_spice(log, "conv1", spice_conv1(115200), 115200, golden)


def verify_conv2(log: Log) -> None:
    golden = golden_conv2()
    log("=== CONV2 ===")
    log("Loop: oc(0..15) -> oy(0..9) -> ox(0..9) -> ic(0..7) -> ky(0..2) -> kx(0..2)")
    log("Expected MAC: 16*10*10*8*3*3 = 115200")
    log(f"Golden MAC count: {len(golden)}")
    log.check(len(golden) == 115200, "CONV2 MAC count = 115200")
    log.check(sum(1 for g in golden if (g.ky, g.kx, g.ic) == (0, 0, 0)) == 16 * 10 * 10,
              "CONV2 points = 16*10*10 = 1600")
    ina = [g.ina for g in golden]
    wa = [g.wa for g in golden]
    oa = [g.oa for g in golden]
    log.check((min(ina), max(ina)) == (0, 1151), f"CONV2 IN_ADDR bounds 0..1151 (got {min(ina)}..{max(ina)})")
    log.check((min(wa), max(wa)) == (0, 1151), f"CONV2 W_ADDR bounds 0..1151 (got {min(wa)}..{max(wa)})")
    log.check((min(oa), max(oa)) == (0, 1599), f"CONV2 OUT_ADDR bounds 0..1599 (got {min(oa)}..{max(oa)})")
    last = golden[-1]
    log.check((last.oc, last.oy, last.ox, last.ic, last.ky, last.kx) == (15, 9, 9, 7, 2, 2),
              "CONV2 last MAC at oc=15,oy=9,ox=9,ic=7,ky=2,kx=2")
    log.check((last.ina, last.wa, last.oa) == (1151, 1151, 1599),
              "CONV2 last addresses = (1151,1151,1599)")
    hw_conv2(log, golden)
    run_spice(log, "conv2", spice_conv2(115200), 115200, golden)


def verify_fc(log: Log) -> None:
    golden, writes = golden_fc()
    log("=== FC1 / FC2 ===")
    log("FC1: neuron(0..31) -> index(0..399), 12800 MAC")
    log("FC2: neuron(0..9) -> index(0..31), 320 MAC")
    log(f"Golden MAC count: {len(golden)} (12800 + 320)")
    log.check(len(golden) == 13120, "FC total MAC count = 13120")
    log.check(len(golden[:12800]) == 32 * 400, "FC1 MAC count = 32*400 = 12800")
    log.check(len(golden[12800:]) == 10 * 32, "FC2 MAC count = 10*32 = 320")
    ina = [g.ina for g in golden]
    wa = [g.wa for g in golden]
    oa = [g.oa for g in golden]
    log.check((min(ina), max(ina)) == (0, 399), f"FC IN_ADDR bounds 0..399 (got {min(ina)}..{max(ina)})")
    log.check((min(wa), max(wa)) == (0, 12799), f"FC W_ADDR bounds 0..12799 (got {min(wa)}..{max(wa)})")
    log.check((min(oa), max(oa)) == (0, 36), f"FC OUT_ADDR bounds 0..36 (got {min(oa)}..{max(oa)})")
    log.check(len(writes) == 72, "FC output writes = 32 (FC1) + 40 (FC2) = 72")
    fc2_addrs = [w[2] for w in writes[32:]]
    log.check((min(fc2_addrs), max(fc2_addrs)) == (0, 39),
              f"FC2 write address bounds 0..39 (got {min(fc2_addrs)}..{max(fc2_addrs)})")
    fc2_writes = writes[32:]
    le_ok = all(fc2_writes[4 * n + b] == (n, b, 4 * n + b)
                for n in range(10) for b in range(4))
    log.check(le_ok, "FC2 writes 4 bytes little-endian per class, addresses 4n..4n+3")
    hw_fc(log, golden)
    run_spice(log, "fc", spice_fc(13120), 13120, golden)


def main() -> int:
    logs = []
    for name, fn in (("conv1", verify_conv1), ("conv2", verify_conv2), ("fc", verify_fc)):
        log = Log(os.path.join(OUT_DIR, f"{name}_engine.log"))
        logs.append(log)
        log("COMMAND: python sim/gen_engine_tb.py")
        log(f"ENGINE: {name}")
        try:
            fn(log)
        except Exception as exc:  # noqa: BLE001
            log("EXCEPTION:", repr(exc))
            log.ok = False
        log(f"RESULT: {'PASS' if log.ok else 'FAIL'}")
        log.close()
    ok = all(lg.ok for lg in logs)
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
