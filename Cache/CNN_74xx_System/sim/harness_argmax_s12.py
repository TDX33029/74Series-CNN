"""Harness for the S06/S04 four-byte Argmax read transaction.

Two independent checks:

1. Structural: parse output/top.net and confirm the new nets really connect
   S06 (byte counter / address output), S12B (byte lanes and MEM_ACK), S04
   (Argmax address buffers) and S11 (Argmax master / map ROM A7).
2. Behavioral: cycle model of the S06 FSM, the S02 read transaction, the S12B
   four-lane latch and the class/byte counters.  It verifies that every class
   issues SCORE_ADDR = class*4+byte, that SCORE_RD is high exactly for the
   four S02 transactions, that the four latches assemble the little-endian
   word, and that the signed argmax result is correct (including ties and
   negative scores).

Run:
    python sim/harness_argmax_s12.py [output/top.net]
"""
from __future__ import annotations

import re
import sys


def load_nets(path: str) -> dict[str, list[tuple[str, str, str]]]:
    text = open(path, encoding="utf-8").read()
    nets: dict[str, list[tuple[str, str, str]]] = {}
    for block in re.split(r"\n\t\t\(net\n", text)[1:]:
        m = re.search(r'\(name "([^"]+)"\)', block)
        if not m:
            continue
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', block)
        nets.setdefault(m.group(1), []).extend((r, p, "") for r, p in nodes)
    return nets


def structural(nets: dict[str, list[tuple[str, str, str]]]) -> int:
    checks = 0

    def has(net: str, ref: str, pin: str) -> bool:
        return any(r == ref and p == pin for r, p, _ in nets.get(net, []))

    def pins(net: str) -> set[tuple[str, str]]:
        return {(r, p) for r, p, _ in nets.get(net, [])}

    # Address low bits come from the S06 541 (U6038) and go to the S12B decoder and
    # S04 Argmax buffers (U4050/U4051).
    for bit, pin in enumerate(("18", "17", "16", "15", "14", "13")):
        net = f"SCORE_ADDR{bit}"
        assert has(net, "U6038", pin), (net, "S06 output", pins(net))
    for bit in range(6):
        assert has(f"SCORE_ADDR{bit}", "U4049", str(2 + bit)), f"SCORE_ADDR{bit} S04 pin"

    # S12B latch clocks are qualified by MEM_ACK, not SCORE_RD.
    assert has("MEM_ACK", "U13205", "6"), "S12B 74HC238 E3 is not MEM_ACK"
    assert has("MEM_ACK", "U6042", "10"), "S06 D_BYTE_DONE is not MEM_ACK"
    assert has("SCORE_DATA0", "U13201", "19"), "S12B lane0 Q output missing"
    assert has("SCORE_DATA31", "U13204", "12"), "S12B lane3 Q output missing"

    # S06 byte counter and hold logic.
    assert has("/B10_S06_Argmax/BYTE0", "U6039", "14"), "byte counter Q0 missing"
    assert has("/B10_S06_Argmax/BYTE1", "U6039", "13"), "byte counter Q1 missing"
    assert has("/B10_S06_Argmax/BYTE0", "U6038", "2"), "SCORE_ADDR0 not from BYTE0"
    assert has("/B10_S06_Argmax/BYTE1", "U6038", "3"), "SCORE_ADDR1 not from BYTE1"
    assert has("/B10_S06_Argmax/WT_HOLD", "U6045", "3"), "WT_HOLD gate missing"
    assert has("/B10_S06_Argmax/WT_HOLD", "U6043", "2"), "D_WT does not use WT_HOLD"
    assert has("/B10_S06_Argmax/D_BYTE_DONE", "U6043", "6"), "D_BYTE_DONE OR missing"
    assert has("/B10_S06_Argmax/BD_HOLD", "U6042", "11"), "BD_HOLD gate missing"

    # S11 Argmax master: active-low busy on 74HC148 I3, MASTER2 to ROM A7.
    assert has("ARGMAX_BUSY_N", "U12001", "13"), "S11 148 I3 not Argmax"
    assert has("/B11_S11_BusFabric/MASTER2", "U12005", "3"), "S11 map A7 not MASTER2"
    assert has("SCORE_RD", "U12010", "5"), "S11 REQ merge missing SCORE_RD"

    # S04 Argmax buffers are enabled by ARGMAX_BUSY_N and drive ADDR.
    for ref in ("U4049", "U4050"):
        assert has("ARGMAX_BUSY_N", ref, "1"), f"{ref} G1 not ARGMAX_BUSY_N"
        assert has("ARGMAX_BUSY_N", ref, "19"), f"{ref} G2 not ARGMAX_BUSY_N"
    assert has("ADDR0", "U4049", "18"), "S04 Argmax buffer does not drive ADDR0"

    checks += 32
    print(f"PASS: structural Argmax/S12B/S04/S11 connections ({checks} checks)")
    return checks


class S02:
    """One-cycle-accurate enough read transaction: ACK at t=3, DONE at t=5."""

    def __init__(self, data_for):
        self.data_for = data_for
        self.t = -1
        self.ack = 0
        self.done = 0
        self.data = 0
        self.req_prev = 0

    def step(self, req: int, byte_addr: int) -> tuple[int, int, int]:
        # A rising REQ when idle starts a transaction; REQ must fall before
        # another one can start (S06 drops it in BYDONE).
        rising = req and not self.req_prev
        self.req_prev = req
        self.ack = 0
        self.done = 0
        if self.t < 0 and rising:
            self.t = 0
        if self.t >= 0:
            if self.t == 3:
                self.ack = 1
                self.data = self.data_for(byte_addr)
                self.t = 4
            elif self.t == 5:
                self.done = 1
                self.t = -1
            else:
                self.t += 1
        return self.ack, self.done, self.data


