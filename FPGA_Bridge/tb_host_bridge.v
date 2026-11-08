// Testbench for host_bridge.v with a behavioural B12 board model.
//
// The model implements the parts of S10/S04 the bridge touches:
//   * a 1 KiB image SRAM at MEM_SEL=0 and a 64 B score SRAM at MEM_SEL=6
//   * H_LOAD_nWE writes, H_LOAD_nOE reads, LOAD_EN gating
//   * DONE / RESULT_VALID / RESULT after a START pulse
//
// The clock/baud are scaled down from the real 50 MHz / 115200 so the
// 784-byte image upload simulates in a few milliseconds.  Both UART
// modules are fully parameterised; the shipped build uses 50 MHz.
//
// Run (ModelSim):
//   vlog uart_rx.v uart_tx.v b12_port.v host_bridge.v tb_host_bridge.v
//   vsim -c tb_host_bridge -do "run -all; quit -f"
`timescale 1ns/1ps

module tb_host_bridge;

    localparam integer CLK_HZ = 16_000_000;
    localparam integer BAUD   = 1_000_000;
    localparam integer DIV    = CLK_HZ / BAUD;
    localparam real    TCLK   = 1.0e9 / CLK_HZ;   // ns

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #(TCLK / 2.0) clk = ~clk;

    // ---------------------------------------------------------- board side
    wire [7:0]  ld_d;
    wire [15:0] ld_a;
    wire [4:0]  ld_sel;
    wire        ld_en, ld_nwe, ld_noe, ld_dir, ld_oe_n;

    wire start_raw, reset_raw, image_done_n, model_done_n;
    reg  st_busy = 0, st_done = 0, st_result_valid = 0, st_error = 0;
    reg  [3:0] st_result = 0, st_error_code = 0;
    reg  st_image_ready = 0, st_model_ready = 0;

    reg [7:0] mem0 [0:1023];
    reg [7:0] mem6 [0:63];

    wire [7:0] rd_val = (ld_sel == 5'd0) ? mem0[ld_a[9:0]] :
                        (ld_sel == 5'd6) ? mem6[ld_a[5:0]] : 8'h00;
    assign ld_d = (ld_en && !ld_noe) ? rd_val : 8'bz;

    always @(negedge ld_nwe)
        if (ld_en) begin
            if (ld_sel == 5'd0) mem0[ld_a[9:0]] <= ld_d;
            if (ld_sel == 5'd6) mem6[ld_a[5:0]] <= ld_d;
        end

    // S04 latches IMAGE_READY when IMAGE_DONE_N is pulsed
    always @(negedge image_done_n) st_image_ready <= 1'b1;

    // the 74LVC245A direction must match the strobe that is about to fire
    integer dir_errors = 0;
    always @(negedge ld_nwe) if (ld_dir !== 1'b0) dir_errors = dir_errors + 1;
    always @(negedge ld_noe) if (ld_dir !== 1'b1) dir_errors = dir_errors + 1;

    // board "run": after START, take 2 ms and publish the scores.  DONE
    // pulses first, RESULT_VALID latches 1 us later - the real order.
    integer k;
    always @(posedge start_raw) begin
        st_result_valid <= 1'b0;
        st_done <= 1'b0;
        #2_000_000;
        for (k = 0; k < 10; k = k + 1) begin
            mem6[4*k + 0] <= k;
            mem6[4*k + 1] <= 8'h00;
            mem6[4*k + 2] <= 8'h00;
            mem6[4*k + 3] <= 8'h00;
        end
        st_result <= 4'd0;
        st_done <= 1'b1;
        #1000;
        st_done <= 1'b0;
        st_result_valid <= 1'b1;
    end

    // ------------------------------------------------------------ uart wire
    reg  host_tx = 1'b1;
    wire dev_tx;

    host_bridge #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .TIMEOUT_MS(500)) dut (
        .clk(clk), .rst_n(rst_n),
        .uart_rx(host_tx), .uart_tx(dev_tx),
        .ld_d(ld_d), .ld_a(ld_a), .ld_sel(ld_sel),
        .ld_en(ld_en), .ld_nwe(ld_nwe), .ld_noe(ld_noe),
        .ld_dir(ld_dir), .ld_oe_n(ld_oe_n),
        .start_raw(start_raw), .reset_raw(reset_raw),
        .image_done_n(image_done_n), .model_done_n(model_done_n),
        .st_busy(st_busy), .st_done(st_done),
        .st_result_valid(st_result_valid), .st_error(st_error),
        .st_result(st_result), .st_error_code(st_error_code),
        .st_image_ready(st_image_ready), .st_model_ready(st_model_ready));

    // --------------------------------------------------------------- crc
    function [15:0] crc_byte;
        input [15:0] crc;
        input [7:0]  b;
        integer i;
        reg [15:0] c;
        begin
            c = crc ^ {b, 8'h00};
            for (i = 0; i < 8; i = i + 1)
                c = c[15] ? ((c << 1) ^ 16'h1021) : (c << 1);
            crc_byte = c;
        end
    endfunction

    // ------------------------------------------------------------ uart i/o
    task uart_byte(input [7:0] b);
        integer i;
        begin
            host_tx = 1'b0;
            #(DIV * TCLK);
            for (i = 0; i < 8; i = i + 1) begin
                host_tx = b[i];
                #(DIV * TCLK);
            end
            host_tx = 1'b1;
            #(DIV * TCLK);
        end
    endtask

    task uart_get(output [7:0] b);
        integer i;
        begin
            @(negedge dev_tx);
            #(DIV * TCLK * 1.5);
            for (i = 0; i < 8; i = i + 1) begin
                b[i] = dev_tx;
                #(DIV * TCLK);
            end
            // stop bit: stop a quarter bit BEFORE the next start edge, or
            // the following @(negedge) races with it and misses the byte
            #(DIV * TCLK * 0.25);
        end
    endtask

    reg [7:0] tb_pay [0:1023];
    reg [7:0] tb_rx  [0:1023];

    task send_frame(input [7:0] cmd, input [10:0] len);
        integer i;
        reg [15:0] crc;
        reg [7:0] b;
        begin
            crc = 16'hFFFF;
            uart_byte(8'hA5);
            uart_byte(8'h5A);
            uart_byte(cmd);
            crc = crc_byte(crc, cmd);
            b = len[7:0]; uart_byte(b); crc = crc_byte(crc, b);
            b = {5'b0, len[10:8]}; uart_byte(b); crc = crc_byte(crc, b);
            for (i = 0; i < len; i = i + 1) begin
                b = tb_pay[i];
                uart_byte(b);
                crc = crc_byte(crc, b);
            end
            uart_byte(crc[7:0]);
            uart_byte(crc[15:8]);
            // no trailing wait: the reply can start one bit time later
        end
    endtask

    task recv_frame(output [7:0] stat, output [10:0] len);
        integer i;
        reg [15:0] crc, got;
        reg [7:0] b;
        begin
            uart_get(b);
            if (b !== 8'h5A) $display("  FAIL: reply SOF0 = %02X", b);
            uart_get(b);
            if (b !== 8'hA5) $display("  FAIL: reply SOF1 = %02X", b);
            uart_get(b);
            stat = b;
            crc = crc_byte(16'hFFFF, b);
            uart_get(b);
            len[7:0] = b;
            crc = crc_byte(crc, b);
            uart_get(b);
            len[10:8] = b[2:0];
            crc = crc_byte(crc, b);
            for (i = 0; i < len; i = i + 1) begin
                uart_get(b);
                tb_rx[i] = b;
                crc = crc_byte(crc, b);
            end
            uart_get(b);
            got[7:0] = b;
            uart_get(b);
            got[15:8] = b;
            if (got !== crc)
                $display("  FAIL: reply CRC got %04X want %04X", got, crc);
            $display("  <- stat=%02X len=%0d", stat, len);
        end
    endtask

    // ------------------------------------------------------------- stimulus
    integer errors = 0;
    integer i;
    reg [7:0] stat;
    reg [10:0] len;

    task check(input cond, input [8*64-1:0] msg);
        begin
            if (!cond) begin
                $display("FAIL: %0s", msg);
                errors = errors + 1;
            end else
                $display("PASS: %0s", msg);
        end
    endtask

    initial begin
        $display("=== host_bridge testbench (CLK=%0d Hz, baud %0d) ===",
                 CLK_HZ, BAUD);
        rst_n = 1'b0;
        #1000 rst_n = 1'b1;
        #(10 * DIV * TCLK);

        // ---- PING
        send_frame(8'h01, 11'd0);
        recv_frame(stat, len);
        check(stat == 8'd0, "PING status OK");
        check(len == 11'd8, "PING length 8");
        check(tb_rx[0] == "M" && tb_rx[1] == "N" && tb_rx[6] == "4"
              && tb_rx[7] == 8'h01, "PING payload");

        // ---- LOAD_IMAGE
        for (i = 0; i < 784; i = i + 1) tb_pay[i] = i[7:0];
        send_frame(8'h02, 11'd784);
        recv_frame(stat, len);
        check(stat == 8'd0, "LOAD_IMAGE status OK");
        check(len == 11'd1 && tb_rx[0] == 8'h01, "LOAD_IMAGE ack");
        check(mem0[0] == 8'h00 && mem0[255] == 8'hFF && mem0[783] == 8'h0F,
              "image written to MEM_SEL=0");
        check(st_image_ready === 1'b1, "IMAGE_DONE_N latched IMAGE_READY");

        // ---- INFER
        send_frame(8'h03, 11'd0);
        recv_frame(stat, len);
        check(stat == 8'd0, "INFER status OK");
        check(len == 11'd43, "INFER returns 40 score bytes + 3 status");
        check(tb_rx[0] == 8'd0 && tb_rx[4] == 8'd1 && tb_rx[36] == 8'd9,
              "score payload from MEM_SEL=6");
        check(tb_rx[40] == 8'd0, "argmax result byte");
        check(tb_rx[41] == 8'd0, "error code byte");
        check(tb_rx[42][0] == 1'b1, "flags: RESULT_VALID seen");
        check(tb_rx[42][2] == 1'b1, "flags: DONE seen");

        // ---- READ_MEM back the image (sel=0, addr=0, n=16)
        tb_pay[0] = 8'd0; tb_pay[1] = 8'd0; tb_pay[2] = 8'd0;
        tb_pay[3] = 8'd16; tb_pay[4] = 8'd0;
        send_frame(8'h08, 11'd5);
        recv_frame(stat, len);
        check(stat == 8'd0 && len == 11'd16, "READ_MEM length");
        check(tb_rx[0] == 8'h00 && tb_rx[15] == 8'h0F, "READ_MEM data");

        // ---- STATUS: bit3=RESULT_VALID, bit2=ERROR, bit1=DONE, bit0=BUSY
        send_frame(8'h06, 11'd0);
        recv_frame(stat, len);
        check(stat == 8'd0 && len == 11'd3, "STATUS reply");
        check(tb_rx[0][3] == 1'b1, "STATUS: RESULT_VALID bit");

        // ---- corrupted frame -> BAD_CRC
        uart_byte(8'hA5); uart_byte(8'h5A);
        uart_byte(8'h01); uart_byte(8'h00); uart_byte(8'h00);
        uart_byte(8'h00); uart_byte(8'h00);
        recv_frame(stat, len);
        check(stat == 8'd1, "bad CRC -> STAT=1");
        check(len == 11'd0, "bad CRC reply has no payload");

        check(dir_errors == 0, "translator DIR matches WE/OE strobes");

        if (errors == 0) $display("TB RESULT: PASS");
        else             $display("TB RESULT: FAIL (%0d errors)", errors);
        $finish;
    end

    initial begin
        #100_000_000;   // 100 ms guard
        $display("TIMEOUT: simulation did not finish");
        $finish;
    end

endmodule
