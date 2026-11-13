"""Apply the JLCEDA B-class changes (B1/V15, B2/V17, B3/V16) to a KiCad netlist.

The JLCEDA project 74CNN-BRD is the fabricated design; the local KiCad project
is the reference transcription.  B1/B2/B3 were only applied in JLCEDA, so the
KiCad netlist used by the simulation has to be patched pin by pin with the
exact same connectivity before it can be re-simulated.

Source of truth:
  D:/tmp/jlc_brd/state/bclass_2026-11-12/report.json          (B1, B3 C1/C2/FC2)
  D:/tmp/jlc_brd/apply_bclass_rest.py                          (B2, B3 FC1)
  D:/Document/tempPrj/74Series-CNN/UPSTREAM_SYNC_2026-11-12.md (summary)

Usage:
    python patch_netlist_bclass.py [--apply]
"""
from __future__ import annotations

import os
import sys

TOOLS = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/tools"
sys.path.insert(0, TOOLS)
import kicad_sexpr as k  # noqa: E402

PROJ = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System"
SRC = os.path.join(PROJ, "output", "top_20261112b.net")
DST = os.path.join(PROJ, "output", "top_20261112c.net")

APPLY = "--apply" in sys.argv

B04 = "/B04_S07_Conv1/"
B05 = "/B05_S05_Pool1/"
B06 = "/B06_S08_Conv2/"
B07 = "/B07_S05_Pool2/"
B08 = "/B08_S09_FC1/"
B09 = "/B09_S09_FC2/"

# ---------------------------------------------------------------- edit lists
# B1 / V15: lane counter /PE = ~(LANE_LAST & ACC_EN)
V15 = [
    ("U7022", "12", B04 + "C1_LANE_LAST", B04 + "C1_LANE0"),
    ("U7022", "13", B04 + "C1_ACC_EN",    B04 + "C1_LANE1"),
    ("U8142", "1",  B06 + "C2_LANE_LAST", B06 + "C2_LANE0"),
    ("U8142", "2",  B06 + "C2_ACC_EN",    B06 + "C2_LANE1"),
    ("U9015", "12", B08 + "FC_LANE_LAST", B08 + "FC_LANE0"),
    ("U9015", "13", B08 + "FC_ACC_EN",    B08 + "FC_LANE1"),
    ("U9215", "12", B09 + "FC_LANE_LAST", B09 + "FC_LANE0"),
    ("U9215", "13", B09 + "FC_ACC_EN",    B09 + "FC_LANE1"),
]

# B3 / V16: 74HC283 B inputs above bit 16 get the PSUM sign (BM17) instead of GND
#
# NOTE: the JLCEDA edit for B08 (apply_bclass_rest.py) covered U9093 p11/p15 and
# U9095/U9096 only -- U9094 (ACC bits 20..23) was missed, so FC1's accumulator
# still added a zero B nibble there and the upper half never sign-extended.
# The list below carries the complete 14-pin change; the schematic needs the
# four extra U9094 pins.
V16 = []
for bm, adds3, add16 in ((B04 + "C1_BM17", ("U7108", "U7109", "U7110"), "U7107"),
                         (B06 + "C2_BM17", ("U8109", "U8110", "U8111"), "U8108"),
                         (B08 + "FC_BM17", ("U9094", "U9095", "U9096"), "U9093"),
                         (B09 + "FC_BM17", ("U9294", "U9295", "U9296"), "U9293")):
    for u in adds3:
        for p in ("2", "6", "11", "15"):
            V16.append((u, p, bm, "GND"))
    V16.append((add16, "11", bm, "GND"))
    V16.append((add16, "15", bm, "GND"))

