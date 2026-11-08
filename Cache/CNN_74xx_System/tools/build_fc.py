"""Build S09_FC.kicad_sch (FC1 + FC2 engine).

Run from the tools directory:
    python build_fc.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from build_conv1 import (BLOCK_LIB, EngineBuilder, GatePool, Grid, PROJECT_DIR,
                         write_block_library)


def build_fc() -> str:
    p = lambda s: f"FC_{s}"
    globals_ = (["CLK", "RESET_N", "FC1_START", "FC2_START", "FC1_DONE",
                 "FC2_DONE", "FC_BUSY", "FC_BUSY_N", "FC_SEL",
                 "MEM_nCE", "MEM_nOE", "MEM_nWE",
                 "MEM_ACK", "MEM_DONE", "MEM_BUSY",
                 "FC_MEM_REQ", "FC_MEM_WE"]
                + [f"DATA{i}" for i in range(8)]
                + [f"FC_ADDR{i}" for i in range(16)]
                + [f"FC_MEM_nCE_{x}" for x in ("IN", "W", "OUT", "B", "Q", "MC")]
                # Simple V2 Requant interface to S17_Requant_FC.
                + [f"FC_ACC{i}" for i in range(32)]
                + [f"FC_REQ_Q{i}" for i in range(8)]
                + ["FC_REQ_START", "FC_REQ_QSTB",
                   "FC_SAT_FLAG", "FC_REQ_BUSY", "FC_REQ_DONE"])
    e = EngineBuilder("FC", "S09_FC - FC1/FC2 Fully-Connected Engine",
                      paper="A0", global_nets=globals_)
    e.gates = GatePool(e, 20, 284, cols=5, dx=55.0, dy=20.0)
    e.text("S09  FULLY-CONNECTED ENGINE  (FC1 and FC2)", 15, 10, size=3.0, bold=True)
    e.text(
        "FC1: 400 -> 32, uint8 + ReLU.  FC2: 32 -> 10, signed32 unified scale, little-endian.\n"
        "FC1 loop: neuron(0..31) -> index(0..399); 400 MAC/neuron; 12800 MAC total.\n"
        "FC2 loop: neuron(0..9) -> index(0..31);   32 MAC/neuron;   320 MAC total.\n"
        "FC_SEL=0 selects FC1, FC_SEL=1 selects FC2 (valid with FC1_START/FC2_START).\n"
        "IN_ADDR = index                                   FC1 0..399, FC2 0..31\n"
        "W_ADDR  = FC1 neuron*400 + index (0..12799)        FC2 neuron*32 + index (0..319)\n"
        "OUT_ADDR= FC1 neuron (0..31)                       FC2 neuron*4 + byte, byte=0..3 LE\n"
        "Output order: FC1 neuron 0..31, one byte each; FC2 neuron 0..9, bytes 0..3 of each\n"
        "signed32 score in little-endian order (Q0 is the LSB byte).",
        15, 16, size=1.3,
    )
    e.text(
        "4x LUT_Mult_Unit (S_LUT_Mult_1 interface), 4-deep pixel/weight pipeline, "
        "4-product 18-bit adder tree, 32-bit accumulator (8x74HC283 + 4x74HCT574).",
        430, 748, size=1.15,
    )
    e.text(
        "Requant core is gate-level on S17_Requant_FC (no macro): FC1 uint8+ReLU,\n"
        "FC2 signed-32 unified scale with four little-endian bytes (QSTB x4).",
        430, 756, size=1.15,
    )

    # --- counters ---------------------------------------------------------
    ST = [p(f"ST{i}") for i in range(5)]
    NEURON = e.counter("NEURON", 20, 62, 5, 31, enable=p("NEURON_EN"),
                       pe_net=p("NEURON_PE_N"), vertical=True)
    e.comparator(100, 85, NEURON, 31, p("NEURON31"))
    e.comparator(100, 135, NEURON, 9, p("NEURON9"))
    e.mux_bank("NEURLAST", 175, 100, [p("NEURON31")], [p("NEURON9")],
               "FC_SEL", [p("NEURON_LAST")])

    INDEX = e.counter("INDEX", 240, 62, 9, 399, enable=p("MAC_EN"),
                      pe_net=p("INDEX_PE_N"), vertical=True)
    e.comparator(320, 65, INDEX, 399, p("INDEX399"))
    e.comparator(320, 135, INDEX, 31, p("INDEX31"))
    e.mux_bank("IDXLAST", 340, 200, [p("INDEX399")], [p("INDEX31")],
               "FC_SEL", [p("INDEX_LAST")])

    # FC2 writes four bytes per neuron: BYTE counts the completed writes
    # (state 10 with MEM_DONE) and resets while INDEX is at its last value.
    # The ROM A12 input tells the microcode when the fourth byte is done.
    # BYTE_EN is driven by the state-10 gate emitted further down.
    BYTE = e.counter("BYTE", 20, 200, 2, 3, enable=p("BYTE_EN"),
                     pe_net="+5V", reset=p("BYTE_RST_N"))
    e.comparator(100, 200, BYTE, 3, p("BYTE_LAST"))

    # --- loop enables -----------------------------------------------------
    e.and2("RESET_N", p("LOOP_CLR_N"), p("CNT_RESET_N"))
    e.and2(p("INDEX_LAST"), p("MAC_EN"), p("NEURON_EN"))
    # V11: the neuron counter must only reload on a MAC edge.  Gating with the
    # bare INDEX_LAST cleared NEURON in the wait state right after the last
    # MAC, so NEURON_LAST was already 0 during the final MAC and IMAGE_LAST
    # never set (the stage ran forever).  NEURON_EN is INDEX_LAST & MAC_EN.
    e.nand2(p("NEURON_LAST"), p("NEURON_EN"), p("NEURON_PE_N"))
    e.nand2(p("INDEX_LAST"), p("MAC_EN"), p("INDEX_PE_N"))
    # State-10 decode inverter (kept in the old BYTE_PE_N slot so the
    # reference sequence of the rest of the sheet is unchanged).
    e.inverter(p("ST10_N"), p("ST10"))
    e.inverter(p("INDEX_LAST"), p("NOT_INDEX_LAST"))
    e.and2(p("CNT_RESET_N"), p("NOT_INDEX_LAST"), p("BYTE_RST_N"))
    # POINT_LAST and IMAGE_LAST are registered in the FSM section.

    # --- addresses --------------------------------------------------------
    AG = Grid(15, 410, 62, 48, 4)
    INA = [p(f"IN_ADDR{i}") for i in range(9)]
    for i in range(9):
        INA[i] = INDEX[i]
    # Weight address: FC1 neuron*400, FC2 neuron*32, then +index.
    N400a = [p(f"N400a_{i}") for i in range(13)]
    e.chain_grid(AG, "N400a", ["GND"] * 8 + NEURON, ["GND"] * 7 + NEURON,
                 "GND", N400a, final_carry=p("N400a_13"))
    N400 = [p(f"N400_{i}") for i in range(14)]
    e.chain_grid(AG, "N400", N400a + [p("N400a_13")],
                 ["GND"] * 4 + NEURON + ["GND"], "GND", N400)
    N32 = ["GND"] * 5 + NEURON + ["GND"] * 4     # neuron*32, 14-bit field
    NW = [p(f"NW{i}") for i in range(14)]
    e.mux_bank("NWMUX", 250, 255, N400, N32, "FC_SEL", NW)
    WA = [p(f"W_ADDR{i}") for i in range(14)]
    e.chain_grid(AG, "WA", NW, INA + ["GND"] * 5, "GND", WA)

    # Output address: FC1 neuron, FC2 neuron*4+byte.
    FCOUT2 = [p(f"FCOUT2_{i}") for i in range(7)]
    e.chain_grid(AG, "FCOUT2", ["GND", "GND"] + NEURON, BYTE, "GND", FCOUT2)
    OUTA = [p(f"OUT_ADDR{i}") for i in range(7)]
    e.mux_bank("OUTMUX", 380, 790, NEURON + ["GND", "GND"], FCOUT2,
               "FC_SEL", OUTA, dx=70.0)

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

    # --- simple V2 requant interface (S17) --------------------------------
    # S17 implements FC1 Q = clamp(ACC >> 8, 0, 255) and FC2 raw signed32
    # four-byte output.  There is no bias, zero-point, multiplier or parameter
    # port; FC_SEL only selects the output/byte timing path.
    for k, nm in enumerate(("REQ_QSTB", "SAT_FLAG", "REQ_BUSY", "REQ_DONE")):
        e.testpoint(980, 540 + k * 22, p(nm), local=False)

    # Output data path: the OUTHOLD mux select is tied high, so the 574 is a
    # one-cycle pipeline for FC_REQ_Q (ACC byte selected by BYTE, or the FC1
    # clamp byte).  Keeping the original parts preserves all references.
    QBYTE = [p(f"REQ_Q{i}") for i in range(8)]
    OUTD = [p(f"OUT_D{i}") for i in range(8)]
    OUTQ = [p(f"OUT_DATA{i}") for i in range(8)]
    e.mux_bank("OUTHOLD", 330, 300, OUTQ, QBYTE, "+5V", OUTD, dx=70.0)
    e.reg574(330, 350, OUTD, OUTQ)
    e.transceiver245(395, 350, OUTQ, DATA, "+5V", p("OUT_BUF_N"))
    e.nand2(p("MEM_REQ"), p("MEM_WE"), p("OUT_BUF_N"))

    # --- address mux ------------------------------------------------------
    def pad(bits, n=16):
        return list(bits) + ["GND"] * (n - len(bits))
    MX1 = [p(f"MX1_{i}") for i in range(16)]
    MX2 = [p(f"MX2_{i}") for i in range(16)]
    e.mux_bank("MX1", 430, 220, pad(INA), pad(WA), p("ADD_SEL0"), MX1, dx=65.0)
    e.mux_bank("MX2", 610, 265, MX1, pad(OUTA), p("ADD_SEL1"), MX2, dx=65.0)

    # --- local FSM --------------------------------------------------------
    # 13 states: 0 reset, 1 idle, 2 addr IN, 3 wait A, 4 addr W, 5 wait B,
    # 6 shift, 7 accumulate, 8 requant request, 9 addr OUT, 10 write,
    # 11 next point, 12 done.
    START_ANY = p("START_ANY")
    e.or2("FC1_START", "FC2_START", START_ANY)
    # A12 = BYTE_LAST: the write state repeats four times for FC2 until the
    # last output byte has been stored (FC_SEL=0 ends after one byte).
    ROMA = ST + [START_ANY, p("POINT_LAST"), "MEM_ACK", "MEM_DONE",
                 p("REQ_DONE"), p("IMAGE_LAST"), "FC_SEL", p("BYTE_LAST")]
    MC1 = [p(f"MC1_{i}") for i in range(8)]
    MC2 = [p(f"MC2_{i}") for i in range(8)]
    e.rom27c512(445, 470, ROMA, MC1)
    e.rom27c512(515, 470, ROMA, MC2)
    e.reg273(425, 528, MC1[:5], ST, mr="RESET_N")
    e.reg574(475, 528, ["GND"] * 5 + MC1[5:8],
             ["NC"] * 5 + ["FC_BUSY", p("DONE_I"), p("ACC_CLR_N")])
    # S09 has no OUT_STB: FC_REQ_QSTB is only a status/testpoint here.
    CTRL = [p("MAC_EN"), p("MEM_REQ"), p("MEM_WE"), "NC",
            p("ADD_SEL0"), p("ADD_SEL1"), "NC", "NC"]
    e.reg574(535, 528, MC2, CTRL)
    # V8: the state decoder must not decode state 8 (requant, low three bits
    # = 000) as Y0, or LOOP_CLR_N clears NEURON/INDEX/BYTE once per output
    # point and the engine never leaves the first neuron.  Its used outputs
    # are states 0..7, so ST3 is the correct qualifier.
    e.decoder138(600, 528, ST[:3], "GND", p("ST3"), "+5V",
                 [p("LOOP_CLR_N"), "NC", "NC", p("WAIT_A_N"),
                  "NC", p("WAIT_B_N"), p("SHIFT_N"), p("ACC_N")])
    # Y2 is state 10 (E_WRITE); BYTE_EN pulses on each completed write
    # (V9: MEM_ACK, since E_WRITE now leaves one transfer state before DONE).
    # The two gates are deferred so no existing reference designator moves.
    e.decoder138(670, 528, ST[:3], "GND", "GND", p("ST3"),
                 [p("REQ_START_N"), "NC", p("ST10_N"), "NC",
                  "NC", "NC", "NC", "NC"])

    def _byte_en() -> None:
        e.and2(p("ST10"), "MEM_ACK", p("BYTE_EN"))
    e.pending_gates.append(_byte_en)
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

    # Point last: INDEX_LAST is a level at the last MAC; capture it before
    # the index counter wraps.  IMAGE_LAST is a held flag: set at the last
    # MAC of the last neuron, cleared by the next START pulse.
    e.dff(1060, 450, p("INDEX_LAST"), p("POINT_LAST"))
    e.and2(p("NEURON_LAST"), p("INDEX_LAST"), p("LAST_NEURON"))
    e.and2(p("LAST_NEURON"), p("MAC_EN"), p("LAST_POINT"))
    e.inverter(START_ANY, p("NSTART_ANY"))
    e.and2(p("IMAGE_LAST"), p("NSTART_ANY"), p("IMAGE_HOLD"))
    e.or2(p("LAST_POINT"), p("IMAGE_HOLD"), p("IMAGE_D"))
    e.dff(1060, 510, p("IMAGE_D"), p("IMAGE_LAST"))

    # done routing
    e.inverter("FC_SEL", p("NOT_FC_SEL"))
    e.and2(p("DONE_I"), p("NOT_FC_SEL"), "FC1_DONE")
    e.and2(p("DONE_I"), "FC_SEL", "FC2_DONE")

    # --- shared memory interface (S02 is the only timing controller) ------
    e.decoder138(460, 355, [p("ADD_SEL0"), p("ADD_SEL1"), "GND"],
                 "MEM_nCE", "GND", "+5V",
                 [p("MEM_nCE_IN"), p("MEM_nCE_W"), p("MEM_nCE_OUT"),
                  p("MEM_nCE_B"), p("MEM_nCE_Q"), p("MEM_nCE_MC"), "NC", "NC"])
    e.inverter("FC_BUSY", p("BUSY_N"))
    e.buf541(450, 400, MX2[:8], [f"FC_ADDR{i}" for i in range(8)],
             oe=p("BUSY_N"))
    e.buf541(510, 400, MX2[8:], [f"FC_ADDR{i}" for i in range(8, 16)],
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
        "FSM microcode: A[4:0]=ST, A5=START_ANY, A6=POINT_LAST, A7=MEM_ACK, "
        "A8=MEM_DONE, A9=REQ_DONE, A10=IMAGE_LAST, A11=FC_SEL.  ROM1[4:0]=next "
        "state, D5=BUSY, D6=DONE, D7=ACC_CLR_N; ROM2 D0=MAC_EN, D1=REQ, D2=WE, "
        "D3=NC (QSTB used directly), D4=ADD_SEL0, D5=ADD_SEL1, D6/D7=0.  "
        "DONE is routed to FC1_DONE/FC2_DONE by FC_SEL.  State sequence 0..12 "
        "as on S07.\n"
        "FC1: one S17 QSTB at BC=0.  FC2: QSTB at BC=0..3, DONE at BC=3; the "
        "byte counter (clocked by QSTB) addresses neuron*4+byte.",
        430, 620, size=0.95,
    )
    e.text(
        "A/B path: A_LAT/B_LAT 574 + four hold-enabled 574 stages per operand "
        "(16x157) + eight 27C512 (two per lane).  PROD=A*B; the pipeline is "
        "frozen during S02 wait states.  FC1 has 400 MACs and FC2 has 32, both "
        "exact multiples of four, so no padding is required.",
        430, 650, size=0.95,
    )
    e.text(
        "FC1 requant: Q = clamp(ACC >> 8, 0, 255), one QSTB at BC=0.  FC2: raw "
        "signed32 ACC, four QSTB pulses at BC=0..3 and DONE at BC=3; bytes "
        "are little-endian and Argmax compares the same scale.  No bias, no "
        "zero point, no M multiplier, no parameter loader.",
        430, 680, size=0.95,
    )
    e.text(
        "Memory interface is shared: S02 drives MEM_nCE/nOE/nWE and MEM_ACK/DONE/BUSY "
        "globally; S11 merges FC_MEM_REQ/WE and maps the FC_MEM_nCE_* region code with "
        "FC_SEL to the FC1 or FC2 memory window.  The 74HC138 is qualified by active-low "
        "MEM_nCE; FC_ADDR is driven only while FC_BUSY=1.",
        430, 710, size=0.95,
    )

    template_dir = os.path.join(PROJECT_DIR, "templates")
    os.makedirs(template_dir, exist_ok=True)
    out = os.path.join(template_dir, "S09_FC.kicad_sch")
    e.flush_pending()
    e.write(out)
    import json
    with open(os.path.join(PROJECT_DIR, "output", "s09_pins.json"), "w", encoding="utf-8") as f:
        json.dump([{"ref": sy.ref, "lib": sy.lib_id,
                    "pins": {n: list(xy) for n, xy in sy.pins.items()}}
                   for sy in e.sh.symbols], f, indent=1)
    return out


def main() -> int:
    write_block_library(BLOCK_LIB)
    print("wrote", build_fc())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
