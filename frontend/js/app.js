/**
 * AI 大模型安全管理系统 - 前端应用
 */

// ========== API 配置 ==========
const API_BASE = 'http://localhost:5001/api';
const API_BASE_URL = 'http://localhost:5001'; // 用于训练API

// ========== API 调用封装 ==========
const API = {
    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || '请求失败');
            }
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // 模型相关
    getModels() {
        return this.request('/models');
    },
    
    getModel(id) {
        return this.request(`/models/${id}`);
    },
    
    createModel(data) {
        return this.request('/models', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    updateModel(id, data) {
        return this.request(`/models/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    deleteModel(id) {
        return this.request(`/models/${id}`, {
            method: 'DELETE'
        });
    },

    getOllamaModels() {
        return this.request('/models/ollama');
    },

    getLocalModels() {
        return this.request('/models/local');
    },

    // 统计数据
    getStats() {
        return this.request('/stats');
    },

    // API 密钥
    saveKey(data) {
        return this.request('/keys', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 健康检查
    healthCheck() {
        return this.request('/health');
    },

    // 对话
    chat(modelIdentifier, message, userId = 'test-user', scene = 'general') {
        const isLocal = typeof modelIdentifier === 'string' &&
            (modelIdentifier.startsWith('ollama:') || modelIdentifier.startsWith('hf:'));
        const body = isLocal
            ? { model_id: modelIdentifier, message, user_id: userId, scene }
            : { model_name: modelIdentifier, message, user_id: userId, scene };
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },

    // 对话日志
    getLogs(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/chat/logs${query ? '?' + query : ''}`);
    },

    // 获取用户列表
    getChatUsers(modelId = null) {
        const query = modelId ? `?model_id=${modelId}` : '';
        return this.request(`/chat/users${query}`);
    },

    // 系统配置
    getConfig() {
        return this.request('/config');
    },

    saveConfig(data) {
        return this.request('/config', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

// 全局模型缓存
let modelsCache = [];

// ========== 页面导航 ==========
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const pageName = item.dataset.page;
            
            // 更新导航状态
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // 切换页面
            document.querySelectorAll('.page').forEach(page => {
                page.classList.remove('active');
            });
            document.getElementById(`page-${pageName}`).classList.add('active');
            
            // 页面切换时的特殊处理
            if (pageName === 'models') {
                renderModelsTable();
            } else if (pageName === 'security') {
                populateModelSelects();
            } else if (pageName === 'chat') {
                populateModelSelects();
            } else if (pageName === 'logs') {
                initLogsPage();
            } else if (pageName === 'evaluation') {
                if (typeof loadEvalTasks === 'function') {
                    loadEvalTasks();
                    populateEvalModelSelect();
                }
            } else if (pageName === 'poison') {
                // 投毒检测页面无需初始化
            } else if (pageName === 'mining') {
                if (typeof initMiningPage === 'function') {
                    initMiningPage();
                }
            } else if (pageName === 'multimodal') {
                // 多模态安全页面无需初始化
            } else if (pageName === 'reports') {
                if (typeof loadReports === 'function') {
                    loadReports();
                    populateReportTaskFilter();
                }
            } else if (pageName === 'policies') {
                if (typeof initPoliciesPage === 'function') {
                    initPoliciesPage();
                }
            } else if (pageName === 'training') {
                // 初始化训练页面
                if (typeof loadAvailableModels === 'function') {
                    loadAvailableModels();
                    loadAvailableDatasets();
                    loadTrainingTasks();
                }
            } else if (pageName === 'settings') {
                loadViolationSettings();
                loadJudgeModelConfig();
                loadVisionModelConfig();
            } else if (pageName === 'dashboard') {
                updateDashboardStats();
            }
        });
    });
}

// ========== 控制台统计 ==========
async function updateDashboardStats() {
    try {
        const result = await API.getStats();
        const stats = result.data;
        
        document.getElementById('local-model-count').textContent = stats.local_model_count || 0;
        document.getElementById('api-model-count').textContent = stats.api_model_count || 0;
        document.getElementById('security-count').textContent = stats.security_count;
        document.getElementById('apikey-count').textContent = stats.apikey_count;
        document.getElementById('chat-count').textContent = stats.chat_count;
    } catch (error) {
        console.error('获取统计数据失败:', error);
        showToast('获取统计数据失败', 'error');
    }
}

