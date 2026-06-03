## Clock
set_property PACKAGE_PIN J19 [get_ports clk_50mhz]
set_property IOSTANDARD LVCMOS33 [get_ports clk_50mhz]
create_clock -period 20.0 [get_ports clk_50mhz]

## Reset (KEY1)
set_property PACKAGE_PIN AA1 [get_ports rst_n]
set_property IOSTANDARD LVCMOS33 [get_ports rst_n]

## LEDs
set_property PACKAGE_PIN M18 [get_ports {led[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[0]}]

set_property PACKAGE_PIN N18 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {led[1]}]

## USB UART (CH340)
## UART_TX  = FPGA -> PC (FPGA 端为输出)  V2 / IO_L2N_T0_34
## UART_RX  = PC -> FPGA (FPGA 端为输入)  U2 / IO_L2P_T0_34
set_property PACKAGE_PIN V2 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]

set_property PACKAGE_PIN U2 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]
