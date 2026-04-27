@echo off
REM ═══════════════════════════════════════
REM  AOS 奥思虚拟助理 — 启动脚本
REM ═══════════════════════════════════════
echo.
echo  🚀 AOS 奥思虚拟助理启动中...
echo.

cd /d "%~dp0"

REM 启动后端
echo [Backend] 启动 FastAPI 服务...
start "AOS-Backend" cmd /c "cd backend && .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端
echo [Frontend] 启动 Vite 开发服务...
start "AOS-Frontend" cmd /c "cd frontend && npm run dev"

timeout /t 3 /nobreak >nul

echo.
echo ════════════════════════════════════
echo  AOS 已启动！
echo.
echo  🌐 前端: http://localhost:5173
echo  📡 后端: http://localhost:8000
echo  📖 API:  http://localhost:8000/docs
echo.
echo  关闭请运行 stop.bat
echo ════════════════════════════════════

REM 自动打开浏览器
start http://localhost:5173
