// UART <-> B12 load-port bridge for the 74-series CNN board.
//
// PC side  : 115200 8N1 framed protocol (Host/protocol.py)
//              A5 5A | CMD | LEN_L LEN_H | payload | CRC_L CRC_H
//              5A A5 | STAT | LEN_L LEN_H | payload | CRC_L CRC_H
// Board side: S10 "PARAM PROG" 2x20 header (H_D, H_A, H_MEM_SEL, LOAD_EN,
//             nWE, nOE) plus IMAGE_DONE_N / MODEL_DONE_N, START_RAW,
//             RESET_RAW and the J10007 status header.
//
// The FPGA does not run the CNN - it sequences the board: stream the image
// into MEM_SEL=0, raise IMAGE_DONE_N, pulse START, wait for RESULT_VALID,
// read the ten int32 logits from MEM_SEL=6 and send them back.
`timescale 1ns/1ps
module host_bridge #(
    parameter integer CLK_HZ     = 50_000_000,
    parameter integer BAUD       = 115200,
    parameter integer TIMEOUT_MS = 3000
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        uart_rx,
    output wire        uart_tx,

    // B12 J6 load port
    inout  wire [7:0]  ld_d,
    output wire [15:0] ld_a,
    output wire [4:0]  ld_sel,
    output wire        ld_en,
    output wire        ld_nwe,
    output wire        ld_noe,
    output wire        ld_dir,      // 74LVC245A DIR: 1 = read
    output wire        ld_oe_n,     // 74LVC245A /OE: 0 while active

    // B12 misc control
    output reg         start_raw,
    output reg         reset_raw,
    output reg         image_done_n,
    output reg         model_done_n,

    // B12 J10007 status header
    input  wire        st_busy,
    input  wire        st_done,
    input  wire        st_result_valid,
    input  wire        st_error,
    input  wire [3:0]  st_result,
    input  wire [3:0]  st_error_code,
    input  wire        st_image_ready,
    input  wire        st_model_ready
);
    localparam [7:0] CMD_PING        = 8'h01;
    localparam [7:0] CMD_LOAD_IMAGE  = 8'h02;
    localparam [7:0] CMD_INFER       = 8'h03;
    localparam [7:0] CMD_READ_SCORES = 8'h04;
    localparam [7:0] CMD_RESET       = 8'h05;
    localparam [7:0] CMD_STATUS      = 8'h06;
    localparam [7:0] CMD_LOAD_MEM    = 8'h07;
    localparam [7:0] CMD_READ_MEM    = 8'h08;

    localparam [7:0] ST_OK        = 8'd0;
    localparam [7:0] ST_BAD_CRC   = 8'd1;
    localparam [7:0] ST_BAD_LEN   = 8'd2;
    localparam [7:0] ST_BAD_CMD   = 8'd3;
    localparam [7:0] ST_TIMEOUT   = 8'd4;
    localparam [7:0] ST_BOARD_ERR = 8'd5;
    localparam [7:0] ST_BAD_ARG   = 8'd6;

    localparam integer START_CLKS = CLK_HZ / 100_000;   // 10 us
    localparam integer RESET_CLKS = CLK_HZ / 100;       // 10 ms
    localparam integer TMO_CLKS   = (CLK_HZ / 1000) * TIMEOUT_MS;
    localparam integer DONE_CLKS  = CLK_HZ / 1_000_000; // 1 us

    localparam [4:0] SEL_IMAGE  = 5'd0;
    localparam [4:0] SEL_SCORES = 5'd6;

    // ------------------------------------------------------------- uart
    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data;
    reg        tx_send;
    wire       tx_busy;

    uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_rx (
        .clk(clk), .rst_n(rst_n), .rx(uart_rx),
        .data(rx_data), .valid(rx_valid));

    uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_tx (
        .clk(clk), .rst_n(rst_n), .data(tx_data), .send(tx_send),
        .busy(tx_busy), .tx(uart_tx));

    // -------------------------------------------------------------- crc
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

    // ------------------------------------------------------------ buffers
    reg [7:0]  pkt [0:1023];
    reg [10:0] p_len;
    reg [7:0]  p_cmd;
    reg        p_ready;         // one-clock pulse: frame received
    reg        p_bad_crc;
    reg [7:0]  r_stat;
    reg [10:0] r_len;

    // ---------------------------------------------------------- frame rx
    localparam R_IDLE = 0, R_SOF2 = 1, R_CMD = 2, R_LENL = 3,
               R_LENH = 4, R_DATA = 5, R_CRCL = 6, R_CRCH = 7;
    reg [2:0]  rxs;
    reg [15:0] crc_rx;
    reg [7:0]  crc_low;
    reg [7:0]  len_l;
    reg [10:0] rx_idx;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rxs <= R_IDLE; p_ready <= 1'b0; p_bad_crc <= 1'b0;
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
                R_CMD: begin
                    p_cmd  <= rx_data;
                    crc_rx <= crc_byte(16'hFFFF, rx_data);
                    rxs    <= R_LENL;
                end
                R_LENL: begin
                    len_l  <= rx_data;
                    crc_rx <= crc_byte(crc_rx, rx_data);
                    rxs    <= R_LENH;
                end
                R_LENH: begin
                    p_len  <= {rx_data[2:0], len_l};
                    crc_rx <= crc_byte(crc_rx, rx_data);
                    rx_idx <= 0;
                    rxs    <= ({rx_data[2:0], len_l} == 0) ? R_CRCL : R_DATA;
                end
                R_DATA: begin
                    if (rx_idx < 11'd1024) pkt[rx_idx] <= rx_data;
                    crc_rx      <= crc_byte(crc_rx, rx_data);
                    rx_idx      <= rx_idx + 1'b1;
                    if (rx_idx + 1'b1 == p_len) rxs <= R_CRCL;
                end
                R_CRCL: begin
                    crc_low <= rx_data;
                    rxs     <= R_CRCH;
                end
                R_CRCH: begin
                    p_bad_crc <= ({rx_data, crc_low} != crc_rx);
                    p_ready   <= 1'b1;
                    rxs       <= R_IDLE;
                end
                default: rxs <= R_IDLE;
                endcase
            end
        end
    end

    // ------------------------------------------------------- status sync
    reg [2:0] sv, se, sd;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin sv <= 0; se <= 0; sd <= 0; end
        else begin
            sv <= {sv[1:0], st_result_valid};
            se <= {se[1:0], st_error};
            sd <= {sd[1:0], st_done};
        end
    wire result_valid_s = sv[2];
    wire error_s        = se[2];
    wire done_s         = sd[2];

    // ------------------------------------------------------- memory port
    reg        mp_start;
    reg        mp_wr;
    reg [4:0]  mp_sel;
    reg [15:0] mp_addr;
    reg [7:0]  mp_wdata;
    wire [7:0] mp_rdata;
    wire       mp_done;

    b12_port u_port (
        .clk(clk), .rst_n(rst_n),
        .start(mp_start), .wr(mp_wr), .sel(mp_sel), .addr(mp_addr),
        .wdata(mp_wdata), .rdata(mp_rdata), .done(mp_done),
        .dir(ld_dir), .oe_n(ld_oe_n),
        .d(ld_d), .a(ld_a), .s(ld_sel), .en(ld_en), .nwe(ld_nwe), .noe(ld_noe));

    // ---------------------------------------------------------- executor
    localparam X_IDLE = 0, X_DISP = 1, X_WR = 2, X_RD = 3, X_STRT = 4,
               X_WAIT = 5, X_IMG = 6, X_FIN = 7, X_TX = 8, X_RSTL = 9;

    reg [3:0]  xs;
    reg        mp_busy;
    reg [4:0]  x_sel;
    reg [15:0] x_base;
    reg [10:0] x_n;
    reg [10:0] x_i;
    reg [10:0] x_off;
    reg [31:0] cnt;            // must hold TMO_CLKS = CLK_HZ/1000*TIMEOUT_MS
    reg        done_seen;
    reg        infer_result;
    reg [7:0]  inf_result, inf_errcode, inf_flags;
    reg        tx_req;
    reg        tx_done;         // level: last byte shifted out, cleared with tx_req

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            xs <= X_IDLE; mp_start <= 1'b0; mp_wr <= 1'b0; mp_sel <= 0;
            mp_addr <= 0; mp_wdata <= 0; mp_busy <= 1'b0;
            x_sel <= 0; x_base <= 0; x_n <= 0; x_i <= 0; x_off <= 0; cnt <= 0;
            r_stat <= ST_OK; r_len <= 0; start_raw <= 1'b0;
            reset_raw <= 1'b1; image_done_n <= 1'b1; model_done_n <= 1'b1;
            done_seen <= 0; infer_result <= 0; tx_req <= 1'b0;
            inf_result <= 0; inf_errcode <= 0; inf_flags <= 0;
        end else begin
            mp_start <= 1'b0;
            case (xs)
            X_IDLE: begin
                start_raw <= 1'b0;
                if (p_ready) begin
                    r_len <= 0;
                    r_stat <= ST_OK;
                    x_i <= 0;
                    x_off <= 0;
                    xs <= X_DISP;
                end
            end

            X_DISP: begin
                if (p_bad_crc) begin
                    r_stat <= ST_BAD_CRC;
                    xs <= X_FIN;
                end else if (p_len > 11'd1024) begin
                    r_stat <= ST_BAD_LEN;   // longer than the frame buffer
                    xs <= X_FIN;
                end else begin
                    case (p_cmd)
                    CMD_PING: begin
                        pkt[0] <= "M"; pkt[1] <= "N"; pkt[2] <= "I";
                        pkt[3] <= "S"; pkt[4] <= "T"; pkt[5] <= "7";
                        pkt[6] <= "4"; pkt[7] <= 8'h01;
                        r_len <= 11'd8;
                        xs <= X_FIN;
                    end
                    CMD_LOAD_IMAGE: begin
                        if (p_len != 11'd784) begin
                            r_stat <= ST_BAD_LEN;
                            xs <= X_FIN;
                        end else begin
                            x_sel <= SEL_IMAGE;
                            x_base <= 16'd0;
                            x_n <= 11'd784;
                            x_i <= 0;
                            x_off <= 0;
                            xs <= X_WR;
                        end
                    end
                    CMD_LOAD_MEM: begin
                        if (p_len < 11'd5) begin
                            r_stat <= ST_BAD_LEN;
                            xs <= X_FIN;
                        end else if (pkt[0] > 5'd7) begin
                            r_stat <= ST_BAD_ARG;   // EEPROM writes need ms
                            xs <= X_FIN;
                        end else if ({pkt[4], pkt[3]} + 11'd5 != p_len) begin
                            r_stat <= ST_BAD_ARG;
                            xs <= X_FIN;
                        end else begin
                            x_sel <= pkt[0];
                            x_base <= {pkt[2], pkt[1]};
                            x_n <= {pkt[4], pkt[3]};
                            x_i <= 0;
                            x_off <= 11'd5;
                            xs <= X_WR;
                        end
                    end
                    CMD_READ_MEM: begin
                        if (p_len != 11'd5) begin
                            r_stat <= ST_BAD_LEN;
                            xs <= X_FIN;
                        end else if ({pkt[4], pkt[3]} > 11'd512) begin
                            r_stat <= ST_BAD_ARG;
                            xs <= X_FIN;
                        end else begin
                            x_sel <= pkt[0];
                            x_base <= {pkt[2], pkt[1]};
                            x_n <= {pkt[4], pkt[3]};
                            x_i <= 0;
                            xs <= X_RD;
                        end
                    end
                    CMD_READ_SCORES: begin
                        x_sel <= SEL_SCORES;
                        x_base <= 16'd0;
                        x_n <= 11'd40;
                        x_i <= 0;
                        xs <= X_RD;
                    end
                    CMD_INFER: begin
                        done_seen <= 1'b0;
                        infer_result <= 1'b1;
                        start_raw <= 1'b1;
                        cnt <= START_CLKS;
                        xs <= X_STRT;
                    end
                    CMD_RESET: begin
                        reset_raw <= 1'b0;
                        cnt <= RESET_CLKS;
                        xs <= X_RSTL;
                    end
                    CMD_STATUS: begin
                        pkt[0] <= {4'b0, result_valid_s, error_s,
                                   done_s, st_busy};
                        pkt[1] <= {4'b0, st_result};
                        pkt[2] <= {4'b0, st_error_code};
                        r_len <= 11'd3;
                        xs <= X_FIN;
                    end
                    default: begin
                        r_stat <= ST_BAD_CMD;
                        xs <= X_FIN;
                    end
                    endcase
                end
            end

            X_WR: begin
                if (!mp_busy) begin
                    mp_start <= 1'b1;
                    mp_wr <= 1'b1;
                    mp_sel <= x_sel;
                    mp_addr <= x_base + x_i;
                    mp_wdata <= pkt[x_i + x_off];
                    mp_busy <= 1'b1;
                end else if (mp_done) begin
                    mp_busy <= 1'b0;
                    if (x_i + 1'b1 == x_n) begin
                        if (p_cmd == CMD_LOAD_IMAGE) begin
                            image_done_n <= 1'b0;
                            cnt <= DONE_CLKS;
                            xs <= X_IMG;
                        end else begin
                            pkt[0] <= 8'h01;
                            r_len <= 11'd1;
                            xs <= X_FIN;
                        end
                    end else begin
                        x_i <= x_i + 1'b1;
                    end
                end
            end

            X_RD: begin
                if (!mp_busy) begin
                    mp_start <= 1'b1;
                    mp_wr <= 1'b0;
                    mp_sel <= x_sel;
                    mp_addr <= x_base + x_i;
                    mp_busy <= 1'b1;
                end else if (mp_done) begin
                    mp_busy <= 1'b0;
                    pkt[x_i] <= mp_rdata;
                    if (x_i + 1'b1 == x_n) begin
                        if (infer_result) begin
                            pkt[40] <= inf_result;
                            pkt[41] <= inf_errcode;
                            pkt[42] <= inf_flags;
                            r_len <= 11'd43;
                            infer_result <= 1'b0;
                        end else begin
                            r_len <= x_n;
                        end
                        xs <= X_FIN;
                    end else begin
                        x_i <= x_i + 1'b1;
                    end
                end
            end

            X_STRT: begin
                if (cnt == 0) begin
                    start_raw <= 1'b0;
                    cnt <= TMO_CLKS;
                    xs <= X_WAIT;
                end else cnt <= cnt - 1'b1;
            end

            X_WAIT: begin
                if (done_s) done_seen <= 1'b1;
                if (error_s) begin
                    r_stat <= ST_BOARD_ERR;
                    inf_flags <= {5'b0, done_seen, 1'b1, 1'b0};
                    xs <= X_FIN;
                end else if (result_valid_s) begin
                    inf_result  <= {4'b0, st_result};
                    inf_errcode <= {4'b0, st_error_code};
                    inf_flags   <= {5'b0, done_seen, 1'b0, 1'b1};
                    x_sel <= SEL_SCORES;
                    x_base <= 16'd0;
                    x_n <= 11'd40;
                    x_i <= 0;
                    xs <= X_RD;
                end else if (cnt == 0) begin
                    r_stat <= ST_TIMEOUT;
                    inf_flags <= {5'b0, done_seen, 1'b0, 1'b0};
                    xs <= X_FIN;
                end else begin
                    cnt <= cnt - 1'b1;
                end
            end

            X_IMG: begin
                if (cnt == 0) begin
                    image_done_n <= 1'b1;
                    pkt[0] <= 8'h01;
                    r_len <= 11'd1;
                    xs <= X_FIN;
                end else cnt <= cnt - 1'b1;
            end

            X_FIN: begin
                tx_req <= 1'b1;
                xs <= X_TX;
            end

            X_TX: begin
                if (tx_done) begin
                    tx_req <= 1'b0;
                    xs <= X_IDLE;
                end
            end

            X_RSTL: begin
                if (cnt == 0) begin
                    reset_raw <= 1'b1;
                    pkt[0] <= 8'h01;
                    r_len <= 11'd1;
                    xs <= X_FIN;
                end else cnt <= cnt - 1'b1;
            end

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
    reg [15:0] crc_tx;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            txs <= T_SOF0; tx_active <= 1'b0; tx_idx <= 0;
            tx_data <= 0; tx_send <= 1'b0; crc_tx <= 16'hFFFF;
            tx_done <= 1'b0;
        end else begin
            tx_send <= 1'b0;

            // A frame is finished only after its CRC_H byte leaves the
            // shifter.  With no `tx_done` gate the FSM would see tx_req
            // still high (the executor needs a cycle to clear it) and
            // immediately repeat the whole frame.
            if (!tx_req) tx_done <= 1'b0;

            if (tx_req && !tx_active && !tx_done) begin
                tx_active <= 1'b1;
                txs <= T_SOF0;
                tx_idx <= 0;
                crc_tx <= 16'hFFFF;
            end

            if (tx_active && !tx_busy && !tx_send) begin
                case (txs)
                T_SOF0: begin tx_data <= 8'h5A; tx_send <= 1'b1; txs <= T_SOF1; end
                T_SOF1: begin tx_data <= 8'hA5; tx_send <= 1'b1; txs <= T_CODE; end
                T_CODE: begin
                    tx_data <= r_stat; tx_send <= 1'b1;
                    crc_tx  <= crc_byte(16'hFFFF, r_stat);
                    txs     <= T_LENL;
                end
                T_LENL: begin
                    tx_data <= r_len[7:0]; tx_send <= 1'b1;
                    crc_tx  <= crc_byte(crc_tx, r_len[7:0]);
                    txs     <= T_LENH;
                end
                T_LENH: begin
                    tx_data <= {5'b0, r_len[10:8]}; tx_send <= 1'b1;
                    crc_tx  <= crc_byte(crc_tx, {5'b0, r_len[10:8]});
                    tx_idx  <= 0;
                    txs     <= (r_len == 0) ? T_CRCL : T_DATA;
                end
                T_DATA: begin
                    tx_data <= pkt[tx_idx]; tx_send <= 1'b1;
                    crc_tx  <= crc_byte(crc_tx, pkt[tx_idx]);
                    tx_idx  <= tx_idx + 1'b1;
                    if (tx_idx + 1'b1 == r_len) txs <= T_CRCL;
                end
                T_CRCL: begin
                    tx_data <= crc_tx[7:0]; tx_send <= 1'b1;
                    txs     <= T_CRCH;
                end
                T_CRCH: begin
                    tx_data <= crc_tx[15:8]; tx_send <= 1'b1;
                    txs     <= T_SOF0;
                    tx_active <= 1'b0;
                    tx_done <= 1'b1;
                end
                default: txs <= T_SOF0;
                endcase
            end
        end
    end

    // The demo assumes the weight EEPROMs were programmed offline, so the
    // model is declared ready together with the image.
    always @(posedge clk or negedge rst_n)
        if (!rst_n) model_done_n <= 1'b1;
        else        model_done_n <= image_done_n;

endmodule
