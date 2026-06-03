# program.tcl - Program the A7-Lite FPGA via JTAG
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target

set devices [get_hw_devices]
if {[llength $devices] == 0} {
    puts "ERROR: No hardware devices found. Check JTAG connection."
    disconnect_hw_server
    close_hw_manager
    exit 1
}

set bit [lindex $devices 0]
current_hw_device $bit
# 从 a7lite_project 根目录出发
set bitfile [file normalize {output/top.bit}]
set_property PROGRAM.FILE $bitfile $bit
puts "Programming device: $bit"
program_hw_devices $bit
puts "Programming completed successfully!"

disconnect_hw_server
close_hw_manager
exit 0