// ========== 模型管理 ==========
async function renderModelsTable() {
    const tbody = document.getElementById('models-table-body');
    
    try {
        const result = await API.getModels();
        modelsCache = result.data;
    } catch (error) {
        showToast('获取模型列表失败', 'error');
        modelsCache = [];
    }
    
    const models = modelsCache;
    
    if (models.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                    <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 1rem; display: block; opacity: 0.5;"></i>
                    暂无模型，点击上方按钮添加
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = models.map(model => `
        <tr>
            <td><strong>${escapeHtml(model.name)}</strong></td>
            <td><code>${escapeHtml(model.model_id)}</code></td>
            <td>${model.url ? `<span class="status active"><i class="fas fa-check"></i> 已设置</span>` : '<span class="status inactive">未设置</span>'}</td>
            <td>${model.api_key ? `<span class="status active"><i class="fas fa-check"></i> 已设置</span>` : '<span class="status inactive">未设置</span>'}</td>
            <td>${model.security_prompt ? `<span class="status active"><i class="fas fa-shield-alt"></i> 已配置</span>` : '<span class="status inactive">未配置</span>'}</td>
            <td>${model.created_at || '-'}</td>
            <td>
                <button class="btn btn-sm btn-outline btn-icon" onclick="editModel(${model.id})" title="编辑">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-danger btn-icon" onclick="deleteModel(${model.id})" title="删除">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function openAddModelModal() {
    document.getElementById('modal-title').textContent = '添加模型';
    document.getElementById('edit-model-index').value = '';
    document.getElementById('model-name').value = '';
    document.getElementById('model-id').value = '';
    document.getElementById('model-url').value = '';
    document.getElementById('model-api-key').value = '';
    openModal('model-modal');
}

function editModel(id) {
    const model = modelsCache.find(m => m.id === id);
    if (!model) {
        showToast('模型不存在', 'error');
        return;
    }
    
    document.getElementById('modal-title').textContent = '编辑模型';
    document.getElementById('edit-model-index').value = id;  // 存储模型 ID
    document.getElementById('model-name').value = model.name || '';
    document.getElementById('model-id').value = model.model_id || '';
    document.getElementById('model-url').value = model.url || '';
    document.getElementById('model-api-key').value = model.api_key || '';
    
    openModal('model-modal');
}

async function saveModel() {
    const idStr = document.getElementById('edit-model-index').value;
    const name = document.getElementById('model-name').value.trim();
    const modelId = document.getElementById('model-id').value.trim();
    const url = document.getElementById('model-url').value.trim();
    const apiKey = document.getElementById('model-api-key').value.trim();
    
    if (!name) {
        showToast('请输入模型名称', 'error');
        return;
    }
    if (!modelId) {
        showToast('请输入 Model ID', 'error');
        return;
    }
    
    const isEdit = idStr !== '';
    const modelData = {
        name,
        model_id: modelId,
        url,
        api_key: apiKey
    };
    
    try {
        if (isEdit) {
            // 编辑时保留原有的 security_prompt
            const oldModel = modelsCache.find(m => m.id === parseInt(idStr));
            if (oldModel) {
                modelData.security_prompt = oldModel.security_prompt || '';
            }
            await API.updateModel(parseInt(idStr), modelData);
            showToast('模型已更新', 'success');
            addActivity(`修改了模型「${name}」`, 'blue');
        } else {
            await API.createModel(modelData);
            showToast('模型已添加', 'success');
            addActivity(`添加了新模型「${name}」`, 'green');
        }
        
        closeModal('model-modal');
        renderModelsTable();
        updateDashboardStats();
    } catch (error) {
        showToast(error.message || '保存失败', 'error');
    }
}

async function deleteModel(id) {
    if (!confirm('确定要删除此模型吗？此操作不可撤销。')) {
        return;
    }
    
    const model = modelsCache.find(m => m.id === id);
    const modelName = model ? model.name : '未知';
    
    try {
        await API.deleteModel(id);
        showToast('模型已删除', 'success');
        addActivity(`删除了模型「${modelName}」`, 'red');
        renderModelsTable();
        updateDashboardStats();
    } catch (error) {
        showToast(error.message || '删除失败', 'error');
    }
}

// ========== 安全策略 ==========
async function populateModelSelects() {
    // 确保有最新的模型数据
    if (modelsCache.length === 0) {
        try {
            const result = await API.getModels();
            modelsCache = result.data;
        } catch (error) {
            console.error('获取模型失败:', error);
        }
    }

    // 并行获取 Ollama 和 HuggingFace 本地模型
    let ollamaModels = [];
    let localModels = [];
    try {
        const [ollamaResult, localResult] = await Promise.allSettled([
            API.getOllamaModels(),
            API.getLocalModels(),
        ]);
        if (ollamaResult.status === 'fulfilled') ollamaModels = ollamaResult.value.data || [];
        if (localResult.status === 'fulfilled') localModels = localResult.value.data || [];
    } catch (e) {}
    
    const dbOptions = modelsCache.map(m => 
        `<option value="${m.id}">${escapeHtml(m.name)} (${escapeHtml(m.model_id)})</option>`
    ).join('');

    const ollamaOptions = ollamaModels.map(m =>
        `<option value="ollama:${escapeHtml(m.name)}">[Ollama] ${escapeHtml(m.name)} (${escapeHtml(m.size)})</option>`
    ).join('');

    const hfOptions = localModels.map(m =>
        `<option value="hf:${escapeHtml(m.name)}">[HF本地] ${escapeHtml(m.name)} (${escapeHtml(m.parameters || m.size)})</option>`
    ).join('');

    const ollamaSep = ollamaOptions ? '<option disabled>── Ollama 模型 ──</option>' : '';
    const hfSep = hfOptions ? '<option disabled>── HuggingFace 本地模型 ──</option>' : '';
    
    const defaultOption = '<option value="">-- 请选择模型 --</option>';
    const allOptions = defaultOption + dbOptions + ollamaSep + ollamaOptions + hfSep + hfOptions;
    
    const securitySelect = document.getElementById('security-model-select');
    const chatSelect = document.getElementById('chat-model-select');
    
    if (securitySelect) {
        securitySelect.innerHTML = allOptions;
        securitySelect.onchange = onSecurityModelChange;
    }
    if (chatSelect) {
        chatSelect.innerHTML = allOptions;
        chatSelect.onchange = onChatModelChange;
    }
}

function onSecurityModelChange() {
    const select = document.getElementById('security-model-select');
    const modelId = select.value;
    const preview = document.getElementById('security-prompt-preview');
    const editor = document.getElementById('security-prompt-edit');
    
    if (modelId === '') {
        preview.innerHTML = '<p class="placeholder-text">选择模型后显示其安全提示词</p>';
        editor.value = '';
        return;
    }
    
    const model = modelsCache.find(m => m.id === parseInt(modelId));
    
    if (model && model.security_prompt) {
        preview.innerHTML = `<p>${escapeHtml(model.security_prompt)}</p>`;
        editor.value = model.security_prompt;
    } else {
        preview.innerHTML = '<p class="placeholder-text">该模型尚未配置安全提示词</p>';
        editor.value = '';
    }
}

function generateSecurityPrompt() {
    const select = document.getElementById('security-model-select');
    const description = document.getElementById('project-description').value.trim();
    
    if (select.value === '') {
        showToast('请先选择目标模型', 'warning');
        return;
    }
    if (!description) {
        showToast('请输入项目描述', 'warning');
        return;
    }
    
    // 模拟 AI 生成（实际项目中调用后端 API）
    showToast('正在生成安全提示词...', 'info');
    
    setTimeout(() => {
        const generatedPrompt = generateMockSecurityPrompt(description);
        document.getElementById('security-prompt-edit').value = generatedPrompt;
        document.getElementById('security-prompt-preview').innerHTML = 
            `<p>${escapeHtml(generatedPrompt)}</p>`;
        showToast('安全提示词生成完成', 'success');
    }, 1500);
}

function generateMockSecurityPrompt(description) {
    // 模拟生成逻辑（实际应调用后端 AI）
    const keywords = [];
    if (description.includes('医')) keywords.push('患者隐私', '医疗数据', '诊断结果');
    if (description.includes('金融')) keywords.push('交易数据', '账户信息', '风控报告');
    if (description.includes('知识库')) keywords.push('内部文档', '商业机密', '员工信息');
    
    const defaultKeywords = ['用户个人信息', '敏感数据', '系统日志'];
    const finalKeywords = keywords.length > 0 ? keywords : defaultKeywords;
    
    return `你必须严格保护数据安全和用户隐私。禁止输出以下敏感信息：${finalKeywords.join('、')}。所有输出须遵循最小必要原则，不得返回原始数据、错误堆栈或调试信息。对敏感内容进行脱敏处理后方可输出。`;
}

async function saveSecurityPrompt() {
    const select = document.getElementById('security-model-select');
    const prompt = document.getElementById('security-prompt-edit').value.trim();
    
    if (select.value === '') {
        showToast('请先选择目标模型', 'warning');
        return;
    }
    
    const modelId = parseInt(select.value);
    const model = modelsCache.find(m => m.id === modelId);
    
    if (!model) {
        showToast('模型不存在', 'error');
        return;
    }
    
    try {
        await API.updateModel(modelId, {
            name: model.name,
            model_id: model.model_id,
            url: model.url,
            api_key: model.api_key,
            security_prompt: prompt
        });
        
        // 更新缓存
        model.security_prompt = prompt;
        
        showToast('安全策略已保存', 'success');
        addActivity(`更新了「${model.name}」的安全策略`, 'green');
        
        // 刷新预览
        document.getElementById('security-prompt-preview').innerHTML = 
            prompt ? `<p>${escapeHtml(prompt)}</p>` : '<p class="placeholder-text">该模型尚未配置安全提示词</p>';
    } catch (error) {
        showToast(error.message || '保存失败', 'error');
    }
}

// ========== 对话测试 ==========
function onChatModelChange() {
    const select = document.getElementById('chat-model-select');
    const infoCard = document.getElementById('chat-model-info');
    
    if (select.value === '') {
        infoCard.innerHTML = '<p class="placeholder-text">选择模型后显示详情</p>';
        return;
    }
    
    const model = modelsCache.find(m => m.id === parseInt(select.value));
    
    infoCard.innerHTML = `
        <h4 style="margin-bottom: 0.75rem;">${escapeHtml(model.name)}</h4>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
            <strong>Model ID:</strong> ${escapeHtml(model.model_id)}
        </p>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
            <strong>API:</strong> ${model.api_key ? '✅ 已配置' : '❌ 未配置'}
        </p>
        <p style="font-size: 0.875rem; color: var(--text-secondary);">
            <strong>安全策略:</strong> ${model.security_prompt ? '✅ 已配置' : '❌ 未配置'}
        </p>
    `;
    
    // 清空聊天记录
    document.getElementById('chat-messages').innerHTML = `
        <div class="chat-welcome">
            <i class="fas fa-robot"></i>
            <p>已选择「${escapeHtml(model.name)}」，开始对话吧</p>
        </div>
    `;
}

// ========== 附件处理 ==========
let currentAttachment = null;

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 检查文件大小 (最大 10MB)
    if (file.size > 10 * 1024 * 1024) {
        showToast('文件大小不能超过 10MB', 'error');
        return;
    }
    
    // 检查文件类型
    const ext = file.name.split('.').pop().toLowerCase();
    const imageTypes = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'];
    const docTypes = ['pdf', 'doc', 'docx'];
    
    if (!imageTypes.includes(ext) && !docTypes.includes(ext)) {
        showToast('不支持的文件格式', 'error');
        return;
    }
    
    currentAttachment = {
        file: file,
        name: file.name,
        type: imageTypes.includes(ext) ? 'image' : 'document',
        ext: ext
    };
    
    // 显示预览
    const preview = document.getElementById('attachment-preview');
    const icon = document.getElementById('attachment-icon');
    const name = document.getElementById('attachment-name');
    const item = preview.querySelector('.attachment-item');
    
    // 设置图标
    if (currentAttachment.type === 'image') {
        icon.className = 'fas fa-image';
        // 图片预览
        const reader = new FileReader();
        reader.onload = function(e) {
            item.classList.add('image-preview');
            item.innerHTML = `
                <img src="${e.target.result}" alt="预览">
                <span>${escapeHtml(file.name)}</span>
                <button class="btn-remove" onclick="removeAttachment()">
                    <i class="fas fa-times"></i>
                </button>
            `;
        };
        reader.readAsDataURL(file);
    } else if (ext === 'pdf') {
        icon.className = 'fas fa-file-pdf';
        name.textContent = file.name;
        item.classList.remove('image-preview');
    } else {
        icon.className = 'fas fa-file-word';
        name.textContent = file.name;
        item.classList.remove('image-preview');
    }
    
    preview.style.display = 'block';
}

function removeAttachment() {
    currentAttachment = null;
    document.getElementById('file-input').value = '';
    document.getElementById('attachment-preview').style.display = 'none';
    
    // 重置预览区域
    const item = document.querySelector('.attachment-item');
    item.classList.remove('image-preview');
    item.innerHTML = `
        <i class="fas fa-file" id="attachment-icon"></i>
        <span id="attachment-name"></span>
        <button class="btn-remove" onclick="removeAttachment()">
            <i class="fas fa-times"></i>
        </button>
    `;
}

// 对话历史（用于多轮对话）
let chatHistory = [];

function clearChatHistory() {
    chatHistory = [];
    const chatContainer = document.getElementById('chat-messages');
    chatContainer.innerHTML = `
        <div class="chat-welcome">
            <i class="fas fa-robot"></i>
            <p>选择代理项目后开始对话</p>
            <p style="font-size:0.85rem;color:#888;">所有消息将通过安全代理转发并审查</p>
        </div>`;
    showToast('对话历史已清空', 'success');
}

async function sendMessage() {
    const proxySelect = document.getElementById('chat-proxy-select');
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!proxySelect || !proxySelect.value) {
        showToast('请先选择代理项目', 'warning');
        return;
    }
    if (!message && !currentAttachment) {
        return;
    }

    const proxyId = proxySelect.value;
    const modelOverride = document.getElementById('chat-model-override').value.trim();

    const chatContainer = document.getElementById('chat-messages');

    // 清除欢迎信息
    const welcome = chatContainer.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // 构建用户消息显示（含附件）
    let userContentHtml = escapeHtml(message || '');
    if (currentAttachment) {
        if (currentAttachment.type === 'image') {
            userContentHtml += `<div class="user-attachment"><i class="fas fa-image"></i> ${escapeHtml(currentAttachment.name)}</div>`;
        } else {
            userContentHtml += `<div class="user-attachment"><i class="fas fa-file"></i> ${escapeHtml(currentAttachment.name)}</div>`;
        }
    }

    // 添加用户消息到界面
    chatContainer.innerHTML += `
        <div class="chat-message user">
            <div class="avatar"><i class="fas fa-user"></i></div>
            <div class="content">${userContentHtml}</div>
        </div>
    `;

    input.value = '';
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // 显示加载状态
    const loadingId = 'loading-' + Date.now();
    chatContainer.innerHTML += `
        <div class="chat-message assistant" id="${loadingId}">
            <div class="avatar"><i class="fas fa-robot"></i></div>
            <div class="content"><i class="fas fa-spinner fa-spin"></i> 正在通过代理转发...</div>
        </div>
    `;
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // 保存附件引用并清除预览
    const attachment = currentAttachment;
    if (currentAttachment) {
        removeAttachment();
    }

    // 构建 messages 数组（多轮对话）
    chatHistory.push({ role: 'user', content: message || '请分析这个文件' });

    // 通过代理 API 转发 — 只传 _proxy_id，后端自动匹配配置
    try {
        const proxyBody = {
            _proxy_id: proxyId,
            messages: chatHistory.slice(),
        };
        if (modelOverride) proxyBody.model = modelOverride;

        const resp = await fetch(`${API_BASE}/proxy/v1/chat/completions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(proxyBody),
        });
        const data = await resp.json();

        // 移除加载状态
        document.getElementById(loadingId)?.remove();

        // 被拦截
        if (data.blocked) {
            const blockType = data.block_type === 'input' ? '输入审查' : '输出审查';
            const audit = data.audit || {};
            chatContainer.innerHTML += `
                <div class="chat-message blocked">
                    <div class="avatar" style="background: var(--danger-color);"><i class="fas fa-shield-alt"></i></div>
                    <div class="content">
                        <strong>🚫 已拦截 (${blockType})</strong><br>
                        <span class="block-reason">${escapeHtml(audit.reason || '内容不安全')}</span>
                        <div class="block-meta">
                            <span class="risk-score">风险评分: ${audit.risk_score || 0}</span>
                            <span class="response-time">${data.latency_ms || 0}ms</span>
                        </div>
                    </div>
                </div>
            `;
            // 拦截时移除最后一条 user 消息，不计入历史
            chatHistory.pop();
            showToast(`内容被${blockType}拦截`, 'warning');

        } else if (data.error) {
            // 代理返回错误
            throw new Error(data.error.message || JSON.stringify(data.error));

        } else {
            // 成功：提取 AI 回复
            const choices = data.choices || [];
            const reply = choices.length > 0 ? (choices[0].message?.content || '') : '(无回复内容)';
            const proxy = data._proxy || {};
            const latency = proxy.latency_ms || 0;
            const tokens = proxy.tokens || {};
            const inputAudit = proxy.input_audit;
            const outputAudit = proxy.output_audit;

            // 构建审查标记
            let auditBadges = '';
            if (inputAudit) {
                const ic = inputAudit.safe ? 'success' : 'danger';
                auditBadges += `<span class="check-badge ${ic}"><i class="fas fa-arrow-right"></i> 输入: ${inputAudit.safe ? '安全' : '风险(' + inputAudit.risk_score + ')'}</span> `;
            }
            if (outputAudit) {
                const oc = outputAudit.safe ? 'success' : 'danger';
                auditBadges += `<span class="check-badge ${oc}"><i class="fas fa-arrow-left"></i> 输出: ${outputAudit.safe ? '安全' : '风险(' + outputAudit.risk_score + ')'}</span> `;
            }

            chatContainer.innerHTML += `
                <div class="chat-message assistant">
                    <div class="avatar"><i class="fas fa-robot"></i></div>
                    <div class="content">${escapeHtml(reply)}</div>
                    <div class="message-meta">
                        ${auditBadges}
                        <small class="response-time">${latency}ms</small>
                        ${tokens.total_tokens ? `<small style="margin-left:0.5rem;">Token: ${tokens.total_tokens}</small>` : ''}
                    </div>
                </div>
            `;

            // 记录 assistant 回复到历史
            chatHistory.push({ role: 'assistant', content: reply });
        }

        chatContainer.scrollTop = chatContainer.scrollHeight;

    } catch (error) {
        document.getElementById(loadingId)?.remove();
        chatHistory.pop(); // 移除失败的 user 消息
        chatContainer.innerHTML += `
            <div class="chat-message blocked">
                <div class="avatar" style="background: var(--danger-color);"><i class="fas fa-robot"></i></div>
                <div class="content">
                    <strong>❌ 请求失败</strong><br>
                    ${escapeHtml(error.message)}
                </div>
            </div>
        `;
        chatContainer.scrollTop = chatContainer.scrollHeight;
        showToast(error.message, 'error');
    }
}

