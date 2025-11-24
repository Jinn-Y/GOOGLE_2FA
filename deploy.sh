#!/bin/bash

# Google 2FA Docker 部署脚本

echo "=========================================="
echo "Google 2FA Docker 部署脚本"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: 未检测到 Docker，请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: 未检测到 Docker Compose，请先安装 Docker Compose"
    exit 1
fi

# 停止并删除旧容器（如果存在）
echo "停止旧容器..."
docker-compose down

# 构建并启动新容器
echo "构建并启动容器..."
docker-compose up -d --build

# 等待容器启动
echo "等待容器启动..."
sleep 5

# 检查容器状态
if docker-compose ps | grep -q "Up"; then
    echo "=========================================="
    echo "✅ 部署成功！"
    echo "=========================================="
    echo "应用地址: http://localhost:5000"
    echo ""
    echo "常用命令:"
    echo "  查看日志: docker-compose logs -f"
    echo "  停止服务: docker-compose down"
    echo "  重启服务: docker-compose restart"
    echo "=========================================="
else
    echo "=========================================="
    echo "❌ 部署失败，请检查日志:"
    echo "   docker-compose logs"
    echo "=========================================="
    exit 1
fi

