# build.tcl - A7-Lite LED Blinker - 官方 QSPI 配置
# 按 MicroPhase 官方教程：SPIx4 + 50MHz + 压缩
# 使用方法: vivado -mode batch -source scripts/build.tcl

# 清理 + 建工程
file delete -force ./output
file mkdir ./output
create_project a7lite_led_blink ./output -part xc7a35tfgg484-2L -force

# 1. 添加源文件
add_files -norecurse [glob ./src/*.v]
set_property top top [current_fileset]
update_compile_order -fileset sources_1

# 2. 添加约束文件
add_files -fileset constrs_1 ./constraints/constraints.xdc

# 3. 综合
puts "\n>>> [clock format [clock seconds]] 综合 (Synth)..."
launch_runs synth_1 -jobs 4
wait_on_run synth_1

if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    puts "❌ 综合失败"
    exit 1
}

# 4. QSPI 配置 - 按 MicroPhase 官方教程
puts "\n>>> 设置 QSPI 配置..."
open_run synth_1 -name synth_1

# 官方教程的配置
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4    [current_design]
set_property CONFIG_MODE SPIx4                   [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 50      [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE     [current_design]

puts "✅ QSPI: SPIx4, BUSWIDTH=4, CONFIGRATE=50MHz, COMPRESS=TRUE"

# 5. 实现
puts "\n>>> [clock format [clock seconds]] 实现 (Implementation)..."
launch_runs impl_1 -jobs 4
wait_on_run impl_1

if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    puts "❌ 实现失败"
    exit 1
}

# 6. 生成比特流 (含 bin 文件 - 官方要求用 bin 烧 Flash)
puts "\n>>> [clock format [clock seconds]] 生成比特流 (bit + bin)..."
open_run impl_1
write_bitstream -force -bin_file ./output/top.bit

# 7. 确认文件
set bitfile "./output/top.bit"
set binfile "./output/top.bin"

puts "\n========================================="
if {[file exists $bitfile]} {
    puts "✅ BIT: [file size $bitfile] bytes"
} else {
    puts "❌ BIT 未找到"
}
if {[file exists $binfile]} {
    puts "✅ BIN: [file size $binfile] bytes"
} else {
    puts "❌ BIN 未找到"
}
puts "========================================="
exit 0
