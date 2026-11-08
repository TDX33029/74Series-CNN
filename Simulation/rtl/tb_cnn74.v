// Board-level smoke/structural test for the 12-board CNN_74xx_System.
//
// The DUT is the flat structural netlist generated from output/top.net, with
// behavioural 74xx/memory models.  The testbench plays the host:
//   1. power-on reset
//   2. load bytes through the real H_A/H_D/LOAD_* path into SRAM and EEPROM
//   3. read them back through the real read-back path
//   4. raise IMAGE_READY / MODEL_READY and pulse START
//   5. watch the supervisor run the stage chain
//
// It does not check CNN numerics (all memories are zero unless written); it
// checks that the wiring carries the protocol.
`timescale 1ns/1ps

module tb_cnn74;

  reg [15:0] H_A;
  wire H_D0, H_D1, H_D2, H_D3, H_D4, H_D5, H_D6, H_D7;
  reg [7:0] hd_val = 8'h00;
  reg hd_en = 1'b0;
  assign H_D0 = hd_en ? hd_val[0] : 1'bz;
  assign H_D1 = hd_en ? hd_val[1] : 1'bz;
  assign H_D2 = hd_en ? hd_val[2] : 1'bz;
  assign H_D3 = hd_en ? hd_val[3] : 1'bz;
  assign H_D4 = hd_en ? hd_val[4] : 1'bz;
  assign H_D5 = hd_en ? hd_val[5] : 1'bz;
  assign H_D6 = hd_en ? hd_val[6] : 1'bz;
  assign H_D7 = hd_en ? hd_val[7] : 1'bz;
  reg [4:0] H_MEM_SEL;
  reg H_LOAD_nOE, H_LOAD_nWE, LOAD_EN;
  reg START_RAW, RESET_RAW, IMAGE_DONE_N, MODEL_DONE_N;

  wire BUSY, DONE, RESULT_VALID, ERROR;
  wire RESULT0, RESULT1, RESULT2, RESULT3;
  wire ERROR_CODE0, ERROR_CODE1, ERROR_CODE2, ERROR_CODE3;
  wire IMAGE_READY, MODEL_READY;

  cnn74_top dut (
    .H_A0(H_A[0]),   .H_A1(H_A[1]),   .H_A2(H_A[2]),   .H_A3(H_A[3]),
    .H_A4(H_A[4]),   .H_A5(H_A[5]),   .H_A6(H_A[6]),   .H_A7(H_A[7]),
    .H_A8(H_A[8]),   .H_A9(H_A[9]),   .H_A10(H_A[10]), .H_A11(H_A[11]),
    .H_A12(H_A[12]), .H_A13(H_A[13]), .H_A14(H_A[14]), .H_A15(H_A[15]),
    .H_D0(H_D0), .H_D1(H_D1), .H_D2(H_D2), .H_D3(H_D3),
    .H_D4(H_D4), .H_D5(H_D5), .H_D6(H_D6), .H_D7(H_D7),
    .H_MEM_SEL0(H_MEM_SEL[0]), .H_MEM_SEL1(H_MEM_SEL[1]),
    .H_MEM_SEL2(H_MEM_SEL[2]), .H_MEM_SEL3(H_MEM_SEL[3]),
    .H_MEM_SEL4(H_MEM_SEL[4]),
    .H_LOAD_nOE(H_LOAD_nOE), .H_LOAD_nWE(H_LOAD_nWE),
    .LOAD_EN(LOAD_EN),
    .START_RAW(START_RAW), .RESET_RAW(RESET_RAW),
    .IMAGE_DONE_N(IMAGE_DONE_N), .MODEL_DONE_N(MODEL_DONE_N),
    .BUSY(BUSY), .DONE(DONE), .RESULT_VALID(RESULT_VALID), .ERROR(ERROR),
    .RESULT0(RESULT0), .RESULT1(RESULT1),
    .RESULT2(RESULT2), .RESULT3(RESULT3),
    .ERROR_CODE0(ERROR_CODE0), .ERROR_CODE1(ERROR_CODE1),
    .ERROR_CODE2(ERROR_CODE2), .ERROR_CODE3(ERROR_CODE3),
    .IMAGE_READY(IMAGE_READY), .MODEL_READY(MODEL_READY)
  );

  wire CLK = dut.CLK;
  wire [4:0] SUP_ST = {dut._B01_S01_Supervisor_ST4,
                       dut._B01_S01_Supervisor_ST3,
                       dut._B01_S01_Supervisor_ST2,
                       dut._B01_S01_Supervisor_ST1,
                       dut._B01_S01_Supervisor_ST0};
  wire [2:0] TS = {dut._B02_S02_Timing_TS2,
                   dut._B02_S02_Timing_TS1,
                   dut._B02_S02_Timing_TS0};

  integer errors = 0;
  reg done_seen = 1'b0;
  integer i;
  reg [7:0] rb;

  // ---------------------------------------------------------------- helpers
  task check;
    input cond;
    input [255:0] msg;
    begin
      if (!cond) begin
        $display("FAIL @%0t: %0s", $time, msg);
        errors = errors + 1;
      end else begin
        $display("PASS @%0t: %0s", $time, msg);
      end
    end
  endtask

  task drive_d;
    input [7:0] v;
    begin
      hd_val = v;
      hd_en = 1'b1;
    end
  endtask

  task release_d;
    begin
      hd_en = 1'b0;
    end
  endtask

  task sample_d;
    output [7:0] v;
    begin
      v = {H_D7, H_D6, H_D5, H_D4, H_D3, H_D2, H_D1, H_D0};
    end
  endtask

  task host_write;
    input [15:0] addr;
    input [7:0] data;
    input [4:0] sel;
    begin
      // V1 fix: ADDR[23:16] is generated on B12 as {000,MEM_SEL}, so the
      // host only drives the 16-bit offset and the memory select.
      H_A = addr;
      H_MEM_SEL = sel;
      LOAD_EN = 1'b1;
      H_LOAD_nOE = 1'b1;
      H_LOAD_nWE = 1'b1;
      drive_d(data);
      repeat (4) @(posedge CLK);
      H_LOAD_nWE = 1'b0;
      repeat (4) @(posedge CLK);
      H_LOAD_nWE = 1'b1;          // rising edge commits the write
      repeat (4) @(posedge CLK);
    end
  endtask

  task host_read;
    input [15:0] addr;
    input [4:0] sel;
    output [7:0] data;
    begin
      H_A = addr;
      H_MEM_SEL = sel;
      LOAD_EN = 1'b1;
      H_LOAD_nWE = 1'b1;
      release_d();
      H_LOAD_nOE = 1'b0;
      repeat (6) @(posedge CLK);
      sample_d(data);
      H_LOAD_nOE = 1'b1;
      repeat (2) @(posedge CLK);
    end
  endtask

  task do_reset;
    begin
      RESET_RAW = 1'b0;
      START_RAW = 1'b0;
      LOAD_EN = 1'b0;
      H_LOAD_nOE = 1'b1;
      H_LOAD_nWE = 1'b1;
      H_MEM_SEL = 5'b11111;
      H_A = 16'h0000;
      IMAGE_DONE_N = 1'b1;
      MODEL_DONE_N = 1'b1;
      release_d();
      repeat (20) @(posedge CLK);
      RESET_RAW = 1'b1;
      repeat (20) @(posedge CLK);
    end
  endtask

  task set_ready;
    begin
      @(posedge CLK);
      IMAGE_DONE_N = 1'b0;
      MODEL_DONE_N = 1'b0;
      repeat (4) @(posedge CLK);
      IMAGE_DONE_N = 1'b1;
      MODEL_DONE_N = 1'b1;
      repeat (6) @(posedge CLK);
    end
  endtask

  // ---------------------------------------------------------------- monitors
  always @(SUP_ST)
    if ($test$plusargs("verbose"))
      $display("  [%0t] supervisor state = %0d", $time, SUP_ST);
  wire [4:0] C1_ST = {dut._B04_S07_Conv1_C1_ST4, dut._B04_S07_Conv1_C1_ST3,
                      dut._B04_S07_Conv1_C1_ST2, dut._B04_S07_Conv1_C1_ST1,
                      dut._B04_S07_Conv1_C1_ST0};
  always @(C1_ST)
    if ($test$plusargs("verbose"))
      $display("  [%0t] C1 state = %0d (ACK=%b DONE=%b POINT_LAST=%b SP_LAST=%b)",
               $time, C1_ST, dut.MEM_ACK, dut.C1_REQ_DONE,
               dut._B04_S07_Conv1_C1_POINT_LAST,
               dut._B04_S07_Conv1_C1_SP_LAST);
  integer n_mem_ce = 0;
  integer n_mem_we = 0;
  always @(negedge dut.MEM_nCE) n_mem_ce = n_mem_ce + 1;
  always @(negedge dut.MEM_nWE) n_mem_we = n_mem_we + 1;
  // POINT_LAST / PAD diagnostics (first few events only).
  integer n_point = 0;
  integer n_pad = 0;
  wire [9:0] SP_BUS = {dut._B04_S07_Conv1_C1_SP9,
                       dut._B04_S07_Conv1_C1_SP8,
                       dut._B04_S07_Conv1_C1_SP7,
                       dut._B04_S07_Conv1_C1_SP6,
                       dut._B04_S07_Conv1_C1_SP5,
                       dut._B04_S07_Conv1_C1_SP4,
                       dut._B04_S07_Conv1_C1_SP3,
                       dut._B04_S07_Conv1_C1_SP2,
                       dut._B04_S07_Conv1_C1_SP1,
                       dut._B04_S07_Conv1_C1_SP0};
  integer n_stb = 0;
  always @(posedge dut._B04_S07_Conv1_C1_OUT_STB) n_stb = n_stb + 1;
  always @(posedge dut._B04_S07_Conv1_C1_POINT_LAST) begin
    n_point = n_point + 1;
    if (n_point <= 6 || (SP_BUS > 570))
      $display("  [%0t] C1 POINT_LAST rise #%0d PAD=%b%b SP=%0d SP_LAST=%b OUT_STB#=%0d",
               $time, n_point, dut._B04_S07_Conv1_C1_PAD1,
               dut._B04_S07_Conv1_C1_PAD0, SP_BUS,
               dut._B04_S07_Conv1_C1_SP_LAST, n_stb);
  end
  wire [4:0] C2_ST = {dut._B06_S08_Conv2_C2_ST4, dut._B06_S08_Conv2_C2_ST3,
                      dut._B06_S08_Conv2_C2_ST2, dut._B06_S08_Conv2_C2_ST1,
                      dut._B06_S08_Conv2_C2_ST0};
  wire [3:0] C2_OC = {dut._B06_S08_Conv2_C2_OC3, dut._B06_S08_Conv2_C2_OC2,
                      dut._B06_S08_Conv2_C2_OC1, dut._B06_S08_Conv2_C2_OC0};
  wire [3:0] C2_OY = {dut._B06_S08_Conv2_C2_OY3, dut._B06_S08_Conv2_C2_OY2,
                      dut._B06_S08_Conv2_C2_OY1, dut._B06_S08_Conv2_C2_OY0};
  wire [3:0] C2_OX = {dut._B06_S08_Conv2_C2_OX3, dut._B06_S08_Conv2_C2_OX2,
                      dut._B06_S08_Conv2_C2_OX1, dut._B06_S08_Conv2_C2_OX0};
  wire [2:0] C2_IC = {dut._B06_S08_Conv2_C2_IC2, dut._B06_S08_Conv2_C2_IC1,
                      dut._B06_S08_Conv2_C2_IC0};
  wire [1:0] C2_KY = {dut._B06_S08_Conv2_C2_KY1, dut._B06_S08_Conv2_C2_KY0};
  wire [1:0] C2_KX = {dut._B06_S08_Conv2_C2_KX1, dut._B06_S08_Conv2_C2_KX0};
  wire [6:0] C2_SP = {dut._B06_S08_Conv2_C2_SP6, dut._B06_S08_Conv2_C2_SP5,
                      dut._B06_S08_Conv2_C2_SP4, dut._B06_S08_Conv2_C2_SP3,
                      dut._B06_S08_Conv2_C2_SP2, dut._B06_S08_Conv2_C2_SP1,
                      dut._B06_S08_Conv2_C2_SP0};
  integer hb2 = 0;
  always @(posedge CLK) begin
    hb2 = hb2 + 1;
    if (hb2 % 8000 == 0 && SUP_ST == 8)
      $display("  [%0t] C2: ST=%0d OC=%0d OY=%0d OX=%0d IC=%0d KY=%0d KX=%0d SP=%0d POINT=%b SPLAST=%b MACEN=%b",
               $time, C2_ST, C2_OC, C2_OY, C2_OX, C2_IC, C2_KY, C2_KX, C2_SP,
               dut._B06_S08_Conv2_C2_POINT_LAST, dut._B06_S08_Conv2_C2_SP_LAST,
               dut._B06_S08_Conv2_C2_MAC_EN);
  end
  wire [4:0] FC_ST = {dut._B08_S09_FC1_FC_ST4, dut._B08_S09_FC1_FC_ST3,
                      dut._B08_S09_FC1_FC_ST2, dut._B08_S09_FC1_FC_ST1,
                      dut._B08_S09_FC1_FC_ST0};
  wire [4:0] FC_NEU = {dut._B08_S09_FC1_FC_NEURON4, dut._B08_S09_FC1_FC_NEURON3,
                       dut._B08_S09_FC1_FC_NEURON2, dut._B08_S09_FC1_FC_NEURON1,
                       dut._B08_S09_FC1_FC_NEURON0};
  wire [8:0] FC_IDX = {dut._B08_S09_FC1_FC_INDEX8, dut._B08_S09_FC1_FC_INDEX7,
                       dut._B08_S09_FC1_FC_INDEX6, dut._B08_S09_FC1_FC_INDEX5,
                       dut._B08_S09_FC1_FC_INDEX4, dut._B08_S09_FC1_FC_INDEX3,
                       dut._B08_S09_FC1_FC_INDEX2, dut._B08_S09_FC1_FC_INDEX1,
                       dut._B08_S09_FC1_FC_INDEX0};
  integer hb3 = 0;
  always @(posedge CLK) begin
    hb3 = hb3 + 1;
    if (hb3 % 200 == 0 && SUP_ST >= 11 && FC_NEU >= 28)
      $display("  [%0t] FC: ST=%0d NEU=%0d IDX=%0d PTL=%b IMGL=%b LCLR_N=%b NLAST=%b FC_SEL=%b",
               $time, FC_ST, FC_NEU, FC_IDX,
               dut._B08_S09_FC1_FC_POINT_LAST, dut._B08_S09_FC1_FC_IMAGE_LAST,
               dut._B08_S09_FC1_FC_LOOP_CLR_N, dut._B08_S09_FC1_FC_NEURON_LAST,
               dut.FC_SEL);
    if (hb3 % 200 == 0 && SUP_ST >= 11 && FC_NEU >= 28)
      $display("     N31raw=%b N9raw=%b N31=%b N9=%b IMGL=%b NPE_N=%b IDX399=%b IDXLAST=%b",
               dut._B08_S09_FC1_FC_NEURON31_LO_N, dut._B08_S09_FC1_FC_NEURON9_LO_N,
               dut._B08_S09_FC1_FC_NEURON31, dut._B08_S09_FC1_FC_NEURON9,
               dut._B08_S09_FC1_FC_IMAGE_LAST,
               dut._B08_S09_FC1_FC_NEURON_PE_N,
               dut._B08_S09_FC1_FC_INDEX399, dut._B08_S09_FC1_FC_INDEX_LAST);
  end
  // Progress heartbeat every 1 ms of simulated time.
  integer hb = 0;
  always @(posedge CLK) begin
    hb = hb + 1;
    if (hb % 8000 == 0)
      $display("  [%0t] progress: SUP_ST=%0d C1_ST=%0d nCE=%0d nWE=%0d",
               $time, SUP_ST, C1_ST, n_mem_ce, n_mem_we);
  end
  always @(posedge dut.C1_DONE)
    $display("  [%0t] C1_DONE  (MEM_nCE pulses so far: %0d, writes: %0d)",
             $time, n_mem_ce, n_mem_we);
  always @(posedge dut.P1_DONE)     $display("  [%0t] P1_DONE", $time);
  always @(posedge dut.C2_DONE)     $display("  [%0t] C2_DONE", $time);
  always @(posedge dut.P2_DONE)     $display("  [%0t] P2_DONE", $time);
  always @(posedge dut.FC1_DONE)    $display("  [%0t] FC1_DONE", $time);
  always @(posedge dut.FC2_DONE)    $display("  [%0t] FC2_DONE", $time);
  always @(posedge dut.ARGMAX_DONE) $display("  [%0t] ARGMAX_DONE", $time);
  always @(posedge BUSY)        $display("  [%0t] BUSY=1", $time);
  always @(posedge DONE)        $display("  [%0t] DONE=1", $time);
  always @(posedge ERROR)       $display("  [%0t] ERROR=1", $time);

  // ---------------------------------------------------------------- stimulus
  initial begin
    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_cnn74.vcd");
      $dumpvars(0, tb_cnn74);
    end

    $display("=== reset ===");
    do_reset();
    check(RESET_RAW === 1'b1, "RESET_RAW released");
    check(dut.RESET_N === 1'b1, "RESET_N follows RESET_RAW");
    check(dut._B12_S10_Top_IO_CLK_SEL === 1'b0 ||
          dut._B12_S10_Top_IO_CLK_SEL === 1'b1, "clock reaches CLK_SEL");
    @(posedge CLK); @(posedge CLK);
    check(BUSY === 1'b0 && DONE === 1'b0 && ERROR === 1'b0,
          "status idle after reset");

    $display("=== host load: SRAM0 ===");
    for (i = 0; i < 8; i = i + 1)
      host_write(16'h0000 + i, 8'hA0 + i, 5'd0);
    for (i = 0; i < 8; i = i + 1) begin
      host_read(16'h0000 + i, 5'd0, rb);
      if (rb !== (8'hA0 + i)) begin
        $display("FAIL: SRAM0[%0d] read %02X expected %02X", i, rb, 8'hA0 + i);
        errors = errors + 1;
      end else begin
        $display("PASS: SRAM0[%0d] = %02X", i, rb);
      end
    end

    $display("=== host load: 28C256 W_FC1 (MEM_SEL=10) ===");
    for (i = 0; i < 4; i = i + 1)
      host_write(16'h0000 + i, 8'h5A + i, 5'd10);
    for (i = 0; i < 4; i = i + 1) begin
      host_read(16'h0000 + i, 5'd10, rb);
      if (rb !== (8'h5A + i)) begin
        $display("FAIL: EEPROM[%0d] read %02X expected %02X", i, rb, 8'h5A + i);
        errors = errors + 1;
      end else begin
        $display("PASS: EEPROM[%0d] = %02X", i, rb);
      end
    end

    LOAD_EN = 1'b0;
    H_LOAD_nOE = 1'b1;
    H_LOAD_nWE = 1'b1;
    release_d();
    H_MEM_SEL = 5'b11111;
    repeat (4) @(posedge CLK);

    $display("=== ready handshake ===");
    set_ready();
    check(IMAGE_READY === 1'b1, "IMAGE_READY set by IMAGE_DONE_N");
    check(MODEL_READY === 1'b1, "MODEL_READY set by MODEL_DONE_N");

    $display("=== start ===");
    START_RAW = 1'b1;
    repeat (8) @(posedge CLK);
    START_RAW = 1'b0;

    // Run until DONE/ERROR or timeout.
    fork : run
      begin
        wait (DONE === 1'b1 || ERROR === 1'b1);
        done_seen = (DONE === 1'b1);
        $display("  [%0t] run finished: DONE=%b ERROR=%b", $time, DONE, ERROR);
      end
      begin
        repeat (16000000) @(posedge CLK);
        $display("  [%0t] TIMEOUT: SUP_ST=%0d TS=%0d BUSY=%b DONE=%b ERROR=%b",
                 $time, SUP_ST, TS, BUSY, DONE, ERROR);
        errors = errors + 1;
      end
    join_any
    disable run;

    // RESULT_VALID is set from the microcode word of G_FINISH, i.e. one
    // clock after DONE; sample it a few clocks later.
    repeat (8) @(posedge CLK);
    $display("=== result ===");
    $display("  BUSY=%b DONE=%b RESULT_VALID=%b ERROR=%b",
             BUSY, DONE, RESULT_VALID, ERROR);
    $display("  RESULT=%b%b%b%b (dec %0d) ERROR_CODE=%b%b%b%b (valid only if ERROR=1)",
             RESULT3, RESULT2, RESULT1, RESULT0,
             {RESULT3, RESULT2, RESULT1, RESULT0},
             ERROR_CODE3, ERROR_CODE2, ERROR_CODE1, ERROR_CODE0);
    check(done_seen === 1'b1, "DONE pulsed at end of chain");
    check(ERROR === 1'b0, "no error reported");
    check(RESULT_VALID === 1'b1, "RESULT_VALID latched");
    // All memories are zero, so all ten scores are equal and the first
    // (class 0) must win.
    check({RESULT3, RESULT2, RESULT1, RESULT0} === 4'd0,
          "ARGMAX returns class 0");

    if (errors == 0) $display("TB RESULT: PASS");
    else             $display("TB RESULT: FAIL (%0d errors)", errors);
    $finish;
  end

endmodule
