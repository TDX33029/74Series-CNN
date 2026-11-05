#!/usr/bin/env python3
"""Static top-level connectivity audit for the 74-series CNN netlist.

This is deliberately independent of the SPICE models: it reads a KiCad netlist
and looks for the failure modes that module-level testbenches cannot see:
single-node module-boundary nets, engine address/chip-select nets that never
reach S04, and multiple 74HCT541 outputs driving the same status net.

Usage:
    python tools/audit_top_connectivity.py output/visual_fix/after/top.net
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 74HCT541 Y0..Y7 output pin numbers (A0..A7 are 2..9, Y0..Y7 are 18..11).
HCT541_OUTPUT_PINS = {str(p) for p in range(11, 19)}


def parse_nets(text: str) -> dict[str, list[tuple[str, str]]]:
    nets: dict[str, list[tuple[str, str]]] = {}
    for name, body in re.findall(
        r'\(net\s+\(code[^)]*\)\s+\(name\s+"([^"]+)"\)(.*?)(?=\n\s*\(net\s+\(code|\Z)',
        text,
        re.S,
    ):
        nodes = re.findall(
            r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', body
        )
        nets[name] = nodes
    return nets


def parse_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for ref, value in re.findall(
        r'\(comp\s+\(ref\s+"([^"]+)"\)\s+\(value\s+"([^"]*)"\)', text
    ):
        values[ref] = value
    return values


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/visual_fix/after/top.net")
    text = path.read_text(encoding="utf-8", errors="replace")
    nets = parse_nets(text)
    values = parse_values(text)

    prefixes = (
        "P1_START", "P2_START", "ARGMAX_START",
        "C1_ADDR", "C2_ADDR", "FC_ADDR",
        "C1_MEM_nCE", "C2_MEM_nCE", "FC_MEM_nCE",
        "C1_WAIT_READ", "C1_WAIT_WRITE", "C2_WAIT_READ", "C2_WAIT_WRITE",
        "FC_WAIT_READ", "FC_WAIT_WRITE",
        "C1_ACC", "C1_B_DATA", "C1_M", "C1_SHIFT", "C1_ZP_X", "C1_ZP_W",
        "C1_ZP_OUT", "C1_N_MACS", "C2_ACC", "C2_B_DATA", "C2_M", "C2_SHIFT",
        "C2_ZP_X", "C2_ZP_W", "C2_ZP_OUT", "C2_N_MACS", "FC_ACC", "FC_B_DATA",
        "FC_M", "FC_SHIFT", "FC_ZP_X", "FC_ZP_W", "FC_ZP_OUT", "FC_N_MACS",
        "MEM_DATA", "MEM_ACK", "MEM_DONE", "MEM_BUSY",
        "POOL_BUSY", "ARGMAX_BUSY", "ARGMAX_RESULT_VALID",
    )
    single: list[dict[str, object]] = []
    unexpanded_bus: list[dict[str, object]] = []
    bus_re = re.compile(r"^(.*)\[(\d+):(\d+)\]$")
    leaf_names = {name.rsplit("/", 1)[-1] for name in nets}
    for name, nodes in sorted(nets.items()):
        leaf = name.rsplit("/", 1)[-1]
        if not leaf.startswith(prefixes):
            continue
        if len(nodes) == 1:
            m = bus_re.match(leaf)
            if m:
                base, hi, lo = m.group(1), int(m.group(2)), int(m.group(3))
                members = [f"{base}{i}" for i in range(lo, hi + 1)]
                if any(member in leaf_names for member in members):
                    # Bus pin with real bit members: the bus net itself is a
                    # single pin, but the members carry the connectivity.
                    continue
                unexpanded_bus.append({"net": name, "nodes": nodes})
            else:
                single.append({"net": name, "nodes": nodes})

    done = nets.get("DONE", [])
    done_541_outputs = [
        (ref, pin, values.get(ref, ""))
        for ref, pin in done
        if pin in HCT541_OUTPUT_PINS and "541" in values.get(ref, "")
    ]

    report = {
        "netlist": str(path),
        "net_count": len(nets),
        "single_node_module_nets": single,
        "unexpanded_bus_nets": unexpanded_bus,
        "done_nodes": done,
        "done_74hct541_outputs": done_541_outputs,
        "start_nodes": nets.get("START", []),
        "checks": {
            "single_node_module_nets": len(single),
            "unexpanded_bus_nets": len(unexpanded_bus),
            "done_541_output_count": len(done_541_outputs),
            "done_multidriver": len(done_541_outputs) > 1,
        },
    }
    out = path.with_suffix(".audit.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["checks"], ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return 1 if report["checks"]["done_multidriver"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
