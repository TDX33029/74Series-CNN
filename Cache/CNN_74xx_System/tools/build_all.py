"""Rebuild the complete 12-board Option-A project.

Order matters:

  0. image generators          LUT + S01/S07/S08/S09 microcode ROMs
  1. module builders           S01..S17 (S05/S09/S17 land in templates/)
  2. make_variants.py          six fixed per-layer engine sheets
  3. build_boards.py           12 connector sheets + manifests + pinouts
  4. renumber_refs.py          one reference block per sheet
  5. build_top.py              12-board root hierarchy + connection matrix

Run from the project root:
    python tools/build_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))

MODULES = [
    "build_supervisor.py",
    "build_timing.py",
    "build_memories.py",
    "build_s12_split.py",
    "build_argmax.py",
    "build_conv1.py",
    "build_conv2.py",
    "build_fc.py",
    "build_requant_simple.py",
    "build_bus.py",
    "build_select.py",
    "build_top_io.py",
    "build_pool.py",
]

# Microcode / LUT images are inputs to the 27C512 models; regenerate them
# before the sheets so the ROM wiring and the images never drift apart.
IMAGES = [
    "gen_lut.py",
    "gen_engine_microcode.py",
    "gen_supervisor_microcode.py",
]

STEPS = IMAGES + MODULES + [
    "make_variants.py",
    "strip_pwr_flags.py",
    "build_boards.py",
    "renumber_refs.py",
    "build_top.py",
]


def main() -> int:
    for script in STEPS:
        print(f"\n=== {script} ===")
        r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           cwd=PROJECT_DIR)
        if r.returncode:
            print(f"FAILED: {script} (exit {r.returncode})")
            return r.returncode
    print("\nall sheets rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
