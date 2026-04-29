@echo off
REM AOS 停止脚本
echo 正在停止 AOS 服务...
taskkill /FI "WINDOWTITLE eq AOS-Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AOS-Frontend" /F >nul 2>&1
taskkill /F /IM "uvicorn.exe" >nul 2>&1
echo AOS 已停止。