def signed32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def run_vector(scores: list[int], verbose: bool = False) -> int:
    assert len(scores) == 10
    # S06 state starts at IDLE (all state bits zero).
    st = dict(S_INIT=0, S_RD=0, S_WT=0, S_LD0=0, S_NEXT=0, S_CMP=0,
              S_DONE=0, S_WAIT=0, S_BYTE_DONE=0, S_BYTE_NEXT=0)
    klass = 0
    byte = 0
    first = 0
    latches = [0, 0, 0, 0]
    score_regs = 0
    maxv = 0
    maxi = 0
    result = 0
    result_valid = 0
    start = 1
    addrs: list[int] = []
    ack_count = 0
    done_count = 0

    def word_bytes(c, b):
        return (scores[c] >> (8 * b)) & 0xFF

    s02 = S02(lambda a: word_bytes(a // 4, a % 4))

    for cyc in range(5000):
        cur = st
        eq9 = klass == 9
        score_rd = cur["S_RD"] or cur["S_WT"]
        byte3 = (byte & 3) == 3
        byte_clr = cur["S_INIT"] or cur["S_LD0"] or cur["S_NEXT"]
        byte_done_p = cur["S_BYTE_DONE"] and s02.done
        byte_inc = byte_done_p and not byte3
        byte_last = byte_done_p and byte3
        d_rda = cur["S_NEXT"] and not eq9
        d_rd = cur["S_INIT"] or cur["S_BYTE_NEXT"] or d_rda
        d_wt = cur["S_RD"] or (cur["S_WT"] and not s02.ack)
        d_byte_done = ((cur["S_WT"] and s02.ack)
                       or (cur["S_BYTE_DONE"] and not s02.done))
        d_init = start and not any(st.values())
        d_next = cur["S_LD0"] or cur["S_CMP"]
        d_done = cur["S_NEXT"] and eq9
        d_wait = cur["S_DONE"] or (cur["S_WAIT"] and start)
        d_ld0 = byte_last and first
        d_cmp = byte_last and not first

        # S02 sees SCORE_RD and the byte address class*4+byte.
        s02.step(1 if score_rd else 0, klass * 4 + byte)
        if cur["S_RD"]:
            addrs.append(klass * 4 + byte)
        if s02.ack:
            ack_count += 1
            lane = byte
            latches[lane] = s02.data
        if s02.done:
            done_count += 1

        # Score registers capture the assembled word every CLK.
        score_regs = sum(latches[i] << (8 * i) for i in range(4))

        if cur["S_LD0"]:
            maxv, maxi = score_regs, klass
            first = 0
        if cur["S_CMP"] and signed32(score_regs) > signed32(maxv):
            maxv, maxi = score_regs, klass
        if cur["S_DONE"]:
            result, result_valid = maxi, 1
        if cur["S_WAIT"] and not start:
            break

        # State update (74HCT273 / 74HCT273 pair).
        st = dict(
            S_INIT=d_init, S_RD=d_rd, S_WT=d_wt, S_LD0=d_ld0,
            S_NEXT=d_next, S_CMP=d_cmp, S_DONE=d_done, S_WAIT=d_wait,
            S_BYTE_DONE=d_byte_done, S_BYTE_NEXT=byte_inc,
        )
        # Async-ish FIRST set/clear and counters (the 74HC161 sees the
        # current S_NEXT/BYTE_INC level before the state edge).
        if cur["S_INIT"]:
            first = 1
        if cur["S_LD0"]:
            first = 0
        if byte_clr:
            byte = 0
        elif byte_inc:
            byte = (byte + 1) & 3
        if cur["S_NEXT"]:
            klass = (klass + 1) & 0xF
        start = 0  # one-cycle START pulse
    else:
        raise AssertionError("FSM did not finish")

    if verbose:
        print(f"  result={result} valid={result_valid} addrs={addrs}")
    assert result_valid == 1, "RESULT_VALID not set"
    assert len(addrs) == 40, f"expected 40 byte reads, got {len(addrs)}: {addrs}"
    assert addrs == [4 * c + b for c in range(10) for b in range(4)], addrs
    assert ack_count == 40 and done_count == 40, (ack_count, done_count)
    expected = max(range(10), key=lambda i: (signed32(scores[i]), -i))
    assert result == expected, (result, expected)
    return result


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "output/top.net"
    nets = load_nets(path)
    structural(nets)

    vectors = [
        ([0x00000000, 0x00000001, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000,
          0x00000010, 0xFFFFFFFE, 0x12345678, 0x00000002, 0x00000003], 3),
        ([0xFFFFFFF6, 0xFFFFFFEC, 0xFFFFFFFD, 0xFFFFFF00, 0xFFFFFE00,
          0xFFFFFFF0, 0xFFFFFFFB, 0xFFFFFFC0, 0xFFFFFFD0, 0xFFFFFFE0], 2),
        ([0x00000005, 0x00000001, 0x00000009, 0x00000002, 0x00000003,
          0x00000009, 0x00000004, 0x00000006, 0x00000007, 0x00000008], 2),
    ]
    for scores, expected in vectors:
        got = run_vector(scores)
        assert got == expected, (got, expected)
        print(f"PASS: 4-byte address sequence + S12B latches, argmax={got}")
    print("PASS: S06/S04/S12B Argmax four-byte transaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
