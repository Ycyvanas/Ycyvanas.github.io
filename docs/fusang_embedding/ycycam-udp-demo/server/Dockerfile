FROM python:3.11-slim

LABEL maintainer="ycycam"
LABEL description="ycycam-udp Web接收端服务器"

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (libjpeg等)
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY web_receiver.py .
COPY detector.py .

# 暴露端口
EXPOSE 8000/tcp
EXPOSE 5000/udp

# 健康检查
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD curl -f http://localhost:8000/status || exit 1

# 启动命令
CMD ["python", "web_receiver.py"]

# 安装OpenCV运行时依赖
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libxcb1 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*
