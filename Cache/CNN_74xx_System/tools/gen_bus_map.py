"""Generate the S11 bus-fabric map ROM image (27C512).

The S11 map ROM converts the active engine's master code and region code into
the 5-bit S04 device index MEM_SEL[4:0]:

    ROM address A[8:0] = {POOL_SEL, MASTER[2], FC_SEL, MASTER[1:0],
                          REGION[2:0], 1'b0}
    ROM data    D[4:0] = MEM_SEL[4:0]

A0 is tied low on the schematic, so only even addresses are used.  Every
address that is not in the table below is programmed to 0x1F (no device).

Master codes:  1 = CONV1, 2 = CONV2, 3 = FC, 4 = ARGMAX, 5 = POOL
Region codes:  0 = IN, 1 = W, 2 = OUT, 3 = B, 4 = Q, 5 = MC, 7 = none

Run from the tools directory:
    python gen_bus_map.py
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT_DIR = os.path.join(PROJECT_DIR, "model", "busmap")

REGIONS = ["IN", "W", "OUT", "B", "Q", "MC", "RES6", "NONE"]
MASTER_NAME = {1: "C1", 2: "C2", 3: "FC", 4: "ARGMAX", 5: "POOL"}

# MEM_SEL per (master, fc_sel, region)
MAP = {}
for region, sel in enumerate([0, 8, 1, 12, 16, 20]):
    MAP[(1, 0, region)] = sel          # CONV1
for region, sel in enumerate([2, 9, 3, 13, 17, 22]):
    MAP[(2, 0, region)] = sel          # CONV2
for region, sel in enumerate([4, 10, 5, 14, 18, 24]):
    MAP[(3, 0, region)] = sel          # FC1 (FC_SEL=0)
for region, sel in enumerate([5, 11, 6, 15, 19, 26]):
    MAP[(3, 1, region)] = sel          # FC2 (FC_SEL=1)
# Argmax reads FC2_LOGITS.  Its region code is 7 when all engines are idle;
# map every region/fc_sel combination for master 4 to 6 for robustness.
for fc in (0, 1):
    for region in range(8):
        MAP[(4, fc, region)] = 6
# Pool reads CONV1_OUT/CONV2_OUT and writes POOL1_OUT/POOL2_OUT.
# POOL_SEL=0 -> P1 (IN=1, OUT=2); POOL_SEL=1 -> P2 (IN=3, OUT=4).
POOL_MAP = {}
for pool_sel, in_sel, out_sel in ((0, 1, 2), (1, 3, 4)):
    POOL_MAP[(5, 0, 0, pool_sel)] = in_sel
    POOL_MAP[(5, 0, 2, pool_sel)] = out_sel

WINDOW = {
    0: "INPUT_SRAM", 1: "CONV1_OUT_SRAM", 2: "POOL1_OUT_SRAM",
    3: "CONV2_OUT_SRAM", 4: "POOL2_OUT_SRAM", 5: "FC1_OUT_SRAM",
    6: "FC2_LOGITS_SRAM", 8: "W_CONV1", 9: "W_CONV2", 10: "W_FC1",
    11: "W_FC2", 12: "B_CONV1", 13: "B_CONV2", 14: "B_FC1", 15: "B_FC2",
    16: "Q_CONV1", 17: "Q_CONV2", 18: "Q_FC1", 19: "Q_FC2",
    20: "LUT0_LO", 21: "LUT0_HI", 22: "LUT1_LO", 23: "LUT1_HI",
    24: "LUT2_LO", 25: "LUT2_HI", 26: "LUT3_LO", 27: "LUT3_HI",
}


def rom_addr(fc_sel: int, master: int, region: int, pool_sel: int = 0) -> int:
    return (((pool_sel & 1) << 8) | ((master >> 2) & 1) << 7 |
            ((fc_sel & 1) << 6) | ((master & 3) << 4) | ((region & 7) << 1))


def build() -> bytearray:
    image = bytearray([0x1F]) * 65536
    for (master, fc_sel, region), sel in MAP.items():
        assert 0 <= sel <= 31, sel
        image[rom_addr(fc_sel, master, region, 0)] = sel
    for (master, fc_sel, region, pool_sel), sel in POOL_MAP.items():
        assert 0 <= sel <= 31, sel
        image[rom_addr(fc_sel, master, region, pool_sel)] = sel
    return image


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    image = build()
    bin_path = os.path.join(OUT_DIR, "bus_map.bin")
    hex_path = os.path.join(OUT_DIR, "bus_map.hex")
    csv_path = os.path.join(OUT_DIR, "bus_map.csv")
    with open(bin_path, "wb") as f:
        f.write(image)
    with open(hex_path, "w", encoding="ascii", newline="\n") as f:
        f.writelines(f"{b:02X}\n" for b in image)

    rows = []
    for (master, fc_sel, region), sel in sorted(MAP.items()):
        addr = rom_addr(fc_sel, master, region)
        rows.append((MASTER_NAME[master], fc_sel, REGIONS[region], 0, addr, sel,
                     WINDOW.get(sel, "unmapped")))
    for (master, fc_sel, region, pool_sel), sel in sorted(POOL_MAP.items()):
        addr = rom_addr(fc_sel, master, region, pool_sel)
        rows.append((MASTER_NAME[master], fc_sel, REGIONS[region], pool_sel, addr,
                     sel, WINDOW.get(sel, "unmapped")))
    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("master,fc_sel,region,pool_sel,rom_addr_hex,mem_sel,window\n")
        for name, fc, region, pool_sel, addr, sel, window in rows:
            f.write(f"{name},{fc},{region},{pool_sel},0x{addr:02X},{sel},{window}\n")

    used = {rom_addr(fc, m, r, 0) for (m, fc, r) in MAP}
    used |= {rom_addr(fc, m, r, p) for (m, fc, r, p) in POOL_MAP}
    print(f"wrote {bin_path} ({len(image)} bytes, {len(used)} mapped addresses)")
    print(f"wrote {hex_path}")
    print(f"wrote {csv_path}")
    assert len(used) == len(MAP) + len(POOL_MAP), "ROM address collision"
    # Spot checks from the design table.
    checks = [
        ((1, 0, 0), 0, "C1 IN -> INPUT_SRAM"),
        ((1, 0, 1), 8, "C1 W -> W_CONV1"),
        ((2, 0, 3), 13, "C2 B -> B_CONV2"),
        ((3, 0, 5), 24, "FC1 MC -> LUT2"),
        ((3, 1, 2), 6, "FC2 OUT -> FC2_LOGITS"),
        ((3, 1, 5), 26, "FC2 MC -> LUT3"),
        ((4, 0, 7), 6, "ARGMAX (idle region) -> FC2_LOGITS"),
        ((4, 1, 0), 6, "ARGMAX (FC_SEL=1) -> FC2_LOGITS"),
        ((5, 0, 0), 1, "POOL P1 IN -> CONV1_OUT"),
        ((5, 0, 2), 2, "POOL P1 OUT -> POOL1_OUT"),
        ((5, 0, 0, 1), 3, "POOL P2 IN -> CONV2_OUT"),
        ((5, 0, 2, 1), 4, "POOL P2 OUT -> POOL2_OUT"),
    ]
    for item in checks:
        key, want, label = item
        if len(key) == 3:
            m, fc, r = key
            pool_sel = 0
        else:
            m, fc, r, pool_sel = key
        addr = rom_addr(fc, m, r, pool_sel)
        got = image[addr]
        assert got == want, (label, got, want)
        print(f"  {label}: addr 0x{addr:02X} -> {got} OK")
    print("PASS: bus map image checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
