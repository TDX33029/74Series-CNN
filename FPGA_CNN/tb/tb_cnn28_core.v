// Bit-exact test of cnn28_core against the integer reference model.
//
// Loads weights / biases / qparams / image through the host byte port,
// runs the core, and compares the ten int32 logits with the values
// exported by FPGA_CNN/train_export.py.  Vector k is the first MNIST test
// image of class k, so the expected argmax is k.
//
// Run from FPGA_CNN/sim (see run_core_sim.sh):
//   vlog ../rtl/cnn28_core.v ../tb/tb_cnn28_core.v
//   vsim -c tb_cnn28_core -do "run -all; quit -f"
`timescale 1ns/1ps

module tb_cnn28_core;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;                 // 100 MHz: timing only

    reg         h_we = 0;
    reg         h_addr_ok = 1;
    reg  [15:0] h_addr = 0;
    reg  [7:0]  h_wdata = 0;
    wire [7:0]  h_rdata;
    reg         start = 0;
    wire        busy, done;
    wire [3:0]  result;

    cnn28_core dut (
        .clk(clk), .rst_n(rst_n),
        .h_we(h_we), .h_addr_ok(h_addr_ok), .h_addr(h_addr),
        .h_wdata(h_wdata), .h_rdata(h_rdata),
        .start(start), .busy(busy), .done(done), .result(result));

    reg [7:0]  w1 [0:199];
    reg [7:0]  w2 [0:1151];
    reg [7:0]  w3 [0:12799];
    reg [7:0]  w4 [0:319];
    reg [31:0] b1 [0:7];
    reg [31:0] b2 [0:15];
    reg [31:0] b3 [0:31];
    reg [31:0] b4 [0:9];
    reg [7:0]  qp [0:1055];
    reg [7:0]  img [0:783];
    reg [31:0] expl [0:9];

    task wr(input [15:0] a, input [7:0] d);
        begin
            @(negedge clk); h_we = 1; h_addr = a; h_wdata = d;
            @(negedge clk); h_we = 0;
        end
    endtask

    task rd(input [15:0] a, output [7:0] d);
        begin
            @(negedge clk); h_addr = a;
            @(negedge clk); d = h_rdata;      // RAM data, one cycle later
        end
    endtask

    integer i, k, errors = 0, e0, argmax_i, cyc, cyc0;
    reg [7:0]  b0, b1r, b2r, b3r;
    reg [31:0] got, want, bestv;

    initial begin
        $display("=== cnn28_core bit-exact test ===");
        $readmemh("../../weights/x28/conv1_weight.hex", w1);
        $readmemh("../../weights/x28/conv2_weight.hex", w2);
        $readmemh("../../weights/x28/fc1_weight.hex", w3);
        $readmemh("../../weights/x28/fc2_weight.hex", w4);
        $readmemh("../../weights/x28/conv1_bias.hex", b1);
        $readmemh("../../weights/x28/conv2_bias.hex", b2);
        $readmemh("../../weights/x28/fc1_bias.hex", b3);
        $readmemh("../../weights/x28/fc2_bias.hex", b4);
        $readmemh("../../weights/x28/qparams.hex", qp);

        #100 rst_n = 1'b1;
        @(negedge clk);

        // ---- parameters ------------------------------------------------
        for (i = 0; i < 200;   i = i + 1) wr(16'h0400 + i, w1[i]);
        for (i = 0; i < 1152;  i = i + 1) wr(16'h0600 + i, w2[i]);
        for (i = 0; i < 12800; i = i + 1) wr(16'h0B00 + i, w3[i]);
        for (i = 0; i < 320;   i = i + 1) wr(16'h3D00 + i, w4[i]);
        for (i = 0; i < 8;     i = i + 1) begin
            wr(16'h6200 + 4*i + 0, b1[i][7:0]);
            wr(16'h6200 + 4*i + 1, b1[i][15:8]);
            wr(16'h6200 + 4*i + 2, b1[i][23:16]);
            wr(16'h6200 + 4*i + 3, b1[i][31:24]);
        end
        for (i = 0; i < 16;    i = i + 1) begin
            wr(16'h6220 + 4*i + 0, b2[i][7:0]);
            wr(16'h6220 + 4*i + 1, b2[i][15:8]);
            wr(16'h6220 + 4*i + 2, b2[i][23:16]);
            wr(16'h6220 + 4*i + 3, b2[i][31:24]);
        end
        for (i = 0; i < 32;    i = i + 1) begin
            wr(16'h6260 + 4*i + 0, b3[i][7:0]);
            wr(16'h6260 + 4*i + 1, b3[i][15:8]);
            wr(16'h6260 + 4*i + 2, b3[i][23:16]);
            wr(16'h6260 + 4*i + 3, b3[i][31:24]);
        end
        for (i = 0; i < 10;    i = i + 1) begin
            wr(16'h62E0 + 4*i + 0, b4[i][7:0]);
            wr(16'h62E0 + 4*i + 1, b4[i][15:8]);
            wr(16'h62E0 + 4*i + 2, b4[i][23:16]);
            wr(16'h62E0 + 4*i + 3, b4[i][31:24]);
        end
        for (i = 0; i < 1056;  i = i + 1) wr(16'h6400 + i, qp[i]);
        $display("parameters loaded");

        // ---- eight test images ----------------------------------------
        for (k = 0; k < 8; k = k + 1) begin
            case (k)
            0: begin $readmemh("../../weights/x28/vectors/img_0.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_0.hex", expl); end
            1: begin $readmemh("../../weights/x28/vectors/img_1.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_1.hex", expl); end
            2: begin $readmemh("../../weights/x28/vectors/img_2.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_2.hex", expl); end
            3: begin $readmemh("../../weights/x28/vectors/img_3.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_3.hex", expl); end
            4: begin $readmemh("../../weights/x28/vectors/img_4.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_4.hex", expl); end
            5: begin $readmemh("../../weights/x28/vectors/img_5.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_5.hex", expl); end
            6: begin $readmemh("../../weights/x28/vectors/img_6.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_6.hex", expl); end
            default: begin $readmemh("../../weights/x28/vectors/img_7.hex", img);
                     $readmemh("../../weights/x28/vectors/logit_7.hex", expl); end
            endcase

            for (i = 0; i < 784; i = i + 1) wr(16'h0000 + i, img[i]);
            @(negedge clk) start = 1;
            @(negedge clk) start = 0;
            cyc0 = cyc;
            @(posedge done);
            $display("image %0d: %0d cycles", k, cyc - cyc0);

            e0 = errors;
            argmax_i = 0;
            bestv = 32'sh80000000;
            for (i = 0; i < 10; i = i + 1) begin
                rd(16'h6100 + 4*i + 0, b0);
                rd(16'h6100 + 4*i + 1, b1r);
                rd(16'h6100 + 4*i + 2, b2r);
                rd(16'h6100 + 4*i + 3, b3r);
                got = {b3r, b2r, b1r, b0};
                want = expl[i];
                if (got !== want) begin
                    $display("  class %0d: got %0d want %0d", i,
                             $signed(got), $signed(want));
                    errors = errors + 1;
                end
                if ($signed(got) > $signed(bestv)) begin
                    bestv = $signed(got);
                    argmax_i = i;
                end
            end
            if (argmax_i !== result) begin
                $display("  result %0d, expected argmax %0d", result, argmax_i);
                errors = errors + 1;
            end
            if (errors == e0)
                $display("PASS: image %0d logits match, argmax %0d", k, result);
            else
                $display("FAIL: image %0d (%0d errors so far)", k, errors);
        end

        if (errors == 0) $display("TB RESULT: PASS");
        else             $display("TB RESULT: FAIL (%0d)", errors);
        $finish;
    end

    always @(posedge clk) cyc <= cyc + 1;
    initial cyc = 0;

    initial begin
        #100_000_000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
