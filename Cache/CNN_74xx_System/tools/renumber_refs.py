"""Give every sheet a unique reference-designator block.

KiCad references are project-wide.  Each module was drawn independently and
starts at U1/C1, which makes the hierarchy merge different chips with the same
reference and produces ``different_unit_net`` errors.  This script rewrites the
Reference properties and instance references in each sheet:

    S01  U5  -> U1005      S07  U5  -> U7005
    S02  C1  -> C2001      S10  J1  -> J10001
    ...

Power symbols (#PWR...) and unannotated references (U?) are left alone.  The
script is intentionally not idempotent; run it once after the last module
build.  Use --dry-run first.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

# file -> numeric block for the first reference
BLOCKS = {
    "S01_Supervisor.kicad_sch": 1000,
    "S02_Timing.kicad_sch": 2000,
    "S04_Memories.kicad_sch": 4000,
    "S05_Pool1.kicad_sch": 5000,
    "S05_Pool2.kicad_sch": 5100,
    "S06_Argmax.kicad_sch": 6000,
    "S07_Conv1.kicad_sch": 7000,
    "S08_Conv2.kicad_sch": 8000,
    "S09_FC1.kicad_sch": 9000,
    "S09_FC2.kicad_sch": 9200,
    "S10_Top_IO.kicad_sch": 10000,
    "S11_BusFabric.kicad_sch": 12000,
    "S11A_EngineMerge.kicad_sch": 12500,
    "S12A_PoolLatch1.kicad_sch": 13000,
    "S12A_PoolLatch2.kicad_sch": 13100,
    "S12B_ScoreLatch.kicad_sch": 13200,
    "S13_Requant_C1.kicad_sch": 14000,
    "S15_Requant_C2.kicad_sch": 15000,
    "S17_FC1.kicad_sch": 16000,
    "S17_FC2.kicad_sch": 16200,
    "S_LUT_Mult_1.kicad_sch": 11000,
    "B01_Conn.kicad_sch": 20000,
    "B02_Conn.kicad_sch": 20100,
    "B03_Conn.kicad_sch": 20200,
    "B04_Conn.kicad_sch": 20300,
    "B05_Conn.kicad_sch": 20400,
    "B06_Conn.kicad_sch": 20500,
    "B07_Conn.kicad_sch": 20600,
    "B08_Conn.kicad_sch": 20700,
    "B09_Conn.kicad_sch": 20800,
    "B10_Conn.kicad_sch": 20900,
    "B11_Conn.kicad_sch": 21000,
    "B12_Conn.kicad_sch": 21100,
}

REF_PROP = re.compile(r'\(property "Reference" "([A-Za-z]+)(\d+)"')
REF_INST = re.compile(r'\(reference "([A-Za-z]+)(\d+)"')


def renumber(path: str, block: int, dry_run: bool) -> int:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    refs = set()
    for m in REF_PROP.finditer(text):
        refs.add(m.group(1) + m.group(2))
    for m in REF_INST.finditer(text):
        refs.add(m.group(1) + m.group(2))
    # Idempotent, collision-free renumbering: keep references already in the
    # sheet's block, and move only new low references above the current maximum.
    by_prefix = {}
    for ref in refs:
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref)
        if not m:
            continue
        prefix, num = m.group(1), int(m.group(2))
        if prefix.startswith("#"):
            continue
        by_prefix.setdefault(prefix, []).append(num)
    mapping = {}
    for prefix, nums in by_prefix.items():
        high = [n for n in nums if n >= block]
        low = sorted(n for n in nums if n < block)
        if not low:
            continue
        next_num = (max(high) if high else block) + 1
        for n in low:
            mapping[f"{prefix}{n}"] = f"{prefix}{next_num}"
            next_num += 1
    if not mapping:
        print(f"  {os.path.basename(path)}: no references found")
        return 0
    # Replace only the two reference contexts, never labels or notes.
    def repl_prop(m):
        ref = m.group(1) + m.group(2)
        return f'(property "Reference" "{mapping.get(ref, ref)}"'
    def repl_inst(m):
        ref = m.group(1) + m.group(2)
        return f'(reference "{mapping.get(ref, ref)}"'
    new = REF_PROP.sub(repl_prop, text)
    new = REF_INST.sub(repl_inst, new)
    changed = sum(1 for a, b in zip(text.splitlines(), new.splitlines()) if a != b)
    print(f"  {os.path.basename(path)}: block {block}, {len(mapping)} refs, {changed} lines")
    if not dry_run:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
    return len(mapping)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dir", default=PROJECT_DIR)
    args = ap.parse_args()
    total = 0
    for name, block in BLOCKS.items():
        path = os.path.join(args.dir, name)
        if not os.path.exists(path):
            print(f"  {name}: missing, skipped")
            continue
        total += renumber(path, block, args.dry_run)
    print(("DRY RUN: " if args.dry_run else "") + f"{total} references renumbered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
