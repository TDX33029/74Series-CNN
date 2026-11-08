module lic_test (
    input  wire       clk,
    input  wire       nrst,
    output reg  [7:0] cnt
);
    always @(posedge clk or negedge nrst)
        if (!nrst) cnt <= 8'h00;
        else       cnt <= cnt + 8'd1;
endmodule
