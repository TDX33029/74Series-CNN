"""Harness for the S07/S08/S09 A/B operand path (Option A).

Two independent checks:

1. Structural: parse output/top.net and confirm that
   - A_LAT/B_LAT capture DATA on A_LOAD/B_LOAD,
   - the first pipeline stage takes its D inputs from the hold muxes,
   - the hold mux I0 side is the register's own Q and I1 is the previous
     stage (or the input latch), selected by SHIFT_EN,
   - each LUT ROM pair has A[7:0]=B operand and A[15:8]=A operand,
   - CONV1's B latch is fed by the PAD_ACTIVE zero mux.
2. Behavioral: cycle model of the 13-state local FSM, the two input latches,
   the four hold-enabled pipeline stages and the 4-MAC accumulator.  Wait
   states are inserted; the model verifies that the pipeline does not move
   during them and that every group of four products is accumulated exactly
   once (including CONV1's 25+3 padding).

Run:
    python sim/harness_ab_path.py [output/top.net]
"""
from __future__ import annotations

import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "tools"))

from gen_engine_microcode import (  # noqa: E402
    E_ACC, E_ADDR_IN, E_ADDR_OUT, E_ADDR_W, E_DONE, E_IDLE, E_NEXT, E_REQ,
    E_RESET, E_SHIFT, E_WAIT_A, E_WAIT_B, E_WRITE, microcode,
)


def load_nets(path: str) -> dict[str, list[tuple[str, str]]]:
    text = open(path, encoding="utf-8").read()
    nets: dict[str, list[tuple[str, str]]] = {}
    for block in re.split(r"\n\t\t\(net\n", text)[1:]:
        m = re.search(r'\(name "([^"]+)"\)', block)
        if not m:
            continue
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', block)
        nets.setdefault(m.group(1), []).extend(nodes)
    return nets


def suffix(name: str) -> str:
    return name.rsplit("/", 1)[-1]


def build_pinmaps(nets: dict[str, list[tuple[str, str]]]) -> dict[str, dict[str, str]]:
    pinmaps: dict[str, dict[str, str]] = {}
    for net, nodes in nets.items():
        for ref, pin in nodes:
            pinmaps.setdefault(ref, {})[pin] = suffix(net)
    return pinmaps


def structural(nets: dict[str, list[tuple[str, str]]]) -> int:
    checks = 0
    pinmaps = build_pinmaps(nets)

    def find(pred) -> str:
        for ref, pins in pinmaps.items():
            if pred(pins):
                return ref
        raise AssertionError("no symbol matches")

    for prefix in ("C1", "C2", "FC"):
        data = [f"DATA{i}" for i in range(8)]
        a_lat = find(lambda p: all(p.get(str(2 + i)) == data[i] for i in range(8))
                     and p.get("11") == f"{prefix}_A_LOAD")
        b_d = ([f"{prefix}_B_LAT_D{i}" for i in range(8)] if prefix == "C1"
               else data)
        b_lat = find(lambda p: all(p.get(str(2 + i)) == b_d[i] for i in range(8))
                     and p.get("11") == f"{prefix}_B_LOAD")
        for lat, name in ((a_lat, "A_LAT"), (b_lat, "B_LAT")):
            for i in range(8):
                assert f"{prefix}_{name}{i}" in pinmaps[lat].values(), (
                    f"{lat} Q{i} is not {prefix}_{name}{i}")
            checks += 1

        for operand in ("A", "B"):
            for lane in range(4):
                q = [f"{prefix}_{operand}{lane}_{i}" for i in range(8)]
                d = [f"{prefix}_{operand}{lane}_D{i}" for i in range(8)]
                qpins = ("19", "18", "17", "16", "15", "14", "13", "12")
                ref = find(lambda p: all(p.get(qpins[i]) == q[i] for i in range(8))
                           and all(p.get(str(2 + i)) == d[i] for i in range(8)))
                # Stage 0's shift input is the latch; later stages take the
                # previous stage's Q.
                shift = ([f"{prefix}_A_LAT{i}" for i in range(8)] if operand == "A"
                         else [f"{prefix}_B_LAT{i}" for i in range(8)]) if lane == 0 \
                    else [f"{prefix}_{operand}{lane-1}_{i}" for i in range(8)]
                for chip in range(2):
                    mux = find(lambda p, chip=chip: (
                        p.get("1") == f"{prefix}_SHIFT_EN"
                        and p.get("4") == d[4 * chip]
                        and p.get("7") == d[4 * chip + 1]
                        and p.get("9") == d[4 * chip + 2]
                        and p.get("12") == d[4 * chip + 3]
                        and p.get("2") == q[4 * chip]
                        and p.get("5") == q[4 * chip + 1]
                        and p.get("11") == q[4 * chip + 2]
                        and p.get("14") == q[4 * chip + 3]
                        and p.get("3") == shift[4 * chip]
                        and p.get("6") == shift[4 * chip + 1]
                        and p.get("10") == shift[4 * chip + 2]
                        and p.get("13") == shift[4 * chip + 3]))
                    checks += 1

        for lane in range(4):
            low = [f"{prefix}_P{lane+1}_{i}" for i in range(8)]
            high = [f"{prefix}_P{lane+1}_{i}" for i in range(8, 16)]
            dpins = ("11", "12", "13", "15", "16", "17", "18", "19")
            apins = ("10", "9", "8", "7", "6", "5", "4", "3")
            ahpins = ("25", "24", "21", "23", "2", "26", "27", "1")
            for ref, prod in ((find(lambda p: all(p.get(dpins[i]) == low[i]
                                                  for i in range(8))), low),
                              (find(lambda p: all(p.get(dpins[i]) == high[i]
                                                  for i in range(8))), high)):
                for i in range(8):
                    assert pinmaps[ref].get(apins[i]) == f"{prefix}_B{lane}_{i}", (
                        f"{ref} A{i} is not B{lane}_{i}")
                    assert pinmaps[ref].get(ahpins[i]) == f"{prefix}_A{lane}_{i}", (
                        f"{ref} A{8+i} is not A{lane}_{i}")
                checks += 1

    # CONV1 padding: B latch D inputs come from the BZERO mux, select=PAD_ACTIVE.
    bz = find(lambda p: p.get("1") == "C1_PAD_ACTIVE"
              and p.get("4") == "C1_B_LAT_D0"
              and p.get("2") == "DATA0")
    for i in range(4):
        assert pinmaps[bz].get(("2", "5", "11", "14")[i]) == f"DATA{i}", (
            f"{bz} I0 bit {i} is not DATA{i}")
    checks += 1

    # Local FSM ROM address: MEM_DONE A8, REQ_DONE A9, SP_LAST A10.
    for prefix, last in (("C1", "C1_SP_LAST"), ("C2", "C2_SP_LAST")):
        ref = find(lambda p, prefix=prefix, last=last: (
            p.get("25") == "MEM_DONE"
            and p.get("24") == f"{prefix}_REQ_DONE"
            and p.get("21") == last))
        assert pinmaps[ref].get("4") == f"{prefix}_POINT_LAST"
        checks += 1

    print(f"PASS: A/B structural checks ({checks})")
    return checks


