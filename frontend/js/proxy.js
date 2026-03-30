/**
 * 代理审查管理模块
 * 对接后端 /proxy/v1/* 接口
 */

const PROXY_API = 'http://127.0.0.1:5001';

// 代理项目缓存
let proxyTasksCache = [];

// ─── 页面初始化 ────────────────────────────────────

function initProxyPage() {
    loadProxyConfig();
    loadProxyStats();
    loadProxyTasks();
    loadProxyLogs();
}

// ─── 审查引擎配置 ──────────────────────────────────

async function loadProxyConfig() {
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/config`);
        const data = await resp.json();
        if (data.success && data.config) {
            document.getElementById('proxy-judge-url').value = data.config.judge_url || '';
            document.getElementById('proxy-judge-model').value = data.config.judge_model || '';
            document.getElementById('proxy-judge-key').value = '';
            document.getElementById('proxy-judge-key').placeholder = data.config.judge_key_set ? '已设置（留空不修改）' : '本地 Ollama 无需填写';
            const badge = document.getElementById('proxy-engine-status');
            badge.textContent = '运行中';
            badge.style.background = '#27ae60';
        }
    } catch (e) {
        console.error('加载代理配置失败:', e);
        const badge = document.getElementById('proxy-engine-status');
        badge.textContent = '连接失败';
        badge.style.background = '#e74c3c';
    }
}

async function saveProxyConfig() {
    const judge_url = document.getElementById('proxy-judge-url').value.trim();
    const judge_model = document.getElementById('proxy-judge-model').value.trim();
    const judge_key = document.getElementById('proxy-judge-key').value.trim();

    if (!judge_url && !judge_model) {
        showToast('请至少填写审查模型地址或名称', 'warning');
        return;
    }

    const body = {};
    if (judge_url) body.judge_url = judge_url;
    if (judge_model) body.judge_model = judge_model;
    if (judge_key) body.judge_key = judge_key;

    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.success) {
            showToast('审查引擎配置已更新', 'success');
            loadProxyConfig();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (e) {
        showToast('保存配置失败: ' + e.message, 'error');
    }
}

// ─── 统计概览 ───────────────────────────────────────

async function loadProxyStats() {
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/logs/stats`);
        const data = await resp.json();
        if (data.success) {
            document.getElementById('proxy-total-requests').textContent = data.total_requests || 0;
            document.getElementById('proxy-blocked-input').textContent = data.blocked_input || 0;
            document.getElementById('proxy-blocked-output').textContent = data.blocked_output || 0;
            document.getElementById('proxy-total-tokens').textContent = (data.total_tokens || 0).toLocaleString();
            document.getElementById('proxy-avg-latency').textContent = (data.avg_latency_ms || 0) + ' ms';
        }
    } catch (e) {
        console.error('加载代理统计失败:', e);
    }
}

// ─── 代理项目 CRUD ──────────────────────────────────

