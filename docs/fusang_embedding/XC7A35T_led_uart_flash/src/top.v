`timescale 1ns / 1ps
// =============================================================================
// top.v - A7-Lite 顶层模块
//   功能：
//     1. LED 闪烁（原有功能）
//        - led[0] (D6 红): cnt[26] 慢闪 ~0.37Hz
//        - led[1] (D5 绿): cnt[23] 快闪 ~2.98Hz
//        ⚠ 当串口收到字节后，LED 会被该字节最低 2 位覆盖显示（指示通信工作中）
//     2. UART 回显 (Echo)
//        - 通过板载 CH340 USB-UART (TX=V2, RX=U2)
//        - 115200 bps, 8N1
//        - PC 发送任何字节 → FPGA 接收 → 立刻原样回送
// =============================================================================
module top (
    input  wire        clk_50mhz,   // J19 50MHz
    input  wire        rst_n,       // AA1 KEY1
    output wire [1:0]  led,         // M18, N18
    input  wire        uart_rx,     // U2  (PC -> FPGA)
    output wire        uart_tx      // V2  (FPGA -> PC)
);

    // -------------------------------------------------------------------------
    // LED 计数器
    // -------------------------------------------------------------------------
    reg [26:0] cnt = 27'd0;
    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n)
            cnt <= 27'd0;
        else
            cnt <= cnt + 1'b1;
    end

    // -------------------------------------------------------------------------
    // UART 回显
    // -------------------------------------------------------------------------
    wire [7:0] rx_data;
    wire       rx_done;
    wire       tx_busy;
    reg        tx_start;
    reg  [7:0] tx_data;

    // 接收锁存：保留最后一次收到的字节用来显示在 LED
    reg [7:0] last_rx;
    reg       rx_seen;       // 一旦收到过数据就置 1

    // Echo FIFO：UART 接收和发送同速 (115200 8N1)。
    // 修订 2026-06-02: 16 → 1024 字节。
    //   原因：CH340 USB-UART 在全双工高负载时每 ~218B 会因 USB 调度间隙吞 1B，
    //         加大 FIFO 让 FPGA 可以缓存上位机突发，再以 ~115207bps 平稳回吐，
    //         避开 CH340 RX 缓冲压力。BRAM 单 Block 即可承载，资源代价极低。
    reg [7:0]  fifo_mem [0:1023];
    reg [9:0]  fifo_wr_ptr;
    reg [9:0]  fifo_rd_ptr;
    reg [10:0] fifo_count;
    wire       fifo_empty = (fifo_count == 11'd0);
    wire       fifo_full  = (fifo_count == 11'd1024);

    uart_rx #(
        .CLK_FREQ (50_000_000),
        .BAUD_RATE(115_200)
    ) u_rx (
        .clk     (clk_50mhz),
        .rst_n   (rst_n),
        .rx      (uart_rx),
        .rx_data (rx_data),
        .rx_done (rx_done)
    );

    uart_tx #(
        .CLK_FREQ (50_000_000),
        .BAUD_RATE(115_200)
    ) u_tx (
        .clk     (clk_50mhz),
        .rst_n   (rst_n),
        .tx_start(tx_start),
        .tx_data (tx_data),
        .tx      (uart_tx),
        .tx_busy (tx_busy)
    );

    // 当收到字节 → 入 FIFO；发送器空闲且 FIFO 非空 → 出 FIFO 回送
    // 注意：fifo_mem 单独放在“同步、无异步 reset”的 always 块里，
    //       让 Vivado 能把 1024×8 推断成 BRAM (RAMB18) 而不是 8192 个 FF。
    //       BRAM 同步读：bram_q 在 pop 后的下一拍才有效，因此 tx_start 也
    //       需要延迟一拍 (pop_d1) 与 tx_data=bram_q 对齐再送给 uart_tx。
    wire push = rx_done    && !fifo_full;
    wire pop  = !tx_busy   && !fifo_empty && !pop_d1; // 见下方 reg 声明
    reg  pop_d1;        // 同步读延迟一拍的握手
    reg [7:0] bram_q;   // BRAM 读出寄存

    // BRAM 推断块：仅在 clk 上升沿，不带 reset；读写同步、read-first
    always @(posedge clk_50mhz) begin
        if (push)
            fifo_mem[fifo_wr_ptr] <= rx_data;
        // 同步读：pop 这一拍把 fifo_mem[fifo_rd_ptr] 锁存到 bram_q
        if (pop)
            bram_q <= fifo_mem[fifo_rd_ptr];
    end

    always @(posedge clk_50mhz or negedge rst_n) begin
        if (!rst_n) begin
            tx_start    <= 1'b0;
            tx_data     <= 8'd0;
            last_rx     <= 8'd0;
            rx_seen     <= 1'b0;
            fifo_wr_ptr <= 10'd0;
            fifo_rd_ptr <= 10'd0;
            fifo_count  <= 11'd0;
            pop_d1      <= 1'b0;
        end else begin
            tx_start <= 1'b0; // 默认低，保证只是一拍脉冲

            if (rx_done) begin
                last_rx <= rx_data;
                rx_seen <= 1'b1;
                if (!fifo_full) begin
                    fifo_wr_ptr <= fifo_wr_ptr + 1'b1;
                end
            end

            // 本拍发起读
            pop_d1 <= pop;
            if (pop) begin
                fifo_rd_ptr <= fifo_rd_ptr + 1'b1;
            end

            // 下一拍：BRAM 数据有效，与 tx_start 同拍送进 uart_tx
            if (pop_d1) begin
                tx_data  <= bram_q;
                tx_start <= 1'b1;
            end

            case ({push, pop})
                2'b10: fifo_count <= fifo_count + 1'b1; // only push
                2'b01: fifo_count <= fifo_count - 1'b1; // only pop
                default: fifo_count <= fifo_count;      // both or neither
            endcase
        end
    end

    // -------------------------------------------------------------------------
    // LED 输出
    //   - 未收到过数据时：原始闪烁
    //   - 收到过数据时：显示最后接收字节的低 2 位（视觉反馈）
    // -------------------------------------------------------------------------
    wire led0_blink = cnt[26];
    wire led1_blink = cnt[23];

    assign led[0] = rx_seen ? last_rx[0] : led0_blink;
    assign led[1] = rx_seen ? last_rx[1] : led1_blink;

endmodule
