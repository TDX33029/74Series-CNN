"""Generate and run a SPICE functional testbench for the ARGMAX engine.

The model is register-level: a 4-bit FSM, 4-bit class counter, 3-bit test
counter, 32-bit score register, 32-bit MAX register and 4-bit index register
are XSPICE d_dff instances.

Scores are supplied as four 8-bit byte constants (0..255), which are exactly
representable by the simulator.  The score register is built bit by bit from
those bytes, and the signed compare is a bitwise MSB-first chain that mirrors
the 74HC85 cascade with both sign bits inverted.  No 32-bit integer is ever
carried in an analogue node, avoiding float32 precision loss at 2^31.

Five vectors cover positive/negative scores, MAX at the first and last class,
ties (lowest class wins), -2^31 and 2^31-1 boundaries.  Result is checked at
DONE; PASS/FAIL is written to output/sim/argmax.log.
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

INT32_MIN = -2147483648
INT32_MAX = 2147483647
CASES = [
    # mixed signs, MAX at class 0
    [100, -50, 30, -7, 0, 55, -100, 12, 90, -1],
    # boundaries, MAX at class 9
    [INT32_MIN, -1, 0, 1, 2147483646, -2147483647,
     1073741824, -1073741824, 42, INT32_MAX],
    # all tied: lowest class wins
    [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
    # tie for MAX at classes 2, 5, 7: class 2 must win
    [-9, -9, 12345, 0, 4, 12345, -2, 12345, 0, 1],
    # all negative, MAX at class 4; INT32_MIN present
    [-5, -100, -7, INT32_MIN, -1, -2, -3, -4, -5, -6],
]
EXPECTED_RESULT = [0, 9, 0, 2, 4]
EXPECTED_MAX = [max(v) for v in CASES]
NCASES = len(CASES)

# State encoding used by the testbench FSM.
IDLE, INIT, RD0, WT0, LD0, RD, WT, CMP, NEXT, DONE, WAIT = range(11)
CLK_PERIOD_NS = 100.0
SAMPLE_OFFSET_NS = 80.0  # 30 ns after the rising edge at 50 ns


def b32(v: int) -> int:
    return v & 0xFFFFFFFF


def byte_of(v: int, i: int) -> int:
    return (b32(v) >> (8 * i)) & 0xFF


def class_byte_expr(scores, bi: int) -> str:
    parts = []
    for c, s in enumerate(scores):
        parts.append(f"(abs(V(cls)-{c})<0.5 ? {byte_of(s, bi)} : ")
    return "".join(parts) + "0" + ")" * len(parts)


def next_state_expr() -> str:
    s = "V(st)"
    return (
        f"(abs({s}-0)<0.5 ? ((V(start)>1.65) ? 1 : 0) : "
        f"(abs({s}-1)<0.5 ? 2 : "
        f"(abs({s}-2)<0.5 ? 3 : "
        f"(abs({s}-3)<0.5 ? 4 : "
        f"(abs({s}-4)<0.5 ? 8 : "
        f"(abs({s}-5)<0.5 ? 6 : "
        f"(abs({s}-6)<0.5 ? 7 : "
        f"(abs({s}-7)<0.5 ? 8 : "
        f"(abs({s}-8)<0.5 ? ((abs(V(cls)-9)<0.5) ? 9 : 5) : "
        f"(abs({s}-9)<0.5 ? 10 : "
        f"(abs({s}-10)<0.5 ? ((V(start)>1.65) ? 10 : 0) : 0)))))))))))"
    )


def bit_expr(value: str, k: int) -> str:
    """Return 3.3*bit k of an exact non-negative integer expression."""
    div, div2 = 2 ** k, 2 ** (k + 1)
    return f"3.3*(floor(({value}+0.5)/{div})-2*floor(({value}+0.5)/{div2}))"


def build_netlist() -> str:
    ns = next_state_expr()
    lines = [
        "* ARGMAX signed-32 functional testbench (S06 behavior)",
        ".model ddff d_dff()",
        "Vclk clk 0 PULSE(0 3.3 50n 1n 1n 50n 100n)",
        "Vrst rst 0 PWL(0 3.3 200n 3.3 201n 0)",
        "Vs0 s0 0 0",
        "Bst st 0 V = (V(q0)+2*V(q1)+4*V(q2)+8*V(q3))/3.3",
        "Btval tst 0 V = (V(qt0)+2*V(qt1)+4*V(qt2))/3.3",
        "Bcls cls 0 V = (V(qc0)+2*V(qc1)+4*V(qc2)+8*V(qc3))/3.3",
        # auto START: one pulse per vector while IDLE and vectors remain
        "Bstart start 0 V = ((abs(V(st)-0)<0.5)*(V(tst)<4.5)) ? 3.3 : 0",
        f"Bns ns 0 V = {ns}",
        "Bmclr mclr 0 V = ((V(rst)>1.65)+(abs(V(st)-1)<0.5) > 0.5) ? 3.3 : 0",
        "Bclsn clsn 0 V = (abs(V(st)-8)<0.5) ? (V(cls)+1) : V(cls)",
        "Btnxt tnxt 0 V = (abs(V(st)-9)<0.5) ? (V(tst)+1) : V(tst)",
    ]
    # Byte ROM: one class lookup per test per byte, then a test selector.
    for bi in range(4):
        for ti, scores in enumerate(CASES):
            lines.append(
                f"Bb{bi}_{ti} b{bi}_{ti} 0 V = {class_byte_expr(scores, bi)}"
            )
        sel = []
        for ti in range(NCASES):
            sel.append(f"(abs(V(tst)-{ti})<0.5 ? V(b{bi}_{ti}) : ")
        lines.append(
            f"Bb{bi} b{bi} 0 V = " + "".join(sel) + "0" + ")" * len(sel)
        )
    # state FFs
    for k in range(4):
        lines.append(f"Bd{k} d{k} 0 V = {bit_expr('V(ns)', k)}")
        lines.append(f"A{k} d{k} clk s0 rst q{k} qb{k} ddff")
    # test counter (3 bits)
    for k in range(3):
        lines.append(f"Btd{k} td{k} 0 V = {bit_expr('V(tnxt)', k)}")
        lines.append(f"At{k} td{k} clk s0 rst qt{k} qtb{k} ddff")
    # class counter (4 bits)
    for k in range(4):
        lines.append(f"Bcd{k} cd{k} 0 V = {bit_expr('V(clsn)', k)}")
        lines.append(f"Ac{k} cd{k} clk s0 mclr qc{k} qcb{k} ddff")
    # score register (32 bits) from the byte ROM
    for k in range(32):
        bi, p = k // 8, k % 8
        lines.append(
            f"Bsd{k} sd{k} 0 V = 3.3*(floor((V(b{bi})+0.5)/{2 ** p})"
            f"-2*floor((V(b{bi})+0.5)/{2 ** (p + 1)}))"
        )
        lines.append(f"As{k} sd{k} clk s0 mclr qs{k} qsb{k} ddff")
    # MAX update and index update strobe
    # bitwise signed compare: invert bit 31, then MSB-first chain
    lines.append(
        "Bc31 c31 0 V = ((V(qs31)<1.65)*(V(qm31)>1.65)) ? 3.3 : "
        "(((V(qs31)>1.65)*(V(qm31)<1.65)) ? -3.3 : 0)"
    )
    for k in range(30, -1, -1):
        lines.append(
            f"Bc{k} c{k} 0 V = (abs(V(c{k + 1}))>1.65) ? V(c{k + 1}) : "
            f"(((V(qs{k})>1.65)*(V(qm{k})<1.65)) ? 3.3 : "
            f"(((V(qs{k})<1.65)*(V(qm{k})>1.65)) ? -3.3 : 0))"
        )
    lines.append("Bgt gt 0 V = (V(c0)>1.65) ? 3.3 : 0")
    lines.append(
        "Bupd upd 0 V = ((abs(V(st)-4)<0.5) ? 3.3 : "
        "((abs(V(st)-7)<0.5) ? V(gt) : 0))"
    )
    for k in range(32):
        lines.append(f"Bmxd{k} mxd{k} 0 V = (V(upd)>1.65) ? V(qs{k}) : V(qm{k})")
        lines.append(f"Am{k} mxd{k} clk s0 mclr qm{k} qmb{k} ddff")
    # index register (4 bits), D = class when UPDATE, else hold
    for k in range(4):
        lines.append(f"Bixd{k} ixd{k} 0 V = (V(upd)>1.65) ? V(qc{k}) : V(qi{k})")
        lines.append(f"Ai{k} ixd{k} clk s0 mclr qi{k} qib{k} ddff")
    # byte views of score and MAX registers for logging/checking
    for bi in range(4):
        terms = []
        for p in range(8):
            k = 8 * bi + p
            bit = f"((V(qs{k})>1.65)?1:0)"
            terms.append(bit if p == 0 else f"+{2 ** p}*{bit}")
        lines.append(f"Bsbyte{bi} sbyte{bi} 0 V = " + "".join(terms))
        terms = []
        for p in range(8):
            k = 8 * bi + p
            bit = f"((V(qm{k})>1.65)?1:0)"
            terms.append(bit if p == 0 else f"+{2 ** p}*{bit}")
        lines.append(f"Bmbyte{bi} mbyte{bi} 0 V = " + "".join(terms))
    lines.append(
        "Bres result 0 V = ((V(qi0)>1.65)?1:0)+2*((V(qi1)>1.65)?1:0)"
        "+4*((V(qi2)>1.65)?1:0)+8*((V(qi3)>1.65)?1:0)"
    )
    lines.append("Baddr addr 0 V = V(cls)")
    lines.append("Bdone done 0 V = (abs(V(st)-9)<0.5) ? 3.3 : 0")
    lines.append(
        "Bvalid valid 0 V = ((abs(V(st)-9)<0.5)+(abs(V(st)-10)<0.5) > 0.5) ? 3.3 : 0"
    )
    lines.append(
        "Bsrd srd 0 V = ((abs(V(st)-2)<0.5)+(abs(V(st)-3)<0.5)+"
        "(abs(V(st)-5)<0.5)+(abs(V(st)-6)<0.5) > 0.5) ? 3.3 : 0"
    )
    lines += [".tran 1n 23000n", ".end"]
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


def signed32(b0: int, b1: int, b2: int, b3: int) -> int:
    u = b0 + (b1 << 8) + (b2 << 16) + (b3 << 24)
    return u - (1 << 32) if u >= (1 << 31) else u


def main() -> int:
    cir = os.path.join(SIM_DIR, "tb_argmax.cir")
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
    wave = os.path.join(OUT_DIR, "argmax_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command("wrdata " + wave.replace("\\", "/")
               + " v(st) v(tst) v(cls) v(addr) v(sbyte0) v(sbyte1) "
                 "v(sbyte2) v(sbyte3) v(mbyte0) v(mbyte1) v(mbyte2) "
                 "v(mbyte3) v(result) v(done) v(valid) v(srd)")
    rows = parse_pairs(wave, 16)
    if not rows:
        say("FAIL: no waveform data")
        with open(os.path.join(OUT_DIR, "argmax.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")
        return 1

    samples = []
    for k in range(231):
        t = SAMPLE_OFFSET_NS + k * CLK_PERIOD_NS
        r = sample_at(rows, t)
        if r:
            samples.append((t, int(round(r[1])), int(round(r[2])),
                            int(round(r[3])), int(round(r[4])),
                            int(round(r[5])), int(round(r[6])),
                            int(round(r[7])), int(round(r[8])),
                            int(round(r[9])), int(round(r[10])),
                            int(round(r[11])), int(round(r[12])),
                            int(round(r[13])), r[14] > 1.65,
                            r[15] > 1.65, r[16] > 1.65))
    say("time_ns state test class addr sbyte0-3 mbyte0-3 result done valid srd")
    for s in samples[:40]:
        say("  " + str(s))
    say("... ({} samples total)".format(len(samples)))

    done_samples = [s for s in samples if s[1] == DONE]
    result_ok = True
    got_results = {}
    for s in done_samples:
        ti = s[2]
        maxv = signed32(s[9], s[10], s[11], s[12])
        got_results.setdefault(ti, []).append((s[13], maxv, s[15]))
    for ti in range(NCASES):
        if ti not in got_results:
            result_ok = False
            say(f"MISSING DONE for test {ti}")
            continue
        res, maxv, valid = got_results[ti][0]
        say(f"test {ti}: result={res} max={maxv} expected_result={EXPECTED_RESULT[ti]} "
            f"expected_max={EXPECTED_MAX[ti]} valid={valid}")
        if res != EXPECTED_RESULT[ti] or maxv != EXPECTED_MAX[ti] or not valid:
            result_ok = False

    # Score-register values at CMP must match the vector ROM.
    cmp_ok = True
    for s in samples:
        if s[1] == CMP:
            ti, cl = s[2], s[3]
            want = CASES[ti][cl] if ti < NCASES and cl < 10 else None
            got = signed32(s[5], s[6], s[7], s[8])
            if want is not None and got != want:
                cmp_ok = False
                say(f"CMP MISMATCH t={s[0]:.1f} test={ti} class={cl} "
                    f"sreg={got} want={want}")
    # Every read address must equal the class index.
    addr_ok = all(s[4] == s[3] for s in samples if s[1] in (RD0, RD, WT0, WT))
    # SCORE_RD must be high exactly in read states.
    srd_ok = all((s[1] in (RD0, WT0, RD, WT)) == s[16] for s in samples)
    # Per-test class read sequence must be 0..9.
    seq_ok = True
    for ti in range(NCASES):
        seq = []
        for s in samples:
            if s[1] in (RD0, RD) and s[2] == ti:
                if not seq or seq[-1] != s[3]:
                    seq.append(s[3])
        if seq != list(range(10)):
            seq_ok = False
            say(f"READ SEQUENCE test {ti}: {seq}")

    say(f"result_ok={result_ok} cmp_ok={cmp_ok} addr_ok={addr_ok} "
        f"srd_ok={srd_ok} seq_ok={seq_ok}")
    ok = result_ok and cmp_ok and addr_ok and srd_ok and seq_ok
    say("PASS: ARGMAX signed32, ties, first/last and -2^31/2^31-1 boundaries"
        if ok else "FAIL: ARGMAX functional test")
    with open(os.path.join(OUT_DIR, "argmax.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