async function loadProxyTasks() {
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/tasks`);
        const data = await resp.json();
        if (data.success) {
            proxyTasksCache = data.tasks || [];
            renderTasksTable();
            updateChatProxySelect();
        }
    } catch (e) {
        console.error('加载代理项目失败:', e);
    }
}

function _strategyBadge(ac) {
    if (!ac) return '<span style="color:#999;">-</span>';
    const parts = [];
    if (ac.custom_regex && ac.custom_regex.enabled)
        parts.push('<span title="自定义正则" style="color:#9b59b6;">①</span>');
    if (ac.llm_judge && ac.llm_judge.enabled)
        parts.push('<span title="大模型审查" style="color:#27ae60;">②</span>');
    return parts.length > 0 ? parts.join(' ') : '';
}

function renderTasksTable() {
    const tbody = document.getElementById('proxy-tasks-table');
    if (!tbody) return;
    if (proxyTasksCache.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:2rem;color:var(--text-secondary);">暂无代理项目，点击上方按钮创建</td></tr>';
        return;
    }
    tbody.innerHTML = proxyTasksCache.map(t => {
        const ac = t.audit_config || {};
        const dirMap = { input: '输入', output: '输出', both: '双向' };
        const colorMap = { input: '#3498db', output: '#e74c3c', both: '#8e44ad' };
        const direction = dirMap[ac.direction] || '输入';
        const dirColor = colorMap[ac.direction] || '#3498db';
        const layers = _strategyBadge(ac);
        const threshold = ac.block_threshold || t.min_confidence || 60;
        return `<tr>
            <td><code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:0.85rem;">${t.proxy_id}</code></td>
            <td>${escapeHtml(t.name)}</td>
            <td title="${escapeHtml(t.upstream_url)}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(t.upstream_url)}</td>
            <td>${escapeHtml(t.model || '-')}</td>
            <td><span style="color:${dirColor};font-weight:600;">${direction}</span> ${layers}</td>
            <td>${threshold}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-outline btn-sm" onclick="editTask('${t.proxy_id}')"><i class="fas fa-edit"></i></button>
                <button class="btn btn-danger btn-sm" onclick="deleteTaskConfirm('${t.proxy_id}','${escapeHtml(t.name)}')"><i class="fas fa-trash"></i></button>
            </td>
        </tr>`;
    }).join('');
}

let _currentAuditDirection = 'input';

function switchAuditTab(target) {
    _currentAuditDirection = target;
    // input 和 both 都显示 input 面板（both 共用 input 面板的配置）
    document.getElementById('ac-input-panel').style.display = (target === 'input' || target === 'both') ? '' : 'none';
    document.getElementById('ac-output-panel').style.display = target === 'output' ? '' : 'none';
    // 切换 tab 样式
    document.querySelectorAll('#ac-tabs .ac-tab').forEach(btn => {
        const isActive = btn.dataset.target === target;
        btn.style.borderBottomColor = isActive ? 'var(--primary-color)' : 'transparent';
        btn.style.color = isActive ? 'var(--primary-color)' : 'var(--text-secondary)';
    });
}

function _parseRegexTextarea(textareaId) {
    const raw = (document.getElementById(textareaId).value || '').trim();
    if (!raw) return [];
    return raw.split('\n')
        .map(line => line.trim())
        .filter(line => line && line.includes('|'))
        .map(line => {
            const idx = line.indexOf('|');
            return { label: line.substring(0, idx).trim(), pattern: line.substring(idx + 1).trim() };
        })
        .filter(r => r.pattern);
}

function _rulesToText(rules) {
    if (!Array.isArray(rules) || rules.length === 0) return '';
    return rules.map(r => `${r.label || '未命名'} | ${r.pattern || ''}`).join('\n');
}

function _loadSideConfig(prefix, cfg) {
    // 自定义正则
    const c = cfg.custom_regex || {};
    document.getElementById(`ac-${prefix}-regex-enabled`).checked = !!c.enabled;
    document.getElementById(`ac-${prefix}-regex-action`).value = c.action || 'enhance';
    document.getElementById(`ac-${prefix}-regex-rules`).value = _rulesToText(c.rules);
    // 大模型
    const l = cfg.llm_judge || {};
    document.getElementById(`ac-${prefix}-llm-enabled`).checked = l.enabled !== false;
    // 最终阈值
    document.getElementById(`ac-${prefix}-block-threshold`).value = cfg.block_threshold || 60;
}

function _collectSideConfig(prefix) {
    return {
        enabled: true,
        builtin_rules: { enabled: true, action: 'block' },
        custom_regex: {
            enabled: document.getElementById(`ac-${prefix}-regex-enabled`).checked,
            action: document.getElementById(`ac-${prefix}-regex-action`).value,
            rules: _parseRegexTextarea(`ac-${prefix}-regex-rules`),
        },
        llm_judge: { enabled: document.getElementById(`ac-${prefix}-llm-enabled`).checked },
        block_threshold: parseInt(document.getElementById(`ac-${prefix}-block-threshold`).value) || 60,
    };
}

function openTaskModal(task) {
    document.getElementById('task-edit-id').value = task ? task.proxy_id : '';
    document.getElementById('task-modal-title').textContent = task ? '编辑代理项目' : '新建代理项目';
    document.getElementById('task-name').value = task ? task.name : '';
    document.getElementById('task-upstream-url').value = task ? task.upstream_url : '';
    document.getElementById('task-api-key').value = '';
    if (task && task.api_key) document.getElementById('task-api-key').placeholder = '已设置（留空不修改）';
    else document.getElementById('task-api-key').placeholder = 'sk-xxxx...';
    document.getElementById('task-model').value = task ? task.model : '';
    document.getElementById('task-security-prompt').value = task ? (task.security_prompt || '') : '';

    // 加载 audit_config
    const cfg = (task && task.audit_config) || null;
    const defaultSide = {
        custom_regex: { enabled: false, action: 'enhance', rules: [] },
        llm_judge: { enabled: true },
        block_threshold: 60,
    };
    const direction = (cfg && cfg.direction) || 'input';
    // both 和 input 加载到 input 面板，output 加载到 output 面板
    if (direction === 'output') {
        _loadSideConfig('input', defaultSide);
        _loadSideConfig('output', cfg || defaultSide);
    } else {
        _loadSideConfig('input', cfg || defaultSide);
        _loadSideConfig('output', defaultSide);
    }

    switchAuditTab(direction);
    openModal('task-modal');
}

function editTask(proxyId) {
    const task = proxyTasksCache.find(t => t.proxy_id === proxyId);
    if (task) openTaskModal(task);
}

async function saveTask() {
    const editId = document.getElementById('task-edit-id').value;
    const name = document.getElementById('task-name').value.trim();
    const upstream_url = document.getElementById('task-upstream-url').value.trim();

    if (!name || !upstream_url) {
        showToast('名称和上游地址不能为空', 'warning');
        return;
    }

    // both 和 input 都从 input 面板收集，output 从 output 面板收集
    const collectFrom = _currentAuditDirection === 'output' ? 'output' : 'input';
    const sideCfg = _collectSideConfig(collectFrom);
    const auditConfig = {
        direction: _currentAuditDirection,
        ...sideCfg,
    };

    const body = {
        name,
        upstream_url,
        model: document.getElementById('task-model').value.trim(),
        security_prompt: document.getElementById('task-security-prompt').value.trim(),
        audit_config: auditConfig,
    };
    const apiKey = document.getElementById('task-api-key').value.trim();
    if (apiKey) body.api_key = apiKey;

    try {
        const url = editId
            ? `${PROXY_API}/proxy/v1/tasks/${editId}`
            : `${PROXY_API}/proxy/v1/tasks`;
        const resp = await fetch(url, {
            method: editId ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(editId ? '代理项目已更新' : '代理项目已创建', 'success');
            closeModal('task-modal');
            loadProxyTasks();
        } else {
            showToast(data.error || '操作失败', 'error');
        }
    } catch (e) {
        showToast('操作失败: ' + e.message, 'error');
    }
}

function deleteTaskConfirm(proxyId, name) {
    if (!confirm(`确认删除代理项目「${name}」(${proxyId})？`)) return;
    deleteProxyTask(proxyId);
}

async function deleteProxyTask(proxyId) {
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/tasks/${proxyId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            showToast('代理项目已删除', 'success');
            loadProxyTasks();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

// ─── 对话测试页面 — 代理项目下拉 ─────────────────

function updateChatProxySelect() {
    const select = document.getElementById('chat-proxy-select');
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">-- 请选择代理项目 --</option>' +
        proxyTasksCache.map(t =>
            `<option value="${t.proxy_id}">${escapeHtml(t.name)} (${t.proxy_id})</option>`
        ).join('');
    if (current && proxyTasksCache.find(t => t.proxy_id === current)) {
        select.value = current;
    }
}

function _describeSide(sideCfg) {
    if (!sideCfg || !sideCfg.enabled) return '❌ 关';
    const layers = [];
    if (sideCfg.builtin_rules && sideCfg.builtin_rules.enabled) {
        const a = sideCfg.builtin_rules.action === 'block' ? '拦截' : '增强确认';
        layers.push(`<span style="color:#e67e22;">① 内置规则(${a})</span>`);
    }
    if (sideCfg.custom_regex && sideCfg.custom_regex.enabled) {
        const n = (sideCfg.custom_regex.rules || []).length;
        const a = sideCfg.custom_regex.action === 'block' ? '拦截' : '增强确认';
        layers.push(`<span style="color:#9b59b6;">② 正则${n}条(${a})</span>`);
    }
    if (sideCfg.llm_judge && sideCfg.llm_judge.enabled) {
        layers.push(`<span style="color:#27ae60;">③ 大模型</span>`);
    }
    if (layers.length === 0) return '✅ 开(无策略层)';
    return layers.join(' → ');
}

function onChatProxyChange() {
    const select = document.getElementById('chat-proxy-select');
    const info = document.getElementById('chat-proxy-info');
    const task = proxyTasksCache.find(t => t.proxy_id === select.value);
    if (!task) {
        info.innerHTML = '<p class="placeholder-text">选择代理项目后显示配置详情</p>';
        return;
    }
    const ac = task.audit_config || {};
    info.innerHTML = `
        <div style="line-height:1.8;">
            <div><strong>代理号:</strong> <code>${task.proxy_id}</code></div>
            <div><strong>接入地址:</strong></div>
            <code style="display:block;background:#1a1a2e;color:#0f0;padding:0.4rem 0.6rem;border-radius:4px;font-size:0.8rem;word-break:break-all;margin:0.25rem 0;">
                ${PROXY_API}/proxy/v1/chat/completions
            </code>
            <div><strong>上游:</strong> ${escapeHtml(truncate(task.upstream_url, 40))}</div>
            <div><strong>模型:</strong> ${escapeHtml(task.model || '(未设置)')}</div>
            <div><strong>输入策略:</strong> ${_describeSide(ac.input)}</div>
            <div><strong>输出策略:</strong> ${_describeSide(ac.output)}</div>
            <div><strong>拦截阈值:</strong> ${(ac.input && ac.input.block_threshold) || task.min_confidence || 60}</div>
            <div><strong>API Key:</strong> ${task.api_key ? '已设置' : '未设置'}</div>
        </div>`;
}

function initChatPage() {
    if (proxyTasksCache.length === 0) {
        loadProxyTasks();
    } else {
        updateChatProxySelect();
    }
}

// ─── 代理日志 ───────────────────────────────────────

async function loadProxyLogs() {
    const limit = parseInt(document.getElementById('proxy-log-limit').value) || 30;
    const tbody = document.getElementById('proxy-logs-table');

    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/logs?limit=${limit}`);
        const data = await resp.json();

        if (!data.success || !data.logs || data.logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:3rem;color:var(--text-secondary);">
                <i class="fas fa-inbox" style="font-size:2rem;margin-bottom:1rem;display:block;opacity:0.5;"></i>
                暂无代理日志</td></tr>`;
            return;
        }

        tbody.innerHTML = data.logs.map(log => {
            const time = log.timestamp ? new Date(log.timestamp).toLocaleString('zh-CN') : '-';
            const url = log.url ? truncate(log.url, 30) : '-';
            const model = log.model || '-';
            const status = log.status_code || '-';
            const latency = log.latency_ms ? log.latency_ms + 'ms' : '-';
            const tokens = log.total_tokens || 0;

            const inputSafe = log.input_audit_safe;
            const inputBadge = inputSafe === null || inputSafe === undefined ? '<span style="color:#999;">-</span>'
                : inputSafe ? '<span style="color:#27ae60;">✅ 安全</span>'
                : `<span style="color:#e74c3c;">🚫 风险(${log.input_audit_score || 0})</span>`;

            const outputSafe = log.output_audit_safe;
            const outputBadge = outputSafe === null || outputSafe === undefined ? '<span style="color:#999;">-</span>'
                : outputSafe ? '<span style="color:#27ae60;">✅ 安全</span>'
                : `<span style="color:#e74c3c;">🚫 风险(${log.output_audit_score || 0})</span>`;

            const error = log.error ? `<span style="color:#e74c3c;" title="${escapeHtml(log.error)}">${truncate(log.error, 20)}</span>` : '-';

            const statusColor = status >= 200 && status < 300 ? '#27ae60' : status >= 400 ? '#e74c3c' : '#f39c12';

            return `<tr>
                <td style="white-space:nowrap;font-size:0.85rem;">${time}</td>
                <td title="${escapeHtml(log.url || '')}" style="font-size:0.85rem;">${url}</td>
                <td>${model}</td>
                <td><span style="color:${statusColor};font-weight:600;">${status}</span></td>
                <td>${latency}</td>
                <td>${tokens}</td>
                <td>${inputBadge}</td>
                <td>${outputBadge}</td>
                <td>${error}</td>
            </tr>`;
        }).join('');

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#e74c3c;">加载失败: ${e.message}</td></tr>`;
    }
}

