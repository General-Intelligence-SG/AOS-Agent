@echo off
REM ═══════════════════════════════════════
REM  AOS 奥思虚拟助理 — Windows 安装脚本
REM ═══════════════════════════════════════
echo.
echo  ╔══════════════════════════════════╗
echo  ║   AOS 奥思虚拟助理 - 安装程序    ║
echo  ╚══════════════════════════════════╝
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/4] 创建 Python 虚拟环境...
cd /d "%~dp0"
if not exist "backend\.venv" (
    python -m venv backend\.venv
)

echo [2/4] 安装后端依赖...
call backend\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt -q

echo [3/4] 安装前端依赖...
cd frontend
call npm install --silent
cd ..

echo [4/4] 初始化配置...
if not exist "backend\.env" (
    copy backend\.env.example backend\.env
    echo [INFO] 已创建 backend\.env，请编辑填入 LLM_API_KEY
)

echo.
echo ════════════════════════════════════
echo  安装完成！
echo.
echo  下一步：
echo  1. 编辑 backend\.env 填入 LLM_API_KEY
echo  2. 运行 start.bat 启动服务
echo ════════════════════════════════════
pause