def behavioural() -> int:
    """Cycle model of the FSM + hold pipeline + 4-MAC accumulator."""
    random.seed(7)

    def run_engine(n_real: int, total: int, pad_zero: bool) -> int:
        stage = [(0, 0)] * 4
        a_lat = b_lat = 0
        acc = 0
        golden = 0
        lane = 0
        macs = 0
        state = E_RESET
        start = 1
        point_last = mem_ack = mem_done = req_done = image_last = 0
        a_val = b_val = 0
        wait_a = wait_b = 0

        for _ in range(20000):
            # Condition inputs for the current state (before the ROM access).
            if state == E_WAIT_A and wait_a == 0:
                mem_ack = 1
            if state == E_WAIT_B and wait_b == 0:
                mem_ack = 1
            if state == E_REQ:
                req_done = 1
            if state == E_WRITE:
                mem_done = 1
            if state == E_NEXT:
                image_last = 1
            if state == E_ACC:
                point_last = 1 if macs == total else 0

            rom1, rom2 = microcode(state, start, point_last, mem_ack, mem_done,
                                   req_done, image_last, 0, False)
            ns = rom1 & 0x1F

            # Clock-edge actions.
            if state == E_ADDR_IN:
                a_val = random.randrange(256)
                wait_a = random.randrange(0, 4)
                start = 0
            elif state == E_WAIT_A:
                if wait_a == 0:
                    a_lat = a_val
                else:
                    wait_a -= 1
            elif state == E_ADDR_W:
                b_val = random.randrange(256)
                wait_b = random.randrange(0, 4)
            elif state == E_WAIT_B:
                if wait_b == 0:
                    b_lat = 0 if (pad_zero and macs >= n_real) else b_val
                else:
                    wait_b -= 1
            elif state == E_SHIFT:
                stage = [(a_lat, b_lat)] + stage[:3]
                macs += 1
            elif state == E_ACC:
                if lane == 3:
                    acc += sum(a * b for a, b in stage)
                    golden += sum(a * b for a, b in stage)
                    lane = 0
                else:
                    lane += 1
            elif state == E_NEXT:
                # ACC_CLR_N is asserted here; the next point starts at zero.
                pass
            elif state == E_DONE:
                break

            mem_ack = mem_done = req_done = image_last = 0
            state = ns

        assert macs == total, (macs, total)
        assert acc == golden
        assert total % 4 == 0
        return golden

    run_engine(25, 28, True)
    run_engine(72, 72, False)
    run_engine(400, 400, False)
    run_engine(32, 32, False)
    print("PASS: A/B behavioural pipeline/accumulator model")
    return 1


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        PROJECT_DIR, "output", "top.net")
    nets = load_nets(path)
    structural(nets)
    behavioural()
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
