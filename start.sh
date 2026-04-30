#!/bin/bash
# ═══════════════════════════════════════
#  AOS 奥思虚拟助理 — 启动脚本
# ═══════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

NODE_BIN_DIR="${NODE_BIN_DIR:-$HOME/.nvm/versions/node/v22.22.2/bin}"
if [ -d "$NODE_BIN_DIR" ]; then
  export PATH="$NODE_BIN_DIR:$PATH"
fi

BACKEND_PORT="$(grep -E '^PORT=' backend/.env 2>/dev/null | tail -n 1 | cut -d= -f2)"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ ! -d backend/.venv ]; then
  echo "[Backend] Missing virtualenv at backend/.venv"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[Frontend] npm not found. Check Node.js/NVM installation."
  exit 1
fi

if [ ! -d frontend/node_modules ]; then
  echo "[Frontend] Installing dependencies..."
  (cd frontend && npm install)
fi

echo ""
echo "🚀 AOS 奥思虚拟助理启动中..."
echo ""

if [ -f .backend.pid ] && kill -0 "$(cat .backend.pid)" 2>/dev/null; then
  echo "[Backend] Existing backend process detected, stopping it first..."
  kill "$(cat .backend.pid)" 2>/dev/null || true
  rm -f .backend.pid
fi

if [ -f .frontend.pid ] && kill -0 "$(cat .frontend.pid)" 2>/dev/null; then
  echo "[Frontend] Existing frontend process detected, stopping it first..."
  kill "$(cat .frontend.pid)" 2>/dev/null || true
  rm -f .frontend.pid
fi

pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "node .*vite" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

# 启动后端
echo "[Backend] 启动 FastAPI 服务..."
(
  cd backend
  source .venv/bin/activate
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
) &
BACKEND_PID=$!
echo "$BACKEND_PID" > .backend.pid

sleep 3

# 启动前端
echo "[Frontend] 启动 Vite 开发服务..."
(
  cd frontend
  exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > .frontend.pid

echo ""
echo "════════════════════════════════════"
echo " AOS 已启动！"
echo ""
echo " 🌐 前端: http://localhost:$FRONTEND_PORT"
echo " 📡 后端: http://localhost:$BACKEND_PORT"
echo " 📖 API:  http://localhost:$BACKEND_PORT/docs"
echo ""
echo " PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
echo " 关闭请运行 ./stop.sh"
echo "════════════════════════════════════"

wait