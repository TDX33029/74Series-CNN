"""Run every SPICE/functional testbench through KiCad's bundled ngspice.

Each check is a Python driver that loads a netlist through ngspice.dll, runs
it, samples wrdata output and asserts PASS.  Transcripts are collected under
sim/<name>.log (or output/sim for the drivers that write their own log).
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PY = sys.executable

CHECKS = [
    ("tools/gen_lut.py", [], "lut_contents"),
    ("sim/gen_lut_tb.py", [], "lut_spice"),
    ("sim/gen_glue_tb.py", [], "glue"),
    ("sim/gen_supervisor_tb.py", [], "supervisor"),
    ("sim/gen_timing_tb.py", [], "timing"),
    ("sim/gen_mem_decode_tb.py", [], "mem_decode"),
    ("sim/gen_pool_tb.py", [], "pool"),
    ("sim/gen_argmax_tb.py", [], "argmax"),
    ("sim/harness_argmax_s12.py", ["output/top.net"], "argmax_s12"),
    # S07/S08/S09 A/B split, hold-enabled pipeline and 4-MAC grouping.
    ("sim/harness_ab_path.py", ["output/top.net"], "ab_path"),
    # This driver runs CONV1, CONV2 and FC1/FC2 in sequence and writes
    # output/sim/{conv1,conv2,fc}_engine.log.
    ("sim/gen_engine_tb.py", [], "conv_fc_engines"),
    # V2 simple requant cores S13/S15/S17: golden arithmetic, handshake
    # models, no-parameter-port structure, top netlist and BOM checks.
    ("sim/gen_requant_simple_tb.py", [], "requant_simple"),
    # 12-board backplane: connector pins, power map, net->board matrix.
    ("sim/check_backplane.py", [], "backplane"),
]


def run_one(script: str, args: list[str], label: str) -> bool:
    print(f"== {label} ==")
    proc = subprocess.run(
        [PY, script] + args,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout + proc.stderr
    log = os.path.join(HERE, label + ".log")
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    tail = [ln for ln in out.strip().splitlines() if ln.strip()]
    print("\n".join(tail[-10:]))
    passed = "PASS" in out and "FAIL" not in out and proc.returncode == 0
    print(f"-> {'PASS' if passed else 'FAIL'} ({log})")
    return passed


def main() -> int:
    results = []
    for script, args, label in CHECKS:
        path = os.path.join(PROJECT_DIR, script)
        if not os.path.exists(path):
            print(f"== {label} == missing {script}, skipped")
            results.append((label, False))
            continue
        results.append((label, run_one(script, args, label)))
    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
