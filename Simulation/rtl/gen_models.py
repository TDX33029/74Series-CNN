"""Generate models.v: one behavioural module per 74xx / memory package type.

The port list of every module is derived from analysis/pins.json, so the pin
numbers are exactly the KiCad symbol pin numbers used by output/top.net.  The
module bodies below are written against those numbers directly; each body has
a pin-name comment for review.

Power pins (VCC/GND/Vdd/VSS) and no-connect pins are not modelled as ports.
They are skipped by gen_rtl.py as well, so a package instance only connects the
pins that carry signal.

Run:
    python gen_models.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.abspath(os.path.join(HERE, "..", "analysis"))
PINS_JSON = os.path.join(ANALYSIS, "pins.json")
OUT = os.path.join(HERE, "models.v")
PORTS_JSON = os.path.join(HERE, "model_ports.json")

POWER_NAMES = {"VCC", "GND", "VDD", "VSS", "Vdd", "Vss"}
POWER_TYPES = {"power_in", "no_connect"}


def exposed_pins(part: dict) -> list[tuple[int, dict]]:
    out = []
    for num, rec in part["pins"].items():
        if rec["etype"] in POWER_TYPES:
            continue
        if rec["name"] in POWER_NAMES:
            continue
        out.append((int(num), rec))
    return sorted(out)


BODIES = {
    # ------------------------------------------------------------------ gates
    ("74xx", "74HC00"): """
  // quad 2-input NAND: (1,2)->3 (4,5)->6 (9,10)->8 (12,13)->11
  assign p3  = ~(p1  & p2);
  assign p6  = ~(p4  & p5);
  assign p8  = ~(p9  & p10);
  assign p11 = ~(p12 & p13);
""",
    ("74xx", "74HC02"): """
  // quad 2-input NOR: (2,3)->1 (5,6)->4 (8,9)->10 (11,12)->13
  assign p1  = ~(p2  | p3);
  assign p4  = ~(p5  | p6);
  assign p10 = ~(p8  | p9);
  assign p13 = ~(p11 | p12);
""",
    ("74xx", "74HC04"): """
  // hex inverter: 1->2 3->4 5->6 9->8 11->10 13->12
  assign p2  = ~p1;
  assign p4  = ~p3;
  assign p6  = ~p5;
  assign p8  = ~p9;
  assign p10 = ~p11;
  assign p12 = ~p13;
""",
    ("74xx", "74HC08"): """
  // quad 2-input AND: (1,2)->3 (4,5)->6 (9,10)->8 (12,13)->11
  assign p3  = p1  & p2;
  assign p6  = p4  & p5;
  assign p8  = p9  & p10;
  assign p11 = p12 & p13;
""",
    ("74xx", "74HC32"): """
  // quad 2-input OR: (1,2)->3 (4,5)->6 (9,10)->8 (12,13)->11
  assign p3  = p1  | p2;
  assign p6  = p4  | p5;
  assign p8  = p9  | p10;
  assign p11 = p12 | p13;
""",
    # ------------------------------------------------------------- flip-flops
    ("74xx", "74HC74"): """
  // dual D-FF with async ~R/~S: A(1 ~R,2 D,3 C,4 ~S,5 Q,6 ~Q)
  //                           B(13 ~R,12 D,11 C,10 ~S,9 Q,8 ~Q)
  reg qa, qb;
  always @(posedge p3 or negedge p1 or negedge p4)
    if (!p1) qa <= 1'b0;
    else if (!p4) qa <= 1'b1;
    else qa <= p2;
  always @(posedge p11 or negedge p13 or negedge p10)
    if (!p13) qb <= 1'b0;
    else if (!p10) qb <= 1'b1;
    else qb <= p12;
  assign p5 = qa;
  assign p6 = ~qa;
  assign p9 = qb;
  assign p8 = ~qb;
""",
    ("74xx", "74HCT273"): """
  // octal D-FF, async clear: ~MR=1 CP=11
  // D0..D7 = 3,4,7,8,13,14,17,18   Q0..Q7 = 2,5,6,9,12,15,16,19
  reg [7:0] q;
  wire [7:0] d = {p18, p17, p14, p13, p8, p7, p4, p3};
  always @(posedge p11 or negedge p1)
    if (!p1) q <= 8'h00;
    else     q <= d;
  assign p2  = q[0];
  assign p5  = q[1];
  assign p6  = q[2];
  assign p9  = q[3];
  assign p12 = q[4];
  assign p15 = q[5];
  assign p16 = q[6];
  assign p19 = q[7];
