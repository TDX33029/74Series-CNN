"""SPICE functional check of the 8x8 LUT multiplier arithmetic.

The exhaustive 65536-entry check is done in Python (tools/gen_lut.py); this
testbench exercises representative operand pairs through the same
product/low/high-byte equations used by the ROM generator.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from ngspice_runner import NgSpice

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
SIM_DIR = os.path.join(PROJECT_DIR, "sim")
OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
os.makedirs(OUT_DIR, exist_ok=True)

# (A, B) pairs, 200 ns per pair
PAIRS = [(0, 0), (1, 1), (255, 255), (123, 45), (0, 255), (255, 0), (128, 127), (200, 100)]
STEP = 200.0


def build_netlist() -> str:
    a_pts, b_pts = [], []
    for i, (a, b) in enumerate(PAIRS):
        t0 = i * STEP
        t1 = (i + 1) * STEP
        a_pts.append(f"{t0}n {a} {t0 + 1}n {a} {t1}n {a}")
        b_pts.append(f"{t0}n {b} {t0 + 1}n {b} {t1}n {b}")
    lines = [
        "* 8x8 LUT multiplier representative-pair test",
        "Va a 0 PWL(" + " ".join(a_pts) + ")",
        "Vb b 0 PWL(" + " ".join(b_pts) + ")",
        "Bp prod 0 V = V(a)*V(b)",
        "Blo lo 0 V = V(a)*V(b)-256*floor(V(a)*V(b)/256)",
        "Bhi hi 0 V = floor(V(a)*V(b)/256)",
        f".tran 1n {len(PAIRS) * STEP + 10}n",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def parse_pairs(path: str, nvec: int):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2 * nvec:
                continue
            try:
                t = float(parts[0])
                vals = tuple(float(parts[1 + 2 * i]) for i in range(nvec))
                rows.append((t,) + vals)
            except ValueError:
                pass
    return rows


def main() -> int:
    cir = os.path.join(SIM_DIR, "tb_lut.cir")
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_netlist())
    ng = NgSpice()
    ng.run_file(cir)
    ng.command("run")
    print(ng.text()[-500:])
    wave = os.path.join(OUT_DIR, "lut_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command("wrdata " + wave.replace("\\", "/") + " v(prod) v(lo) v(hi)")
    rows = parse_pairs(wave, 3)
    if not rows:
        print("FAIL: no data")
        return 1

    def at(t_ns):
        t = t_ns * 1e-9
        best = None
        for r in rows:
            if r[0] <= t:
                best = r
            else:
                break
        return best

    errors = 0
    for i, (a, b) in enumerate(PAIRS):
        # sample in the middle of each constant interval
        r = at(i * STEP + STEP / 2)
        if r is None:
            errors += 1
            continue
        p = a * b
        ok = abs(r[1] - p) < 0.5 and abs(r[2] - (p & 0xFF)) < 0.5 and abs(r[3] - (p >> 8)) < 0.5
        print(f"A={a:3d} B={b:3d} expect {p:5d}/{p & 0xFF:3d}/{p >> 8:3d} "
              f"got {r[1]:.1f}/{r[2]:.1f}/{r[3]:.1f} {'OK' if ok else 'FAIL'}")
        if not ok:
            errors += 1
    if errors:
        print("FAIL: LUT SPICE arithmetic")
        return 1
    print("PASS: LUT SPICE arithmetic (representative pairs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
