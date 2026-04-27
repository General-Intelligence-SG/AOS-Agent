#!/bin/bash
# ═══════════════════════════════════════
#  AOS 奥思虚拟助理 — Linux/macOS 安装脚本
# ═══════════════════════════════════════
set -e

echo ""
echo "╔══════════════════════════════════╗"
echo "║   AOS 奥思虚拟助理 - 安装程序    ║"
echo "╚══════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] 未找到 Python3，请先安装 Python 3.11+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[ERROR] 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

echo "[1/4] 创建 Python 虚拟环境..."
if [ ! -d "backend/.venv" ]; then
    python3 -m venv backend/.venv
fi

echo "[2/4] 安装后端依赖..."
source backend/.venv/bin/activate
pip install -r backend/requirements.txt -q

echo "[3/4] 安装前端依赖..."
cd frontend && npm install --silent && cd ..

echo "[4/4] 初始化配置..."
if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    echo "[INFO] 已创建 backend/.env，请编辑填入 LLM_API_KEY"
fi

echo ""
echo "════════════════════════════════════"
echo " 安装完成！"
echo ""
echo " 下一步："
echo " 1. 编辑 backend/.env 填入 LLM_API_KEY"
echo " 2. 运行 ./start.sh 启动服务"
echo "════════════════════════════════════"
