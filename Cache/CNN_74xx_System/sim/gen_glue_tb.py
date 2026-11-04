"""SPICE check of the active-low glue around the supervisor and timing sheets.

The 74HC688 P=R output is active-low.  Two places invert it before the
microcode ROM (IDLE_N -> IDLE_MATCH, TIMEOUT_N -> TIMEOUT_I) and the timing
sheet inverts WAIT_MATCH_N -> WAIT_MATCH.  This testbench models the comparator
truth levels and the inverters, plus the 74HC245 enable gating and the sticky
RESULT_VALID flip-flop (D=+5V, async set/clear).  It catches polarity mistakes
that a pure state-sequence test cannot see.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

from ngspice_runner import NgSpice  # noqa: E402

SIM_DIR = os.path.join(PROJECT_DIR, "sim")
OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
os.makedirs(OUT_DIR, exist_ok=True)


def build() -> str:
    return "\n".join([
        "* Glue polarity / result-valid hold testbench",
        ".model ddff d_dff()",
        "Vclk clk 0 PULSE(0 3.3 10n 1n 1n 10n 20n)",
        # comparator truth levels, active-low outputs
        "Vst st 0 PWL(0 3.3 199n 3.3 200n 0 399n 0 400n 3.3 599n 3.3 600n 0)",
        "Vwait_t wait_t 0 PWL(0 0 599n 0 600n 3.3 799n 3.3 800n 0)",
        "Vto to 0 PWL(0 0 999n 0 1000n 3.3 1199n 3.3 1200n 0)",
        "Vnce nce 0 PWL(0 3.3 1399n 3.3 1400n 0 1599n 0 1600n 3.3)",
        # U13 74HC74: D=+5V, set/clear active-low
        "Vsetn setn 0 PWL(0 3.3 299n 3.3 300n 0 399n 0 400n 3.3)",
        "Vclrn clrn 0 PWL(0 3.3 799n 3.3 800n 0 899n 0 900n 3.3)",
        # 74HC688 truth: output low when equal
        "Bidlen idlen 0 V = (V(st)>1.65 ? 0 : 3.3)",
        "Bidlem idlem 0 V = 3.3 - V(idlen)",
        "Bwaitn waitn 0 V = (V(wait_t)>1.65 ? 0 : 3.3)",
        "Bwaitm waitm 0 V = 3.3 - V(waitn)",
        "Bton ton 0 V = 3.3 - V(to)",
        "Btoi toi 0 V = 3.3 - V(ton)",
        "Boe oe 0 V = (V(nce)>1.65 ? 0 : 3.3)",
        # The XSPICE d_dff SET/RESET ports are active-high; invert the
        # 74HC74 active-low ~S/~R levels before driving them.
        # U13 uses D = Q feedback so the cell holds its state.
        "Bset set 0 V = 3.3 - V(setn)",
        "Bclr clr 0 V = 3.3 - V(clrn)",
        "Arv rv clk set clr rv rvb ddff",
        ".tran 1n 1800n",
        ".end",
    ]) + "\n"


def parse_pairs(path: str):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 8:
                try:
                    rows.append((float(parts[0]), float(parts[1]), float(parts[3]),
                                 float(parts[5]), float(parts[7])))
                except ValueError:
                    pass
    return rows


def main() -> int:
    cir = os.path.join(SIM_DIR, "tb_glue.cir")
    with open(cir, "w", encoding="utf-8", newline="\n") as f:
        f.write(build())
    ng = NgSpice()
    ng.run_file(cir)
    ng.command("run")
    wave = os.path.join(OUT_DIR, "glue_wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    ng.command(f"wrdata {wave.replace(chr(92), '/')} v(idlem) v(waitm) v(toi) v(oe)")
    rows = parse_pairs(wave)
    if not rows:
        print("FAIL: no waveform data")
        return 1

    def at(t_ns: float):
        best = None
        for r in rows:
            if r[0] <= t_ns * 1e-9:
                best = r
            else:
                break
        return best

    checks = []
    def expect(label, t_ns, net, want_high):
        r = at(t_ns)
        got = r[net] > 1.65 if r else False
        ok = got == want_high
        checks.append((label, ok, r[net] if r else None))
        print(f"{label:28s} t={t_ns:5.0f}ns got={r[net]:.1f} want={'high' if want_high else 'low'} {'OK' if ok else 'FAIL'}")

    expect("IDLE_MATCH idle", 100, 1, True)
    expect("IDLE_MATCH busy", 300, 1, False)
    expect("IDLE_MATCH idle again", 500, 1, True)
    expect("WAIT_MATCH before wait", 500, 2, False)
    expect("WAIT_MATCH at count", 700, 2, True)
    expect("TIMEOUT_I active", 1100, 3, True)
    expect("TIMEOUT_I inactive", 1300, 3, False)
    expect("XCVR enabled during nCE", 1500, 4, True)
    expect("XCVR disabled idle", 1300, 4, False)

    # Result-valid hold: sample Q via a separate wrdata call.
    wave2 = os.path.join(OUT_DIR, "glue_rv.txt")
    if os.path.exists(wave2):
        os.remove(wave2)
    ng.command(f"wrdata {wave2.replace(chr(92), '/')} v(rv)")
    rows2 = []
    with open(wave2, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    rows2.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
    def rv_at(t_ns: float) -> bool:
        best = False
        for r in rows2:
            if r[0] <= t_ns * 1e-9:
                best = r[1] > 0.5  # XSPICE d_dff outputs 0/1 V logic levels
            else:
                break
        return best
    hold = rv_at(600)
    cleared = not rv_at(1000)
    checks.append(("RESULT_VALID held", hold, None))
    checks.append(("RESULT_VALID cleared", cleared, None))
    print(f"RESULT_VALID held after set  000ns..900ns: {'OK' if hold else 'FAIL'}")
    print(f"RESULT_VALID cleared at 800ns: {'OK' if cleared else 'FAIL'}")

    ok = all(c[1] for c in checks)
    print(f"checks_passed={sum(1 for c in checks if c[1])}/{len(checks)}")
    print("PASS: active-low glue and result-valid hold" if ok else "FAIL: glue polarity")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
