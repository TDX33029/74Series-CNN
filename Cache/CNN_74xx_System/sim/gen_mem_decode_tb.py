"""Address-decode verification for S04_Memories.

This is the Python model of the exact S04 chip-select network:

    MEM_SEL[4:0] --+--> 74HC138 x4 (one per MEM_SEL[4:3] group)
                   +--> 74HC688:  ADDR[23:16] == {000, MEM_SEL[4:0]}
    DEC_EN = ADDR_TAG_OK AND (LOAD_EN OR NOT MEM_nCE)

The script sweeps every MEM_SEL value, every mapped device window, mismatched
address tags and both normal/load modes, and asserts that at most one nCS can
be active.  Results are written to output/sim/mem_decode.log.

Run from the project root or from sim/:
    python sim/gen_mem_decode_tb.py
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT_DIR = os.path.join(PROJECT_DIR, "output", "sim")
LOG_PATH = os.path.join(OUT_DIR, "mem_decode.log")

# (index, reference, name, cs net, window size in bytes)
DEVICES = [
    (0, "U1",  "INPUT_SRAM",      "nCS_SRAM_INPUT",   8192),
    (1, "U2",  "CONV1_OUT_SRAM",  "nCS_SRAM_C1OUT",   8192),
    (2, "U3",  "POOL1_OUT_SRAM",  "nCS_SRAM_P1OUT",   8192),
    (3, "U4",  "CONV2_OUT_SRAM",  "nCS_SRAM_C2OUT",   8192),
    (4, "U5",  "POOL2_OUT_SRAM",  "nCS_SRAM_P2OUT",   8192),
    (5, "U6",  "FC1_OUT_SRAM",    "nCS_SRAM_FC1OUT",  8192),
    (6, "U7",  "FC2_LOGITS_SRAM", "nCS_SRAM_FC2LOG",  8192),
    (8, "U8",  "W_CONV1",         "nCS_W_CONV1",      32768),
    (9, "U9",  "W_CONV2",         "nCS_W_CONV2",      32768),
    (10, "U10", "W_FC1",          "nCS_W_FC1",        32768),
    (11, "U11", "W_FC2",          "nCS_W_FC2",        32768),
    # 12..15 (bias) and 16..19 (qparam) are reserved holes after the V2
    # requant: no device is fitted and no nCS is wired for those indices.
    (20, "U20", "LUT0_LO",        "nCS_LUT0_LO",      65536),
    (21, "U21", "LUT0_HI",        "nCS_LUT0_HI",      65536),
    (22, "U22", "LUT1_LO",        "nCS_LUT1_LO",      65536),
    (23, "U23", "LUT1_HI",        "nCS_LUT1_HI",      65536),
    (24, "U24", "LUT2_LO",        "nCS_LUT2_LO",      65536),
    (25, "U25", "LUT2_HI",        "nCS_LUT2_HI",      65536),
    (26, "U26", "LUT3_LO",        "nCS_LUT3_LO",      65536),
    (27, "U27", "LUT3_HI",        "nCS_LUT3_HI",      65536),
]
DEV_BY_INDEX = {d[0]: d for d in DEVICES}
UNMAPPED = [i for i in range(32) if i not in DEV_BY_INDEX]


def y138(a: int, e0_n: int, e1_n: int, e2: int) -> list[int]:
    """Return the eight active-low outputs of one 74HC138."""
    enabled = (e0_n == 0) and (e1_n == 0) and (e2 == 1)
    if not enabled:
        return [1] * 8
    out = [1] * 8
    out[a] = 0
    return out


def cs_outputs(mem_sel: int, addr: int, mem_nce: int, load_en: int) -> dict[str, int]:
    """Model S04 exactly: four 74HC138s + 74HC688 tag comparator."""
    msel3 = (mem_sel >> 3) & 1
    msel4 = (mem_sel >> 4) & 1
    low3 = mem_sel & 7

    # 74HC688: P = ADDR[23:16], R = {000, MEM_SEL[4:0]}
    addr_tag = (addr >> 16) & 0xFF
    addr_tag_ok_n = 0 if addr_tag == mem_sel else 1
    addr_tag_ok = 1 - addr_tag_ok_n

    # U34 gate 2 and U33 inverter: MEM_CE_OK = NOT(MEM_nCE AND NOT LOAD_EN)
    both_idle = 1 if (mem_nce == 1 and load_en == 0) else 0
    mem_ce_ok = 1 - both_idle

    # U34 gate 1
    dec_en = 1 if (addr_tag_ok == 1 and mem_ce_ok == 1) else 0

    groups = [
        y138(low3, msel4, msel3, dec_en),          # MEM_SEL[4:3] = 00
        y138(low3, msel4, 1 - msel3, dec_en),      # 01
        y138(low3, 1 - msel4, msel3, dec_en),      # 10
        y138(low3, 1 - msel4, 1 - msel3, dec_en),  # 11
    ]

    cs: dict[str, int] = {}
    # group 0: devices 0..6, Y7 unused
    for k in range(7):
        cs[DEV_BY_INDEX[k][3]] = groups[0][k]
    # group 1: devices 8..11 fitted, 12..15 reserved (decoder output is NC)
    for k in range(8):
        d = DEV_BY_INDEX.get(8 + k)
        if d:
            cs[d[3]] = groups[1][k]
    # group 2: 16..19 reserved, devices 20..23
    for k in range(8):
        d = DEV_BY_INDEX.get(16 + k)
        if d:
            cs[d[3]] = groups[2][k]
    # group 3: devices 24..27, Y4..Y7 unused
    for k in range(4):
        cs[DEV_BY_INDEX[24 + k][3]] = groups[3][k]
    return cs


def active(cs: dict[str, int]) -> list[str]:
    return [n for n, v in cs.items() if v == 0]


class Checker:
    def __init__(self) -> None:
        self.checks = 0
        self.failures = 0
        self.lines: list[str] = []

    def check(self, ok: bool, text: str) -> None:
        self.checks += 1
        if not ok:
            self.failures += 1
            self.lines.append(f"[FAIL] {text}")
        else:
            self.lines.append(f"[PASS] {text}")

    def finish(self) -> bool:
        return self.failures == 0


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    ck = Checker()
    ck.lines.append("S04 memory address-decode verification")
    ck.lines.append("model: 4x74HC138 (MEM_SEL[2:0]) + 74HC688 (ADDR[23:16]==MEM_SEL)")
    ck.lines.append("       DEC_EN = ADDR_TAG_OK & (LOAD_EN | ~MEM_nCE)")
    ck.lines.append(f"mapped devices: {len(DEVICES)}  unmapped MEM_SEL: {UNMAPPED}")
    ck.lines.append("")

    # 1. Every mapped device is selected by its own MEM_SEL and base address.
    for idx, ref, name, cs_net, size in DEVICES:
        base = idx << 16
        cs = cs_outputs(idx, base, mem_nce=0, load_en=0)
        act = active(cs)
        ok = act == [cs_net]
        ck.check(ok, f"device {idx:02d} {ref} {name:12s} base=0x{base:06X} "
                     f"size={size:5d} cs={cs_net} active={act}")
        # The whole 64 KB tag window stays selected (within-device aliasing is
        # a documented limitation for the 8K/32K parts).  All offsets below
        # stay inside the 64 KB window.
        for off in (0, 1, size - 1, 0xFFFF):
            cs = cs_outputs(idx, base + off, mem_nce=0, load_en=0)
            act = active(cs)
            ck.check(act == [cs_net],
                     f"  device {idx:02d} offset 0x{off:04X} unique active={act}")

    ck.lines.append("")

    # 2. Unmapped MEM_SEL values must never assert any of the 27 selects.
    for idx in UNMAPPED:
        for addr in (idx << 16, 0x000000, 0x1B0000, 0xFFFFFF):
            cs = cs_outputs(idx, addr, mem_nce=0, load_en=0)
            act = active(cs)
            ck.check(len(act) == 0,
                     f"unmapped MEM_SEL={idx:02d} addr=0x{addr:06X} no CS (active={act})")

    ck.lines.append("")

    # 3. Mismatched address tag: no device may be selected.
    for idx, ref, name, cs_net, size in DEVICES:
        for tag in ((idx + 1) & 0x1F, (idx + 0x10) & 0xFF, 0x00 if idx != 0 else 0x1F):
            addr = (tag << 16) | 0x1234
            cs = cs_outputs(idx, addr, mem_nce=0, load_en=0)
            act = active(cs)
            ck.check(len(act) == 0,
                     f"tag mismatch MEM_SEL={idx:02d} ADDR[23:16]=0x{tag:02X} "
                     f"no CS (active={act})")

    ck.lines.append("")

    # 4. Normal mode requires MEM_nCE asserted.
    for idx, ref, name, cs_net, size in DEVICES:
        cs = cs_outputs(idx, idx << 16, mem_nce=1, load_en=0)
        act = active(cs)
        ck.check(len(act) == 0,
                 f"normal idle MEM_SEL={idx:02d} MEM_nCE=1 no CS (active={act})")

    ck.lines.append("")

    # 5. Load mode (LOAD_EN=1) bypasses MEM_nCE, still one-hot.
    for idx, ref, name, cs_net, size in DEVICES:
        cs = cs_outputs(idx, idx << 16, mem_nce=1, load_en=1)
        act = active(cs)
        ck.check(act == [cs_net],
                 f"load mode MEM_SEL={idx:02d} MEM_nCE=1 active={act}")

    ck.lines.append("")

    # 6. Exhaustive MEM_SEL sweep at matching tags (one-hot proof).
    for idx in range(32):
        cs = cs_outputs(idx, idx << 16, mem_nce=0, load_en=0)
        n = len(active(cs))
        expected = 1 if idx in DEV_BY_INDEX else 0
        ck.check(n == expected,
                 f"one-hot sweep MEM_SEL={idx:02d}: active={n} expected={expected}")

    ck.lines.append("")

    # 7. Random search across all inputs (catches accidental multi-drive).
    rng = random.Random(0xC0FFEE)
    worst = 0
    for _ in range(20000):
        idx = rng.randrange(32)
        addr = rng.getrandbits(24)
        nce = rng.randrange(2)
        load = rng.randrange(2)
        cs = cs_outputs(idx, addr, nce, load)
        n = len(active(cs))
        worst = max(worst, n)
        if n > 1:
            ck.check(False, f"multi-select MEM_SEL={idx} ADDR=0x{addr:06X} "
                            f"nCE={nce} LOAD={load} active={active(cs)}")
            break
    else:
        ck.check(worst <= 1, f"20000 random vectors: max active CS = {worst}")

    ck.lines.append("")
    ck.lines.append(f"checks: {ck.checks}  failures: {ck.failures}")
    ck.lines.append("RESULT: " + ("PASS" if ck.finish() else "FAIL"))
    text = "\n".join(ck.lines) + "\n"
    with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    print(f"log: {LOG_PATH}")
    return 0 if ck.failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
