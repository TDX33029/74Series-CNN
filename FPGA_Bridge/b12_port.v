// B12 load-port sequencer (S10 J6 / "PARAM PROG" 2x20 header).
//
// The 74-series board exposes a static parallel port: LOAD_EN=1 tri-states
// the engines and lets this block drive ADDR, MEM_SEL, DATA and the
// H_LOAD_nWE / H_LOAD_nOE strobes straight into the S04 memories.  Both
// strobes are produced as clean, slow pulses so a 6264 SRAM and a 28C256
// EEPROM both see valid timings even from a 50 MHz FPGA clock.
//
// One byte per `start`/`done` handshake:
//   wr=1 : d = wdata, nWE low for T_STROBE clocks
//   wr=0 : d released, nOE low for T_STROBE clocks, rdata valid at `done`
`timescale 1ns/1ps
module b12_port #(
    parameter integer T_SETUP  = 8,     // clocks of address setup
    parameter integer T_STROBE = 16,    // nWE/nOE low time
    parameter integer T_HOLD   = 8      // clocks after the strobe
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        start,
    input  wire        wr,
    input  wire [4:0]  sel,
    input  wire [15:0] addr,
    input  wire [7:0]  wdata,
    output reg  [7:0]  rdata,
    output reg         done,

    // level-translator control (74LVC245A between H_D and the FPGA pins):
    //   dir   = 1 for a read  (board -> FPGA), 0 for a write
    //   oe_n  = 0 while a transaction is active
    output reg         dir,
    output wire        oe_n,

    inout  wire [7:0]  d,
    output reg  [15:0] a,
    output reg  [4:0]  s,
    output reg         en,
    output reg         nwe,
    output reg         noe
);
    assign d = (en && wr) ? wdata : 8'bz;
    assign oe_n = ~en;

    localparam S_IDLE = 0, S_SETUP = 1, S_STROBE = 2, S_HOLD = 3;
    reg [1:0]  st;
    reg [15:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; cnt <= 0;
            a <= 0; s <= 0; en <= 1'b0; nwe <= 1'b1; noe <= 1'b1;
            rdata <= 0; done <= 1'b0; dir <= 1'b0;
        end else begin
            done <= 1'b0;
            case (st)
            S_IDLE: if (start) begin
                a   <= addr;
                s   <= sel;
                dir <= ~wr;         // set direction before the translator turns on
                en  <= 1'b1;
                nwe <= 1'b1;
                noe <= 1'b1;
                cnt <= T_SETUP - 1;
                st  <= S_SETUP;
            end
            S_SETUP: if (cnt == 0) begin
                cnt <= T_STROBE - 1;
                if (wr) nwe <= 1'b0;
                else    noe <= 1'b0;
                st  <= S_STROBE;
            end else cnt <= cnt - 1'b1;
            S_STROBE: if (cnt == 0) begin
                if (wr) nwe <= 1'b1;
                else begin
                    rdata <= d;         // capture while nOE is still low
                    noe   <= 1'b1;
                end
                cnt <= T_HOLD - 1;
                st  <= S_HOLD;
            end else cnt <= cnt - 1'b1;
            S_HOLD: if (cnt == 0) begin
                en   <= 1'b0;
                noe  <= 1'b1;
                nwe  <= 1'b1;
                done <= 1'b1;
                st   <= S_IDLE;
            end else cnt <= cnt - 1'b1;
            endcase
        end
    end
endmodule
