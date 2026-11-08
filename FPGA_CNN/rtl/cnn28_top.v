// UART front end for the on-chip CNN: same framed protocol the host already
// speaks (Host/protocol.py), but the payload is executed by cnn28_core
// instead of the 74-series board.
//
//   A5 5A | CMD | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H   host -> FPGA
//   5A A5 | STAT| LEN_L LEN_H | PAYLOAD | CRC_L CRC_H   FPGA -> host
//
// CMD 0x01 PING        -> "CNN28-FPGA"
// CMD 0x02 LOAD_IMAGE  -> 784 B into IMG; reply 01
// CMD 0x03 INFER       -> 40 B logits + result + errcode + flags
// CMD 0x04 READ_SCORES -> 40 B logits
// CMD 0x05 RESET       -> 01
// CMD 0x06 STATUS      -> flags + result + errcode
// CMD 0x07 LOAD_MEM    -> sel,addrL,addrH,nL,nH,data... ; reply 01
// CMD 0x08 READ_MEM    -> sel,addrL,addrH,nL,nH -> n bytes
//
// sel map (matches cnn28_core's byte address map):
//   0 IMG 1024 | 1 W1 200 | 2 W2 1152 | 3 W3 12800 | 4 W4 320
//   5 BIAS 264 | 6 LOG 40  | 7 QP 1056
`timescale 1ns/1ps
module cnn28_top #(
    parameter integer CLK_HZ     = 50_000_000,
    parameter integer BAUD       = 115200,
    parameter integer TIMEOUT_MS = 3000
)(
    input  wire clk,
`ifndef NO_EXT_RESET
    input  wire rst_n,
`endif
    input  wire uart_rx,
    output wire uart_tx
`ifdef LED_HEARTBEAT
    , output wire led          // ~1.5 Hz blink: proof the design is running
`endif
);

`ifdef NO_EXT_RESET
    // No reset pin on the board: hold everything for 128 clocks after
    // configuration (all registers power up 0, so this is a real POR).
    reg [7:0] por = 8'd0;
    always @(posedge clk) if (!por[7]) por <= por + 1'b1;
    wire rst_n_i = por[7];