// ─── 复制代理接入地址 ─────────────────────────────

function copyProxyEndpoint() {
    const url = document.getElementById('proxy-endpoint-url').textContent.trim();
    navigator.clipboard.writeText(url).then(() => {
        showToast('代理接入地址已复制', 'success');
    }).catch(() => {
        // fallback
        const ta = document.createElement('textarea');
        ta.value = url;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('代理接入地址已复制', 'success');
    });
}

// ─── 工具函数 ───────────────────────────────────────

function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '...' : str;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── AI 辅助生成 ──────────────────────────────────

async function aiGeneratePrompt() {
    const desc = prompt('简单描述你的业务场景，如：电商客服、医疗咨询、内部知识库...');
    if (!desc || !desc.trim()) return;
    const btn = document.getElementById('btn-ai-prompt');
    const origText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    btn.disabled = true;
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/ai/generate-prompt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ business_desc: desc, direction: _currentAuditDirection }),
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('task-security-prompt').value = data.prompt;
            showToast('安全提示词已生成', 'success');
        } else {
            showToast(data.error || '生成失败', 'error');
        }
    } catch (e) {
        showToast('生成失败: ' + e.message, 'error');
    } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

async function aiGenerateRegex(prefix) {
    const textarea = document.getElementById(`ac-${prefix}-regex-rules`);
    const desc = textarea.value.trim();
    if (!desc) {
        showToast('请先在文本框里描述想检测的内容', 'warning');
        textarea.focus();
        return;
    }
    const btn = document.querySelector(`button[onclick="aiGenerateRegex('${prefix}')"]`);
    let origText = '';
    if (btn) { origText = btn.innerHTML; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; btn.disabled = true; }
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/ai/generate-regex`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_desc: desc }),
        });
        const data = await resp.json();
        if (data.success) {
            textarea.value = data.rules;
            showToast('正则规则已生成', 'success');
        } else {
            showToast(data.error || '生成失败', 'error');
        }
    } catch (e) {
        showToast('生成失败: ' + e.message, 'error');
    } finally {
        if (btn) { btn.innerHTML = origText; btn.disabled = false; }
    }
}

// ─── 策略模板 ──────────────────────────────────────

async function saveStrategyTemplate() {
    const name = prompt('请输入模板名称：');
    if (!name || !name.trim()) return;

    const collectFrom = _currentAuditDirection === 'output' ? 'output' : 'input';
    const sideCfg = _collectSideConfig(collectFrom);
    const auditConfig = { direction: _currentAuditDirection, ...sideCfg };
    const securityPrompt = document.getElementById('task-security-prompt').value.trim();

    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/templates`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name.trim(),
                direction: _currentAuditDirection,
                security_prompt: securityPrompt,
                audit_config: auditConfig,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`策略模板「${name.trim()}」已保存`, 'success');
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

