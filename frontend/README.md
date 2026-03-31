# AI 大模型安全管理系统 - 前端

## 项目结构

```
frontend/
├── index.html          # 主页面（单页应用）
├── css/
│   └── style.css       # 全局样式
├── js/
│   └── app.js          # 应用逻辑
├── assets/             # 静态资源（图片等）
└── README.md           # 说明文档
```

## 功能模块

### 1. 控制台 (Dashboard)
- 显示系统统计数据
- 最近活动记录

### 2. 模型管理 (Models)
- 添加/编辑/删除大模型
- 配置模型名称、Model ID、API URL、API Key

### 3. 安全策略 (Security)
- AI 自动生成安全提示词
- 手动编辑安全提示词
- 保存到对应模型

### 4. 对话测试 (Chat)
- 选择模型进行对话测试
- 输入/输出安全审核模拟

### 5. 系统设置 (Settings)
- API Key 管理
- 数据导入/导出
- 清空数据

## 使用方法

### 方式一：直接打开
双击 `index.html` 在浏览器中打开

### 方式二：本地服务器
```bash
# 使用 Python
python -m http.server 8080

# 使用 Node.js
npx serve .

# 使用 VS Code Live Server 插件
```

## 数据存储

当前使用 `localStorage` 模拟数据库存储，数据结构：

```javascript
// models - 模型列表
[
    {
        "name": "模型名称",
        "model_id": "model-id",
        "url": "https://api.example.com/v1",
        "api_key": "sk-xxx",
        "security_prompt": "安全提示词...",
        "added_at": "2025-12-04 12:00:00"
    }
]

// config - 系统配置
{
    "bailianApiKey": "sk-xxx",
    "createdAt": "2025-12-04T04:00:00.000Z"
}
```

## 后续集成

将 `localStorage` 替换为后端 API 调用：

```javascript
// 示例：获取模型列表
async function getModels() {
    const response = await fetch('/api/models');
    return response.json();
}

// 示例：保存模型
async function saveModel(model) {
    await fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(model)
    });
}
```

## 技术栈

- **HTML5** - 页面结构
- **CSS3** - 样式（CSS 变量、Grid、Flexbox）
- **JavaScript (ES6+)** - 应用逻辑
- **Font Awesome 6** - 图标库
