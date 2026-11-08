// UART transmitter, 8N1.
`timescale 1ns/1ps
module uart_tx #(
    parameter integer CLK_HZ = 50_000_000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data,
    input  wire       send,
    output reg        busy,
    output reg        tx
);
    localparam integer DIV = CLK_HZ / BAUD;

    reg [9:0]  sh;      // {stop, data[7:0], start}
    reg [15:0] cnt;
    reg [3:0]  bitn;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0; tx <= 1'b1; cnt <= 0; bitn <= 0; sh <= 10'h3FF;
        end else if (!busy) begin
            tx <= 1'b1;
            if (send) begin
                sh   <= {1'b1, data, 1'b0};
                bitn <= 4'd0;
                cnt  <= DIV - 1;
                busy <= 1'b1;
                tx   <= 1'b0;           // start bit
            end
        end else if (cnt == 0) begin
            cnt <= DIV - 1;
            if (bitn == 4'd9) begin     // stop bit finished
                busy <= 1'b0;
                tx   <= 1'b1;
            end else begin
                bitn <= bitn + 1'b1;
                tx   <= sh[bitn + 1'b1];
            end
        end else begin
            cnt <= cnt - 1'b1;
        end
    end
endmodule
