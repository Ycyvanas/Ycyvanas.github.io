# probe.tcl - 探测 JTAG 链 + 读取 Flash JEDEC ID
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target

puts "\n=== JTAG Devices ==="
foreach d [get_hw_devices] {
    puts "Device: $d"
    foreach prop {PART IDCODE IR_LENGTH} {
        catch {puts "   $prop = [get_property $prop $d]"}
    }
}

set fpga [lindex [get_hw_devices] 0]
current_hw_device $fpga

puts "\n=== Available IS25 / S25FL128 / W25Q128 / N25Q128 / MT25Q128 parts ==="
foreach p [get_cfgmem_parts] {
    if {[regexp {is25(lp|wp)128|s25fl128|w25q128|n25q128|mt25ql128} $p]} {
        puts "  $p"
    }
}

puts "\n=== Trying to read Flash JEDEC ID via boot_hw_device + readback ==="
# 创建一个临时 cfgmem 不烧录，仅尝试 init 看 Flash 是否能响应
if {![catch {set cfg [create_hw_cfgmem -hw_device $fpga [lindex [get_cfgmem_parts is25lp128f-spi-x1_x2_x4] 0]]} err]} {
    puts "✅ cfgmem 创建成功: $cfg"
    catch {delete_hw_cfgmem $cfg}
} else {
    puts "❌ cfgmem 创建失败: $err"
}

disconnect_hw_server
close_hw_manager
exit 0
