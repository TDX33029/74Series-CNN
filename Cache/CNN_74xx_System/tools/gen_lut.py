"""Generate and exhaustively verify the 8x8 LUT multiplier ROM images.

Two variants:
  * unsigned (default): p = a * b, both 8-bit unsigned   (V1 contract)
  * --signed          : p = a * int8(b), 16-bit two's complement
                        (V2/scheme C: a = uint8 pixel, b = int8 weight)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(PROJECT_DIR, "model", "lut")
os.makedirs(OUT, exist_ok=True)

SIGNED = "--signed" in sys.argv
TAG = "_signed" if SIGNED else ""

lo = bytearray(65536)
hi = bytearray(65536)
for a in range(256):
    for b in range(256):
        addr = (a << 8) | b
        bs = b - 256 if (SIGNED and b >= 128) else b
        p = a * bs
        lo[addr] = p & 0xFF
        hi[addr] = (p >> 8) & 0xFF

with open(os.path.join(OUT, f"lut_lo{TAG}.bin"), "wb") as f:
    f.write(lo)
with open(os.path.join(OUT, f"lut_hi{TAG}.bin"), "wb") as f:
    f.write(hi)

# Human-readable hex files for ROM programmers (one byte per line).
with open(os.path.join(OUT, f"lut_lo{TAG}.hex"), "w", encoding="ascii", newline="\n") as f:
    f.writelines(f"{b:02X}\n" for b in lo)
with open(os.path.join(OUT, f"lut_hi{TAG}.hex"), "w", encoding="ascii", newline="\n") as f:
    f.writelines(f"{b:02X}\n" for b in hi)

if SIGNED:
    # Scheme C is the production contract: the signed image is the canonical
    # one that gen_rtl.py copies into rtl/init.  Keep the unsigned build for
    # reference.
    for stem, data in (("lut_lo", lo), ("lut_hi", hi)):
        u = os.path.join(OUT, stem + ".hex")
        if os.path.exists(u) and not os.path.exists(os.path.join(OUT, stem + "_unsigned.hex")):
            os.replace(u, os.path.join(OUT, stem + "_unsigned.hex"))
        with open(u, "w", encoding="ascii", newline="\n") as f:
            f.writelines(f"{b:02X}\n" for b in data)

errors = 0
for a in range(256):
    for b in range(256):
        addr = (a << 8) | b
        bs = b - 256 if (SIGNED and b >= 128) else b
        p = a * bs
        if lo[addr] != (p & 0xFF) or hi[addr] != ((p >> 8) & 0xFF):
            errors += 1
            if errors <= 5:
                print("MISMATCH", a, b, lo[addr], hi[addr], p)

print(f"generated {len(lo)} entries ({'signed' if SIGNED else 'unsigned'}); errors={errors}")
print("lo bytes", len(lo), "hi bytes", len(hi))
print("checksum lo", sum(lo) & 0xFFFFFFFF, "hi", sum(hi) & 0xFFFFFFFF)
if errors:
    sys.exit(1)
print("PASS: exhaustive 8x8 LUT")