# B2 / V17: spare 74HC02 U7157 gates on B04-4 hold KX/KY during pad cycles
#
# NOTE: the JLCEDA edit (apply_bclass_rest.py, state bclass_2026-11-12/rest)
# connected gate 2 with 74HC00-style pin numbering:
#       U7157 p4 = C1_KY_EN   p5 = C1_PAD_ACTIVE   p6 = C1_KX_PE_N
# but a 74HC02 is NOT a 74HC00: pin 4 is the gate-2 OUTPUT, pins 5/6 are the
# inputs (identical to the netlist libpart).  As built that ties an output pin
# to KY_EN and leaves KX_PE_N undriven.  The simulation therefore uses the
# electrically correct connection below; the schematic/PCB must be corrected
# (swap p4 and p6 nets).  Gate 3 (p8/p9 in, p10 out) was already correct.
V17_NEW = [
    # (ref, pin, net, pintype) -- added nodes
    ("U7157", "4",  B04 + "C1_KX_PE_N",    "output"),
    ("U7157", "5",  B04 + "C1_KY_EN",      "input"),
    ("U7157", "6",  B04 + "C1_PAD_ACTIVE", "input"),
    ("U7157", "8",  B04 + "C1_OX_EN",      "input"),
    ("U7157", "9",  B04 + "C1_PAD_ACTIVE", "input"),
    ("U7157", "10", B04 + "C1_KY_PE_N",    "output"),
]
V17_DISCONNECT = [("U7021", "3"), ("U7021", "6")]

# V16 (missing piece): the 18-bit PSUM adder only computed the carry out of
# bit 16 as PSUM17.  For signed 17-bit partial sums S12/S34 the 18th bit must
# be the *sum* of the two sign bits plus that carry, i.e. the addends have to
# be sign-extended into bit 17 (A2 <- S12_16, B2 <- S34_16).
V16B = []
for ref, pre, s12 in (("U7097", B04, "C1_S12_16"), ("U8098", B06, "C2_S12_16"),
                      ("U9083", B08, "FC_S12_16"), ("U9283", B09, "FC_S12_16")):
    V16B.append((ref, "3", pre + s12, "GND"))
    V16B.append((ref, "2", pre + s12.replace("S12", "S34"), "GND"))

# PSUM17 must be the *sum* bit (S2, pin 1) of the last 74HC283, not its carry
# out (C4, pin 9): with the sign bits now on A2/B2 the sum bit is PSUM17.
V16C = [(ref, "1", pre + s12.replace("S12_16", "PSUM17"))
        for ref, pre, s12 in (("U7097", B04, "C1_S12_16"), ("U8098", B06, "C2_S12_16"),
                              ("U9083", B08, "FC_S12_16"), ("U9283", B09, "FC_S12_16"))]

# V19: C1 input address adder.  build_conv1.py synthesises 28*SY as
# (SY<<5) + ~(SY<<2) + 1 over 10 bits, but only complements bits 2..6; the
# two's-complement extension of the "-4*SY" term (bits 7..9) is left at GND,
# so the hardware computes 28*SY + 125.  Every C1 input address is therefore
# offset by +125 (reads image[125+n] instead of image[n]).
# Fix: tie the three missing complement inputs to +5V.
V19 = [("U7028", "6",  "+5V", "GND"),    # b bit 0 (also part of ~(4*SY))
       ("U7028", "2",  "+5V", "GND"),    # b bit 1
       ("U7029", "11", "+5V", "GND"),    # b bit 7 of the SY28 chain
       ("U7030", "6",  "+5V", "GND"),    # b bit 8
       ("U7030", "2",  "+5V", "GND")]    # b bit 9

# V20: IMAGE_LAST was SP_LAST only, so C1 stopped after 576 of 4608 output
# points (one filter) and C2 after 100 of 1600.
#   * ROM1 (state ROM, U7132/U8132) has a free address pin A11: wire it to
#     OC_LAST and program IMAGE_LAST = A10 & A11 (gen_engine_microcode.py
#     oc_last_bit).  ROM2 keeps A11 = GND; its words do not depend on it.
#   * OC must advance on the *end of filter*, i.e. SP_LAST & OUT_STB (the same
#     edge on which SP wraps), not on the last MAC_EN: otherwise OC_LAST is
#     already high during the last point of the previous filter and the FSM
#     stops one filter early.
V20 = [("U7132", "23", B04 + "C1_OC_LAST", "GND"),
       ("U8132", "23", B06 + "C2_OC_LAST", "GND")]
