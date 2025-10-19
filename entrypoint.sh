#!/bin/bash
set -e

echo "========================================"
echo "  闲鱼自动回复系统 - 启动中..."
echo "========================================"

# 显示环境信息
echo "环境信息："
echo "  - Python版本: $(python --version)"
echo "  - 工作目录: $(pwd)"
echo "  - 时区: ${TZ:-未设置}"
echo "  - 数据库路径: ${DB_PATH:-/app/data/xianyu_data.db}"
echo "  - 日志级别: ${LOG_LEVEL:-INFO}"

# 禁用 core dumps 防止生成 core 文件
ulimit -c 0
echo "✓ 已禁用 core dumps"

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p /app/data /app/logs /app/backups /app/static/uploads/images
mkdir -p /app/trajectory_history
echo "✓ 目录创建完成"

# 设置目录权限
echo "设置目录权限..."
chmod 777 /app/data /app/logs /app/backups /app/static/uploads /app/static/uploads/images
chmod 777 /app/trajectory_history 2>/dev/null || true
echo "✓ 权限设置完成"

# 检查关键文件
echo "检查关键文件..."
if [ ! -f "/app/global_config.yml" ]; then
    echo "⚠ 警告: 全局配置文件不存在，将使用默认配置"
fi

if [ ! -f "/app/Start.py" ]; then
    echo "✗ 错误: Start.py 文件不存在！"
    exit 1
fi
echo "✓ 关键文件检查完成"

# 检查 Python 依赖
echo "检查 Python 依赖..."
python -c "import fastapi, uvicorn, loguru, websockets" 2>/dev/null || {
    echo "⚠ 警告: 部分 Python 依赖可能未正确安装"
}
echo "✓ Python 依赖检查完成"

# 显示启动信息
echo "========================================"
echo "  系统启动参数："
echo "  - API端口: ${API_PORT:-8080}"
echo "  - API主机: ${API_HOST:-0.0.0.0}"
echo "  - Debug模式: ${DEBUG:-false}"
echo "  - 自动重载: ${RELOAD:-false}"
echo "========================================"

# 启动应用
echo "正在启动应用..."
echo ""

# 使用 exec 替换当前 shell，这样 Python 进程可以接收信号
exec python Start.py
