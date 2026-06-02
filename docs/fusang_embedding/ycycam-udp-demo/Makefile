# ycycam-udp - Makefile
#
# 常用命令:
#   make          - 编译所有目标
#   make cpp      - 编译C++接收端
#   make py-deps  - 安装Python依赖
#   make clean    - 清理编译产物
#   make test     - 运行测试 (发送器+接收器)
#

.PHONY: all cpp py-deps clean test help

# 默认目标
all: cpp

# 编译C++接收端
cpp: receiver
	@echo "C++接收端编译完成!"

receiver: receiver.cpp
	@echo "正在编译C++接收端..."
	g++ -std=c++17 -O2 receiver.cpp -o receiver \
		-lopencv_core -lopencv_highgui -lopencv_imgproc -lopencv_imgcodecs \
		-DOPENCV_AVAILABLE

# 无OpenCV版本的C++接收端 (仅统计)
receiver-nocv: receiver.cpp
	@echo "正在编译无OpenCV的C++接收端..."
	g++ -std=c++17 -O2 receiver.cpp -o receiver-nocv

# 安装Python依赖
py-deps:
	@echo "安装Python依赖..."
	pip3 install opencv-python pillow numpy

# 清理
clean:
	@echo "清理编译产物..."
	rm -f receiver receiver-nocv
	rm -rf frames/ *.mp4 *.jpg
	rm -rf __pycache__/ *.pyc

# 运行测试: 启动测试发送器 + Python接收器
test:
	@echo "启动测试..."
	@echo "终端1: python3 receiver.py"
	@echo "终端2: python3 test_sender.py"
	@echo ""
	@echo "按 Ctrl+C 停止所有进程"

# 帮助
help:
	@echo "ycycam-udp - Makefile 使用帮助"
	@echo ""
	@echo "目标:"
	@echo "  make cpp      - 编译C++接收端 (需要OpenCV)"
	@echo "  make py-deps  - 安装Python依赖"
	@echo "  make clean    - 清理编译产物"
	@echo "  make test     - 显示测试命令"
	@echo ""
	@echo "ESP32编译:"
	@echo "  cd build && make -j"
	@echo "  或使用 idf.py build"