V20B = [("U7020", "12", B04 + "C1_SP_LAST", B04 + "C1_OXYO"),
        ("U7020", "13", B04 + "C1_OUT_STB", B04 + "C1_MAC_EN"),
        ("U8018", "9",  B06 + "C2_SP_LAST", B06 + "C2_ICXO"),
        ("U8018", "10", B06 + "C2_OUT_STB", B06 + "C2_MAC_EN"),
        # C2's OC load must use the same filter-boundary term as C1; the old
        # IMG_LAST&MAC_EN cleared OC at the final MAC, long before E_NEXT, so
        # the FSM never saw OC_LAST and restarted filter 0 forever.
        ("U8020", "4",  B06 + "C2_OC_LAST", B06 + "C2_IMG_LAST"),
        ("U8020", "5",  B06 + "C2_OC_EN",   B06 + "C2_MAC_EN")]


# V21: Pool1/Pool2 window-pixel counter V (74HC161 U5004/U5104) is clocked at
# S_CP, i.e. it advances during the capture state.  V_LAST (V=3) is therefore
# evaluated one pixel too early: the window is written after v0..v2 and the
# fourth read lands on WB(+2)+W+1 = the *next* window's bottom-right pixel.
# Moving CEP/CET to S_WT advances V after the comparison state so all four
# pixels are read (offsets 0,1,W,W+1) before V_LAST triggers the write.
V21 = [("U5004", "7",  B05 + "S_WT", B05 + "S_CP"),
       ("U5004", "10", B05 + "S_WT", B05 + "S_CP"),
       ("U5104", "7",  B07 + "S_WT", B07 + "S_CP"),
       ("U5104", "10", B07 + "S_WT", B07 + "S_CP")]

# V22: C1 weight address multiplier truncates OC5 = 5*OC to 5 bits.  For OC=7
# 5*7 = 35 needs bit 5, but U7035's S2 (pin 1) is left unconnected and U7037's
# bit-5/bit-7 inputs (p3/p11) are grounded, so OC25 = 25*OC wraps to 15 and
# filter 7 reads weights 15..39 instead of 175..199.
# Fix: U7035 p1 = OC5_5, U7037 p3 = OC5_5, U7037 p11 = OC5_5.
V22_ADD = [("U7035", "1", B04 + "C1_OC5_5", "output")]
V22_MOVE = [("U7037", "3",  B04 + "C1_OC5_5", "GND"),
            ("U7037", "11", B04 + "C1_OC5_5", "GND")]

# V23: C2 weight address uses the 5x5 row stride (KY3 = 5*KY) copied from the
# C1 sheet, but conv2's kernel is 3x3: W_ADDR must be oc*72 + ic*9 + ky*3 + kx.
# U8035 currently adds 4*KY on top of KY (p15=KY0, p11=KY1); rewire to 2*KY
# (p2=KY0, p15=KY1, p11=GND).
V23 = [("U8035", "2",  B06 + "C2_KY0", "GND"),
       ("U8035", "15", B06 + "C2_KY1", B06 + "C2_KY0"),
       ("U8035", "11", "GND",         B06 + "C2_KY1")]

# V24: the FC weight base N400a = 384*NEURON is 13 bits, but chain_grid's
# "final_carry" takes C4 of the last 74HC283 nibble, i.e. bit 16, not bit 13.
# N400a bit 13 is actually the S2 sum output (pin 1) of U9020/U9220.
# Without it 400*NEURON wraps modulo 8192 from neuron 22 on (8800 -> 608).
V24 = [("U9020", "1", B08 + "FC_N400a_13", "S2"),
       ("U9220", "1", B09 + "FC_N400a_13", "S2")]

# V25: S09 stored neuron n at output address n+1 (NEURON advanced on
# INDEX_LAST & MAC_EN, before the write) and neuron 31 wrapped onto address 0.
# Move the neuron strobe into the spare 74HC74 unit B, which delays it one
# clock and delivers a clean single pulse at E_ADDR_IN/E_WAIT_A.  ROM2 D3
# (left open on S09) is programmed as that strobe.
V25 = [
    # register Q3 (ROM2 D3) becomes the neuron strobe source
    ("U9122", "16", B08 + "FC_NEU_STB"),
    ("U9130", "12", B08 + "FC_NEU_STB"),   # spare FF D <- strobe
    ("U9130", "9",  B08 + "FC_NEURON_EN"), # spare FF Q -> NEURON_EN
    ("U9322", "16", B09 + "FC_NEU_STB"),
    ("U9330", "12", B09 + "FC_NEU_STB"),
    ("U9330", "9",  B09 + "FC_NEURON_EN"),
]
V25_RELEASE = [("U9014", "6"), ("U9214", "6")]

