#!/bin/bash
# ═══════════════════════════════════════
#  AOS 奥思虚拟助理 — 启动脚本
# ═══════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "🚀 AOS 奥思虚拟助理启动中..."
echo ""

# 启动后端
echo "[Backend] 启动 FastAPI 服务..."
(cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!

sleep 3

# 启动前端
echo "[Frontend] 启动 Vite 开发服务..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "════════════════════════════════════"
echo " AOS 已启动！"
echo ""
echo " 🌐 前端: http://localhost:5173"
echo " 📡 后端: http://localhost:8000"
echo " 📖 API:  http://localhost:8000/docs"
echo ""
echo " PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
echo " 关闭请运行 ./stop.sh"
echo "════════════════════════════════════"

# 保存 PID
echo "$BACKEND_PID" > .backend.pid
echo "$FRONTEND_PID" > .frontend.pid

wait
