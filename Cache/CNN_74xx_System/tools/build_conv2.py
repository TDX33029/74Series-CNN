"""Build S08_Conv2.kicad_sch (CONV2 engine).

Run from the tools directory:
    python build_conv2.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from build_conv1 import (BLOCK_LIB, EngineBuilder, GatePool, Grid, PROJECT_DIR,
                         write_block_library)


def build_conv2() -> str:
    p = lambda s: f"C2_{s}"
    globals_ = (["CLK", "RESET_N", "C2_START", "C2_DONE", "C2_BUSY",
                 "C2_BUSY_N", "MEM_nCE", "MEM_nOE", "MEM_nWE",
                 "MEM_ACK", "MEM_DONE", "MEM_BUSY",
                 "C2_MEM_REQ", "C2_MEM_WE"]
                + [f"DATA{i}" for i in range(8)]
                + [f"C2_ADDR{i}" for i in range(16)]
                + [f"C2_MEM_nCE_{x}" for x in ("IN", "W", "OUT", "B", "Q", "MC")]
                # Simple V2 Requant interface to S15_Requant_C2.
                + [f"C2_ACC{i}" for i in range(32)]
                + [f"C2_REQ_Q{i}" for i in range(8)]
                + ["C2_REQ_START", "C2_REQ_QSTB",
                   "C2_SAT_FLAG", "C2_REQ_BUSY", "C2_REQ_DONE"])
    e = EngineBuilder("C2", "S08_Conv2 - CONV2 Engine (12x12x8 -> 10x10x16, K=3)",
                      paper="A0", global_nets=globals_)
    e.refn = 8000
    e.gates = GatePool(e, 20, 284, cols=5, dx=55.0, dy=20.0)
    e.text("S08  CONV2 ENGINE", 15, 10, size=3.0, bold=True)
    e.text(
        "H=12 W=12 Cin=8 Cout=16 K=3  ->  Hout=10 Wout=10\n"
        "Loop order: oc(0..15) -> oy(0..9) -> ox(0..9) -> ic(0..7) -> ky(0..2) -> kx(0..2).\n"
        "MAC/point = 8x3x3 = 72; points = 16x10x10 = 1600; total MAC = 115200.\n"
        "Input layout CHW C=8 (POOL1_OUT):  IN_ADDR = ic*144 + (oy+ky)*12 + (ox+kx)   range 0..1151\n"
        "Weight layout [oc][ic][ky][kx]:  W_ADDR = oc*72 + ic*9 + ky*3 + kx        range 0..1151\n"
        "Output layout CHW C=16:  OUT_ADDR = oc*100 + oy*10 + ox                 range 0..1599\n"
        "Output order: for oc, for oy, for ox -> one uint8 per output point (little-endian byte 0 only).",
        15, 18, size=1.5,
    )
    e.text(
        "MAC datapath identical to S07: 4x LUT_Mult_Unit, 4-deep pixel/weight pipeline, "
        "4-product 18-bit adder tree, 32-bit accumulator (8x74HC283 + 4x74HCT574), requant core on S15.",
        430, 748, size=1.15,
    )
    e.text(
        "Local FSM: 2x27C512 + 74HCT273 + 2x74HCT574 + 74HC138.",
        430, 756, size=1.15,
    )

    # --- loop counters ----------------------------------------------------
    OC = e.counter("OC", 20, 62, 4, 15, enable=p("OC_EN"), pe_net=p("OC_PE_N"))
    e.comparator(20, 122, OC, 15, p("OC_LAST"))
    OY = e.counter("OY", 115, 62, 4, 9, enable=p("OY_EN"), pe_net=p("OY_PE_N"))
    e.comparator(115, 122, OY, 9, p("OY_LAST"))
    OX = e.counter("OX", 240, 62, 4, 9, enable=p("OX_EN"), pe_net=p("OX_PE_N"))
    e.comparator(240, 122, OX, 9, p("OX_LAST"))
    IC = e.counter("IC", 20, 188, 3, 7, enable=p("IC_EN"), pe_net=p("IC_PE_N"))
    e.comparator(20, 248, IC, 7, p("IC_LAST"))
    KY = e.counter("KY", 115, 188, 2, 2, enable=p("KY_EN"), pe_net=p("KY_PE_N"))
    e.comparator(115, 248, KY, 2, p("KY_LAST"))
    KX = e.counter("KX", 240, 188, 2, 2, enable=p("MAC_EN"), pe_net=p("KX_PE_N"))
    e.comparator(240, 248, KX, 2, p("KX_LAST"))
    SP = e.counter("SP", 340, 62, 7, 99, enable=p("OUT_STB"),
                   pe_net=p("SP_PE_N"), vertical=True)
    e.comparator(340, 180, SP, 99, p("SP_LAST"))

    # --- loop enables / synchronous loads --------------------------------
    e.and2("RESET_N", p("LOOP_CLR_N"), p("CNT_RESET_N"))
    e.and2(p("KX_LAST"), p("MAC_EN"), p("KY_EN"))
    e.and2(p("KX_LAST"), p("KY_LAST"), p("KXKY"))
    e.and2(p("KXKY"), p("IC_LAST"), p("ICKY"))
    # V10: every counter increments when all loops INSIDE it have wrapped.
    # The original chain fed each enable from the "self is last" term one
    # level up, so IC (and therefore OX/OY/OC) never advanced: the engine
    # looped over ky/kx only and no output point was ever completed.
    e.and2(p("KXKY"), p("MAC_EN"), p("IC_EN"))
    e.and2(p("ICKY"), p("OX_LAST"), p("ICX"))
    e.and2(p("ICKY"), p("MAC_EN"), p("OX_EN"))
    e.and2(p("ICX"), p("OY_LAST"), p("ICXO"))
    e.and2(p("ICX"), p("MAC_EN"), p("OY_EN"))
    e.and2(p("ICXO"), p("OC_LAST"), p("IMG_LAST"))
    e.and2(p("ICXO"), p("MAC_EN"), p("OC_EN"))
    # Active-low synchronous load, gated by all inner loops reaching their
    # last value (V7).  Loading on <own>_LAST alone would clear KY/IC/OX/OY
    # as soon as they reach their maximum.
    e.nand2(p("KX_LAST"), p("MAC_EN"), p("KX_PE_N"))
    e.nand2(p("KXKY"), p("MAC_EN"), p("KY_PE_N"))
    e.nand2(p("ICKY"), p("MAC_EN"), p("IC_PE_N"))
    e.nand2(p("ICX"), p("MAC_EN"), p("OX_PE_N"))
    e.nand2(p("ICXO"), p("MAC_EN"), p("OY_PE_N"))
    e.nand2(p("IMG_LAST"), p("MAC_EN"), p("OC_PE_N"))
    e.nand2(p("SP_LAST"), p("OUT_STB"), p("SP_PE_N"))

    # --- input address: CHW (c*H*W + y*W + x) -----------------------------
    AG = Grid(15, 410, 62, 48, 4)
    SY = [p(f"SY{i}") for i in range(4)]
    SX = [p(f"SX{i}") for i in range(4)]
    e.chain_grid(AG, "SY", OY, KY, "GND", SY)
    e.chain_grid(AG, "SX", OX, KX, "GND", SX)
    # SY12 = 12*SY = 8*SY + 4*SY = (SY<<3) + (SY<<2), range 0..132 (8 bit)
    SY12 = [p(f"SY12_{i}") for i in range(8)]
    e.chain_grid(AG, "SY12", ["GND"] * 3 + SY, ["GND"] * 2 + SY, "GND", SY12)
    # IC9 = 9*IC = 8*IC + IC (also reused by the weight address)
    IC9 = [p(f"IC9_{i}") for i in range(6)]
    e.chain_grid(AG, "IC9", ["GND", "GND", "GND"] + IC, IC, "GND", IC9)
    # IC144 = 16*IC9 = (IC*9)<<4, low 4 bits tied to GND, range 0..1008
    IC144 = ["GND"] * 4 + IC9
    # T1 = IC144 + SY12, range 0..1140 (11 bit)
    T1 = [p(f"T1_{i}") for i in range(11)]
    e.chain_grid(AG, "T1", IC144, SY12 + ["GND"] * 3, "GND", T1)
    # INA = T1 + SX = ic*144 + (oy+ky)*12 + (ox+kx), range 0..1151 (11 bit)
    INA = [p(f"IN_ADDR{i}") for i in range(11)]
    e.chain_grid(AG, "INA", T1, SX + ["GND"] * 7, "GND", INA)

    # --- weight address: oc*72 + ic*9 + ky*3 + kx -------------------------
    OC9 = [p(f"OC9_{i}") for i in range(8)]
    e.chain_grid(AG, "OC9", ["GND", "GND", "GND"] + OC, OC, "GND", OC9)
    KY3 = [p(f"KY3_{i}") for i in range(3)]
    e.chain_grid(AG, "KY3", KY, ["GND", "GND"] + KY[:2], "GND", KY3)
    KYK = [p(f"KYK{i}") for i in range(4)]
    e.chain_grid(AG, "KYK", KY3, KX, "GND", KYK)
    W1 = [p(f"W1_{i}") for i in range(11)]
    e.chain_grid(AG, "W1", ["GND"] * 3 + OC9, IC9, "GND", W1)
    WA = [p(f"W_ADDR{i}") for i in range(11)]
    e.chain_grid(AG, "WA", W1, KYK + ["GND"] * 7, "GND", WA)

    # --- output address: oc*100 + sp -------------------------------------
    OC24 = [p(f"OC24_{i}") for i in range(9)]
    e.chain_grid(AG, "OC24", ["GND", "GND", "GND", "GND"] + OC,
                 ["GND", "GND", "GND"] + OC, "GND", OC24)
    OC25 = [p(f"OC25_{i}") for i in range(9)]
    e.chain_grid(AG, "OC25", OC24, OC, "GND", OC25)
    OUTA = [p(f"OUT_ADDR{i}") for i in range(11)]
    e.chain_grid(AG, "OUTA", ["GND", "GND"] + OC25, SP + ["GND"] * 4,
                 "GND", OUTA)

    # --- A/B operand path: latches, hold-enabled pipeline, 8x27C512 LUT ----
    A_ST = [[p(f"A{lane}_{i}") for i in range(8)] for lane in range(4)]
    B_ST = [[p(f"B{lane}_{i}") for i in range(8)] for lane in range(4)]
    A_LAT = [p(f"A_LAT{i}") for i in range(8)]
    B_LAT = [p(f"B_LAT{i}") for i in range(8)]
    DATA = [f"DATA{i}" for i in range(8)]
    LUT_PROD = [[p(f"P{lane+1}_{i}") for i in range(16)] for lane in range(4)]
    e.ab_lut_path(700, 40, DATA, p("A_LOAD"), p("B_LOAD"),
                  p("SHIFT_EN"), A_LAT, B_LAT, A_ST, B_ST, LUT_PROD)

    TG = Grid(270, 410, 65, 48, 2)
    S12 = [p(f"S12_{i}") for i in range(16)]
    e.chain_grid(TG, "S12", LUT_PROD[0], LUT_PROD[1], "GND", S12,
                 final_carry=p("S12_16"))
    S34 = [p(f"S34_{i}") for i in range(16)]
    e.chain_grid(TG, "S34", LUT_PROD[2], LUT_PROD[3], "GND", S34,
                 final_carry=p("S34_16"))
    PSUM = [p(f"PSUM{i}") for i in range(18)]
    e.chain_grid(TG, "PSUM", S12 + [p("S12_16")], S34 + [p("S34_16")],
                 "GND", PSUM[:17], final_carry=PSUM[17])

    # --- accumulator (8x74HC283 + 4x74HC273) ------------------------------
    BM = [p(f"BM{i}") for i in range(18)]
    e.mux_bank("BMSK", 610, 450, ["GND"] * 18, PSUM, p("ACC_LD"), BM, dx=65.0)
    ACC = [p(f"ACC{i}") for i in range(32)]
    SUM = [p(f"SUM{i}") for i in range(32)]
    ACCG = Grid(600, 310, 65, 45, 4)
    e.chain_grid(ACCG, "ACCSUM", ACC, BM + ["GND"] * 14, "GND", SUM)
    e.and2("RESET_N", p("ACC_CLR_N"), p("ACC_MR_N"))
    for i in range(4):
        e.reg273(610 + i * 65, 395,
                 SUM[8*i:8*i+8], ACC[8*i:8*i+8], mr=p("ACC_MR_N"))

    # --- simple V2 requant interface (S15) --------------------------------
    # S15 implements Q = clamp(ACC >> 9, 0, 255) with a two-cycle handshake.
    for k, nm in enumerate(("REQ_QSTB", "SAT_FLAG", "REQ_BUSY", "REQ_DONE")):
        e.testpoint(980, 560 + k * 22, p(nm), local=False)

    QBYTE = [p(f"REQ_Q{i}") for i in range(8)]
    OUTD = [p(f"OUT_D{i}") for i in range(8)]
    OUTQ = [p(f"OUT_DATA{i}") for i in range(8)]
    e.mux_bank("OUTHOLD", 330, 300, OUTQ, QBYTE, p("REQ_QSTB"), OUTD, dx=70.0)
    e.reg574(330, 350, OUTD, OUTQ)
    e.transceiver245(395, 350, OUTQ, DATA, "+5V", p("OUT_BUF_N"))
    e.nand2(p("MEM_REQ"), p("MEM_WE"), p("OUT_BUF_N"))

    # --- address mux ------------------------------------------------------
    def pad16(bits):
        return list(bits) + ["GND"] * (16 - len(bits))
    MX1 = [p(f"MX1_{i}") for i in range(16)]
    MX2 = [p(f"MX2_{i}") for i in range(16)]
    e.mux_bank("MX1", 430, 220, pad16(INA), pad16(WA), p("ADD_SEL0"), MX1, dx=65.0)
    e.mux_bank("MX2", 610, 265, MX1, pad16(OUTA), p("ADD_SEL1"), MX2, dx=65.0)

    # --- local FSM --------------------------------------------------------
    # 13 states: 0 reset, 1 idle, 2 addr IN, 3 wait A, 4 addr W, 5 wait B,
    # 6 shift, 7 accumulate, 8 requant request, 9 addr OUT, 10 write,
    # 11 next point, 12 done.
    ST = [p(f"ST{i}") for i in range(5)]
    ROMA = ST + ["C2_START", p("POINT_LAST"), "MEM_ACK", "MEM_DONE",
                 p("REQ_DONE"), p("SP_LAST")]
    MC1 = [p(f"MC1_{i}") for i in range(8)]
    MC2 = [p(f"MC2_{i}") for i in range(8)]
    e.rom27c512(445, 470, ROMA, MC1)
    e.rom27c512(515, 470, ROMA, MC2)
    e.reg273(425, 528, MC1[:5], ST, mr="RESET_N")
    e.reg574(475, 528, ["GND"] * 5 + MC1[5:8],
             ["NC"] * 5 + ["C2_BUSY", "C2_DONE", p("ACC_CLR_N")])
    CTRL = [p("MAC_EN"), p("MEM_REQ"), p("MEM_WE"), p("OUT_STB"),
            p("ADD_SEL0"), p("ADD_SEL1"), "NC", "NC"]
    e.reg574(535, 528, MC2, CTRL)
    # V8: qualify the state decoder with ST3.  States 0..7 are the only ones
    # that use these outputs, but without the ST3 gate state 8 (requant, low
    # three bits = 000) also decodes as Y0 and clears every loop counter once
    # per output point, so the engine restarts from point 0 forever.
    e.decoder138(600, 528, ST[:3], "GND", p("ST3"), "+5V",
                 [p("LOOP_CLR_N"), "NC", "NC", p("WAIT_A_N"),
                  "NC", p("WAIT_B_N"), p("SHIFT_N"), p("ACC_N")])
    e.decoder138(670, 528, ST[:3], "GND", "GND", p("ST3"),
                 [p("REQ_START_N"), "NC", "NC", "NC", "NC", "NC", "NC", "NC"])
    e.inverter(p("WAIT_A_N"), p("WAIT_A"))
    e.inverter(p("WAIT_B_N"), p("WAIT_B"))
    e.inverter(p("SHIFT_N"), p("SHIFT_EN"))
    e.inverter(p("ACC_N"), p("ACC_EN"))
    e.inverter(p("REQ_START_N"), p("REQ_START"))
    e.and2(p("WAIT_A"), "MEM_ACK", p("A_LOAD"))
    e.and2(p("WAIT_B"), "MEM_ACK", p("B_LOAD"))

    e.counter("LANE", 960, 450, 2, 3, enable=p("ACC_EN"),
              pe_net=p("LANE_PE_N"))
    e.nand2(p("LANE0"), p("LANE1"), p("LANE_PE_N"))
    e.and2(p("LANE0"), p("LANE1"), p("LANE_LAST"))
    e.and2(p("ACC_EN"), p("LANE_LAST"), p("ACC_LD"))

    # Point last: 3x3x8 = 72 MACs; capture the comparator result before the
    # counters wrap at the last MAC edge.
    e.and2(p("KX_LAST"), p("KY_LAST"), p("KXKY_LAST"))
    e.and2(p("KXKY_LAST"), p("IC_LAST"), p("POINT_LAST_C"))
    e.dff(1060, 450, p("POINT_LAST_C"), p("POINT_LAST"))

    # --- shared memory interface (S02 is the only timing controller) ------
    e.decoder138(460, 355, [p("ADD_SEL0"), p("ADD_SEL1"), "GND"],
                 "MEM_nCE", "GND", "+5V",
                 [p("MEM_nCE_IN"), p("MEM_nCE_W"), p("MEM_nCE_OUT"),
                  p("MEM_nCE_B"), p("MEM_nCE_Q"), p("MEM_nCE_MC"), "NC", "NC"])
    e.inverter("C2_BUSY", p("BUSY_N"))
    e.buf541(450, 400, MX2[:8], [f"C2_ADDR{i}" for i in range(8)],
             oe=p("BUSY_N"))
    e.buf541(510, 400, MX2[8:], [f"C2_ADDR{i}" for i in range(8, 16)],
             oe=p("BUSY_N"))

    ust = e.add_ic("74xx:74HCT541", 950, 600)
    e.connect(ust, {
        "G1": "GND", "G2": "GND",
        "A0": "MEM_nCE", "A1": "MEM_nOE", "A2": "MEM_nWE",
        "A3": "MEM_ACK", "A4": "MEM_DONE", "A5": "MEM_BUSY",
        "A6": "GND", "A7": "GND",
        "Y0": p("MEM_STAT_nCE"), "Y1": p("MEM_STAT_nOE"),
        "Y2": p("MEM_STAT_nWE"), "Y3": p("MEM_STAT_ACK"),
        "Y4": p("MEM_STAT_DONE"), "Y5": p("MEM_STAT_BUSY"),
        "Y6": "NC", "Y7": "NC",
    })
    for k, st in enumerate(("nCE", "nOE", "nWE", "ACK", "DONE", "BUSY")):
        e.testpoint(1000, 620 + k * 22, p(f"MEM_STAT_{st}"))

    # --- notes ------------------------------------------------------------
    e.text(
        "Microcode: A[4:0]=ST, A5=START, A6=POINT_LAST, A7=MEM_ACK, A8=MEM_DONE, "
        "A9=REQ_DONE, A10=SP_LAST.  ROM1[4:0]=next state, D5=BUSY, D6=DONE, "
        "D7=ACC_CLR_N; ROM2 D0=MAC_EN, D1=REQ, D2=WE, D3=OUT_STB, D4=ADD_SEL0, "
        "D5=ADD_SEL1, D6/D7=0.  State sequence 0..12 as on S07.",
        430, 620, size=0.9,
    )
    e.text(
        "A/B path: A_LAT/B_LAT 574 + four hold-enabled 574 stages per operand "
        "(16x157) + eight 27C512 (two per lane).  PROD=A*B; the pipeline is "
        "frozen during S02 wait states.  CONV2 has 72 MACs (18 complete groups "
        "of four), so no padding is required.",
        430, 650, size=0.95,
    )
    e.text(
        "Requant: S15 computes Q = clamp(ACC >> 9, 0, 255) with a 74HCT574 output "
        "register and two 74HC74 handshake stages.  No bias, zero-point, multiplier "
        "or parameter port; symmetric quantization with bias trained to zero.",
        430, 680, size=0.95,
    )
    e.text(
        "Memory interface is shared: S02 drives MEM_nCE/nOE/nWE and MEM_ACK/DONE/BUSY "
        "globally; S11 merges C2_MEM_REQ/WE and maps the C2_MEM_nCE_* region code to "
        "MEM_SEL.  The 74HC138 is qualified by active-low MEM_nCE; C2_ADDR is driven "
        "only while C2_BUSY=1.",
        430, 710, size=0.95,
    )

    out = os.path.join(PROJECT_DIR, "S08_Conv2.kicad_sch")
    e.flush_pending()
    e.write(out)
    return out


def main() -> int:
    write_block_library(BLOCK_LIB)
    print("wrote", build_conv2())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