async function loadStrategyTemplate() {
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/templates`);
        const data = await resp.json();
        if (!data.success || !data.templates || data.templates.length === 0) {
            showToast('暂无策略模板', 'warning');
            return;
        }
        const tpls = data.templates;
        const dirLabel = { input: '输入', output: '输出', both: '双向' };
        const choices = tpls.map((t, i) => `${i + 1}. ${t.name} (${dirLabel[t.direction] || t.direction})`).join('\n');
        const input = prompt(`选择模板编号：\n${choices}`);
        if (!input) return;
        const idx = parseInt(input) - 1;
        if (isNaN(idx) || idx < 0 || idx >= tpls.length) {
            showToast('无效选择', 'warning');
            return;
        }
        const tpl = tpls[idx];
        const ac = tpl.audit_config || {};
        const direction = ac.direction || tpl.direction || 'input';

        // 加载安全提示词
        if (tpl.security_prompt) {
            document.getElementById('task-security-prompt').value = tpl.security_prompt;
        }

        // 加载审查配置到对应面板
        if (direction === 'output') {
            _loadSideConfig('output', ac);
        } else {
            _loadSideConfig('input', ac);
        }
        switchAuditTab(direction);
        showToast(`已加载模板「${tpl.name}」`, 'success');
    } catch (e) {
        showToast('加载失败: ' + e.message, 'error');
    }
}

// ─── 页面切换钩子 ──────────────────────────────────

(function() {
    const origSwitchPage = window.switchPage;
    window.switchPage = function(page) {
        if (typeof origSwitchPage === 'function') origSwitchPage(page);
        if (page === 'proxy') initProxyPage();
        if (page === 'chat') initChatPage();
    };

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.nav-item[data-page="proxy"]').forEach(item => {
            item.addEventListener('click', () => initProxyPage());
        });
        document.querySelectorAll('.nav-item[data-page="chat"]').forEach(item => {
            item.addEventListener('click', () => initChatPage());
        });
    });
})();
