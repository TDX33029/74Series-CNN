"""Generate and run a SPICE functional testbench for the POOL engine.

The netlist models the S05 datapath at register level: the 9-state FSM, the
2-bit value phase, the window counter, the 8-bit unsigned MAX register and the
output register are XSPICE d_dff instances.  B sources implement the next-state
table, the 4-window address sequence and the window data ROM.

Covered vectors (10 windows, one row of a POOL1 feature map):
  * MAX at window position 0, 1, 2 and 3 (255 cases)
  * equal values (7,7,7,7)
  * 0 boundary (0,0,0,0) and 255 boundary (255,0,0,0 etc.)
The testbench checks the four read addresses per window (2n, 2n+1, 2n+W,
2n+W+1 with W=24) and the MAX/DONE sequence, then prints PASS/FAIL.
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

# 10 windows; each tuple is v0..v3 for one output pixel.
WINDOWS = [
    (5, 200, 30, 40),      # max 200 at position 1
    (10, 20, 30, 255),     # max 255 at position 3
    (250, 20, 3, 4),       # max 250 at position 0
    (1, 2, 240, 4),        # max 240 at position 2
    (7, 7, 7, 7),          # all equal
    (0, 0, 0, 0),          # 0 boundary
    (255, 0, 0, 0),        # 255 boundary, position 0
    (0, 255, 0, 0),        # 255 boundary, position 1
    (0, 0, 255, 0),        # 255 boundary, position 2
    (0, 0, 0, 255),        # 255 boundary, position 3
]
EXPECTED_MAX = [max(w) for w in WINDOWS]
W = 24
CLK_PERIOD_NS = 100.0
SAMPLE_OFFSET_NS = 80.0  # 30 ns after each rising edge (50 ns + 30 ns)

# State encoding used by the testbench FSM.
IDLE, INIT, RD, WT, CP, OUTLD, NEXT, DONE, WAIT = range(9)


def val_expr(net: str) -> str:
    return f"V({net})"


def data_expr() -> str:
    parts = []
    for n, vals in enumerate(WINDOWS):
        vparts = []
        for v, val in enumerate(vals):
            vparts.append(f"(abs(V(v)-{v})<0.5 ? {val} : ")
        expr = "".join(vparts) + "0" + ")" * len(vparts)
        parts.append(f"(abs(V(n)-{n})<0.5 ? ({expr}) : ")
    return "".join(parts) + "0" + ")" * len(parts)


def next_state_expr() -> str:
    s = "V(st)"
    return (
        f"(abs({s}-0)<0.5 ? ((V(start)>1.65) ? 1 : 0) : "
        f"(abs({s}-1)<0.5 ? 2 : "
        f"(abs({s}-2)<0.5 ? 3 : "
        f"(abs({s}-3)<0.5 ? 4 : "
        f"(abs({s}-4)<0.5 ? ((V(v)>2.5) ? 5 : 2) : "
        f"(abs({s}-5)<0.5 ? 6 : "
        f"(abs({s}-6)<0.5 ? ((abs(V(n)-9)<0.5) ? 7 : 2) : "
        f"(abs({s}-7)<0.5 ? 8 : "
        f"(abs({s}-8)<0.5 ? ((V(start)>1.65) ? 8 : 0) : 0)))))))))"
    )


def build_netlist() -> str:
    ns = next_state_expr()
    dat = data_expr()
    lines = [
        "* POOL engine functional testbench (S05 behavior)",
        ".model ddff d_dff()",
        "Vclk clk 0 PULSE(0 3.3 50n 1n 1n 50n 100n)",
        "Vrst rst 0 PWL(0 3.3 200n 3.3 201n 0)",
        "Vstart start 0 PWL(0 0 300n 0 301n 3.3 700n 3.3 701n 0)",
        "Vs0 s0 0 0",
        # state register (4 bits)
        f"Bst st 0 V = (V(q0)+2*V(q1)+4*V(q2)+8*V(q3))/3.3",
        f"Bns ns 0 V = {ns}",
        # value phase counter (2 bits), cleared in INIT
        "Bvval v 0 V = (V(qv0)+2*V(qv1))/3.3",
        "Bvn vn 0 V = (abs(V(st)-4)<0.5) ? ((floor(V(v)+1.01)-4*floor((V(v)+1.01)/4+0.01))) : V(v)",
        "Bmclr mclr 0 V = ((V(rst)>1.65) + (abs(V(st)-1)<0.5) > 0.5) ? 3.3 : 0",
        # window counter (4 bits), cleared in INIT
        "Bnval n 0 V = (V(qn0)+2*V(qn1)+4*V(qn2)+8*V(qn3))/3.3",
        "Bnn nn 0 V = (abs(V(st)-6)<0.5) ? (V(n)+1) : V(n)",
        # window data ROM (10 windows x 4 values)
        f"Bdata data 0 V = {dat}",
        # unsigned compare and MAX update strobe
        "Bgt gt 0 V = (V(data)>V(max)+0.5) ? 3.3 : 0",
        "Bupd upd 0 V = ((abs(V(st)-4)<0.5) ? ((abs(V(v)-0)<0.5) ? 3.3 : V(gt)) : 0)",
        # address = 2*n + (v==2 ? W : v==3 ? W+1 : v)
        "Baddr addr 0 V = 2*V(n) + ((abs(V(v)-0)<0.5) ? 0 : "
        "((abs(V(v)-1)<0.5) ? 1 : ((abs(V(v)-2)<0.5) ? 24 : 25)))",
    ]
    # state FFs
    for k in range(4):
        div, div2 = 2 ** k, 2 ** (k + 1)
        lines.append(f"Bd{k} d{k} 0 V = 3.3*(floor(V(ns)/{div}+0.01)-2*floor(V(ns)/{div2}+0.005))")
        lines.append(f"A{k} d{k} clk s0 rst q{k} qb{k} ddff")
    # value FFs
    for k in range(2):
        div, div2 = 2 ** k, 2 ** (k + 1)
        lines.append(f"Bvd{k} vd{k} 0 V = 3.3*(floor(V(vn)/{div}+0.01)-2*floor(V(vn)/{div2}+0.005))")
        lines.append(f"Av{k} vd{k} clk s0 mclr qv{k} qvb{k} ddff")
    # window FFs
    for k in range(4):
        div, div2 = 2 ** k, 2 ** (k + 1)
        lines.append(f"Bnd{k} nd{k} 0 V = 3.3*(floor(V(nn)/{div}+0.01)-2*floor(V(nn)/{div2}+0.005))")
        lines.append(f"An{k} nd{k} clk s0 mclr qn{k} qnb{k} ddff")
    # MAX FFs
    for k in range(8):
        div, div2 = 2 ** k, 2 ** (k + 1)
        lines.append(
            f"Bmb{k} mb{k} 0 V = 3.3*(floor((V(data)+0.5)/{div})-2*floor((V(data)+0.5)/{div2}))"
        )
        lines.append(
            f"Bmxd{k} mxd{k} 0 V = ((V(upd)>1.65) ? V(mb{k}) : V(qm{k}))"
        )
        lines.append(f"Am{k} mxd{k} clk s0 mclr qm{k} qmb{k} ddff")
    # MAX value and output register
    lines.append("Bmax max 0 V = (V(qm0)+2*V(qm1)+4*V(qm2)+8*V(qm3)+16*V(qm4)+32*V(qm5)+64*V(qm6)+128*V(qm7))/3.3")
    for k in range(8):
        lines.append(f"Ao{k} qm{k} clk s0 mclr qo{k} qob{k} ddff")
    lines.append("Bout out 0 V = (V(qo0)+2*V(qo1)+4*V(qo2)+8*V(qo3)+16*V(qo4)+32*V(qo5)+64*V(qo6)+128*V(qo7))/3.3")
    lines += [
        "Bdone done 0 V = 3.3*((abs(V(st)-7)<0.5) ? 1 : 0)",
        ".tran 1n 17500n",
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


def sample_at(rows, t_ns: float):
    t = t_ns * 1e-9
    best = None
    for r in rows:
        if r[0] <= t:
            best = r
        else:
            break
    return best


def main() -> int:
    cir = os.path.join(SIM_DIR, "tb_pool.cir")
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_netlist())
    log = []
    def say(s=""):
        print(s)
        log.append(s)

    ng = NgSpice()
    ng.run_file(cir)
    say(ng.text())
    ng.command("run")
    say(ng.text())
    wave = os.path.join(OUT_DIR, "pool_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command("wrdata " + wave.replace("\\", "/")
               + " v(st) v(n) v(v) v(addr) v(max) v(out) v(done)")
    rows = parse_pairs(wave, 7)
    if not rows:
        say("FAIL: no waveform data")
        with open(os.path.join(OUT_DIR, "pool.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
        return 1

    samples = []
    for k in range(171):
        t = SAMPLE_OFFSET_NS + k * CLK_PERIOD_NS
        r = sample_at(rows, t)
        if r:
            samples.append((t, int(round(r[1])), int(round(r[2])),
                            int(round(r[3])), int(round(r[4])),
                            int(round(r[5])), int(round(r[6])),
                            r[7] > 1.65))
    say("time_ns state n v addr max out done")
    for s in samples[:40]:
        say("  " + str(s))
    say("... ({} samples total)".format(len(samples)))

    # Collapse state sequence.
    collapsed = [s for i, s in enumerate(samples) if i == 0 or s[1] != samples[i - 1][1]]
    seq = [s[1] for s in collapsed]
    say("state sequence: " + str(seq))

    # Check every RD address against the expected 4-value order.
    addr_ok = True
    rd_count = 0
    for s in samples:
        if s[1] == RD:
            n, v, addr = s[2], s[3], s[4]
            want = 2 * n + (0 if v == 0 else 1 if v == 1 else W if v == 2 else W + 1)
            rd_count += 1
            if addr != want:
                addr_ok = False
                say(f"ADDR MISMATCH t={s[0]:.1f} n={n} v={v} addr={addr} want={want}")

    # Check each window's MAX/OUT at NEXT.
    next_samples = [s for s in samples if s[1] == NEXT]
    seen = {}
    for s in next_samples:
        seen.setdefault(s[2], []).append(s)
    max_ok = True
    for n in range(10):
        got = seen.get(n, [])
        if not got:
            max_ok = False
            say(f"MISSING window {n}")
            continue
        s = got[0]
        want = EXPECTED_MAX[n]
        say(f"window {n}: out={s[6]} max_reg={s[5]} expected={want}")
        if s[6] != want or s[5] != want:
            max_ok = False

    init_clear = any(s[1] == INIT and s[5] == 0 for s in samples)
    done_seen = any(s[1] == DONE and s[7] for s in samples)
    seq_ok = (INIT in seq and RD in seq and WT in seq and CP in seq
              and OUTLD in seq and NEXT in seq and DONE in seq)
    v_ok = all(s[3] in (0, 1, 2, 3) for s in samples if s[1] in (RD, WT, CP))
    say(f"addr_ok={addr_ok} rd_checks={rd_count} max_ok={max_ok} "
        f"init_clear={init_clear} done_seen={done_seen} seq_ok={seq_ok} v_ok={v_ok}")
    ok = addr_ok and max_ok and init_clear and done_seen and seq_ok and v_ok
    say("PASS: POOL 2x2 max, 4-value order, 0/255 and equal-value coverage"
        if ok else "FAIL: POOL functional test")
    with open(os.path.join(OUT_DIR, "pool.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
