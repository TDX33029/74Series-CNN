// End-to-end UART test for cnn28_top: download the whole model over the
// framed protocol, load one MNIST image, run INFER, and compare the ten
// logits with the reference export.
//
// Clock/baud are scaled (32 MHz / 4 Mbaud) so 16 KB of parameters simulate
// in tens of milliseconds; the modules are fully parameterised and the
// shipped build uses 50 MHz / 115200.
`timescale 1ns/1ps
module tb_cnn28_top;

    localparam integer CLK_HZ = 32_000_000;
    localparam integer BAUD   = 4_000_000;
    localparam integer DIV    = CLK_HZ / BAUD;
    localparam real    TCLK   = 1.0e9 / CLK_HZ;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #(TCLK / 2.0) clk = ~clk;

    reg  host_tx = 1'b1;
    wire dev_tx;

`ifdef NO_EXT_RESET
    // power-on reset build: no rst_n port at all
    cnn28_top #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .TIMEOUT_MS(1000)) dut (
        .clk(clk), .uart_rx(host_tx), .uart_tx(dev_tx));
`else
    cnn28_top #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .TIMEOUT_MS(1000)) dut (
        .clk(clk), .rst_n(rst_n), .uart_rx(host_tx), .uart_tx(dev_tx));
`endif

    // ------------------------------------------------------------ data
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
    reg [7:0]  bb [0:263];
    reg [7:0]  log0 [0:39];
    reg [7:0]  tb_pay [0:1023];
    reg [7:0]  tb_rx  [0:1023];

    integer i, k, off, chunk, errors = 0, e0;
    reg [7:0]  stat;
    reg [10:0] len;
    reg [31:0] got, want;

    // ------------------------------------------------------------ uart
    task uart_byte(input [7:0] b);
        integer j;
        begin
            host_tx = 1'b0;
            #(DIV * TCLK);
            for (j = 0; j < 8; j = j + 1) begin
                host_tx = b[j];
                #(DIV * TCLK);
            end
            host_tx = 1'b1;
            #(DIV * TCLK);
        end
    endtask

    task uart_get(output [7:0] b);
        integer j;
        begin
            @(negedge dev_tx);
            #(DIV * TCLK * 1.5);
            for (j = 0; j < 8; j = j + 1) begin
                b[j] = dev_tx;
                #(DIV * TCLK);
            end
            #(DIV * TCLK * 0.25);
        end
    endtask

    function [15:0] crc_byte;
        input [15:0] crc;
        input [7:0]  b;
        integer j;
        reg [15:0] c;
        begin
            c = crc ^ {b, 8'h00};
            for (j = 0; j < 8; j = j + 1)
                c = c[15] ? ((c << 1) ^ 16'h1021) : (c << 1);
            crc_byte = c;
        end
    endfunction

    task send_frame(input [7:0] cmd, input [10:0] n);
        integer j;
        reg [15:0] crc;
        reg [7:0]  b;
        begin
            crc = 16'hFFFF;
            uart_byte(8'hA5); uart_byte(8'h5A);
            uart_byte(cmd); crc = crc_byte(crc, cmd);
            b = n[7:0]; uart_byte(b); crc = crc_byte(crc, b);
            b = {5'b0, n[10:8]}; uart_byte(b); crc = crc_byte(crc, b);
            for (j = 0; j < n; j = j + 1) begin
                b = tb_pay[j]; uart_byte(b); crc = crc_byte(crc, b);
            end
            uart_byte(crc[7:0]); uart_byte(crc[15:8]);
        end
    endtask

    task recv_frame(output [7:0] s, output [10:0] n);
        integer j;
        reg [15:0] crc, gotc;
        reg [7:0]  b;
        begin
            uart_get(b); if (b !== 8'h5A) $display("  bad SOF0 %02x", b);
            uart_get(b); if (b !== 8'hA5) $display("  bad SOF1 %02x", b);
            uart_get(b); s = b; crc = crc_byte(16'hFFFF, b);
            uart_get(b); n[7:0] = b; crc = crc_byte(crc, b);
            uart_get(b); n[10:8] = b[2:0]; crc = crc_byte(crc, b);
            for (j = 0; j < n; j = j + 1) begin
                uart_get(b); tb_rx[j] = b; crc = crc_byte(crc, b);
            end
            uart_get(b); gotc[7:0] = b;
            uart_get(b); gotc[15:8] = b;
            if (gotc !== crc) begin
                $display("  bad reply CRC got %04x want %04x", gotc, crc);
                errors = errors + 1;
            end
        end
    endtask

    task check(input cond, input [8*72-1:0] msg);
        begin
            if (!cond) begin $display("FAIL: %0s", msg); errors = errors + 1; end
            else $display("PASS: %0s", msg);
        end
    endtask

    // send one LOAD_MEM frame for `n` bytes of section `sel` starting at `a`
    task load_chunk(input [2:0] sel, input integer a, input integer n);
        integer j;
        begin
            tb_pay[0] = {5'b0, sel};
            tb_pay[1] = a[7:0]; tb_pay[2] = a[15:8];
            tb_pay[3] = n[7:0]; tb_pay[4] = n[15:8];
            for (j = 0; j < n; j = j + 1) begin
                case (sel)
                3'd1: tb_pay[5+j] = w1[a+j];
                3'd2: tb_pay[5+j] = w2[a+j];
                3'd3: tb_pay[5+j] = w3[a+j];
                3'd4: tb_pay[5+j] = w4[a+j];
                3'd5: tb_pay[5+j] = bb[a+j];
                default: tb_pay[5+j] = qp[a+j];
                endcase
            end
            send_frame(8'h07, 5 + n);
            recv_frame(stat, len);
            if (stat !== 8'd0 || len !== 11'd1 || tb_rx[0] !== 8'h01) begin
                $display("  LOAD_MEM sel=%0d addr=%0d n=%0d -> stat %0d len %0d",
                         sel, a, n, stat, len);
                errors = errors + 1;
            end
        end
    endtask

    task load_all(input [2:0] sel, input integer total);
        integer a, c;
        begin
            a = 0;
            while (a < total) begin
                c = total - a;
                if (c > 500) c = 500;
                load_chunk(sel, a, c);
                a = a + c;
            end
        end
    endtask

    initial begin
        $display("=== cnn28_top UART end-to-end test ===");
        $readmemh("../../weights/x28/conv1_weight.hex", w1);
        $readmemh("../../weights/x28/conv2_weight.hex", w2);
        $readmemh("../../weights/x28/fc1_weight.hex", w3);
        $readmemh("../../weights/x28/fc2_weight.hex", w4);
        $readmemh("../../weights/x28/conv1_bias.hex", b1);
        $readmemh("../../weights/x28/conv2_bias.hex", b2);
        $readmemh("../../weights/x28/fc1_bias.hex", b3);
        $readmemh("../../weights/x28/fc2_bias.hex", b4);
        $readmemh("../../weights/x28/qparams.hex", qp);
        $readmemh("../../weights/x28/vectors/img_0.hex", img);
        $readmemh("../../weights/x28/vectors/logit_0.hex", expl);

        // bias block: conv1 8, conv2 16, fc1 32, fc2 10 x int32 LE
        for (i = 0; i < 8; i = i + 1) begin
            bb[4*i+0] = b1[i][7:0];  bb[4*i+1] = b1[i][15:8];
            bb[4*i+2] = b1[i][23:16]; bb[4*i+3] = b1[i][31:24];
        end
        for (i = 0; i < 16; i = i + 1) begin
            bb[32+4*i+0] = b2[i][7:0];  bb[32+4*i+1] = b2[i][15:8];
            bb[32+4*i+2] = b2[i][23:16]; bb[32+4*i+3] = b2[i][31:24];
        end
        for (i = 0; i < 32; i = i + 1) begin
            bb[96+4*i+0] = b3[i][7:0];  bb[96+4*i+1] = b3[i][15:8];
            bb[96+4*i+2] = b3[i][23:16]; bb[96+4*i+3] = b3[i][31:24];
        end
        for (i = 0; i < 10; i = i + 1) begin
            bb[224+4*i+0] = b4[i][7:0];  bb[224+4*i+1] = b4[i][15:8];
            bb[224+4*i+2] = b4[i][23:16]; bb[224+4*i+3] = b4[i][31:24];
        end

        #1000 rst_n = 1'b1;          // ignored by the NO_EXT_RESET build
        #20_000;                     // let the internal power-on reset finish

        // ---- PING
        send_frame(8'h01, 11'd0);
        recv_frame(stat, len);
        check(stat == 0 && len == 11'd10, "PING reply");
        check(tb_rx[0] == "C" && tb_rx[1] == "N" && tb_rx[9] == "A",
              "PING payload CNN28-FPGA");

        // ---- model download
        load_all(3'd1, 200);
        load_all(3'd2, 1152);
        load_all(3'd3, 12800);
        load_all(3'd4, 320);
        load_all(3'd5, 264);
        load_all(3'd7, 1056);
        check(errors == 0, "model downloaded over UART");

        // ---- image
        for (i = 0; i < 784; i = i + 1) tb_pay[i] = img[i];
        send_frame(8'h02, 11'd784);
        recv_frame(stat, len);
        check(stat == 0 && len == 11'd1 && tb_rx[0] == 8'h01, "LOAD_IMAGE ack");

        // ---- inference
        send_frame(8'h03, 11'd0);
        recv_frame(stat, len);
        check(stat == 0 && len == 11'd43, "INFER returns 43 bytes");
        e0 = errors;
        for (i = 0; i < 10; i = i + 1) begin
            got  = {tb_rx[4*i+3], tb_rx[4*i+2], tb_rx[4*i+1], tb_rx[4*i]};
            want = expl[i];
            if (got !== want) begin
                $display("  class %0d: got %0d want %0d", i,
                         $signed(got), $signed(want));
                errors = errors + 1;
            end
        end
        check(errors == e0, "10 logits match the reference");
        for (i = 0; i < 40; i = i + 1) log0[i] = tb_rx[i];
        check(tb_rx[40] == 8'd0, "argmax result 0");
        check(tb_rx[42][0] == 1'b1 && tb_rx[42][2] == 1'b1, "flags valid+done");

        // ---- READ_SCORES
        send_frame(8'h04, 11'd0);
        recv_frame(stat, len);
        check(stat == 0 && len == 11'd40, "READ_SCORES length");
        e0 = errors;
        for (i = 0; i < 40; i = i + 1)
            if (tb_rx[i] !== log0[i]) errors = errors + 1;
        check(errors == e0, "READ_SCORES returns the same logits");

        // ---- STATUS
        send_frame(8'h06, 11'd0);
        recv_frame(stat, len);
        check(stat == 0 && len == 11'd3, "STATUS reply");
        check(tb_rx[0][3] == 1'b1, "STATUS result_valid");

        // ---- bad CRC
        uart_byte(8'hA5); uart_byte(8'h5A);
        uart_byte(8'h01); uart_byte(8'h00); uart_byte(8'h00);
        uart_byte(8'h00); uart_byte(8'h00);
        recv_frame(stat, len);
        check(stat == 8'd1, "bad CRC rejected");

        if (errors == 0) $display("TB RESULT: PASS");
        else             $display("TB RESULT: FAIL (%0d)", errors);
        $finish;
    end

    initial begin
        #300_000_000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
