# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（OpenCV 需要）
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY app.py .
COPY migration_pb2.py .
COPY templates/ ./templates/

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

# 创建数据目录并设置权限（在切换用户之前）
RUN mkdir -p /app/data/uploads && \
    chown -R appuser:appuser /app

# 复制启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    chown appuser:appuser /entrypoint.sh

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# 使用启动脚本
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]