// simulateAIResponse 已移除，改用真实 API 调用

// ========== 对话日志 ==========
let currentPage = 1;
let totalPages = 1;

async function initLogsPage() {
    // 加载模型选项
    const select = document.getElementById('logs-model-select');
    
    try {
        if (modelsCache.length === 0) {
            const result = await API.getModels();
            modelsCache = result.data;
        }
        
        const options = modelsCache.map(m => 
            `<option value="${m.id}">${escapeHtml(m.name)}</option>`
        ).join('');
        
        select.innerHTML = '<option value="">全部模型</option>' + options;
    } catch (error) {
        console.error('加载模型失败:', error);
    }
    
    // 加载日志
    loadLogs(1);
}

async function loadLogs(page = currentPage) {
    const modelId = document.getElementById('logs-model-select').value;
    const userId = document.getElementById('logs-user-id').value.trim();
    const status = document.getElementById('logs-status-select').value;
    const pageSize = document.getElementById('logs-page-size').value;
    
    currentPage = page;
    
    const tbody = document.getElementById('logs-table-body');
    tbody.innerHTML = `
        <tr>
            <td colspan="8" style="text-align: center; padding: 2rem;">
                <i class="fas fa-spinner fa-spin"></i> 加载中...
            </td>
        </tr>
    `;
    
    // 隐藏分页
    document.getElementById('logs-pagination').style.display = 'none';
    
    try {
        const params = { page, page_size: pageSize };
        if (modelId) params.model_id = modelId;
        if (userId) params.user_id = userId;
        if (status) params.status = status;
        
        const result = await API.getLogs(params);
        const logs = result.data;
        const pagination = result.pagination;
        
        totalPages = pagination.total_pages;
        currentPage = pagination.page;
        
        document.getElementById('logs-count').textContent = `共 ${pagination.total} 条记录`;
        
        if (logs.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                        <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 1rem; display: block; opacity: 0.5;"></i>
                        暂无对话记录
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = logs.map(log => {
            const isBlocked = log.input_blocked || log.output_blocked;
            const statusHtml = isBlocked 
                ? `<span class="status blocked"><i class="fas fa-ban"></i> 已拦截</span>`
                : `<span class="status success"><i class="fas fa-check"></i> 成功</span>`;
            
            const userInput = log.user_input || '';
            const aiResponse = log.ai_response || (isBlocked ? `拦截原因: ${log.block_reason || '未知'}` : '-');
            const riskScore = log.confidence || 0;
            const riskClass = riskScore >= 60 ? 'high' : (riskScore >= 30 ? 'medium' : 'low');
            const riskHtml = log.confidence !== null && log.confidence !== undefined
                ? `<span class="risk-badge ${riskClass}">${riskScore}%</span>` 
                : '-';
            
            const contextSummary = log.context_summary || '';
            
            return `
                <tr class="${isBlocked ? 'blocked-row' : ''}">
                    <td>${log.created_at || '-'}</td>
                    <td>${escapeHtml(log.model_name || '未知模型')}</td>
                    <td>${log.user_id ? escapeHtml(log.user_id) : '<span style="color: var(--text-secondary);">-</span>'}</td>
                    <td title="${escapeHtml(userInput)}">${truncateText(escapeHtml(userInput), 50)}</td>
                    <td title="${escapeHtml(aiResponse)}">${truncateText(escapeHtml(aiResponse), 50)}</td>
                    <td title="${escapeHtml(contextSummary)}">${contextSummary ? truncateText(escapeHtml(contextSummary), 40) : '<span style="color: var(--text-secondary);">-</span>'}</td>
                    <td>${riskHtml}</td>
                    <td>${statusHtml}</td>
                </tr>
            `;
        }).join('');
        
        // 更新分页控件
        updatePagination(pagination);
        
    } catch (error) {
        console.error('加载日志失败:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 2rem; color: var(--danger);">
                    <i class="fas fa-exclamation-circle"></i> 加载失败
                </td>
            </tr>
        `;
        showToast('加载日志失败', 'error');
    }
}

function updatePagination(pagination) {
    const container = document.getElementById('logs-pagination');
    
    if (pagination.total_pages <= 1) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'flex';
    
    // 更新按钮状态
    document.getElementById('btn-first').disabled = currentPage === 1;
    document.getElementById('btn-prev').disabled = currentPage === 1;
    document.getElementById('btn-next').disabled = currentPage === totalPages;
    document.getElementById('btn-last').disabled = currentPage === totalPages;
    
    // 生成页码按钮
    const pageNumbers = document.getElementById('page-numbers');
    let html = '';
    
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    if (startPage > 1) {
        html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
        if (startPage > 2) html += `<span style="padding: 0 0.5rem;">...</span>`;
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span style="padding: 0 0.5rem;">...</span>`;
        html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }
    
    pageNumbers.innerHTML = html;
    
    // 更新页面信息
    document.getElementById('page-info').textContent = `第 ${currentPage} / ${totalPages} 页，共 ${pagination.total} 条`;
}

function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    loadLogs(page);
}

// 导出日志为 TXT 文件
async function exportLogs() {
    const modelId = document.getElementById('logs-model-select').value;
    const userId = document.getElementById('logs-user-id').value.trim();
    const status = document.getElementById('logs-status-select').value;
    
    showToast('正在导出...', 'info');
    
    try {
        // 获取所有符合条件的记录（不分页）
        const params = { page: 1, page_size: 10000 };
        if (modelId) params.model_id = modelId;
        if (userId) params.user_id = userId;
        if (status) params.status = status;
        
        const result = await API.getLogs(params);
        const logs = result.data;
        
        if (logs.length === 0) {
            showToast('没有可导出的记录', 'warning');
            return;
        }
        
        // 生成 TXT 内容
        let content = '='.repeat(80) + '\n';
        content += '对话日志导出\n';
        content += `导出时间: ${new Date().toLocaleString()}\n`;
        content += `总记录数: ${logs.length}\n`;
        content += '='.repeat(80) + '\n\n';
        
        logs.forEach((log, index) => {
            const isBlocked = log.input_blocked || log.output_blocked;
            const statusText = isBlocked ? '已拦截' : '成功';
            
            content += `----- 记录 ${index + 1} -----\n`;
            content += `时间: ${log.created_at || '-'}\n`;
            content += `模型: ${log.model_name || '未知模型'}\n`;
            content += `用户ID: ${log.user_id || '-'}\n`;
            content += `状态: ${statusText}\n`;
            content += `风险评分: ${log.confidence !== null ? log.confidence + '%' : '-'}\n`;
            content += `\n[用户输入]\n${log.user_input || '-'}\n`;
            
            if (isBlocked) {
                content += `\n[拦截原因]\n${log.block_reason || '-'}\n`;
            } else {
                content += `\n[AI回复]\n${log.ai_response || '-'}\n`;
            }
            
            if (log.context_summary) {
                content += `\n[上下文摘要]\n${log.context_summary}\n`;
            }
            
            content += '\n';
        });
        
        // 创建并下载文件
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `对话日志_${new Date().toISOString().slice(0, 10)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast(`成功导出 ${logs.length} 条记录`, 'success');
        
    } catch (error) {
        console.error('导出失败:', error);
        showToast('导出失败', 'error');
    }
}

function truncateText(text, maxLen) {
    if (!text) return '-';
    return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

// ========== 系统设置 ==========

// 加载违规预警设置
async function loadViolationSettings() {
    try {
        const result = await API.getConfig();
        const config = result.data;
        
        if (config.violation_threshold) {
            document.getElementById('violation-threshold').value = config.violation_threshold;
        }
        if (config.violation_reset_hours) {
            document.getElementById('violation-reset-hours').value = config.violation_reset_hours;
        }
        if (config.min_confidence_threshold) {
            document.getElementById('min-confidence-threshold').value = config.min_confidence_threshold;
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 保存违规预警设置
async function saveViolationSettings() {
    const threshold = document.getElementById('violation-threshold').value;
    const resetHours = document.getElementById('violation-reset-hours').value;
    const minConfidence = document.getElementById('min-confidence-threshold').value;
    
    // 验证
    if (threshold < 1 || threshold > 20) {
        showToast('违规阈值必须在 1-20 之间', 'error');
        return;
    }
    if (resetHours < 1 || resetHours > 168) {
        showToast('重置时间必须在 1-168 小时之间', 'error');
        return;
    }
    if (minConfidence < 0 || minConfidence > 100) {
        showToast('风险拦截阈值必须在 0-100 之间', 'error');
        return;
    }
    
    try {
        await API.saveConfig({
            violation_threshold: threshold,
            violation_reset_hours: resetHours,
            min_confidence_threshold: minConfidence
        });
        showToast('违规预警设置已保存', 'success');
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    input.type = input.type === 'password' ? 'text' : 'password';
}

// 保存审查模型配置
async function saveJudgeModelConfig() {
    const url = document.getElementById('judge-api-url').value.trim();
    const key = document.getElementById('judge-api-key').value.trim();
    const modelName = document.getElementById('judge-model-name').value.trim();
    
    if (!url || !key || !modelName) {
        showToast('请填写完整的审查模型配置', 'error');
        return;
    }
    
    try {
        await API.saveConfig({
            judge_api_url: url,
            judge_model_name: modelName
        });
        
        // 保存 API Key
        await API.saveKey({
            key_name: 'JUDGE_API_KEY',
            key_value: key,
            description: '审查模型 API Key'
        });
        
        showToast('审查模型配置已保存', 'success');
    } catch (error) {
        showToast(error.message || '保存失败', 'error');
    }
}

// 加载审查模型配置
async function loadJudgeModelConfig() {
    try {
        const result = await API.getConfig();
        const config = result.data;
        
        if (config.judge_api_url) {
            document.getElementById('judge-api-url').value = config.judge_api_url;
        }
        if (config.judge_model_name) {
            document.getElementById('judge-model-name').value = config.judge_model_name;
        }
    } catch (error) {
        console.error('加载审查模型配置失败:', error);
    }
}

// 保存视觉模型配置
async function saveVisionModelConfig() {
    const url = document.getElementById('vision-api-url').value.trim();
    const key = document.getElementById('vision-api-key').value.trim();
    const modelName = document.getElementById('vision-model-name').value.trim();
    
    if (!url || !key || !modelName) {
        showToast('请填写完整的视觉模型配置', 'error');
        return;
    }
    
    try {
        await API.saveConfig({
            vision_api_url: url,
            vision_model_name: modelName
        });
        
        // 保存 API Key
        await API.saveKey({
            key_name: 'VISION_API_KEY',
            key_value: key,
            description: '视觉模型 API Key'
        });
        
        showToast('视觉模型配置已保存', 'success');
    } catch (error) {
        showToast(error.message || '保存失败', 'error');
    }
}

// 加载视觉模型配置
async function loadVisionModelConfig() {
    try {
        const result = await API.getConfig();
        const config = result.data;
        
        if (config.vision_api_url) {
            document.getElementById('vision-api-url').value = config.vision_api_url;
        }
        if (config.vision_model_name) {
            document.getElementById('vision-model-name').value = config.vision_model_name;
        }
    } catch (error) {
        console.error('加载视觉模型配置失败:', error);
    }
}

async function exportConfig() {
    try {
        const result = await API.getModels();
        const data = {
            models: result.data,
            exportedAt: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ai-config-${formatDate(new Date())}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        showToast('配置已导出', 'success');
    } catch (error) {
        showToast('导出失败', 'error');
    }
}

async function importConfig() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const data = JSON.parse(event.target.result);
                if (data.models && Array.isArray(data.models)) {
                    for (const model of data.models) {
                        try {
                            await API.createModel(model);
                        } catch (err) {
                            console.log('跳过已存在的模型:', model.name);
                        }
                    }
                }
                showToast('配置已导入', 'success');
                location.reload();
            } catch (err) {
                showToast('导入失败：文件格式错误', 'error');
            }
        };
        reader.readAsText(file);
    };
    input.click();
}

function clearAllData() {
    showToast('清空数据功能需要后端支持', 'warning');
}

// ========== 弹窗控制 ==========
function openModal(modalId) {
    const el = document.getElementById(modalId);
    el.style.display = '';
    el.classList.add('active');
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    el.classList.remove('active');
    el.style.display = 'none';
}

// ========== Toast 提示 ==========
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-circle',
        info: 'fa-info-circle'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span>${escapeHtml(message)}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== 活动记录 ==========
function addActivity(text, iconClass = 'blue') {
    const list = document.getElementById('activity-list');
    const icons = {
        green: 'fa-plus-circle',
        blue: 'fa-edit',
        orange: 'fa-exclamation-triangle',
        red: 'fa-trash'
    };
    
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <i class="fas ${icons[iconClass]} ${iconClass}"></i>
        <span>${escapeHtml(text)}</span>
        <small>刚刚</small>
    `;
    
    list.insertBefore(item, list.firstChild);
    
    // 保留最近 10 条
    while (list.children.length > 10) {
        list.removeChild(list.lastChild);
    }
}

// ========== 工具函数 ==========
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateTime(date) {
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).replace(/\//g, '-');
}

function formatDate(date) {
    return date.toISOString().split('T')[0];
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', async () => {
    initNavigation();
    
    // 检查后端连接
    try {
        await API.healthCheck();
        console.log('✅ 后端 API 连接成功');
    } catch (error) {
        showToast('后端 API 连接失败，请确保后端服务已启动', 'error');
        console.error('❌ 后端 API 连接失败:', error);
    }
    
    // 加载统计数据
    updateDashboardStats();
    
    // Enter 键发送消息
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    console.log('🚀 AI 大模型安全管理系统已启动');
});
