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

function renderTasksTable() {
    const tbody = document.getElementById('proxy-tasks-table');
    if (!tbody) return;
    if (proxyTasksCache.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-secondary);">暂无代理项目，点击上方按钮创建</td></tr>';
        return;
    }
    tbody.innerHTML = proxyTasksCache.map(t => {
        const inputBadge = t.enable_input_audit
            ? '<span style="color:#27ae60;">开</span>'
            : '<span style="color:#999;">关</span>';
        const outputBadge = t.enable_output_audit
            ? '<span style="color:#27ae60;">开</span>'
            : '<span style="color:#999;">关</span>';
        return `<tr>
            <td><code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:0.85rem;">${t.proxy_id}</code></td>
            <td>${escapeHtml(t.name)}</td>
            <td title="${escapeHtml(t.upstream_url)}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(t.upstream_url)}</td>
            <td>${escapeHtml(t.model || '-')}</td>
            <td>${inputBadge}</td>
            <td>${outputBadge}</td>
            <td>${t.min_confidence}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-outline btn-sm" onclick="editTask('${t.proxy_id}')"><i class="fas fa-edit"></i></button>
                <button class="btn btn-danger btn-sm" onclick="deleteTaskConfirm('${t.proxy_id}','${escapeHtml(t.name)}')"><i class="fas fa-trash"></i></button>
            </td>
        </tr>`;
    }).join('');
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
    document.getElementById('task-input-audit').checked = task ? task.enable_input_audit : true;
    document.getElementById('task-output-audit').checked = task ? task.enable_output_audit : true;
    document.getElementById('task-min-confidence').value = task ? task.min_confidence : 60;
    document.getElementById('task-security-prompt').value = task ? (task.security_prompt || '') : '';
    document.getElementById('task-modal').style.display = 'flex';
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

    const body = {
        name,
        upstream_url,
        model: document.getElementById('task-model').value.trim(),
        enable_input_audit: document.getElementById('task-input-audit').checked,
        enable_output_audit: document.getElementById('task-output-audit').checked,
        min_confidence: parseInt(document.getElementById('task-min-confidence').value) || 60,
        security_prompt: document.getElementById('task-security-prompt').value.trim(),
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

function onChatProxyChange() {
    const select = document.getElementById('chat-proxy-select');
    const info = document.getElementById('chat-proxy-info');
    const task = proxyTasksCache.find(t => t.proxy_id === select.value);
    if (!task) {
        info.innerHTML = '<p class="placeholder-text">选择代理项目后显示配置详情</p>';
        return;
    }
    info.innerHTML = `
        <div style="line-height:1.8;">
            <div><strong>代理号:</strong> <code>${task.proxy_id}</code></div>
            <div><strong>接入地址:</strong></div>
            <code style="display:block;background:#1a1a2e;color:#0f0;padding:0.4rem 0.6rem;border-radius:4px;font-size:0.8rem;word-break:break-all;margin:0.25rem 0;">
                ${PROXY_API}/proxy/v1/chat/completions
            </code>
            <div><strong>上游:</strong> ${escapeHtml(truncate(task.upstream_url, 40))}</div>
            <div><strong>模型:</strong> ${escapeHtml(task.model || '(未设置)')}</div>
            <div><strong>输入审查:</strong> ${task.enable_input_audit ? '✅ 开' : '❌ 关'}</div>
            <div><strong>输出审查:</strong> ${task.enable_output_audit ? '✅ 开' : '❌ 关'}</div>
            <div><strong>拦截阈值:</strong> ${task.min_confidence}</div>
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
