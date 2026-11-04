"""Generate and run a SPICE functional testbench for the supervisor FSM.

The FSM is modeled at the state-bit level: five XSPICE d_dff instances hold
the state, and behavioural B sources implement the next-state table.  This is
the same state table that drives the microcode ROM and the manual.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ngspice_runner import NgSpice

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
SIM_DIR = os.path.join(PROJECT_DIR, "sim")
OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
os.makedirs(SIM_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# State encoding from the architecture contract
G_RESET, G_WAIT_READY, G_IDLE = 0, 1, 2
STARTS = [3, 5, 7, 9, 11, 13, 15]
WAITS = [4, 6, 8, 10, 12, 14, 16]
G_FINISH, G_WAIT_START_LOW, G_ERROR = 17, 18, 19
DONE_NETS = ["c1", "p1", "c2", "p2", "fc1", "fc2", "am"]


def s(expr: str) -> str:
    """Boolean 0/1 from a SPICE expression (ngspice ternary syntax)."""
    return f"(({expr}) ? 1 : 0)"


def build_netlist() -> str:
    start = s("V(start)>1.65")
    img = s("V(img)>1.65")
    mdl = s("V(mdl)>1.65")
    ready = f"({img}*{mdl})"
    to = s("V(to)>1.65")
    done = {k: s(f"V({k})>1.65") for k in DONE_NETS}

    # Next-state function as a nested if on the state variable.
    terms = []
    for st in range(20):
        if st == G_RESET:
            e = "1"
        elif st == G_WAIT_READY:
            e = f"({ready} ? 2 : ({start} ? 19 : 1))"
        elif st == G_IDLE:
            e = f"({start} ? ({ready} ? 3 : 19) : 2)"
        elif st in STARTS:
            e = str(st + 1)
        elif st in WAITS:
            k = DONE_NETS[WAITS.index(st)]
            e = f"({to} ? 19 : ({done[k]} ? {st+1} : {st}))"
        elif st == G_FINISH:
            e = "18"
        elif st == G_WAIT_START_LOW:
            e = f"({start} ? 18 : 2)"
        else:
            e = "19"
        terms.append(f"(abs(V(st)-{st})<0.5 ? {e} : ")
    ns_expr = "".join(terms) + "0" + ")" * len(terms)

    lines = [
        "* Supervisor FSM functional testbench (state-bit level)",
        ".model ddff d_dff()",
        "Vclk clk 0 PULSE(0 3.3 50n 1n 1n 50n 100n)",
        "Vrst rst 0 PWL(0 3.3 200n 3.3 201n 0)",
        "Vs0 s0 0 0",
        "Vstart start 0 PWL(0 0 500n 0 501n 3.3 1000n 3.3 1001n 0)",
        "Vimg img 0 PWL(0 0 300n 0 301n 3.3)",
        "Vmdl mdl 0 PWL(0 0 400n 0 401n 3.3)",
        # one-cycle-ish done pulses, scheduled after each WAIT state is entered
        "Vc1 c1 0 PWL(0 0 740n 0 741n 3.3 760n 3.3 761n 0)",
        "Vp1 p1 0 PWL(0 0 940n 0 941n 3.3 960n 3.3 961n 0)",
        "Vc2 c2 0 PWL(0 0 1140n 0 1141n 3.3 1160n 3.3 1161n 0)",
        "Vp2 p2 0 PWL(0 0 1340n 0 1341n 3.3 1360n 3.3 1361n 0)",
        "Vfc1 fc1 0 PWL(0 0 1540n 0 1541n 3.3 1560n 3.3 1561n 0)",
        "Vfc2 fc2 0 PWL(0 0 1740n 0 1741n 3.3 1760n 3.3 1761n 0)",
        "Vam am 0 PWL(0 0 1940n 0 1941n 3.3 1960n 3.3 1961n 0)",
        "Vto to 0 0",
        f"Bst st 0 V = (V(q0)+2*V(q1)+4*V(q2)+8*V(q3)+16*V(q4))/3.3",
        f"Bns ns 0 V = {ns_expr}",
    ]
    for k in range(5):
        div = 2 ** k
        div2 = 2 ** (k + 1)
        lines.append(
            f"Bd{k} d{k} 0 V = 3.3*(floor(V(ns)/{div}+0.01)-2*floor(V(ns)/{div2}+0.005))"
        )
        lines.append(f"A{k} d{k} clk s0 rst q{k} qb{k} ddff")
    lines += [
        "Bbusy busy 0 V = 3.3*((V(st)>2.5) ? ((V(st)<16.5) ? 1 : 0) : 0)",
        "Bdon done 0 V = 3.3*((abs(V(st)-17)<0.5) ? 1 : 0)",
        "Berr err 0 V = 3.3*((abs(V(st)-19)<0.5) ? 1 : 0)",
        ".tran 1n 3000n",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def parse_wrdata(path: str):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            # wrdata writes a scale/value pair for every vector.
            if len(parts) >= 8:
                try:
                    rows.append((float(parts[0]), float(parts[1]),
                                 float(parts[3]), float(parts[5]), float(parts[7])))
                except ValueError:
                    pass
    return rows


def main() -> int:
    cir = os.path.join(SIM_DIR, "tb_supervisor.cir")
    netlist = build_netlist()
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(netlist)

    ng = NgSpice()
    rc = ng.run_file(cir)
    print("load rc", rc)
    print(ng.text())
    ng.command("run")
    print(ng.text())
    wave = os.path.join(OUT_DIR, "supervisor_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command(f"wrdata {wave.replace(chr(92), '/')} v(st) v(busy) v(done) v(err)")
    print(ng.text())
    rows = parse_wrdata(wave)
    if not rows:
        print("FAIL: no waveform data")
        return 1

    # Sample the state 30 ns after every rising clock edge.  The analogue
    # state bits can show nanosecond-scale skew glitches during a clock
    # transition; sampling after settling is the correct way to read a
    # synchronous state register.
    def sample_at(t: float):
        best = None
        for row in rows:
            if row[0] <= t:
                best = row
            else:
                break
        return best

    samples = []
    for k in range(30):
        t = (80.0 + k * 100.0) * 1e-9
        row = sample_at(t)
        if row is not None:
            samples.append((t, int(round(row[1])), int(round(row[2])),
                            int(round(row[3])), int(round(row[4]))))
    print("sampled states (time_ns, state, BUSY, DONE, ERROR):")
    for tr in samples:
        print("  ", tr)

    collapsed = []
    for tr in samples:
        if not collapsed or collapsed[-1][1] != tr[1]:
            collapsed.append(tr)
    print("collapsed states:", [tr[1] for tr in collapsed])
    expected = [G_RESET, G_WAIT_READY, G_IDLE,
                3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                G_FINISH, G_WAIT_START_LOW, G_IDLE]
    actual = [tr[1] for tr in collapsed]
    ok = actual[:len(expected)] == expected
    busy_ok = all(tr[2] > 1.65 for tr in samples if 3 <= tr[1] <= 16)
    done_ok = all((tr[3] > 1.65) == (tr[1] == G_FINISH) for tr in samples)
    error_ok = all(tr[4] < 1.65 for tr in samples)
    print(f"sequence_ok={ok} busy_ok={busy_ok} done_ok={done_ok} error_ok={error_ok}")
    if ok and busy_ok and done_ok and error_ok:
        print("PASS: supervisor state sequence")
        return 0
    print("FAIL: supervisor state sequence")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
