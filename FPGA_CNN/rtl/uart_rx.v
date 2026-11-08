// UART receiver, 8N1, 16x-free (mid-bit sampling).
//
// CLK_HZ/BAUD must be >= 8 for reliable sampling; 50 MHz / 115200 = 434.
`timescale 1ns/1ps
module uart_rx #(
    parameter integer CLK_HZ = 50_000_000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx,
    output reg  [7:0] data,
    output reg        valid
);
    localparam integer DIV  = CLK_HZ / BAUD;
    localparam integer HALF = DIV / 2;

    // two-flop synchroniser
    reg [2:0] sync;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) sync <= 3'b111;
        else        sync <= {sync[1:0], rx};
    wire rx_s = sync[2];

    localparam S_IDLE = 0, S_START = 1, S_DATA = 2, S_STOP = 3;
    reg [1:0]  st;
    reg [15:0] cnt;
    reg [2:0]  bitn;
    reg [7:0]  sh;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; cnt <= 0; bitn <= 0; sh <= 0;
            data <= 0; valid <= 0;
        end else begin
            valid <= 1'b0;
            case (st)
            S_IDLE: if (!rx_s) begin
                cnt <= HALF;            // sample the middle of the start bit
                st  <= S_START;
            end
            S_START: if (cnt == 0) begin
                if (rx_s) st <= S_IDLE; // false start
                else begin
                    cnt <= DIV - 1;
                    bitn <= 0;
                    st  <= S_DATA;
                end
            end else cnt <= cnt - 1'b1;
            S_DATA: if (cnt == 0) begin
                cnt <= DIV - 1;
                sh[bitn] <= rx_s;
                if (bitn == 3'd7) st <= S_STOP;
                else              bitn <= bitn + 1'b1;
            end else cnt <= cnt - 1'b1;
            S_STOP: if (cnt == 0) begin
                st <= S_IDLE;
                if (rx_s) begin         // stop bit must be high
                    data  <= sh;
                    valid <= 1'b1;
                end
            end else cnt <= cnt - 1'b1;
            endcase
        end
    end
endmodule
