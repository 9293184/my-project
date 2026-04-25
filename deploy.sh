#!/bin/bash
# ============================================
# LLM 安全代理网关 — 一键部署脚本
# ============================================
set -e

echo "=========================================="
echo "  LLM 安全代理网关 — 一键部署"
echo "=========================================="

# ─── 颜色定义 ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }

# ─── 1. 检查 Python ───
echo ""
echo ">>> [1/3] 检查 Python..."

command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 || fail "未找到 Python，请先安装 Python 3.9+"
PYTHON=$(command -v python3 || command -v python)
PY_VER=$($PYTHON --version 2>&1)
ok "Python: $PY_VER"

$PYTHON -m pip --version >/dev/null 2>&1 || fail "未找到 pip，请先安装 pip"
ok "pip 已就绪"

# ─── 2. 安装 Python 依赖 ───
echo ""
echo ">>> [2/3] 安装 Python 依赖..."
cd "$(dirname "$0")"
$PYTHON -m pip install -r backend/requirements.txt -q
ok "Python 依赖安装完成"

# ─── 3. 启动后端服务 ───
echo ""
echo ">>> [3/3] 启动后端服务..."
echo "    数据库（SQLite）将在首次启动时自动创建，无需手动初始化"
cd backend
$PYTHON run_modular.py &
sleep 3
cd ..
ok "后端服务已启动"

# ─── 完成 ───
echo ""
echo "=========================================="
echo -e "${GREEN}  ✓ 部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务地址:"
echo "  管理界面:  浏览器打开 frontend/index.html"
echo "  后端 API:  http://localhost:5001"
echo "  代理地址:  http://localhost:5001/proxy/<项目ID>/v1"
echo ""
echo "快速开始:"
echo "  1. 打开管理界面，进入\"代理审查\"页面"
echo "  2. 配置审查引擎（填入审查模型的 API 地址、模型名称和 API Key）"
echo "     - 支持任意 OpenAI 兼容 API（DeepSeek、通义千问、GPT 等）"
echo "     - 也支持本地 Ollama（地址填 http://localhost:11434/v1）"
echo "  3. 创建代理项目 → 填写上游大模型地址 → 获取代理地址"
echo "  4. 将客户端 API base URL 替换为代理地址即可"
echo "=========================================="
