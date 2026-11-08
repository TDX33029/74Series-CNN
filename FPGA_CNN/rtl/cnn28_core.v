// 28x28 MNIST CNN core, bit-exact with the integer reference model in
// FPGA_CNN/train_export.py.
//
//   IMG 28x28 u8 -> CONV 5x5 1->8  -> ReLU -> POOL 2x2 -> 12x12x8
//                -> CONV 3x3 8->16 -> ReLU -> POOL 2x2 -> 5x5x16
//                -> FC 400->32 -> ReLU -> FC 32->10 -> ARGMAX
//
// Arithmetic (doc 2.5):
//   ACC = SUM(q_x*q_w) - 128*SUM(q_x) + bias_int32
//   q   = clamp((ACC*M + 2^(S-1)) >> S, 0, 255)
//   FC2 : logit = (ACC*M + 2^(S-1)) >> S, signed, no clamp
//
// The byte memory has one read port and one write port.  Addresses are
// combinational, so operands are consumed one cycle after the address is
// presented.  A MAC term costs two cycles (activation, weight).
//
// Byte address map (all sections are byte arrays):
//   0x0000 IMG 1024 | 0x0400 W1 512   | 0x0600 W2 1280  | 0x0B00 W3 12800
//   0x3D00 W4 512   | 0x4000 C1 4608  | 0x5200 P1 1280  | 0x5700 C2 1792
//   0x5E00 P2 512   | 0x6000 F1 64    | 0x6100 LOG 64   | 0x6200 BIAS 512
//   0x6400 QP 1280
`timescale 1ns/1ps
module cnn28_core (
    input  wire        clk,
    input  wire        rst_n,

    // host byte port (used while !busy); read data follows one cycle later
    input  wire        h_we,
    input  wire        h_addr_ok,
    input  wire [15:0] h_addr,
    input  wire [7:0]  h_wdata,
    output wire [7:0]  h_rdata,

    // control
    input  wire        start,
    output reg         busy,
    output reg         done,
    output reg  [3:0]  result
);

    // ------------------------------------------------------------ memories
    reg [7:0] mem_img [0:1023];
    reg [7:0] mem_w1  [0:511];
    reg [7:0] mem_w2  [0:1279];
    reg [7:0] mem_w3  [0:12799];
    reg [7:0] mem_w4  [0:511];
    reg [7:0] mem_c1  [0:4607];
    reg [7:0] mem_p1  [0:1279];
    reg [7:0] mem_c2  [0:1791];
    reg [7:0] mem_p2  [0:511];
    reg [7:0] mem_f1  [0:63];
    reg [7:0] mem_lg  [0:63];
    reg [7:0] mem_bi  [0:511];
    reg [7:0] mem_qp  [0:1279];

    reg  [7:0]  m_rd;
    reg  [15:0] m_addr_r;      // address the registered read data belongs to
    wire        core_owns = busy;

    // core access signals (combinational, driven below)
    reg  [15:0] c_addr;
    reg         c_we;
    reg  [7:0]  c_wd;

    wire [15:0] m_addr = core_owns ? c_addr : h_addr;
    wire        m_we   = core_owns ? c_we   : h_we;
    wire [7:0]  m_wd   = core_owns ? c_wd   : h_wdata;

    // One simple-dual-port RAM per region.  Quartus only maps an array to
    // M9K when the read is unconditional, so every region gets its own
    // registered read port and the result is muxed combinationally below.
    reg [7:0] q_img, q_w1, q_w2, q_w3, q_w4;
    reg [7:0] q_c1, q_p1, q_c2, q_p2, q_f1, q_lg, q_bi, q_qp;

    function [15:0] sel_ix;
        input [15:0] a, base, size;
        begin
            sel_ix = (a >= base && a < base + size) ? (a - base) : 16'd0;
        end
    endfunction

    wire [15:0] ix_img = sel_ix(m_addr, 16'h0000, 16'd1024);
    wire [15:0] ix_w1  = sel_ix(m_addr, 16'h0400, 16'd512);
    wire [15:0] ix_w2  = sel_ix(m_addr, 16'h0600, 16'd1280);
    wire [15:0] ix_w3  = sel_ix(m_addr, 16'h0B00, 16'd12800);
    wire [15:0] ix_w4  = sel_ix(m_addr, 16'h3D00, 16'd384);
    wire [15:0] ix_c1  = sel_ix(m_addr, 16'h4000, 16'd4608);
    wire [15:0] ix_p1  = sel_ix(m_addr, 16'h5200, 16'd1184);
    wire [15:0] ix_c2  = sel_ix(m_addr, 16'h5700, 16'd1664);
    wire [15:0] ix_p2  = sel_ix(m_addr, 16'h5E00, 16'd512);
    wire [15:0] ix_f1  = sel_ix(m_addr, 16'h6000, 16'd64);
    wire [15:0] ix_lg  = sel_ix(m_addr, 16'h6100, 16'd64);
    wire [15:0] ix_bi  = sel_ix(m_addr, 16'h6200, 16'd264);
    wire [15:0] ix_qp  = sel_ix(m_addr, 16'h6400, 16'd1088);

    always @(posedge clk) begin
        if (m_we) begin
            if      (m_addr < 16'h0400) mem_img[m_addr[9:0]]       <= m_wd;
            else if (m_addr < 16'h0600) mem_w1 [m_addr - 16'h0400] <= m_wd;
            else if (m_addr < 16'h0B00) mem_w2 [m_addr - 16'h0600] <= m_wd;
            else if (m_addr < 16'h3D00) mem_w3 [m_addr - 16'h0B00] <= m_wd;
            else if (m_addr < 16'h3F00) mem_w4 [m_addr - 16'h3D00] <= m_wd;
            else if (m_addr < 16'h5200) mem_c1 [m_addr - 16'h4000] <= m_wd;
            else if (m_addr < 16'h5700) mem_p1 [m_addr - 16'h5200] <= m_wd;
            else if (m_addr < 16'h5E00) mem_c2 [m_addr - 16'h5700] <= m_wd;
            else if (m_addr < 16'h6000) mem_p2 [m_addr - 16'h5E00] <= m_wd;
            else if (m_addr < 16'h6100) mem_f1 [m_addr - 16'h6000] <= m_wd;
            else if (m_addr < 16'h6200) mem_lg [m_addr - 16'h6100] <= m_wd;
            else if (m_addr < 16'h6400) mem_bi [m_addr - 16'h6200] <= m_wd;
            else if (m_addr < 16'h6900) mem_qp [m_addr - 16'h6400] <= m_wd;
        end
        // unconditional reads; the index is clamped into the region so
        // that addresses belonging to other regions never read out of range
        q_img <= mem_img[ix_img[9:0]];
        q_w1  <= mem_w1 [ix_w1 [8:0]];
        q_w2  <= mem_w2 [ix_w2 [10:0]];
        q_w3  <= mem_w3 [ix_w3 [13:0]];
        q_w4  <= mem_w4 [ix_w4 [8:0]];
        q_c1  <= mem_c1 [ix_c1 [12:0]];
        q_p1  <= mem_p1 [ix_p1 [10:0]];
        q_c2  <= mem_c2 [ix_c2 [10:0]];
        q_p2  <= mem_p2 [ix_p2 [8:0]];
        q_f1  <= mem_f1 [ix_f1 [5:0]];
        q_lg  <= mem_lg [ix_lg [5:0]];
        q_bi  <= mem_bi [ix_bi [8:0]];
        q_qp  <= mem_qp [ix_qp [10:0]];
        m_addr_r <= m_addr;
    end

    always @(*) begin
        if      (m_addr_r < 16'h0400) m_rd = q_img;
        else if (m_addr_r < 16'h0600) m_rd = q_w1;
        else if (m_addr_r < 16'h0B00) m_rd = q_w2;
        else if (m_addr_r < 16'h3D00) m_rd = q_w3;
        else if (m_addr_r < 16'h3F00) m_rd = q_w4;
        else if (m_addr_r < 16'h5200) m_rd = q_c1;
        else if (m_addr_r < 16'h5700) m_rd = q_p1;
        else if (m_addr_r < 16'h5E00) m_rd = q_c2;
        else if (m_addr_r < 16'h6000) m_rd = q_p2;
        else if (m_addr_r < 16'h6100) m_rd = q_f1;
        else if (m_addr_r < 16'h6200) m_rd = q_lg;
        else if (m_addr_r < 16'h6400) m_rd = q_bi;
        else if (m_addr_r < 16'h6900) m_rd = q_qp;
        else                        m_rd = 8'h00;
    end

    assign h_rdata = m_rd;

    // ----------------------------------------------------------- addresses
    function [15:0] a_img;      input [5:0] y, x;
        a_img = 16'h0000 + y * 28 + x; endfunction
    function [15:0] a_c1w;      input [3:0] oc, ky, kx;
        a_c1w = 16'h0400 + oc * 25 + ky * 5 + kx; endfunction
    function [15:0] a_c2w;      input [3:0] oc, ic, ky, kx;
        a_c2w = 16'h0600 + oc * 72 + ic * 9 + ky * 3 + kx; endfunction
    function [15:0] a_f1w;      input [4:0] n; input [8:0] j;
        a_f1w = 16'h0B00 + n * 400 + j; endfunction
    function [15:0] a_f2w;      input [3:0] c; input [4:0] j;
        a_f2w = 16'h3D00 + c * 32 + j; endfunction
    function [15:0] a_c1o;      input [3:0] oc; input [4:0] y, x;
        a_c1o = 16'h4000 + oc * 576 + y * 24 + x; endfunction
    function [15:0] a_c1i;      input [3:0] ic; input [4:0] y, x;
        a_c1i = 16'h4000 + ic * 576 + y * 24 + x; endfunction
    function [15:0] a_p1;       input [3:0] ic; input [4:0] y, x;
        a_p1 = 16'h5200 + ic * 144 + y * 12 + x; endfunction
    function [15:0] a_c2o;      input [3:0] oc; input [4:0] y, x;
        a_c2o = 16'h5700 + oc * 100 + y * 10 + x; endfunction
    function [15:0] a_p2i;      input [3:0] ic; input [4:0] y, x;
        a_p2i = 16'h5700 + ic * 100 + y * 10 + x; endfunction
    function [15:0] a_p2o;      input [3:0] oc; input [4:0] y, x;
        a_p2o = 16'h5E00 + oc * 25 + y * 5 + x; endfunction
    function [15:0] a_log;      input [3:0] c; input [1:0] b;
        a_log = 16'h6100 + c * 4 + b; endfunction
    function [15:0] a_bias;     input [6:0] id; input [1:0] b;
        a_bias = 16'h6200 + id * 4 + b; endfunction
    function [15:0] a_qp;       input [6:0] id; input [3:0] b;
        a_qp = 16'h6400 + id * 16 + b; endfunction

    // ------------------------------------------------------------- control
    localparam S_IDLE      = 0,
               S_C1_SETUP  = 1,  S_C1_TERM = 2,  S_C1_REQ = 3,
               S_C1_MUL    = 4,  S_C1_WR   = 5,
               S_P1        = 6,
               S_C2_SETUP  = 7,  S_C2_TERM = 8,  S_C2_REQ = 9,
               S_C2_MUL    = 10, S_C2_WR   = 11,
               S_P2        = 12,
               S_F1_SETUP  = 13, S_F1_TERM = 14, S_F1_REQ = 15,
               S_F1_MUL    = 16, S_F1_WR   = 17,
               S_F2_SETUP  = 18, S_F2_TERM = 19, S_F2_REQ = 20,
               S_F2_MUL    = 21, S_F2_WR   = 22,
               S_AM        = 23, S_DONE    = 24,
               S_C1_SH     = 25, S_C2_SH   = 26,
               S_F1_SH     = 27, S_F2_SH   = 28;

    reg [4:0]  st;
    reg [3:0]  oc, ic, ky, kx;
    reg [4:0]  oy, ox, n;
    reg [8:0]  j;               // 0..399 for FC1, 0..31 for FC2
    reg [3:0]  f2b;
    reg [2:0]  ph, ss;
    reg [3:0]  amc, amp;

    reg signed [31:0] raw, acc, bias_r, best;
    reg        [19:0] sx;
    reg        [15:0] m_r;
    reg        [6:0]  s_r;
    reg        [7:0]  a_r, w_r, v0, v1, v2, v3;
    reg signed [47:0] prod_r;
    reg signed [63:0] sh64_r;   // requantized value, one pipeline stage
    reg        [63:0] rnd_c;    // 1 << (S-1), precomputed per neuron

    wire [31:0] sx128 = {12'd0, sx} << 7;

    wire signed [63:0] prod64 = {{16{prod_r[47]}}, prod_r};
    wire signed [63:0] sh64   = sh64_r;
    wire        [7:0]  sat8   = (sh64_r > 64'sd255) ? 8'd255 :
                                (sh64_r < 64'sd0)   ? 8'd0   : sh64_r[7:0];

    // term counter increments
    wire [3:0] c1_kx_n = (kx == 4'd4) ? 4'd0 : kx + 4'd1;
    wire [3:0] c1_ky_n = (kx == 4'd4) ? ((ky == 4'd4) ? 4'd0 : ky + 4'd1) : ky;

    wire [3:0] c2_kx_n = (kx == 4'd2) ? 4'd0 : kx + 4'd1;
    wire [3:0] c2_ky_n = (kx == 4'd2) ? ((ky == 4'd2) ? 4'd0 : ky + 4'd1) : ky;
    wire [3:0] c2_ic_n = (kx == 4'd2 && ky == 4'd2) ?
                         ((ic == 4'd7) ? 4'd0 : ic + 4'd1) : ic;
    wire [8:0] f1_j_n = (j == 9'd399) ? 9'd0 : j + 9'd1;
    wire [8:0] f2_j_n = (j[4:0] == 5'd31) ? 9'd0 : {4'd0, j[4:0] + 5'd1};

    // coordinate advances
    wire [4:0] c1_ox_n = (ox == 5'd23) ? 5'd0 : ox + 5'd1;
    wire [4:0] c1_oy_n = (ox == 5'd23) ? ((oy == 5'd23) ? 5'd0 : oy + 5'd1) : oy;
    wire [3:0] c1_oc_n = (ox == 5'd23 && oy == 5'd23) ? oc + 4'd1 : oc;

    wire [4:0] c2_ox_n = (ox == 5'd9) ? 5'd0 : ox + 5'd1;
    wire [4:0] c2_oy_n = (ox == 5'd9) ? ((oy == 5'd9) ? 5'd0 : oy + 5'd1) : oy;
    wire [3:0] c2_oc_n = (ox == 5'd9 && oy == 5'd9) ? oc + 4'd1 : oc;

    wire [4:0] p1_ox_n = (ox == 5'd11) ? 5'd0 : ox + 5'd1;
    wire [4:0] p1_oy_n = (ox == 5'd11) ? ((oy == 5'd11) ? 5'd0 : oy + 5'd1) : oy;
    wire [3:0] p1_oc_n = (ox == 5'd11 && oy == 5'd11) ? oc + 4'd1 : oc;

    wire [4:0] p2_ox_n = (ox == 5'd4) ? 5'd0 : ox + 5'd1;
    wire [4:0] p2_oy_n = (ox == 5'd4) ? ((oy == 5'd4) ? 5'd0 : oy + 5'd1) : oy;
    wire [3:0] p2_oc_n = (ox == 5'd4 && oy == 5'd4) ? oc + 4'd1 : oc;

    // ------------------------------------------------------------- datapath
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            raw <= 0; acc <= 0; sx <= 0; bias_r <= 0; m_r <= 0; s_r <= 0;
            a_r <= 0; w_r <= 0; prod_r <= 0; best <= 0; result <= 0;
            v0 <= 0; v1 <= 0; v2 <= 0; v3 <= 0;
        end else begin
            case (st)
            S_C1_SETUP: begin
                case (ss)
                1: bias_r[7:0]   <= m_rd;
                2: bias_r[15:8]  <= m_rd;
                3: bias_r[23:16] <= m_rd;
                4: bias_r[31:24] <= m_rd;
                5: m_r[7:0]      <= m_rd;
                6: m_r[15:8]     <= m_rd;
                7: begin s_r <= m_rd[6:0]; raw <= 0; sx <= 0;
                         rnd_c <= (m_rd[6:0] == 7'd0) ? 64'd0 :
                                  (64'd1 <<< (m_rd[6:0] - 7'd1)); end
                default: ;
                endcase
            end
            S_C1_TERM: begin
                if (ph == 1) a_r <= m_rd;
                else begin
                    raw <= raw + a_r * m_rd;   // m_rd is this term's weight
                    sx  <= sx + a_r;
                end
            end
            S_C1_REQ: acc <= raw - $signed({1'b0, sx128}) + bias_r;
            S_C1_MUL: prod_r <= $signed(acc) * $signed({1'b0, m_r});
            S_C1_SH:  sh64_r <= (prod64 + $signed(rnd_c)) >>> s_r;

            S_C2_SETUP: begin
                case (ss)
                1: bias_r[7:0]   <= m_rd;
                2: bias_r[15:8]  <= m_rd;
                3: bias_r[23:16] <= m_rd;
                4: bias_r[31:24] <= m_rd;
                5: m_r[7:0]      <= m_rd;
                6: m_r[15:8]     <= m_rd;
                7: begin s_r <= m_rd[6:0]; raw <= 0; sx <= 0;
                         rnd_c <= (m_rd[6:0] == 7'd0) ? 64'd0 :
                                  (64'd1 <<< (m_rd[6:0] - 7'd1)); end
                default: ;
                endcase
            end
            S_C2_TERM: begin
                if (ph == 1) a_r <= m_rd;
                else begin
                    raw <= raw + a_r * m_rd;   // m_rd is this term's weight
                    sx  <= sx + a_r;
                end
            end
            S_C2_REQ: acc <= raw - $signed({1'b0, sx128}) + bias_r;
            S_C2_MUL: prod_r <= $signed(acc) * $signed({1'b0, m_r});
            S_C2_SH:  sh64_r <= (prod64 + $signed(rnd_c)) >>> s_r;

            S_F1_SETUP: begin
                case (ss)
                1: bias_r[7:0]   <= m_rd;
                2: bias_r[15:8]  <= m_rd;
                3: bias_r[23:16] <= m_rd;
                4: bias_r[31:24] <= m_rd;
                5: m_r[7:0]      <= m_rd;
                6: m_r[15:8]     <= m_rd;
                7: begin s_r <= m_rd[6:0]; raw <= 0; sx <= 0;
                         rnd_c <= (m_rd[6:0] == 7'd0) ? 64'd0 :
                                  (64'd1 <<< (m_rd[6:0] - 7'd1)); end
                default: ;
                endcase
            end
            S_F1_TERM: begin
                if (ph == 1) a_r <= m_rd;
                else begin
                    raw <= raw + a_r * m_rd;   // m_rd is this term's weight
                    sx  <= sx + a_r;
                end
            end
            S_F1_REQ: acc <= raw - $signed({1'b0, sx128}) + bias_r;
            S_F1_MUL: prod_r <= $signed(acc) * $signed({1'b0, m_r});
            S_F1_SH:  sh64_r <= (prod64 + $signed(rnd_c)) >>> s_r;

            S_F2_SETUP: begin
                case (ss)
                1: bias_r[7:0]   <= m_rd;
                2: bias_r[15:8]  <= m_rd;
                3: bias_r[23:16] <= m_rd;
                4: bias_r[31:24] <= m_rd;
                5: m_r[7:0]      <= m_rd;
                6: m_r[15:8]     <= m_rd;
                7: begin s_r <= m_rd[6:0]; raw <= 0; sx <= 0;
                         rnd_c <= (m_rd[6:0] == 7'd0) ? 64'd0 :
                                  (64'd1 <<< (m_rd[6:0] - 7'd1)); end
                default: ;
                endcase
            end
            S_F2_TERM: begin
                if (ph == 1) a_r <= m_rd;
                else begin
                    raw <= raw + a_r * m_rd;   // m_rd is this term's weight
                    sx  <= sx + a_r;
                end
            end
            S_F2_REQ: acc <= raw - $signed({1'b0, sx128}) + bias_r;
            S_F2_MUL: prod_r <= $signed(acc) * $signed({1'b0, m_r});
            S_F2_SH:  sh64_r <= (prod64 + $signed(rnd_c)) >>> s_r;

            S_P1: begin
                case (ph)
                1: v0 <= m_rd;
                2: v1 <= m_rd;
                3: v2 <= m_rd;
                4: v3 <= m_rd;
                default: ;
                endcase
            end
            S_P2: begin
                case (ph)
                1: v0 <= m_rd;
                2: v1 <= m_rd;
                3: v2 <= m_rd;
                4: v3 <= m_rd;
                default: ;
                endcase
            end

            S_AM: begin
                case (amp)
                1: v0 <= m_rd;
                2: v1 <= m_rd;
                3: v2 <= m_rd;
                4: v3 <= m_rd;
                5: if (amc == 0) begin
                       best <= $signed({v3, v2, v1, v0});
                       result <= 4'd0;
                   end else if ($signed({v3, v2, v1, v0}) > best) begin
                       best <= $signed({v3, v2, v1, v0});
                       result <= amc;
                   end
                default: ;
                endcase
            end
            endcase
        end
    end

    // ------------------------------------------------------- address unit
    always @(*) begin
        c_addr = 16'h0000;
        c_we   = 1'b0;
        c_wd   = 8'h00;
        if (!core_owns) begin
            // host owns the port; core outputs are idle
            c_addr = 16'h0000;
        end else begin
            case (st)
            S_C1_SETUP: begin
                case (ss)
                0: c_addr = a_bias(oc, 2'd0);
                1: c_addr = a_bias(oc, 2'd1);
                2: c_addr = a_bias(oc, 2'd2);
                3: c_addr = a_bias(oc, 2'd3);
                4: c_addr = a_qp(oc, 4'd4);
                5: c_addr = a_qp(oc, 4'd5);
                6: c_addr = a_qp(oc, 4'd8);
                7: c_addr = a_img({1'b0, oy} + {1'b0, ky},
                                  {1'b0, ox} + {1'b0, kx});
                default: ;
                endcase
            end
            S_C1_TERM: begin
                if (ph == 1) c_addr = a_c1w(oc, ky, kx);
                else         c_addr = a_img({1'b0, oy} + {2'b0, c1_ky_n},
                                            {1'b0, ox} + {2'b0, c1_kx_n});
            end
            S_C1_WR: begin
                c_we   = 1'b1;
                c_addr = a_c1o(oc, oy, ox);
                c_wd   = sat8;
            end

            S_P1: begin
                case (ph)
                0: c_addr = a_c1i(oc, oy * 2, ox * 2);
                1: c_addr = a_c1i(oc, oy * 2, ox * 2 + 1);
                2: c_addr = a_c1i(oc, oy * 2 + 1, ox * 2);
                3: c_addr = a_c1i(oc, oy * 2 + 1, ox * 2 + 1);
                4: c_addr = a_p1(oc, oy, ox);          // destination
                5: begin
                    c_we   = 1'b1;
                    c_addr = a_p1(oc, oy, ox);
                    c_wd   = ((v0 > v1) ? v0 : v1) >
                             ((v2 > v3) ? v2 : v3) ?
                             ((v0 > v1) ? v0 : v1) : ((v2 > v3) ? v2 : v3);
                end
                default: ;
                endcase
            end

            S_C2_SETUP: begin
                case (ss)
                0: c_addr = a_bias(7'd8 + oc, 2'd0);
                1: c_addr = a_bias(7'd8 + oc, 2'd1);
                2: c_addr = a_bias(7'd8 + oc, 2'd2);
                3: c_addr = a_bias(7'd8 + oc, 2'd3);
                4: c_addr = a_qp(7'd8 + oc, 4'd4);
                5: c_addr = a_qp(7'd8 + oc, 4'd5);
                6: c_addr = a_qp(7'd8 + oc, 4'd8);
                7: c_addr = a_p1({1'b0, ic}, oy + ky, ox + kx);
                default: ;
                endcase
            end
            S_C2_TERM: begin
                if (ph == 1) c_addr = a_c2w(oc, ic, ky, kx);
                else         c_addr = a_p1(c2_ic_n, oy + c2_ky_n, ox + c2_kx_n);
            end
            S_C2_WR: begin
                c_we   = 1'b1;
                c_addr = a_c2o(oc, oy, ox);
                c_wd   = sat8;
            end

            S_P2: begin
                case (ph)
                0: c_addr = a_p2i(oc, oy * 2, ox * 2);
                1: c_addr = a_p2i(oc, oy * 2, ox * 2 + 1);
                2: c_addr = a_p2i(oc, oy * 2 + 1, ox * 2);
                3: c_addr = a_p2i(oc, oy * 2 + 1, ox * 2 + 1);
                4: c_addr = a_p2o(oc, oy, ox);
                5: begin
                    c_we   = 1'b1;
                    c_addr = a_p2o(oc, oy, ox);
                    c_wd   = ((v0 > v1) ? v0 : v1) >
                             ((v2 > v3) ? v2 : v3) ?
                             ((v0 > v1) ? v0 : v1) : ((v2 > v3) ? v2 : v3);
                end
                default: ;
                endcase
            end

            S_F1_SETUP: begin
                case (ss)
                0: c_addr = a_bias(7'd24 + n, 2'd0);
                1: c_addr = a_bias(7'd24 + n, 2'd1);
                2: c_addr = a_bias(7'd24 + n, 2'd2);
                3: c_addr = a_bias(7'd24 + n, 2'd3);
                4: c_addr = a_qp(7'd24 + n, 4'd4);
                5: c_addr = a_qp(7'd24 + n, 4'd5);
                6: c_addr = a_qp(7'd24 + n, 4'd8);
                7: c_addr = 16'h5E00 + j;             // pool2 byte j
                default: ;
                endcase
            end
            S_F1_TERM: begin
                if (ph == 1) c_addr = a_f1w(n, j);
                else         c_addr = 16'h5E00 + f1_j_n;
            end
            S_F1_WR: begin
                c_we   = 1'b1;
                c_addr = 16'h6000 + n;
                c_wd   = sat8;
            end

            S_F2_SETUP: begin
                case (ss)
                0: c_addr = a_bias(7'd56 + oc, 2'd0);
                1: c_addr = a_bias(7'd56 + oc, 2'd1);
                2: c_addr = a_bias(7'd56 + oc, 2'd2);
                3: c_addr = a_bias(7'd56 + oc, 2'd3);
                4: c_addr = a_qp(7'd56 + oc, 4'd4);
                5: c_addr = a_qp(7'd56 + oc, 4'd5);
                6: c_addr = a_qp(7'd56 + oc, 4'd8);
                7: c_addr = 16'h6000 + j;             // fc1 byte j
                default: ;
                endcase
            end
            S_F2_TERM: begin
                if (ph == 1) c_addr = a_f2w(oc, j);
                else         c_addr = 16'h6000 + f2_j_n;
            end
            S_F2_WR: begin
                c_we   = 1'b1;
                c_addr = a_log(oc, f2b[1:0]);
                c_wd   = (f2b == 0) ? sh64[7:0]   :
                         (f2b == 1) ? sh64[15:8]  :
                         (f2b == 2) ? sh64[23:16] : sh64[31:24];
            end

            S_AM: begin
                case (amp)
                0: c_addr = a_log(amc, 2'd0);
                1: c_addr = a_log(amc, 2'd1);
                2: c_addr = a_log(amc, 2'd2);
                3: c_addr = a_log(amc, 2'd3);
                default: ;
                endcase
            end
            default: ;
            endcase
        end
    end

    // ------------------------------------------------------------ sequencer
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; busy <= 1'b0; done <= 1'b0;
            oc <= 0; ic <= 0; ky <= 0; kx <= 0; oy <= 0; ox <= 0;
            j <= 0; n <= 0; f2b <= 0; ph <= 0; ss <= 0; amc <= 0; amp <= 0;
        end else begin
            done <= 1'b0;
            case (st)
            S_IDLE: if (start) begin
                busy <= 1'b1;
                oc <= 0; oy <= 0; ox <= 0; ky <= 0; kx <= 0; ic <= 0;
                n <= 0; j <= 0; ph <= 0; ss <= 0;
                st <= S_C1_SETUP;
            end

            // ---------------------------------------------------- conv1
            S_C1_SETUP: begin
                if (ss == 3'd7) begin
                    ss <= 0; ph <= 1; st <= S_C1_TERM;
                end else ss <= ss + 3'd1;
            end
            S_C1_TERM: begin
                if (ph == 2'd1) ph <= 2'd2;
                else begin
                    kx <= c1_kx_n; ky <= c1_ky_n;
                    ph <= 2'd1;
                    if (kx == 4'd4 && ky == 4'd4) st <= S_C1_REQ;
                end
            end
            S_C1_REQ: st <= S_C1_MUL;
            S_C1_MUL: st <= S_C1_SH;
            S_C1_SH:  st <= S_C1_WR;
            S_C1_WR: begin
                if (ox == 5'd23 && oy == 5'd23 && oc == 4'd7) begin
                    oc <= 0; oy <= 0; ox <= 0; ph <= 0; ss <= 0; st <= S_P1;
                end else begin
                    ox <= c1_ox_n; oy <= c1_oy_n; oc <= c1_oc_n;
                    ss <= 0; st <= S_C1_SETUP;
                end
            end

            // ---------------------------------------------------- pool1
            S_P1: begin
                ph <= ph + 3'd1;
                if (ph == 3'd5) begin
                    if (ox == 5'd11 && oy == 5'd11 && oc == 4'd7) begin
                        oc <= 0; oy <= 0; ox <= 0; ky <= 0; kx <= 0; ic <= 0;
                        ph <= 0; ss <= 0; st <= S_C2_SETUP;
                    end else begin
                        ox <= p1_ox_n; oy <= p1_oy_n; oc <= p1_oc_n; ph <= 0;
                    end
                end
            end

            // ---------------------------------------------------- conv2
            S_C2_SETUP: begin
                if (ss == 3'd7) begin
                    ss <= 0; ph <= 1; st <= S_C2_TERM;
                end else ss <= ss + 3'd1;
            end
            S_C2_TERM: begin
                if (ph == 2'd1) ph <= 2'd2;
                else begin
                    kx <= c2_kx_n; ky <= c2_ky_n; ic <= c2_ic_n;
                    ph <= 2'd1;
                    if (kx == 4'd2 && ky == 4'd2 && ic == 4'd7) st <= S_C2_REQ;
                end
            end
            S_C2_REQ: st <= S_C2_MUL;
            S_C2_MUL: st <= S_C2_SH;
            S_C2_SH:  st <= S_C2_WR;
            S_C2_WR: begin
                if (ox == 5'd9 && oy == 5'd9 && oc == 4'd15) begin
                    oc <= 0; oy <= 0; ox <= 0; ph <= 0; st <= S_P2;
                end else begin
                    ox <= c2_ox_n; oy <= c2_oy_n; oc <= c2_oc_n;
                    ss <= 0; st <= S_C2_SETUP;
                end
            end

            // ---------------------------------------------------- pool2
            S_P2: begin
                ph <= ph + 3'd1;
                if (ph == 3'd5) begin
                    if (ox == 5'd4 && oy == 5'd4 && oc == 4'd15) begin
                        n <= 0; j <= 0; ph <= 0; ss <= 0; st <= S_F1_SETUP;
                    end else begin
                        ox <= p2_ox_n; oy <= p2_oy_n; oc <= p2_oc_n; ph <= 0;
                    end
                end
            end

            // ----------------------------------------------------- fc1
            S_F1_SETUP: begin
                if (ss == 3'd7) begin
                    ss <= 0; ph <= 1; st <= S_F1_TERM;
                end else ss <= ss + 3'd1;
            end
            S_F1_TERM: begin
                if (ph == 2'd1) ph <= 2'd2;
                else begin
                    j <= f1_j_n;
                    ph <= 2'd1;
                    if (j == 9'd399) st <= S_F1_REQ;
                end
            end
            S_F1_REQ: st <= S_F1_MUL;
            S_F1_MUL: st <= S_F1_SH;
            S_F1_SH:  st <= S_F1_WR;
            S_F1_WR: begin
                if (n == 5'd31) begin
                    oc <= 0; j <= 0; ph <= 0; ss <= 0; st <= S_F2_SETUP;
                end else begin
                    n <= n + 5'd1; j <= 0; ss <= 0; st <= S_F1_SETUP;
                end
            end

            // ----------------------------------------------------- fc2
            S_F2_SETUP: begin
                if (ss == 3'd7) begin
                    ss <= 0; ph <= 1; st <= S_F2_TERM;
                end else ss <= ss + 3'd1;
            end
            S_F2_TERM: begin
                if (ph == 2'd1) ph <= 2'd2;
                else begin
                    j <= f2_j_n;
                    ph <= 2'd1;
                    if (j[4:0] == 5'd31) st <= S_F2_REQ;
                end
            end
            S_F2_REQ: st <= S_F2_MUL;
            S_F2_MUL: begin f2b <= 0; st <= S_F2_SH; end
            S_F2_SH:  st <= S_F2_WR;
            S_F2_WR: begin
                if (f2b == 4'd3) begin
                    if (oc == 4'd9) begin amc <= 0; amp <= 0; st <= S_AM; end
                    else begin oc <= oc + 4'd1; j <= 0; ss <= 0;
                               st <= S_F2_SETUP; end
                end else f2b <= f2b + 4'd1;
            end

            // ---------------------------------------------------- argmax
            S_AM: begin
                amp <= amp + 3'd1;
                if (amp == 3'd5) begin
                    if (amc == 4'd9) st <= S_DONE;
                    else begin amc <= amc + 4'd1; amp <= 0; end
                end
            end

            S_DONE: begin
                busy <= 1'b0; done <= 1'b1;
                st <= S_IDLE;
            end

            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
