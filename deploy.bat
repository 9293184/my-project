@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ==========================================
echo   LLM 安全代理网关 - 一键部署（Windows）
echo ==========================================
echo.

:: ─── 1. 检查 Python ───
echo [1/3] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i
echo.

:: ─── 2. 安装 Python 依赖 ───
echo [2/3] 安装 Python 依赖...
cd /d "%~dp0"
python -m pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Python 依赖安装失败
    pause
    exit /b 1
)
echo   Python 依赖安装完成
echo.

:: ─── 完成 ───
echo ==========================================
echo   环境部署完成！
echo ==========================================
echo.
echo 下一步：双击 start.bat 启动服务
echo.
echo 服务地址:
echo   管理界面:  http://localhost:51438
echo   后端 API:  http://localhost:5001
echo   代理地址:  http://localhost:5001/proxy/^<项目ID^>/v1
echo.
echo 快速开始:
echo   1. 打开管理界面，进入“代理审查”页面
echo   2. 配置审查引擎（填入审查模型的 API 地址、模型名称和 API Key）
echo      - 支持任意 OpenAI 兼容 API（DeepSeek、通义千问、GPT 等）
echo      - 也支持本地 Ollama（地址填 http://localhost:11434/v1）
echo   3. 创建代理项目 - 填写上游大模型地址 - 获取代理地址
echo   4. 将客户端 API base URL 替换为代理地址即可
echo ==========================================
echo.
pause
