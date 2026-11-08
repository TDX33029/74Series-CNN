// probe_top.v - minimal free-running counter blinker for Quartus toolchain probe.
// No board-specific pin assignments. Board clock assumed to be 50 MHz,
// so led[3] toggles at 50e6 / 2^26 / 2 ~= 0.37 Hz.

module probe_top (
    input  wire       clk,
    output wire [3:0] led
);

    reg [31:0] counter;

    always @(posedge clk) begin
        counter <= counter + 32'd1;
    end

    assign led = counter[27:24];

endmodule
