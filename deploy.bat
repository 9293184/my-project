@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ==========================================
echo   LLM 安全代理网关 - 一键部署（Windows）
echo ==========================================
echo.

:: ─── 1. 检查 Python ───
echo [1/6] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i
echo.

:: ─── 2. 检查 Ollama ───
echo [2/6] 检查 Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] 未找到 Ollama，请先安装:
    echo   https://ollama.com/download/windows
    echo 安装后重新运行此脚本
    pause
    exit /b 1
)
echo   Ollama 已安装
echo.

:: ─── 3. 启动 Ollama 服务 ───
echo [3/6] 启动 Ollama 服务...
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    start "" ollama serve
    timeout /t 3 /nobreak >nul
    echo   Ollama 服务已启动
) else (
    echo   Ollama 服务已在运行
)
echo.

:: ─── 4. 下载审查模型 ───
echo [4/6] 下载默认审查模型: huihui_ai/qwen3-abliterated:8b
echo   （去除审查限制的 Qwen3 8B，适合作为安全审查 Judge 模型）
echo   首次下载约 5GB，请耐心等待...
echo.
ollama pull huihui_ai/qwen3-abliterated:8b
if errorlevel 1 (
    echo [ERROR] 模型下载失败，请检查网络连接
    pause
    exit /b 1
)
echo   审查模型下载完成
echo.

:: ─── 5. 安装 Python 依赖 ───
echo [5/6] 安装 Python 依赖...
cd /d "%~dp0"
python -m pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Python 依赖安装失败
    pause
    exit /b 1
)
echo   Python 依赖安装完成
echo.

:: ─── 6. 初始化数据库 ───
echo [6/6] 初始化 MySQL 数据库...
echo   请确保 MySQL 服务已运行（默认 root/root@localhost:3306）
cd /d "%~dp0backend"
python init_db.py
if errorlevel 1 (
    echo [WARN] 数据库初始化可能失败，请手动执行: cd backend ^&^& python init_db.py
) else (
    echo   数据库初始化完成
)
cd /d "%~dp0"
echo.

:: ─── 完成 ───
echo ==========================================
echo   部署完成！
echo ==========================================
echo.
echo 启动后端服务:
echo   cd backend ^&^& python run_modular.py
echo.
echo 服务地址:
echo   管理界面:  浏览器打开 frontend\index.html
echo   代理 API:  http://localhost:5001/proxy/^<项目ID^>/v1
echo   Ollama:    http://localhost:11434
echo.
echo 默认审查模型: huihui_ai/qwen3-abliterated:8b
echo   Ollama 地址: http://localhost:11434/v1
echo   模型名称:    huihui_ai/qwen3-abliterated:8b
echo.
echo 快速开始:
echo   1. 启动后端: cd backend ^& python run_modular.py
echo   2. 打开管理界面 - 配置审查引擎（填入上述 Ollama 地址和模型名）
echo   3. 创建代理项目 - 填写上游地址 - 获取代理地址
echo   4. 将客户端 API base URL 替换为代理地址即可
echo ==========================================
echo.
pause