""",
    ("74xx", "74HCT574"): """
  // octal D-FF, 3-state: OE=1 (active low) CP=11
  // D0..D7 = 2..9   Q0..Q7 = 19,18,17,16,15,14,13,12
  // 74HCT574 has no asynchronous clear.  Real devices power up in an
  // unknown state; the model starts at 0 so the supervisor ROM address is
  // defined before the first stage writes these registers.
  reg [7:0] q = 8'h00;
  wire [7:0] d = {p9, p8, p7, p6, p5, p4, p3, p2};
  always @(posedge p11)
    q <= d;
  assign p19 = p1 ? 1'bz : q[0];
  assign p18 = p1 ? 1'bz : q[1];
  assign p17 = p1 ? 1'bz : q[2];
  assign p16 = p1 ? 1'bz : q[3];
  assign p15 = p1 ? 1'bz : q[4];
  assign p14 = p1 ? 1'bz : q[5];
  assign p13 = p1 ? 1'bz : q[6];
  assign p12 = p1 ? 1'bz : q[7];
""",
    # --------------------------------------------------------------- counters
    ("74xx", "74HC161"): """
  // synchronous 4-bit counter: ~MR=1 CP=2 ~PE=9 CEP=7 CET=10
  // D0..D3 = 3..6   Q0..Q3 = 14,13,12,11   TC=15
  reg [3:0] q;
  wire [3:0] d = {p6, p5, p4, p3};
  always @(posedge p2 or negedge p1)
    if (!p1)            q <= 4'h0;
    else if (!p9)       q <= d;
    else if (p7 & p10)  q <= q + 4'd1;
  assign p14 = q[0];
  assign p13 = q[1];
  assign p12 = q[2];
  assign p11 = q[3];
  assign p15 = p10 & (q == 4'hF);
""",
    # ---------------------------------------------------------------- mux/buf
    ("74xx", "74HC157"): """
  // quad 2:1 mux, active-low enable E=15, select S=1
  // a: I0=2 I1=3 Z=4   b: I0=5 I1=6 Z=7
  // c: I0=11 I1=10 Z=9 d: I0=14 I1=13 Z=12
  assign p4  = p15 ? 1'b0 : (p1 ? p3  : p2);
  assign p7  = p15 ? 1'b0 : (p1 ? p6  : p5);
  assign p9  = p15 ? 1'b0 : (p1 ? p10 : p11);
  assign p12 = p15 ? 1'b0 : (p1 ? p13 : p14);
""",
    ("74xx", "74HCT541"): """
  // octal buffer, active-low enables G1=1 G2=19
  // A0..A7 = 2..9   Y0..Y7 = 18,17,16,15,14,13,12,11
  wire en = ~(p1 | p19);
  assign p18 = en ? p2 : 1'bz;
  assign p17 = en ? p3 : 1'bz;
  assign p16 = en ? p4 : 1'bz;
  assign p15 = en ? p5 : 1'bz;
  assign p14 = en ? p6 : 1'bz;
  assign p13 = en ? p7 : 1'bz;
  assign p12 = en ? p8 : 1'bz;
  assign p11 = en ? p9 : 1'bz;
""",
    ("74xx", "74HC245"): """
  // octal transceiver: DIR=1 A->B (pin 1), active-low CE=19
  // A0..A7 = 2..9   B0..B7 = 18,17,16,15,14,13,12,11
  wire en = ~p19;
  assign p18 = (en &  p1) ? p2 : 1'bz;
  assign p17 = (en &  p1) ? p3 : 1'bz;
  assign p16 = (en &  p1) ? p4 : 1'bz;
  assign p15 = (en &  p1) ? p5 : 1'bz;
  assign p14 = (en &  p1) ? p6 : 1'bz;
  assign p13 = (en &  p1) ? p7 : 1'bz;
  assign p12 = (en &  p1) ? p8 : 1'bz;
  assign p11 = (en &  p1) ? p9 : 1'bz;
  assign p2  = (en & ~p1) ? p18 : 1'bz;
  assign p3  = (en & ~p1) ? p17 : 1'bz;
  assign p4  = (en & ~p1) ? p16 : 1'bz;
  assign p5  = (en & ~p1) ? p15 : 1'bz;
  assign p6  = (en & ~p1) ? p14 : 1'bz;
  assign p7  = (en & ~p1) ? p13 : 1'bz;
  assign p8  = (en & ~p1) ? p12 : 1'bz;
  assign p9  = (en & ~p1) ? p11 : 1'bz;
""",
    # --------------------------------------------------------------- decoders
    ("74xx", "74HC138"): """
  // 3-to-8 decoder, active-low outputs
  // A0..A2 = 1,2,3   ~E0=4 ~E1=5 E2=6   ~Y0..~Y7 = 15,14,13,12,11,10,9,7
  wire [2:0] sel = {p3, p2, p1};
  wire en = ~p4 & ~p5 & p6;
  assign p15 = (en & (sel == 3'd0)) ? 1'b0 : 1'b1;
  assign p14 = (en & (sel == 3'd1)) ? 1'b0 : 1'b1;
  assign p13 = (en & (sel == 3'd2)) ? 1'b0 : 1'b1;
  assign p12 = (en & (sel == 3'd3)) ? 1'b0 : 1'b1;
  assign p11 = (en & (sel == 3'd4)) ? 1'b0 : 1'b1;
  assign p10 = (en & (sel == 3'd5)) ? 1'b0 : 1'b1;
  assign p9  = (en & (sel == 3'd6)) ? 1'b0 : 1'b1;
  assign p7  = (en & (sel == 3'd7)) ? 1'b0 : 1'b1;
""",
    ("74xx", "74HC238"): """
  // 3-to-8 decoder, active-high outputs
  // A0..A2 = 1,2,3   ~E1=4 ~E2=5 E3=6   Y0..Y7 = 15,14,13,12,11,10,9,7
  wire [2:0] sel = {p3, p2, p1};
  wire en = ~p4 & ~p5 & p6;
  assign p15 = en & (sel == 3'd0);
  assign p14 = en & (sel == 3'd1);
  assign p13 = en & (sel == 3'd2);
  assign p12 = en & (sel == 3'd3);
  assign p11 = en & (sel == 3'd4);
  assign p10 = en & (sel == 3'd5);
  assign p9  = en & (sel == 3'd6);
  assign p7  = en & (sel == 3'd7);
""",
    ("74xx", "74LS148"): """
  // 8-to-3 priority encoder, active-low inputs/outputs
  // I0..I7 = 10,11,12,13,1,2,3,4   EI=5
  // S0=9 S1=7 S2=6   GS=14 EO=15
  reg [2:0] code;
  reg gs, eo;
  always @* begin
    if (p5)            begin code = 3'b111; gs = 1'b1; eo = 1'b1; end
    else if (!p4)      begin code = ~3'd7;  gs = 1'b0; eo = 1'b1; end
    else if (!p3)      begin code = ~3'd6;  gs = 1'b0; eo = 1'b1; end
    else if (!p2)      begin code = ~3'd5;  gs = 1'b0; eo = 1'b1; end
    else if (!p1)      begin code = ~3'd4;  gs = 1'b0; eo = 1'b1; end
    else if (!p13)     begin code = ~3'd3;  gs = 1'b0; eo = 1'b1; end
    else if (!p12)     begin code = ~3'd2;  gs = 1'b0; eo = 1'b1; end
    else if (!p11)     begin code = ~3'd1;  gs = 1'b0; eo = 1'b1; end
    else if (!p10)     begin code = ~3'd0;  gs = 1'b0; eo = 1'b1; end
    else               begin code = 3'b111; gs = 1'b1; eo = 1'b0; end
  end
  assign p9  = code[0];
  assign p7  = code[1];
  assign p6  = code[2];
  assign p14 = gs;
  assign p15 = eo;
""",
    # ------------------------------------------------------------- arithmetic
    ("74xx", "74HC283"): """
  // 4-bit binary adder: A1..A4 = 5,3,14,12  B1..B4 = 6,2,15,11
  // S1..S4 = 4,1,13,10   C0=7   C4=9
  wire [3:0] a = {p12, p14, p3, p5};
  wire [3:0] b = {p11, p15, p2, p6};
  wire [4:0] s = a + b + {4'b0000, p7};
  assign p4  = s[0];
  assign p1  = s[1];
  assign p13 = s[2];
  assign p10 = s[3];
  assign p9  = s[4];
""",
    ("74xx", "74HC85"): """
  // 4-bit magnitude comparator
  // A0..A3 = 10,12,13,15   B0..B3 = 9,11,14,1
  // Ia<b=2 Ia=b=3 Ia>b=4   Oa>b=5 Oa=b=6 Oa<b=7
  wire [3:0] a = {p15, p13, p12, p10};
  wire [3:0] b = {p1,  p14, p11, p9};
  assign p6 = (a == b) & p3;
  assign p5 = (a >  b) | ((a == b) & p4);
  assign p7 = (a <  b) | ((a == b) & p2);
""",
    ("74xx", "74HC688"): """
  // 8-bit identity comparator, active-low enable G=1, active-low output P=R=19
  // P0..P7 = 2,4,6,8,11,13,15,17   R0..R7 = 3,5,7,9,12,14,16,18
  wire [7:0] p = {p17, p15, p13, p11, p8, p6, p4, p2};
  wire [7:0] r = {p18, p16, p14, p12, p9, p7, p5, p3};
  assign p19 = p1 ? 1'b1 : ((p == r) ? 1'b0 : 1'b1);
""",
    # ---------------------------------------------------------------- memories
    ("Memory_EPROM", "27C512"): """
  // 64K x 8 OTP EPROM.  A0..A15 = 10,9,8,7,6,5,4,3,25,24,21,23,2,26,27,1
  // D0..D7 = 11,12,13,15,16,17,18,19   ~CE=20 ~OE=22
  parameter INIT = "";
  reg [7:0] mem [0:65535];
  integer i;
  initial begin
    for (i = 0; i < 65536; i = i + 1) mem[i] = 8'h00;
    if (INIT != "") $readmemh(INIT, mem);
  end
  wire [15:0] a_raw = {p1, p27, p26, p2, p23, p21, p24, p25,
                       p3, p4, p5, p6, p7, p8, p9, p10};
  // X-optimistic decode: an unknown address bit reads as 0.  Real hardware
  // always has a definite level here; this only avoids 4-state X-lock while
  // the power-up state of the DONE/REQ registers is still unknown.
  reg [15:0] a;
  integer j;
  always @* for (j = 0; j < 16; j = j + 1) a[j] = (a_raw[j] === 1'b1);
  wire oe = ~p20 & ~p22;
  wire [7:0] dout = mem[a];
  assign p11 = oe ? dout[0] : 1'bz;
  assign p12 = oe ? dout[1] : 1'bz;
  assign p13 = oe ? dout[2] : 1'bz;
  assign p15 = oe ? dout[3] : 1'bz;
  assign p16 = oe ? dout[4] : 1'bz;
  assign p17 = oe ? dout[5] : 1'bz;
  assign p18 = oe ? dout[6] : 1'bz;
  assign p19 = oe ? dout[7] : 1'bz;
""",
    ("Memory_EEPROM", "28C256"): """
  // 32K x 8 EEPROM.  A0..A14 = 10,9,8,7,6,5,4,3,25,24,21,23,2,26,1
  // D0..D7 = 11,12,13,15,16,17,18,19   ~CS=20 ~OE=22 ~WE=27
  parameter INIT = "";
  reg [7:0] mem [0:32767];
  integer i;
  initial begin
    for (i = 0; i < 32768; i = i + 1) mem[i] = 8'h00;
    if (INIT != "") $readmemh(INIT, mem);
  end
  wire [14:0] a_raw = {p1, p26, p2, p23, p21, p24, p25,
                       p3, p4, p5, p6, p7, p8, p9, p10};
  reg [14:0] a;
  integer j;
  always @* for (j = 0; j < 15; j = j + 1) a[j] = (a_raw[j] === 1'b1);
  wire [7:0] din = {p19, p18, p17, p16, p15, p13, p12, p11};
  wire oe = ~p20 & ~p22 & p27;
  wire [7:0] dout = mem[a];
  assign p11 = oe ? dout[0] : 1'bz;
  assign p12 = oe ? dout[1] : 1'bz;
  assign p13 = oe ? dout[2] : 1'bz;
  assign p15 = oe ? dout[3] : 1'bz;
  assign p16 = oe ? dout[4] : 1'bz;
  assign p17 = oe ? dout[5] : 1'bz;
  assign p18 = oe ? dout[6] : 1'bz;
  assign p19 = oe ? dout[7] : 1'bz;
  always @(posedge p27)
    if (!p20) mem[a] <= din;
""",
    ("Memory_RAM", "CY62256-70PC"): """
  // 32K x 8 SRAM (MEM_BOOT swap for 28C256; pin-compatible DIP-28,
  // wired 1=A14 26=A13 20=~CE 22=~OE 27=~WE).
  parameter INIT = "";
  reg [7:0] mem [0:32767];
  integer i;
  initial begin
    for (i = 0; i < 32768; i = i + 1) mem[i] = 8'h00;
    if (INIT != "") $readmemh(INIT, mem);
  end
  wire [14:0] a_raw = {p1, p26, p2, p23, p21, p24, p25,
                       p3, p4, p5, p6, p7, p8, p9, p10};
  reg [14:0] a;
  integer j;
  always @* for (j = 0; j < 15; j = j + 1) a[j] = (a_raw[j] === 1'b1);
  wire [7:0] din = {p19, p18, p17, p16, p15, p13, p12, p11};
  wire oe = ~p20 & ~p22 & p27;
  wire [7:0] dout = mem[a];
  assign p11 = oe ? dout[0] : 1'bz;
  assign p12 = oe ? dout[1] : 1'bz;
  assign p13 = oe ? dout[2] : 1'bz;
  assign p15 = oe ? dout[3] : 1'bz;
  assign p16 = oe ? dout[4] : 1'bz;
  assign p17 = oe ? dout[5] : 1'bz;
  assign p18 = oe ? dout[6] : 1'bz;
  assign p19 = oe ? dout[7] : 1'bz;
  always @(posedge p27)
    if (!p20) mem[a] <= din;
""",
    ("Memory_RAM", "HY6264AxP"): """
  // 8K x 8 SRAM.  A0..A12 = 10,9,8,7,6,5,4,3,25,24,21,23,2
  // I/O0..7 = 11,12,13,15,16,17,18,19   ~CS1=20 CS2=26 ~OE=22 ~WE=27
  parameter INIT = "";
  reg [7:0] mem [0:8191];
  integer i;
  initial begin
    for (i = 0; i < 8192; i = i + 1) mem[i] = 8'h00;
    if (INIT != "") $readmemh(INIT, mem);
  end
  wire [12:0] a_raw = {p2, p23, p21, p24, p25,
                       p3, p4, p5, p6, p7, p8, p9, p10};
  reg [12:0] a;
  integer j;
  always @* for (j = 0; j < 13; j = j + 1) a[j] = (a_raw[j] === 1'b1);
  wire [7:0] din = {p19, p18, p17, p16, p15, p13, p12, p11};
  wire sel = ~p20 & p26;
  wire oe = sel & ~p22 & p27;
  wire [7:0] dout = mem[a];
  assign p11 = oe ? dout[0] : 1'bz;
  assign p12 = oe ? dout[1] : 1'bz;
  assign p13 = oe ? dout[2] : 1'bz;
  assign p15 = oe ? dout[3] : 1'bz;
  assign p16 = oe ? dout[4] : 1'bz;
  assign p17 = oe ? dout[5] : 1'bz;
  assign p18 = oe ? dout[6] : 1'bz;
  assign p19 = oe ? dout[7] : 1'bz;
  always @(posedge p27)
    if (sel) mem[a] <= din;
""",
    # --------------------------------------------------------------- clock can
    ("Oscillator", "ASE-xxxMHz"): """
  // 4-pin active oscillator: EN=1 OUT=3 (GND/Vdd are power pins)
  parameter HALF_NS = 62.5;   // 8.000 MHz
  reg clk = 1'b0;
  always #(HALF_NS) clk = ~clk;
  assign p3 = clk;
""",
}

# 74HCT245 shares the 74HC245 body.
BODIES[("74xx", "74HCT245")] = BODIES[("74xx", "74HC245")]


def main() -> int:
    parts = json.load(open(PINS_JSON, encoding="utf-8"))["parts"]

    lines = [
        "// Generated by gen_models.py - do not edit by hand.",
        "// Behavioural models keyed by KiCad symbol pin number.",
        "`timescale 1ns/1ps",
        "",
    ]
    ports_out = {}

    for key in sorted(BODIES):
        lib, part = key
        full = f"{lib}:{part}"
        if full not in parts:
            # device family not present in the current netlist: skip quietly
            # (kept in the table for other design states, e.g. AT28C256)
            continue
        pins = exposed_pins(parts[full])
        mod = "m_" + f"{lib}_{part}".replace("-", "_")
        ports = [f"p{n}" for n, _ in pins]
        ports_out[full] = [int(n) for n, _ in pins]

        lines.append(f"// {full}: " + ", ".join(
            f"{n}={rec['name'] or '-'}" for n, rec in pins))
        lines.append(f"module {mod} (" + ", ".join(ports) + ");")
        for n, rec in pins:
            etype = rec["etype"]
            kw = "inout" if etype in ("tri_state", "bidirectional") else (
                "input" if etype == "input" else "output")
            lines.append(f"  {kw} p{n};")
        lines.append(BODIES[key].rstrip("\n"))
        lines.append("endmodule")
        lines.append("")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    with open(PORTS_JSON, "w", encoding="utf-8") as f:
        json.dump(ports_out, f, indent=1, sort_keys=True)
        f.write("\n")

    print(f"wrote {OUT} ({len(BODIES)} modules)")
    print(f"wrote {PORTS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