# V26: the S09 byte counter drives only the sheet-local FC_BYTE0/1 nets, while
# the S17_FC2 byte-select muxes listen on the global FC2_BYTE0/1 nets -- those
# global nets have no driver anywhere in the netlist (and no backplane pins),
# so FC2 read four undefined bytes and FC2LOG came out all-X.  Tie the two
# counter outputs to the S17 muxes (board ECO: two wires from U9212 Q0/Q1 to
# the backplane, or a direct wire across the two S17/S09 connectors).
V26 = [("U16212", "1", B09 + "FC_BYTE0", "FC2_BYTE0"),
       ("U16213", "1", B09 + "FC_BYTE0", "FC2_BYTE0"),
       ("U16214", "1", B09 + "FC_BYTE0", "FC2_BYTE0"),
       ("U16215", "1", B09 + "FC_BYTE0", "FC2_BYTE0"),
       ("U16216", "1", B09 + "FC_BYTE1", "FC2_BYTE1"),
       ("U16217", "1", B09 + "FC_BYTE1", "FC2_BYTE1")]


# ---------------------------------------------------------------- serializer
def ser(x, ind=0) -> str:
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    head = x[0]
    simple = all(isinstance(c, str) for c in x[1:])
    if simple and len(x) <= 5 and head in ("code", "name", "class", "ref", "pin",
                                           "pinfunction", "pintype", "value"):
        return "(" + head + " " + " ".join(ser(c, 0) for c in x[1:]) + ")"
    out = ["(" + head]
    for c in x[1:]:
        out.append("\t" * (ind + 1) + ser(c, ind + 1))
    out.append("\t" * ind + ")")
    return "\n".join(out)


# ---------------------------------------------------------------- patch
with open(SRC, encoding="utf-8") as f:
    TEXT = f.read()

blk = k.extract_block(TEXT, "\n\t(nets")
if blk is None:
    raise SystemExit("nets section not found")
start = TEXT.index("\n\t(nets") + 2          # keep "\n\t"
end = start + len(blk)
root = k.parse(blk)[0]
nets = [n for n in root[1:] if isinstance(n, list) and n and n[0] == "net"]

# index
pin_net = {}
net_by_name = {}
for n in nets:
    nm = k.atoms(k.first(n, "name"))[0]
    net_by_name[nm] = n
    for x in k.children(n, "node"):
        pin_net[(k.atoms(k.first(x, "ref"))[0], k.atoms(k.first(x, "pin"))[0])] = (n, x)

next_code = max(int(k.atoms(k.first(n, "code"))[0]) for n in nets) + 1
problems = []


def move(ref, pin, newnet, oldnet_expected):
    global next_code
    ent = pin_net.get((ref, pin))
    if ent is None:
        problems.append(f"{ref}.{pin}: pin not found in any net")
        return
    cur, node = ent
    cur_name = k.atoms(k.first(cur, "name"))[0]
    if cur_name != oldnet_expected:
        problems.append(f"{ref}.{pin}: on {cur_name!r}, expected {oldnet_expected!r}")
        return
    if newnet not in net_by_name:
        if not APPLY:
            print(f"  [dry] create net {newnet}")
        n = ["net", ["code", str(next_code)], ["name", newnet], ["class", "Default"]]
        next_code += 1
        nets.append(n)
        net_by_name[newnet] = n
    tgt = net_by_name[newnet]
    # remove from old net
    cur[:] = [c for c in cur if not (isinstance(c, list) and c is node)]
    del pin_net[(ref, pin)]
    # insert into target before the closing of the block (append)
    tgt.append(node)
    pin_net[(ref, pin)] = (tgt, node)
    print(f"  {ref}.{pin}: {cur_name} -> {newnet}")


def move_any(ref, pin, newnet):
    """Move a pin from whatever net currently holds it."""
    ent = pin_net.get((ref, pin))
    if ent is None:
        problems.append(f"{ref}.{pin}: pin not found in any net")
        return
    cur, node = ent
    cur_name = k.atoms(k.first(cur, "name"))[0]
    if cur_name == newnet:
        return
    move(ref, pin, newnet, cur_name)


