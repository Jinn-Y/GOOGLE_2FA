#!/bin/bash
# Docker 容器启动脚本

# 确保上传目录存在
mkdir -p /app/data/uploads

# 检查目录是否可写
if [ -w /app/data/uploads ]; then
    echo "✓ 上传目录权限正常"
else
    echo "⚠ 警告: 上传目录可能无写入权限"
    echo "   请确保主机目录 ./data 的权限允许容器用户写入"
    echo "   可以运行: sudo chown -R 1000:1000 ./data"
fi

# 执行原始命令
exec "$@"

