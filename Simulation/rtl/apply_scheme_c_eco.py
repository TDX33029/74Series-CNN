"""Scheme-C ECO: make the 4-product sum tree truly signed.

The 74HC283 chain adds the four 16-bit LUT products as unsigned numbers, so a
negative product is treated as a large positive value.  Two sign bits are
missing per stage:

  * S12_16 (17th bit of P1+P2) must be  P1_15 XOR P2_15 XOR carry15
    (a 74HC283's C4 only gives the carry, i.e. the majority of the three).
  * S34_16 likewise from P3/P4.
  * PSUM17 = S12_16 + S34_16 + carry16  -- already wired by the netlist patch
    (U7097/U8098/U9083/U9283 A2/B2).

Hardware cost: one 74HC86 per engine board (2 XOR gates for S12_16, 2 for
S34_16).

Run after gen_rtl.py; the edit is idempotent.
"""
from __future__ import annotations

import re
import sys

RTL = r"D:/Document/tempPrj/74Series-CNN/Simulation/rtl/cnn74_top.v"

# engine -> (prefix, S12 chip, S34 chip)
ENG = [
    ("_B04_S07_Conv1_C1_", "U7088", "U7092"),
    ("_B06_S08_Conv2_C2_", "U8089", "U8093"),
    ("_B08_S09_FC1_FC_",   "U9074", "U9078"),
    ("_B09_S09_FC2_FC_",   "U9274", "U9278"),
]

text = open(RTL, encoding="utf-8").read()
if "SCHEME_C_ECO" in text:
    print("already applied")
    sys.exit(0)

lines = text.splitlines(keepends=True)
out = []
applied = 0
for ln in lines:
    m = re.match(r"(\s*)m_74xx_74HC283 (U\d+) \(", ln)
    if m and any(m.group(2) == s12 or m.group(2) == s34 for _, s12, s34 in ENG):
        chip = m.group(2)
        pre = next(p for p, s12, s34 in ENG if chip in (s12, s34))
        stage = "S12" if chip == next(s for p, s, _ in ENG if p == pre) else "S34"
        src = pre + stage + "_16"                 # currently driven by C4
        c4 = pre + stage + "_C4"                  # new name for the carry
        b_hi = (pre + "P1_15", pre + "P2_15") if stage == "S12" else (pre + "P3_15", pre + "P4_15")
        ln = ln.replace(f".p9({src})", f".p9({c4})")
        out.append(f"  // SCHEME_C_ECO {chip}: {stage}_16 = sign bit (XOR3)\n")
        out.append(f"  wire {c4};\n")
        out.append(f"  assign {src} = {b_hi[0]} ^ {b_hi[1]} ^ {c4};\n")
        applied += 1
    out.append(ln)

open(RTL, "w", encoding="utf-8", newline="\n").write("".join(out))
print(f"applied {applied} XOR3 sign-bit ECOs")
