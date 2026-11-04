"""Promote Conv1/Conv2 internal DONE/BUSY labels to global status outputs.

S07/S08 generate C1_DONE_I / C1_BUSY / C2_DONE_I / C2_BUSY as local labels at
the engine output.  The supervisor expects C1_DONE/P1_DONE/... so these nets
must be visible across the hierarchy.  The label name itself changes (there is
only one occurrence), and the S-expression kind becomes global_label.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

PATCHES = {
    "S07_Conv1.kicad_sch": [("C1_DONE_I", "C1_DONE"), ("C1_BUSY_I", "C1_BUSY")],
    "S08_Conv2.kicad_sch": [("C2_DONE_I", "C2_DONE"), ("C2_BUSY_I", "C2_BUSY")],
}


def main() -> int:
    changed = 0
    for name, pairs in PATCHES.items():
        path = os.path.join(PROJECT_DIR, name)
        if not os.path.exists(path):
            print(f"  {name}: missing, skipped")
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for old, new in pairs:
            pat = re.compile(r'\(label "' + re.escape(old) + r'"')
            if pat.search(text):
                text = pat.sub(
                    f'(global_label "{new}"\n\t\t(shape output)', text, count=1
                )
                changed += 1
                print(f"  {name}: {old} -> global {new}")
            elif f'(global_label "{new}"' in text:
                print(f"  {name}: {new} already global")
            else:
                print(f"  {name}: label {old} not found")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(f"{changed} label(s) promoted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