def add(ref, pin, netname, pintype):
    tgt = net_by_name.get(netname)
    if tgt is None:
        problems.append(f"target net {netname!r} does not exist")
        return
    node = ["node", ["ref", ref], ["pin", pin], ["pintype", pintype]]
    tgt.append(node)
    pin_net[(ref, pin)] = (tgt, node)
    print(f"  {ref}.{pin}: (new) -> {netname}")


print("B1 / V15  lane /PE")
for ref, pin, new, old in V15:
    move(ref, pin, new, old)

print("B3 / V16  BM17 sign extension")
for ref, pin, new, old in V16:
    move(ref, pin, new, old)

print("B3b / V16  PSUM17 sign extension (S12_16/S34_16 into bit 17)")
for ref, pin, new, old in V16B:
    move(ref, pin, new, old)
print("B3c / V16  PSUM17 <- S2 (sum bit), C4 set free")
for ref, pin, new in V16C:
    move_any(ref, "9", f"unconnected-({ref}-C4-Pad9)")
    move_any(ref, pin, new)

print("B2 / V17  pad hold (U7157, B04-4)")
for ref, pin in V17_DISCONNECT:
    move(ref, pin, f"unconnected-({ref}-Pad{pin})", B04 + ("C1_KX_PE_N" if pin == "3" else "C1_KY_PE_N"))
    # the freshly created net is a dummy; keep the node but rename it
    for n in nets:
        if k.atoms(k.first(n, "name"))[0].startswith("unconnected-"):
            pass
for ref, pin, netname, ptype in V17_NEW:
    add(ref, pin, netname, ptype)

print("V19  C1 input address +125 (28*SY complement)")
for ref, pin, new, old in V19:
    move(ref, pin, new, old)

print("V20  IMAGE_LAST = SP_LAST & OC_LAST (ROM1 A11)")
for ref, pin, new, old in V20:
    move(ref, pin, new, old)
print("V20b OC advances on OUT_STB (same edge as SP)")
for ref, pin, new, old in V20B:
    move(ref, pin, new, old)

print("V21  pool V counter advances at S_WT (4th pixel included)")
for ref, pin, new, old in V21:
    move(ref, pin, new, old)

print("V22  C1 OC*25 keeps bit 5 (filter 7 weight base)")
for ref, pin, netname, ptype in V22_ADD:
    if netname not in net_by_name:
        if not APPLY:
            print(f"  [dry] create net {netname}")
        n = ["net", ["code", str(next_code)], ["name", netname], ["class", "Default"]]
        next_code += 1
        nets.append(n)
        net_by_name[netname] = n
    add(ref, pin, netname, ptype)
for ref, pin, new, old in V22_MOVE:
    move(ref, pin, new, old)

print("V23  C2 weight row stride ky*3 (was ky*5)")
for ref, pin, new, old in V23:
    move(ref, pin, new, old)

print("V24  FC weight base bit13 from the adder sum output (not C4)")
for ref, pin, new, _tag in V24:
    move_any(ref, "9", f"unconnected-({ref}-C4-Pad9)")
    move_any(ref, pin, new)

print("V25  FC neuron strobe moved to after the output write")
for ref, pin, new in V25:
    move_any(ref, pin, new)
for ref, pin in V25_RELEASE:
    move_any(ref, pin, f"unconnected-({ref}-Pad{pin})")

print("V26  FC2 byte-select muxes driven from the S09 byte counter")
for ref, pin, new, old in V26:
    move(ref, pin, new, old)

if problems:
    print("\nPROBLEMS:")
    for p in problems:
        print("  " + p)
    if APPLY:
        raise SystemExit("refusing to write with problems")

# drop nets that lost their last node (moved pins leave empty unconnected nets)
empty = [n for n in nets if not k.children(n, "node")]
nets = [n for n in nets if k.children(n, "node")]

# serialise
body = "\n\t\t".join(ser(n, 2) for n in nets)
new_blk = "(nets\n\t\t" + body + "\n\t)"
OUT = TEXT[:start] + new_blk + TEXT[end:]

print(f"\nnets: {len(nets)}  out: {len(OUT)} bytes  -> {DST}")
if APPLY and not problems:
    with open(DST, "w", encoding="utf-8", newline="\n") as f:
        f.write(OUT)
    print("written")
else:
    print("dry run (pass --apply to write)")
