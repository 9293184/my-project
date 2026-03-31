# LLM 安全代理网关

部署于大语言模型与用户之间的透明安全代理，通过三层协同审查（内置规则引擎 + 自定义正则 + AI 语义审查）实现实时安全检测与拦截，同时保持对客户端完全透明——请求头和请求体零修改。

## 快速部署

### 环境要求

- **Python** 3.9+
- **MySQL** 5.7+（默认 root/root@localhost:3306）
- **Ollama**（本地大模型运行时）
- 可选：**Docker** + **Docker Compose**

### 一键部署

**Linux / macOS：**

```bash
chmod +x deploy.sh
./deploy.sh
```

**Windows：**

```
双击 deploy.bat
```

脚本会自动完成：
1. 检查并安装 Ollama
2. 下载默认审查模型（`huihui_ai/qwen3-abliterated:8b`，约 5GB）
3. 安装 Python 依赖
4. 初始化 MySQL 数据库

### 手动部署

```bash
# 1. 安装 Python 依赖
cd backend
pip install -r requirements.txt

# 2. 安装并启动 Ollama
# Linux:
curl -fsSL https://ollama.com/install.sh | sh
# Windows/macOS: 从 https://ollama.com/download 下载安装

ollama serve  # 启动服务（后台运行）

# 3. 下载审查模型
ollama pull huihui_ai/qwen3-abliterated:8b

# 4. 初始化数据库（确保 MySQL 已运行）
python init_db.py

# 5. 启动后端
python run_modular.py
```

### Docker 部署

```bash
docker-compose up -d
```

## 使用方法

### 1. 启动服务

```bash
cd backend
python run_modular.py
```

服务启动后：
- 管理界面：浏览器打开 `frontend/index.html`
- 后端 API：`http://localhost:5001`
- Ollama：`http://localhost:11434`

### 2. 配置审查引擎

在管理界面 → 代理网关 → 审查引擎配置：

| 配置项 | 值 |
|--------|-----|
| Judge 模型地址 | `http://localhost:11434/v1` |
| 模型名称 | `huihui_ai/qwen3-abliterated:8b` |
| API Key | 留空（Ollama 本地不需要） |

### 3. 创建代理项目

在管理界面 → 代理网关 → 新建代理项目：

- 填写**项目名称**（如"OpenClaw 审查"）
- 填写**上游 API 地址**（如 `https://api.openai.com/v1`）
- 配置**审查策略**（审查方向、正则规则、拦截阈值）
- 保存后获得**代理地址**：`http://localhost:5001/proxy/PX-xxxx/v1`

### 4. 接入客户端

将客户端的 API base URL 替换为代理地址即可，**无需修改任何请求头或请求体**：

```
# 原始配置
API_BASE_URL=https://api.openai.com/v1

# 替换为代理地址
API_BASE_URL=http://代理服务器:5001/proxy/PX-xxxx/v1
```

代理会：
- 透传所有请求头（含 Authorization）和请求体
- 对输入/输出执行安全审查
- 记录完整日志
- 将请求转发到上游大模型

## 架构概览

```
客户端 → 安全代理网关（审查 + 日志）→ 上游大模型
              │
              ├── 第一层：内置规则引擎（30+ 条规则，毫秒级）
              ├── 第二层：自定义正则（AI 辅助生成，毫秒级）
              └── 第三层：AI 语义审查（Judge 模型深度分析，秒级）
```

## 目录结构

```
├── backend/                    # 后端服务
│   ├── aisec_app/             # Flask 应用主体
│   ├── proxy/                 # 安全代理网关核心
│   │   ├── gateway.py         # 透明代理转发 + 审查流水线
│   │   ├── audit.py           # AI 语义审查引擎
│   │   ├── rule_engine.py     # 内置规则引擎
│   │   ├── routes.py          # 代理 API 路由
│   │   ├── tasks.py           # 代理项目管理
│   │   └── logger.py          # 日志记录
│   └── requirements.txt
├── frontend/                   # 前端管理界面
├── database/                   # 数据库脚本
├── deploy.sh                   # Linux/macOS 一键部署
├── deploy.bat                  # Windows 一键部署
├── Dockerfile
└── docker-compose.yml
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/proxy/<项目ID>/v1/chat/completions` | 透明代理转发（零修改） |
| GET/POST/PUT/DELETE | `/proxy/v1/tasks` | 代理项目管理 |
| GET | `/proxy/v1/logs` | 查询日志 |
| GET | `/proxy/v1/logs/stats` | 日志统计 |
| POST | `/proxy/v1/ai/generate-prompt` | AI 生成安全提示词 |
| POST | `/proxy/v1/ai/generate-regex` | AI 生成正则规则 |
| POST | `/proxy/v1/config` | 配置审查引擎 |

## 许可证

MIT License
