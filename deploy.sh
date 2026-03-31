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

# ─── 1. 检查依赖 ───
echo ""
echo ">>> 检查系统依赖..."

# Python
command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 || fail "未找到 Python，请先安装 Python 3.9+"
PYTHON=$(command -v python3 || command -v python)
PY_VER=$($PYTHON --version 2>&1)
ok "Python: $PY_VER"

# pip
$PYTHON -m pip --version >/dev/null 2>&1 || fail "未找到 pip，请先安装 pip"
ok "pip 已就绪"

# MySQL
command -v mysql >/dev/null 2>&1 || warn "未找到 MySQL 客户端（如果已有远程数据库可忽略）"

# Ollama
if command -v ollama >/dev/null 2>&1; then
    ok "Ollama 已安装: $(ollama --version 2>&1 | head -1)"
    OLLAMA_INSTALLED=true
else
    warn "未找到 Ollama，将尝试自动安装..."
    OLLAMA_INSTALLED=false
fi

# ─── 2. 安装 Ollama（如果未安装）───
if [ "$OLLAMA_INSTALLED" = false ]; then
    echo ""
    echo ">>> 安装 Ollama..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS 请手动安装 Ollama: https://ollama.com/download"
        echo "安装后重新运行此脚本"
        exit 1
    else
        echo "Windows 请手动安装 Ollama: https://ollama.com/download"
        echo "安装后重新运行此脚本"
        exit 1
    fi
    ok "Ollama 安装完成"
fi

# ─── 3. 启动 Ollama 服务 ───
echo ""
echo ">>> 启动 Ollama 服务..."
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    ollama serve &
    sleep 3
    ok "Ollama 服务已启动"
else
    ok "Ollama 服务已在运行"
fi

# ─── 4. 下载审查模型 ───
echo ""
echo ">>> 下载默认审查模型: huihui_ai/qwen3-abliterated:8b"
echo "    （去除审查限制的 Qwen3 8B，适合作为安全审查 Judge 模型）"
echo "    首次下载约 5GB，请耐心等待..."
echo ""
ollama pull huihui_ai/qwen3-abliterated:8b
ok "审查模型下载完成"

# ─── 5. 安装 Python 依赖 ───
echo ""
echo ">>> 安装 Python 依赖..."
cd "$(dirname "$0")"
$PYTHON -m pip install -r backend/requirements.txt -q
ok "Python 依赖安装完成"

# ─── 6. 初始化数据库 ───
echo ""
echo ">>> 初始化 MySQL 数据库..."
echo "    请确保 MySQL 服务已运行（默认 root/root@localhost:3306）"
echo ""

# 检查 MySQL 是否可连接
if command -v mysql >/dev/null 2>&1; then
    if mysql -u root -proot -e "SELECT 1" >/dev/null 2>&1; then
        ok "MySQL 连接成功"
        cd backend
        $PYTHON init_db.py
        cd ..
        ok "数据库初始化完成"
    else
        warn "MySQL 连接失败，请手动执行: cd backend && python init_db.py"
    fi
else
    warn "MySQL 客户端未安装，请手动初始化数据库"
    echo "    步骤: cd backend && python init_db.py"
fi

# ─── 7. 输出部署信息 ───
echo ""
echo "=========================================="
echo -e "${GREEN}  ✓ 部署完成！${NC}"
echo "=========================================="
echo ""
echo "启动后端服务:"
echo "  cd backend && python run_modular.py"
echo ""
echo "服务地址:"
echo "  管理界面:  http://localhost:5001  （浏览器打开 frontend/index.html）"
echo "  代理 API:  http://localhost:5001/proxy/<项目ID>/v1"
echo "  Ollama:    http://localhost:11434"
echo ""
echo "默认审查模型: huihui_ai/qwen3-abliterated:8b"
echo "  Ollama 地址: http://localhost:11434/v1"
echo "  模型名称:    huihui_ai/qwen3-abliterated:8b"
echo ""
echo "快速开始:"
echo "  1. 启动后端: cd backend && python run_modular.py"
echo "  2. 打开管理界面 → 配置审查引擎（填入上述 Ollama 地址和模型名）"
echo "  3. 创建代理项目 → 填写上游地址 → 获取代理地址"
echo "  4. 将客户端 API base URL 替换为代理地址即可"
echo "=========================================="
