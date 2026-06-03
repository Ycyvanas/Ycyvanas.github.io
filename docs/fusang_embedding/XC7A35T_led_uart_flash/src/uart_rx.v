`timescale 1ns / 1ps
// =============================================================================
// uart_rx.v - 8N1 UART 接收器
//   - 16x 过采样
//   - 在起始位中点采样进行确认，之后每 BIT_PERIOD 个 clk 采样一位
//   - rx_done 在收到 stop bit 后输出 1 个周期
// =============================================================================
module uart_rx #(
    parameter CLK_FREQ  = 50_000_000,
    parameter BAUD_RATE = 115_200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx,          // 串行输入 (UART_RX)
    output reg  [7:0] rx_data,     // 接收到的数据
    output reg        rx_done      // 接收完成脉冲（1 clk）
);

    localparam integer BIT_PERIOD = CLK_FREQ / BAUD_RATE;        // 一个 bit 的 clk 周期数
    localparam integer HALF_BIT   = BIT_PERIOD / 2;

    // FSM
    localparam S_IDLE  = 3'd0;
    localparam S_START = 3'd1;
    localparam S_DATA  = 3'd2;
    localparam S_STOP  = 3'd3;

    reg [2:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  data_buf;

    // 输入两级同步，防止亚稳态
    reg rx_sync_0, rx_sync_1;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync_0 <= 1'b1;
            rx_sync_1 <= 1'b1;
        end else begin
            rx_sync_0 <= rx;
            rx_sync_1 <= rx_sync_0;
        end
    end
    wire rx_in = rx_sync_1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            clk_cnt  <= 16'd0;
            bit_idx  <= 3'd0;
            data_buf <= 8'd0;
            rx_data  <= 8'd0;
            rx_done  <= 1'b0;
        end else begin
            rx_done <= 1'b0;
            case (state)
                S_IDLE: begin
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    if (rx_in == 1'b0) begin
                        // 检测到下降沿（起始位），进入 START
                        state <= S_START;
                    end
                end

                S_START: begin
                    // 等到起始位中点确认是有效的低
                    if (clk_cnt == HALF_BIT - 1) begin
                        if (rx_in == 1'b0) begin
                            clk_cnt <= 16'd0;
                            state   <= S_DATA;
                        end else begin
                            state <= S_IDLE; // 误触发
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                S_DATA: begin
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt        <= 16'd0;
                        data_buf[bit_idx] <= rx_in; // LSB first
                        if (bit_idx == 3'd7) begin
                            state <= S_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end
                end

                S_STOP: begin
                    if (clk_cnt < BIT_PERIOD - 1) begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end else begin
                        clk_cnt <= 16'd0;
                        rx_data <= data_buf;
                        rx_done <= 1'b1;
                        state   <= S_IDLE;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