`else
    wire rst_n_i = rst_n;
`endif

    localparam [7:0] CMD_PING        = 8'h01;
    localparam [7:0] CMD_LOAD_IMAGE  = 8'h02;
    localparam [7:0] CMD_INFER       = 8'h03;
    localparam [7:0] CMD_READ_SCORES = 8'h04;
    localparam [7:0] CMD_RESET       = 8'h05;
    localparam [7:0] CMD_STATUS      = 8'h06;
    localparam [7:0] CMD_LOAD_MEM    = 8'h07;
    localparam [7:0] CMD_READ_MEM    = 8'h08;

    localparam [7:0] ST_OK = 0, ST_BAD_CRC = 1, ST_BAD_LEN = 2, ST_BAD_CMD = 3,
                     ST_TIMEOUT = 4, ST_BOARD_ERR = 5, ST_BAD_ARG = 6;

    localparam integer TMO_CLKS = (CLK_HZ / 1000) * TIMEOUT_MS;

    // ------------------------------------------------------------- uart
    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data;
    reg        tx_send;
    wire       tx_busy;

    uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_rx (
        .clk(clk), .rst_n(rst_n_i), .rx(uart_rx),
        .data(rx_data), .valid(rx_valid));

    uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_tx (
        .clk(clk), .rst_n(rst_n_i), .data(tx_data), .send(tx_send),
        .busy(tx_busy), .tx(uart_tx));

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

    function [15:0] sel_base;
        input [2:0] sel;
        begin
            case (sel)
            3'd0: sel_base = 16'h0000;
            3'd1: sel_base = 16'h0400;
            3'd2: sel_base = 16'h0600;
            3'd3: sel_base = 16'h0B00;
            3'd4: sel_base = 16'h3D00;
            3'd5: sel_base = 16'h6200;
            3'd6: sel_base = 16'h6100;
            3'd7: sel_base = 16'h6400;
            endcase
        end
    endfunction

    function [15:0] sel_size;
        input [2:0] sel;
        begin
            case (sel)
            3'd0: sel_size = 16'd784;
            3'd1: sel_size = 16'd200;
            3'd2: sel_size = 16'd1152;
            3'd3: sel_size = 16'd12800;
            3'd4: sel_size = 16'd320;
            3'd5: sel_size = 16'd264;
            3'd6: sel_size = 16'd40;
            3'd7: sel_size = 16'd1056;
            endcase
        end
    endfunction

    // ------------------------------------------------------------ buffers
    reg [7:0]  rxb [0:1023];   // received frame (registered read port)
    reg [7:0]  txb [0:63];     // reply payload (max reply is 43 bytes)
    reg [7:0]  h0, h1, h2, h3, h4;   // first five payload bytes (command header)
    reg [10:0] rd_idx;
    reg [7:0]  rxb_q;
    always @(posedge clk) rxb_q <= rxb[rd_idx];
    reg [10:0] p_len;
    reg [7:0]  p_cmd;
    reg        p_ready, p_bad_crc;
    reg [7:0]  r_stat;
    reg [10:0] r_len;

    localparam R_IDLE = 0, R_SOF2 = 1, R_CMD = 2, R_LENL = 3,
               R_LENH = 4, R_DATA = 5, R_CRCL = 6, R_CRCH = 7;
    reg [2:0]  rxs;
    reg [15:0] crc_rx;
    reg [7:0]  crc_low, len_l;
    reg [10:0] rx_idx;

    always @(posedge clk or negedge rst_n_i) begin
        if (!rst_n_i) begin
            rxs <= R_IDLE; p_ready <= 0; p_bad_crc <= 0;
            p_len <= 0; p_cmd <= 0; crc_rx <= 16'hFFFF; rx_idx <= 0;
        end else begin
            p_ready <= 1'b0;
            if (rx_valid) begin
                case (rxs)
                R_IDLE: if (rx_data == 8'hA5) rxs <= R_SOF2;
                R_SOF2: begin
                    if (rx_data == 8'h5A)      rxs <= R_CMD;
                    else if (rx_data == 8'hA5) rxs <= R_SOF2;
                    else                       rxs <= R_IDLE;
                end
                R_CMD: begin p_cmd <= rx_data; crc_rx <= crc_byte(16'hFFFF, rx_data);
                                rxs <= R_LENL; end
                R_LENL: begin len_l <= rx_data; crc_rx <= crc_byte(crc_rx, rx_data);
                                rxs <= R_LENH; end
                R_LENH: begin
                    p_len  <= {rx_data[2:0], len_l};
                    crc_rx <= crc_byte(crc_rx, rx_data);
                    rx_idx <= 0;
                    rxs    <= ({rx_data[2:0], len_l} == 0) ? R_CRCL : R_DATA;
                end
                R_DATA: begin
                    if (rx_idx < 11'd1024) rxb[rx_idx] <= rx_data;
                    if (rx_idx == 11'd0) h0 <= rx_data;
                    else if (rx_idx == 11'd1) h1 <= rx_data;
                    else if (rx_idx == 11'd2) h2 <= rx_data;
                    else if (rx_idx == 11'd3) h3 <= rx_data;
                    else if (rx_idx == 11'd4) h4 <= rx_data;
                    crc_rx <= crc_byte(crc_rx, rx_data);
                    rx_idx <= rx_idx + 1'b1;
                    if (rx_idx + 1'b1 == p_len) rxs <= R_CRCL;
                end
                R_CRCL: begin crc_low <= rx_data; rxs <= R_CRCH; end
                R_CRCH: begin p_bad_crc <= ({rx_data, crc_low} != crc_rx);
                                p_ready <= 1'b1; rxs <= R_IDLE; end
                default: rxs <= R_IDLE;
                endcase
            end
        end
    end

`ifdef LED_HEARTBEAT
    reg [24:0] hb;
    always @(posedge clk) hb <= hb + 1'b1;
    assign led = hb[24];
`endif

    // ------------------------------------------------------ memory port
    wire        m_we;
    reg  [15:0] m_addr;
    reg  [7:0]  m_wdata;
    wire [7:0]  m_rdata;
    reg         core_start;
    wire        core_busy, core_done;
    wire [3:0]  core_result;

    cnn28_core u_core (
        .clk(clk), .rst_n(rst_n_i),
        .h_we(m_we), .h_addr_ok(1'b1), .h_addr(m_addr),
        .h_wdata(m_wdata), .h_rdata(m_rdata),
        .start(core_start), .busy(core_busy), .done(core_done),
        .result(core_result));

    // ---------------------------------------------------------- executor
    localparam X_IDLE = 0, X_DISP = 1, X_WR = 2, X_RDW = 3, X_RDR = 4,
               X_STRT = 5, X_WAIT = 6, X_FIN = 7, X_TX = 8, X_RDW2 = 9,
               X_WRP = 10, X_WR2 = 11;

    reg [3:0]  xs;
    assign m_we = (xs == X_WR2);
    reg [2:0]  x_sel;
    reg [15:0] x_base;
    reg [10:0] x_n, x_i, x_off;
    reg [31:0] cnt;
    reg        rd_ph;
    reg        done_seen, infer_result;
    reg [7:0]  inf_result, inf_errcode, inf_flags;
    reg        tx_req, tx_done;
    reg        result_valid;

    always @(posedge clk or negedge rst_n_i) begin
        if (!rst_n_i) begin
            xs <= X_IDLE; m_addr <= 0; m_wdata <= 0; core_start <= 0;
            x_sel <= 0; x_base <= 0; x_n <= 0; x_i <= 0; x_off <= 0;
            cnt <= 0; rd_ph <= 0; done_seen <= 0; infer_result <= 0;
            r_stat <= ST_OK; r_len <= 0; inf_result <= 0; inf_errcode <= 0;
            inf_flags <= 0; tx_req <= 0; result_valid <= 0;
        end else begin
            core_start <= 1'b0;
            case (xs)
            X_IDLE: if (p_ready) begin
                r_len <= 0; r_stat <= ST_OK; x_i <= 0; x_off <= 0;
                // prime the registered frame-buffer read port: the byte the
                // first fetch will consume must be requested one cycle early
                rd_idx <= (p_cmd == CMD_LOAD_IMAGE) ? 11'd0 : 11'd5;
                xs <= X_DISP;
            end

            X_DISP: begin
                if (p_bad_crc) begin r_stat <= ST_BAD_CRC; xs <= X_FIN; end
                else if (p_len > 11'd1024) begin r_stat <= ST_BAD_LEN; xs <= X_FIN; end
                else case (p_cmd)
                CMD_PING: begin
                    txb[0] <= "C"; txb[1] <= "N"; txb[2] <= "N";
                    txb[3] <= "2"; txb[4] <= "8"; txb[5] <= "-";
                    txb[6] <= "F"; txb[7] <= "P"; txb[8] <= "G";
                    txb[9] <= "A";
                    r_len <= 11'd10; xs <= X_FIN;
                end
                CMD_LOAD_IMAGE: begin
                    if (p_len != 11'd784) begin r_stat <= ST_BAD_LEN; xs <= X_FIN; end
                    else begin
                        x_sel <= 3'd0; x_base <= 16'h0000; x_n <= 11'd784;
                        x_i <= 0; x_off <= 0;
                        m_addr <= 16'h0000;
                        xs <= X_WRP;
                    end
                end
                CMD_LOAD_MEM: begin
                    if (p_len < 11'd6) begin r_stat <= ST_BAD_LEN; xs <= X_FIN; end
                    else if ({h4, h3} + 11'd5 != p_len) begin
                        r_stat <= ST_BAD_LEN; xs <= X_FIN;
                    end else if (h0 == 8'd6) begin
                        r_stat <= ST_BAD_ARG; xs <= X_FIN;   // logits read-only
                    end else if (h0 > 8'd7) begin
                        r_stat <= ST_BAD_ARG; xs <= X_FIN;
                    end else if ({h2, h1} + {h4, h3} >
                                 sel_size(h0[2:0])) begin
                        r_stat <= ST_BAD_ARG; xs <= X_FIN;
                    end else begin
                        x_sel  <= h0[2:0];
                        x_base <= sel_base(h0[2:0]) + {h2, h1};
                        x_n    <= {h4, h3};
                        x_i    <= 0; x_off <= 11'd5;
                        m_addr <= x_base;
                        xs     <= X_WRP;
                    end
                end
                CMD_READ_MEM: begin
                    if (p_len != 11'd5) begin r_stat <= ST_BAD_LEN; xs <= X_FIN; end
                    else if (h0 > 8'd7) begin r_stat <= ST_BAD_ARG; xs <= X_FIN; end
                    else if ({h2, h1} + {h4, h3} >
                             sel_size(h0[2:0])) begin
                        r_stat <= ST_BAD_ARG; xs <= X_FIN;
                    end else if ({h4, h3} > 11'd64) begin
                        r_stat <= ST_BAD_ARG; xs <= X_FIN;   // reply buffer limit
                    end else begin
                        x_base <= sel_base(h0[2:0]) + {h2, h1};
                        x_n    <= {h4, h3};
                        x_i    <= 0; infer_result <= 0;
                        xs     <= X_RDW;
                    end
                end
                CMD_READ_SCORES: begin
                    x_base <= 16'h6100; x_n <= 11'd40; x_i <= 0;
                    infer_result <= 0; xs <= X_RDW;
                end
                CMD_INFER: begin
                    done_seen <= 0;
                    result_valid <= 0;
                    core_start <= 1'b1;
                    cnt <= TMO_CLKS;
                    xs <= X_WAIT;
                end
                CMD_RESET: begin
                    txb[0] <= 8'h01; r_len <= 11'd1; xs <= X_FIN;
                end
                CMD_STATUS: begin
                    txb[0] <= {3'b0, result_valid, 1'b0, done_seen, core_busy};
                    txb[1] <= {4'b0, core_result};
                    txb[2] <= 8'h00;
                    r_len <= 11'd3; xs <= X_FIN;
                end
                default: begin r_stat <= ST_BAD_CMD; xs <= X_FIN; end
                endcase
            end

            // Byte streaming: rxb has a registered read port, so each
            // payload byte is fetched one cycle before it is written.
            X_WRP: begin                   // fetch byte x_i
                m_wdata <= rxb_q;
                m_addr  <= x_base + x_i;
                rd_idx  <= x_i + x_off + 11'd1;
                xs      <= X_WR2;
            end
            X_WR2: begin                   // m_we high: RAM writes on exit
                if (x_i + 1'b1 == x_n) begin
                    txb[0] <= 8'h01; r_len <= 11'd1;
                    xs <= X_FIN;
                end else begin
                    x_i    <= x_i + 1'b1;
                    rd_idx <= x_i + x_off + 11'd2;
                    xs     <= X_WRP;
                end
            end

            X_RDW: begin
                m_addr <= x_base + x_i;
                xs     <= X_RDW2;      // address register needs one cycle
            end
            X_RDW2: xs <= X_RDR;
            X_RDR: begin
                if (x_i < 11'd64) txb[x_i] <= m_rdata;
                if (x_i + 1'b1 == x_n) begin
                    if (infer_result) begin
                        txb[40] <= inf_result;
                        txb[41] <= inf_errcode;
                        txb[42] <= inf_flags;
                        r_len <= 11'd43;
                        infer_result <= 1'b0;
                    end else r_len <= x_n;
                    xs <= X_FIN;
                end else begin
                    x_i <= x_i + 1'b1;
                    xs  <= X_RDW;
                end
            end

            X_WAIT: begin
                if (core_done) begin
                    done_seen <= 1'b1;
                    result_valid <= 1'b1;
                    inf_result  <= {4'b0, core_result};
                    inf_flags   <= 8'h05;      // bit0 valid, bit2 done
                    x_base <= 16'h6100; x_n <= 11'd40; x_i <= 0;
                    infer_result <= 1'b1;
                    xs <= X_RDW;
                end else if (cnt == 0) begin
                    r_stat <= ST_TIMEOUT;
                    inf_flags <= 8'h00;
                    xs <= X_FIN;
                end else cnt <= cnt - 1'b1;
            end

            X_FIN: begin tx_req <= 1'b1; xs <= X_TX; end
            X_TX: if (tx_done) begin tx_req <= 1'b0; xs <= X_IDLE; end
            default: xs <= X_IDLE;
            endcase
        end
    end

    // --------------------------------------------------------- frame tx
    localparam T_SOF0 = 0, T_SOF1 = 1, T_CODE = 2, T_LENL = 3,
               T_LENH = 4, T_DATA = 5, T_CRCL = 6, T_CRCH = 7;
    reg [2:0]  txs;
    reg        tx_active;
    reg [10:0] tx_idx;
    reg [7:0]  txb_q;
    reg [15:0] crc_tx;

    // registered read port so txb maps to a block RAM
    always @(posedge clk) txb_q <= txb[tx_idx];

    always @(posedge clk or negedge rst_n_i) begin
        if (!rst_n_i) begin
            txs <= T_SOF0; tx_active <= 0; tx_idx <= 0;
            tx_data <= 0; tx_send <= 0; crc_tx <= 16'hFFFF; tx_done <= 0;
        end else begin
            tx_send <= 1'b0;
            if (!tx_req) tx_done <= 1'b0;
            if (tx_req && !tx_active && !tx_done) begin
                tx_active <= 1'b1; txs <= T_SOF0; tx_idx <= 0;
                crc_tx <= 16'hFFFF;
            end
            if (tx_active && !tx_busy && !tx_send) begin
                case (txs)
                T_SOF0: begin tx_data <= 8'h5A; tx_send <= 1; txs <= T_SOF1; end
                T_SOF1: begin tx_data <= 8'hA5; tx_send <= 1; txs <= T_CODE; end
                T_CODE: begin tx_data <= r_stat; tx_send <= 1;
                              crc_tx <= crc_byte(16'hFFFF, r_stat);
                              txs <= T_LENL; end
                T_LENL: begin tx_data <= r_len[7:0]; tx_send <= 1;
                              crc_tx <= crc_byte(crc_tx, r_len[7:0]);
                              txs <= T_LENH; end
                T_LENH: begin tx_data <= {5'b0, r_len[10:8]}; tx_send <= 1;
                              crc_tx <= crc_byte(crc_tx, {5'b0, r_len[10:8]});
                              tx_idx <= 0;
                              txs <= (r_len == 0) ? T_CRCL : T_DATA; end
                T_DATA: begin tx_data <= txb_q; tx_send <= 1;
                              crc_tx <= crc_byte(crc_tx, txb_q);
                              tx_idx <= tx_idx + 1'b1;
                              if (tx_idx + 1'b1 == r_len) txs <= T_CRCL; end
                T_CRCL: begin tx_data <= crc_tx[7:0]; tx_send <= 1; txs <= T_CRCH; end
                T_CRCH: begin tx_data <= crc_tx[15:8]; tx_send <= 1;
                              txs <= T_SOF0; tx_active <= 1'b0; tx_done <= 1'b1; end
                default: txs <= T_SOF0;
                endcase
            end
        end
    end
endmodule
