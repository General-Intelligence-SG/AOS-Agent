#!/bin/bash
# AOS 停止脚本
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "正在停止 AOS 服务..."
if [ -f .backend.pid ]; then kill $(cat .backend.pid) 2>/dev/null; rm .backend.pid; fi
if [ -f .frontend.pid ]; then kill $(cat .frontend.pid) 2>/dev/null; rm .frontend.pid; fi
pkill -f "uvicorn app.main:app" 2>/dev/null
echo "AOS 已停止。"
