# program_qspi.tcl - A7-Lite QSPI Flash 烧录 - 最简配置
# 板载 Flash: ISSI IS25LP128F (128Mbit / 16MB)

set binfile [file normalize {output/top.bin}]
set flash_part "is25lp128f-spi-x1_x2_x4"

puts "\n===== A7-Lite QSPI Flash 烧录 ====="
puts "Flash: ISSI IS25LP128F"
puts "Part:  $flash_part"
puts "File:  $binfile\n"

if {![file exists $binfile]} { puts "❌ bin 文件不存在"; exit 1 }

# 1. 连接硬件
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
set fpga [lindex [get_hw_devices] 0]
current_hw_device $fpga
puts "✅ FPGA: $fpga"

# 2. 创建 cfgmem
puts "\n>>> 创建 cfgmem..."
set cfg [create_hw_cfgmem -hw_device $fpga -mem_dev [lindex [get_cfgmem_parts $flash_part] 0]]

# 3. 最简属性
set_property PROGRAM.FILES                  [list $binfile] $cfg
set_property PROGRAM.ERASE                  1  $cfg
set_property PROGRAM.CFG_PROGRAM            1  $cfg
set_property PROGRAM.VERIFY                 1  $cfg

# 4. 烧录
puts "\n>>> 🔥 开始烧录..."
set t0 [clock seconds]
if {[catch {program_hw_cfgmem -hw_cfgmem $cfg} err]} {
    puts "\n❌ 烧录失败: $err"
    catch {delete_hw_cfgmem -hw_cfgmem $cfg}
    disconnect_hw_server; close_hw_manager
    exit 1
}
set dt [expr {[clock seconds] - $t0}]
puts "\n✅ 烧录完成 (耗时 ${dt}s)"

# 5. Boot
puts "\n>>> Boot from Flash..."
catch {boot_hw_device $fpga} bm
puts "   $bm"

catch {delete_hw_cfgmem -hw_cfgmem $cfg}
disconnect_hw_server; close_hw_manager
puts "\n✅✅✅ QSPI 烧录完成！"
puts "拔电再上电后观察 LED。"
exit 0
