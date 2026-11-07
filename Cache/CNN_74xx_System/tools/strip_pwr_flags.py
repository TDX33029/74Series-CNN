"""Remove per-sheet PWR_FLAG instances so the hierarchy has one driver per rail.

Every module sheet added its own PWR_FLAG for +5V and GND.  In a hierarchy the
power nets are global, so multiple power-output pins on the same net trip ERC.
The root sheet (S00) carries the single pair of PWR_FLAGs; this script removes
the child instances while leaving the embedded symbol definition intact.

The wires that used to join a flag to its power symbol are left in place; they
become harmless dangling wire warnings, not power-output conflicts.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

sys.path.insert(0, HERE)
from build_boards import BOARDS  # noqa: E402

SHEETS = [f for _b in BOARDS for f in _b[3]] + ["S_LUT_Mult_1.kicad_sch"]


def strip(text: str) -> tuple[str, int]:
    removed = 0
    i = 0
    while True:
        idx = text.find("\t(symbol\n", i)
        if idx < 0:
            break
        depth = 0
        j = idx
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        block = text[idx:j + 1]
        if '(lib_id "power:PWR_FLAG")' in block:
            text = text[:idx] + text[j + 1:]
            removed += 1
            i = idx
        else:
            i = j + 1
    return text, removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dir", default=PROJECT_DIR)
    args = ap.parse_args()
    total = 0
    for name in SHEETS:
        path = os.path.join(args.dir, name)
        if not os.path.exists(path):
            print(f"  {name}: missing, skipped")
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new, n = strip(text)
        print(f"  {name}: removed {n} PWR_FLAG instance(s)")
        total += n
        if not args.dry_run and n:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
    print(("DRY RUN: " if args.dry_run else "") + f"{total} instance(s) removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
