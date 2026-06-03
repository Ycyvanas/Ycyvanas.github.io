`timescale 1ns / 1ps
// =============================================================================
// uart_tx.v - 8N1 UART 发送器  (back-to-back 优化版)
//   - tx_start 拉高一拍触发发送 tx_data
//   - tx_busy 高电平表示正在发送，期间忽略新的 tx_start
//   - 帧格式：1 start + 8 data (LSB first) + 1 stop
//
//   ⚙️ 关键优化（解决连续突发丢字节）：
//   ① S_STOP 在 stop bit 的倒数第二个 tick 就把 tx_busy 拉低，
//      让 top.v 的 FIFO 仲裁逻辑在 stop bit 真正结束前就能
//      装载下一字节 (tx_start=1 / tx_data=...)
//   ② S_STOP 在 stop bit 最后一个 tick 检查到 tx_start 后，
//      直接跳 S_START（同时把 tx 拉低做新帧的起始位），
//      不再绕一拍 S_IDLE，做到 back-to-back 发送。
//   修复后每字节固定 10 bit 时间，TX 不再比 PC 慢，FIFO 不会回压。
// =============================================================================
module uart_tx #(
    parameter CLK_FREQ  = 50_000_000,
    parameter BAUD_RATE = 115_200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,    // 发送启动脉冲
    input  wire [7:0] tx_data,     // 待发送数据
    output reg        tx,          // 串行输出 (UART_TX)
    output reg        tx_busy      // 正在发送
);

    localparam integer BIT_PERIOD = CLK_FREQ / BAUD_RATE;

    localparam S_IDLE  = 2'd0;
    localparam S_START = 2'd1;
    localparam S_DATA  = 2'd2;
    localparam S_STOP  = 2'd3;

    reg [1:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  tx_buf;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= S_IDLE;
            clk_cnt <= 16'd0;
            bit_idx <= 3'd0;
            tx_buf  <= 8'd0;
            tx      <= 1'b1;     // 空闲为高
            tx_busy <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    tx      <= 1'b1;
                    tx_busy <= 1'b0;
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    if (tx_start) begin
                        tx_buf  <= tx_data;
                        tx_busy <= 1'b1;
                        tx      <= 1'b0;  // 立刻拉低做起始位
                        state   <= S_START;
                    end
                end

                S_START: begin
                    tx <= 1'b0;
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt <= 16'd0;
                        state   <= S_DATA;
                    end
                end

                S_DATA: begin
                    tx <= tx_buf[bit_idx]; // LSB first
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt <= 16'd0;
                        if (bit_idx == 3'd7) begin
                            state <= S_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end
                end

                S_STOP: begin
                    tx <= 1'b1; // stop bit

                    // ① 倒数第二个 tick 提前释放 busy，给 top.v 一拍
                    //    去仲裁 FIFO 并把下一字节摆到 tx_data / tx_start。
                    if (clk_cnt == BIT_PERIOD - 2) begin
                        tx_busy <= 1'b0;
                    end

                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        // stop bit 的最后一个 tick
                        clk_cnt <= 16'd0;
                        bit_idx <= 3'd0;
                        if (tx_start) begin
                            // ② Back-to-back：直接进入下一帧
                            //    本拍输出 tx=0 当 start bit 的首拍
                            tx_buf  <= tx_data;
                            tx_busy <= 1'b1;
                            tx      <= 1'b0;
                            state   <= S_START;
                        end else begin
                            tx_busy <= 1'b0;
                            state   <= S_IDLE;
                        end
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
