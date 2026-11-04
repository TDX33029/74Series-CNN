"""Generate and run a SPICE functional testbench for the timing controller."""
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

T_IDLE, T_SETUP, T_WAIT, T_CAPTURE, T_HOLD, T_RELEASE, T_DONE = range(7)


def b(expr: str) -> str:
    return f"(({expr}) ? 1 : 0)"


def build_netlist() -> str:
    req = b("V(req)>1.65")
    we = b("V(we)>1.65")
    match = b("abs(V(cnt)-V(waitv))<0.05")
    ts_eq = lambda n: f"(abs(V(ts)-{n})<0.5)"  # noqa: E731

    # Next state
    ns_terms = []
    for st in range(7):
        if st == T_IDLE:
            e = f"({req} ? 1 : 0)"
        elif st == T_SETUP:
            e = "2"
        elif st == T_WAIT:
            e = f"({match} ? ({we} ? 4 : 3) : 2)"
        elif st == T_CAPTURE:
            e = "4"
        elif st == T_HOLD:
            e = "5"
        elif st == T_RELEASE:
            e = "6"
        else:
            e = "0"
        ns_terms.append(f"({ts_eq(st)} ? {e} : ")
    ns_expr = "".join(ns_terms) + "0" + ")" * len(ns_terms)

    lines = [
        "* Timing controller functional testbench",
        ".model ddff d_dff()",
        "Vclk clk 0 PULSE(0 3.3 50n 1n 1n 50n 100n)",
        "Vrst rst 0 PWL(0 3.3 200n 3.3 201n 0)",
        "Vs0 s0 0 0",
        "Vreq req 0 PWL(0 0 300n 0 301n 3.3 1100n 3.3 1101n 0 1500n 0 1501n 3.3 2300n 3.3 2301n 0)",
        "Vwe we 0 PWL(0 0 1400n 0 1401n 3.3)",
        "Vwaitr waitr 0 2",
        "Vwaitw waitw 0 3",
        "Bwaitv waitv 0 V = (V(we)>1.65) ? V(waitw) : V(waitr)",
        "",
        "Bts ts 0 V = (V(q0)+2*V(q1)+4*V(q2))/3.3",
        "Bcnt cnt 0 V = ((V(qc0)>1.65) ? 1 : 0) + 2*((V(qc1)>1.65) ? 1 : 0)",
        f"Bns ns 0 V = {ns_expr}",
        "Bc0n c0n 0 V = 3.3*((abs(V(ts)-1)<0.5) ? 0 : (1 - ((V(qc0)>1.65) ? 1 : 0)))",
        "Bc1n c1n 0 V = 3.3*((abs(V(ts)-1)<0.5) ? 0 : (((V(qc1)>1.65) ? 1 : 0) + ((V(qc0)>1.65) ? 1 : 0) - 2*((V(qc1)>1.65) ? 1 : 0)*((V(qc0)>1.65) ? 1 : 0)))",
    ]
    for k in range(3):
        div, div2 = 2 ** k, 2 ** (k + 1)
        lines.append(f"Bd{k} d{k} 0 V = 3.3*(floor(V(ns)/{div}+0.01)-2*floor(V(ns)/{div2}+0.005))")
        lines.append(f"A{k} d{k} clk s0 rst q{k} qb{k} ddff")
    lines.append("AC0 c0n clk s0 rst qc0 qbc0 ddff")
    lines.append("AC1 c1n clk s0 rst qc1 qbc1 ddff")

    lines += [
        # active-low controls
        "Bnce nce 0 V = 3.3*((V(ts)<0.5) ? 1 : ((V(ts)<3.5) ? 0 : ((V(ts)<4.5) ? 0 : ((V(ts)<5.5) ? 1 : 1))))",
        "Bnoe noe 0 V = 3.3*((V(we)>1.65) ? 1 : ((V(ts)>0.5) ? ((V(ts)<4.5) ? 0 : 1) : 1))",
        "Bnwe nwe 0 V = 3.3*((V(we)<1.65) ? 1 : ((V(ts)>0.5) ? ((V(ts)<3.5) ? 0 : 1) : 1))",
        "Back ack 0 V = 3.3*((((V(we)<1.65)*(V(ts)>2.5)*(V(ts)<3.5)) + ((V(we)>1.65)*(V(ts)>3.5)*(V(ts)<4.5))) ? 1 : 0)",
        "Bdone done 0 V = 3.3*((V(ts)>5.5) ? 1 : 0)",
        "Bbusy busy 0 V = 3.3*((V(ts)>0.5) ? 1 : 0)",
        ".tran 1n 2600n",
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
    cir = os.path.join(SIM_DIR, "tb_timing.cir")
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_netlist())
    ng = NgSpice()
    ng.run_file(cir)
    print(ng.text())
    ng.command("run")
    print(ng.text())
    wave = os.path.join(OUT_DIR, "timing_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command("wrdata " + wave.replace("\\", "/") + " v(ts) v(cnt) v(nce) v(noe) v(nwe) v(ack) v(done) v(busy) v(we)")
    rows = parse_pairs(wave, 9)
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

    samples = []
    for k in range(25):
        r = at(80 + k * 100)
        if r:
            samples.append((80 + k * 100, int(round(r[1])), int(round(r[2])),
                            r[3] > 1.65, r[4] > 1.65, r[5] > 1.65,
                            r[6] > 1.65, r[7] > 1.65, r[8] > 1.65, r[9] > 1.65))
    print("time_ns state cnt nCE nOE nWE ACK DONE BUSY")
    for s in samples:
        print("  ", s)

    states = [s[1] for s in samples]
    collapsed = [s for i, s in enumerate(samples) if i == 0 or s[1] != samples[i - 1][1]]
    seq = [s[1] for s in collapsed]
    print("state sequence:", seq)

    # Basic protocol checks over all samples.
    conflict = any((not s[4]) and (not s[5]) for s in samples)  # nOE and nWE both low
    nce_ok = all(s[3] == (s[1] in (T_IDLE, T_RELEASE, T_DONE)) for s in samples)
    done_ok = all(s[7] == (s[1] == T_DONE) for s in samples)
    # nWE is active-low: high during read, low during write.
    # ACK: read -> CAPTURE, write -> HOLD.  s[9] is the WE input.
    ack_ok = all(s[6] == ((s[1] == T_CAPTURE and not s[9]) or (s[1] == T_HOLD and s[9]))
                 for s in samples)
    start_ok = seq[:3] == [T_IDLE, T_SETUP, T_WAIT] and T_CAPTURE in seq and T_HOLD in seq
    read_capture = any(s[1] == T_CAPTURE and s[6] for s in samples)
    write_hold = any(s[1] == T_HOLD and s[6] for s in samples)
    print(f"no_oe_we_conflict={not conflict} nce_ok={nce_ok} done_ok={done_ok} "
          f"ack_ok={ack_ok} start_ok={start_ok} read_ack={read_capture} write_ack={write_hold}")
    if (not conflict) and nce_ok and done_ok and ack_ok and start_ok and read_capture and write_hold:
        print("PASS: timing controller read/write protocol")
        return 0
    print("FAIL: timing controller protocol")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
