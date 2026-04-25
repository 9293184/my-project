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
    loadProxyUsers();
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
            document.getElementById('proxy-judge-key').placeholder = data.config.judge_key_set ? '已设置（留空不修改）' : 'sk-xxxx...';
            document.getElementById('proxy-http-proxy').value = data.config.http_proxy || '';
            const badge = document.getElementById('proxy-engine-status');
            // 判断用户是否已配置过（key 未设置且使用默认地址视为未配置）
            const isDefault = !data.config.judge_key_set && data.config.judge_url && data.config.judge_url.includes('deepseek.com');
            if (isDefault) {
                badge.textContent = '待配置';
                badge.style.background = '#f39c12';
            } else {
                badge.textContent = '运行中';
                badge.style.background = '#27ae60';
            }
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
    const http_proxy = document.getElementById('proxy-http-proxy').value.trim();

    const body = {};
    if (judge_url) body.judge_url = judge_url;
    if (judge_model) body.judge_model = judge_model;
    if (judge_key) body.judge_key = judge_key;
    body.http_proxy = http_proxy;

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
            updateUserProxyFilter();
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
        const proxyAddr = `${window.location.origin}/proxy/${t.proxy_id}/v1`;
        const paused = t.paused;
        const statusBadge = paused
            ? '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">已暂停</span>'
            : '<span style="background:#27ae60;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">运行中</span>';
        const pauseBtn = paused
            ? `<button class="btn btn-sm" style="background:#27ae60;color:#fff;" onclick="togglePauseTask('${t.proxy_id}',false)" title="恢复"><i class="fas fa-play"></i></button>`
            : `<button class="btn btn-outline btn-sm" onclick="togglePauseTask('${t.proxy_id}',true)" title="暂停"><i class="fas fa-pause"></i></button>`;
        const rowStyle = paused ? 'opacity:0.6;' : '';
        return `<tr style="${rowStyle}">
            <td><code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:0.85rem;">${t.proxy_id}</code></td>
            <td>${escapeHtml(t.name)} ${statusBadge}</td>
            <td title="${escapeHtml(t.upstream_url)}" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(t.upstream_url)}</td>
            <td title="${proxyAddr}" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;color:var(--primary-color);"
                onclick="navigator.clipboard.writeText('${proxyAddr}');showToast('已复制','success')">
                <i class="fas fa-link" style="font-size:0.7rem;margin-right:2px;"></i>${proxyAddr}
            </td>
            <td><span style="color:${dirColor};font-weight:600;">${direction}</span> ${layers}</td>
            <td>${threshold}</td>
            <td style="white-space:nowrap;">
                ${pauseBtn}
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

function toggleHistoryDetail() {
    const enabled = document.getElementById('ac-history-enabled').checked;
    document.getElementById('ac-history-detail').style.display = enabled ? '' : 'none';
}

function copyProxyUrl() {
    const input = document.getElementById('task-proxy-url-display');
    navigator.clipboard.writeText(input.value).then(() => {
        showToast('代理地址已复制', 'success');
    }).catch(() => {
        input.select();
        document.execCommand('copy');
        showToast('代理地址已复制', 'success');
    });
}

function openTaskModal(task) {
    document.getElementById('task-edit-id').value = task ? task.proxy_id : '';
    document.getElementById('task-modal-title').textContent = task ? '编辑代理项目' : '新建代理项目';
    document.getElementById('task-name').value = task ? task.name : '';
    document.getElementById('task-upstream-url').value = task ? task.upstream_url : '';
    document.getElementById('task-model').value = task ? task.model : '';
    document.getElementById('task-security-prompt').value = task ? (task.security_prompt || '') : '';

    // 编辑模式下显示透明代理地址
    const proxyUrlGroup = document.getElementById('task-proxy-url-group');
    if (task && task.proxy_id) {
        const baseUrl = window.location.origin;
        document.getElementById('task-proxy-url-display').value = `${baseUrl}/proxy/${task.proxy_id}/v1`;
        proxyUrlGroup.style.display = '';
    } else {
        proxyUrlGroup.style.display = 'none';
    }

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

    // 加载对话历史配置
    const histCfg = (cfg && cfg.context_history) || {};
    const histEnabled = !!histCfg.enabled;
    document.getElementById('ac-history-enabled').checked = histEnabled;
    document.getElementById('ac-history-window').value = histCfg.window || 10;
    document.getElementById('ac-history-detail').style.display = histEnabled ? '' : 'none';

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
        context_history: {
            enabled: document.getElementById('ac-history-enabled').checked,
            window: parseInt(document.getElementById('ac-history-window').value) || 10,
        },
    };

    const body = {
        name,
        upstream_url,
        model: document.getElementById('task-model').value.trim(),
        security_prompt: document.getElementById('task-security-prompt').value.trim(),
        audit_config: auditConfig,
    };
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

// ─── 暂停/恢复代理 ──────────────────────────────────

async function togglePauseTask(proxyId, paused) {
    const action = paused ? '暂停' : '恢复';
    if (paused && !confirm(`确认暂停该代理项目？暂停后所有请求将被拒绝。`)) return;
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/tasks/${proxyId}/pause`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paused }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`代理已${action}`, 'success');
            loadProxyTasks();
        } else {
            showToast(data.error || `${action}失败`, 'error');
        }
    } catch (e) {
        showToast(`${action}失败: ` + e.message, 'error');
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
    const dir = ac.direction || 'both';
    const inputOn = dir === 'input' || dir === 'both';
    const outputOn = dir === 'output' || dir === 'both';
    info.innerHTML = `
        <div style="line-height:1.8;">
            <div><strong>代理号:</strong> <code>${task.proxy_id}</code></div>
            <div><strong>接入地址:</strong></div>
            <code style="display:block;background:#1a1a2e;color:#0f0;padding:0.4rem 0.6rem;border-radius:4px;font-size:0.8rem;word-break:break-all;margin:0.25rem 0;">
                ${PROXY_API}/proxy/${task.proxy_id}/v1/chat/completions
            </code>
            <div><strong>上游:</strong> ${escapeHtml(truncate(task.upstream_url, 40))}</div>
            <div><strong>模型:</strong> ${escapeHtml(task.model || '(未设置)')}</div>
            <div><strong>输入审查:</strong> ${inputOn ? '<span style="color:#27ae60;">✅ 开</span>' : '<span style="color:#e74c3c;">❌ 关</span>'}</div>
            <div><strong>输出审查:</strong> ${outputOn ? '<span style="color:#27ae60;">✅ 开</span>' : '<span style="color:#e74c3c;">❌ 关</span>'}</div>
            <div><strong>拦截阈值:</strong> ${ac.block_threshold || task.min_confidence || 60}</div>
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

// ─── 用户管理 ───────────────────────────────────────

let _proxyUsersCache = [];

function updateUserProxyFilter() {
    const select = document.getElementById('user-proxy-filter');
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">全部代理项目</option>' +
        proxyTasksCache.map(t =>
            `<option value="${t.proxy_id}">${escapeHtml(t.name)} (${t.proxy_id})</option>`
        ).join('');
    if (current) select.value = current;
}

async function loadProxyUsers() {
    const proxyId = document.getElementById('user-proxy-filter').value;
    const tbody = document.getElementById('proxy-users-table');
    if (!tbody) return;

    try {
        const url = proxyId
            ? `${PROXY_API}/proxy/v1/users?proxy_id=${proxyId}`
            : `${PROXY_API}/proxy/v1/users`;
        const resp = await fetch(url);
        const data = await resp.json();

        if (!data.success || !data.users || data.users.length === 0) {
            _proxyUsersCache = [];
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-secondary);">
                <i class="fas fa-users" style="font-size:1.5rem;margin-bottom:0.5rem;display:block;opacity:0.5;"></i>
                暂无用户记录</td></tr>`;
            return;
        }

        _proxyUsersCache = data.users;
        tbody.innerHTML = data.users.map((u, idx) => {
            const lastActive = u.last_active ? new Date(u.last_active).toLocaleString('zh-CN') : '-';
            const blockRate = u.total_requests > 0 ? ((u.blocked_count / u.total_requests) * 100).toFixed(1) : '0.0';
            const isBanned = u.banned;
            const statusBadge = isBanned
                ? '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">已封禁</span>'
                : '<span style="background:#27ae60;color:#fff;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">正常</span>';
            const rowBg = isBanned ? 'background:rgba(231,76,60,0.05);' : '';
            const blockRateColor = parseFloat(blockRate) > 20 ? '#e74c3c' : parseFloat(blockRate) > 5 ? '#f39c12' : '#27ae60';

            // 操作按钮
            const banBtn = isBanned
                ? `<button class="btn btn-sm" style="background:#27ae60;color:#fff;padding:2px 8px;font-size:0.75rem;" onclick="unbanProxyUser('${escapeHtml(u.user_id)}')" title="解封"><i class="fas fa-unlock"></i> 解封</button>`
                : `<button class="btn btn-danger btn-sm" style="padding:2px 8px;font-size:0.75rem;" onclick="banProxyUser('${escapeHtml(u.user_id)}')" title="封禁"><i class="fas fa-ban"></i> 封禁</button>`;
            const logBtn = `<button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:0.75rem;" onclick="viewUserLogs('${escapeHtml(u.user_id)}')" title="查看日志"><i class="fas fa-eye"></i></button>`;

            return `<tr style="${rowBg}">
                <td style="text-align:center;color:#999;font-size:0.8rem;">${idx + 1}</td>
                <td><code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:0.85rem;">${escapeHtml(u.user_id)}</code></td>
                <td style="text-align:right;font-family:monospace;">${u.total_requests}</td>
                <td style="text-align:right;font-family:monospace;"><span style="color:${blockRateColor};">${u.blocked_count}</span> <small style="color:#888;">(${blockRate}%)</small></td>
                <td style="text-align:right;font-family:monospace;">${(u.total_tokens || 0).toLocaleString()}</td>
                <td style="font-size:0.85rem;">${lastActive}</td>
                <td style="text-align:center;">${statusBadge}</td>
                <td style="text-align:center;white-space:nowrap;">${logBtn} ${banBtn}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#e74c3c;">加载失败: ${e.message}</td></tr>`;
    }
}

async function banProxyUser(userId) {
    const proxyId = document.getElementById('user-proxy-filter').value;
    if (!proxyId) {
        showToast('请先选择一个代理项目再执行封禁操作', 'warning');
        return;
    }
    if (!confirm(`确认封禁用户「${userId}」？封禁后该用户的所有请求将被拒绝。`)) return;
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/tasks/${proxyId}/ban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`用户 ${userId} 已封禁`, 'success');
            loadProxyUsers();
            loadProxyTasks();
        } else {
            showToast(data.error || '封禁失败', 'error');
        }
    } catch (e) {
        showToast('封禁失败: ' + e.message, 'error');
    }
}

async function unbanProxyUser(userId) {
    const proxyId = document.getElementById('user-proxy-filter').value;
    if (!proxyId) {
        showToast('请先选择一个代理项目再执行解封操作', 'warning');
        return;
    }
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/tasks/${proxyId}/unban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`用户 ${userId} 已解封`, 'success');
            loadProxyUsers();
            loadProxyTasks();
        } else {
            showToast(data.error || '解封失败', 'error');
        }
    } catch (e) {
        showToast('解封失败: ' + e.message, 'error');
    }
}

function viewUserLogs(userId) {
    // 滚动到日志区域并按用户过滤
    const logSection = document.getElementById('proxy-logs-container');
    if (logSection) logSection.scrollIntoView({ behavior: 'smooth' });
    // 加载该用户的日志
    _loadUserFilteredLogs(userId);
}

async function _loadUserFilteredLogs(userId) {
    const limit = parseInt(document.getElementById('proxy-log-limit').value) || 30;
    const tbody = document.getElementById('proxy-logs-table');
    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/logs?limit=${limit}&user_id=${encodeURIComponent(userId)}`);
        const data = await resp.json();
        if (!data.success || !data.logs || data.logs.length === 0) {
            _proxyLogsCache = [];
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--text-secondary);">
                用户「${escapeHtml(userId)}」暂无日志记录</td></tr>`;
            return;
        }
        _proxyLogsCache = data.logs;
        // 复用已有渲染逻辑
        _renderLogsTable(data.logs);
        showToast(`已筛选用户「${userId}」的日志`, 'info');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#e74c3c;">加载失败: ${e.message}</td></tr>`;
    }
}

function _renderLogsTable(logs) {
    const tbody = document.getElementById('proxy-logs-table');
    tbody.innerHTML = logs.map((log, idx) => {
        const time = log.timestamp ? new Date(log.timestamp).toLocaleString('zh-CN') : '-';
        const model = log.model || '-';
        const status = log.status_code || '-';
        const latency = log.latency_ms != null ? log.latency_ms + 'ms' : '-';
        const tokens = log.total_tokens || 0;
        const isBlocked = log.input_audit_safe === 0 || log.output_audit_safe === 0;
        const isError = status >= 400 || log.error;
        let statusHtml;
        if (isBlocked) {
            statusHtml = `<span class="log-badge log-badge-blocked">${status}</span>`;
        } else if (isError) {
            statusHtml = `<span class="log-badge log-badge-error">${status}</span>`;
        } else {
            statusHtml = `<span class="log-badge log-badge-ok">${status}</span>`;
        }
        const inputBadge = _auditBadge(log.input_audit_safe, log.input_audit_score);
        const outputBadge = _auditBadge(log.output_audit_safe, log.output_audit_score);
        const rowBg = isBlocked ? 'background:rgba(231,76,60,0.05);' : isError ? 'background:rgba(243,156,18,0.05);' : '';
        return `<tr style="cursor:pointer;${rowBg}" onclick="showLogDetail(${idx})" title="点击查看详情">
            <td style="text-align:center;color:#999;font-size:0.8rem;">${idx + 1}</td>
            <td style="white-space:nowrap;font-size:0.85rem;">${time}</td>
            <td style="font-size:0.9rem;">${model}</td>
            <td style="text-align:center;">${statusHtml}</td>
            <td style="text-align:right;font-family:monospace;font-size:0.85rem;">${latency}</td>
            <td style="text-align:right;font-family:monospace;font-size:0.85rem;">${tokens}</td>
            <td style="text-align:center;">${inputBadge}</td>
            <td style="text-align:center;">${outputBadge}</td>
            <td style="text-align:center;">
                <button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:0.75rem;" onclick="event.stopPropagation();showLogDetail(${idx})">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        </tr>`;
    }).join('');
}

// ─── 代理日志 ───────────────────────────────────────

let _proxyLogsCache = [];

async function loadProxyLogs() {
    const limit = parseInt(document.getElementById('proxy-log-limit').value) || 30;
    const statusFilter = document.getElementById('proxy-log-status-filter').value;
    const tbody = document.getElementById('proxy-logs-table');

    try {
        const resp = await fetch(`${PROXY_API}/proxy/v1/logs?limit=${limit}`);
        const data = await resp.json();

        if (!data.success || !data.logs || data.logs.length === 0) {
            _proxyLogsCache = [];
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:3rem;color:var(--text-secondary);">
                <i class="fas fa-inbox" style="font-size:2rem;margin-bottom:1rem;display:block;opacity:0.5;"></i>
                暂无代理日志</td></tr>`;
            return;
        }

        // 前端过滤
        let logs = data.logs;
        if (statusFilter === 'success') {
            logs = logs.filter(l => l.status_code >= 200 && l.status_code < 300 && l.input_audit_safe !== 0 && l.output_audit_safe !== 0);
        } else if (statusFilter === 'blocked') {
            logs = logs.filter(l => l.input_audit_safe === 0 || l.output_audit_safe === 0);
        } else if (statusFilter === 'error') {
            logs = logs.filter(l => l.status_code >= 400 || l.error);
        }

        _proxyLogsCache = logs;

        if (logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--text-secondary);">无匹配记录</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map((log, idx) => {
            const time = log.timestamp ? new Date(log.timestamp).toLocaleString('zh-CN') : '-';
            const model = log.model || '-';
            const status = log.status_code || '-';
            const latency = log.latency_ms != null ? log.latency_ms + 'ms' : '-';
            const tokens = log.total_tokens || 0;

            // 状态标签
            const isBlocked = log.input_audit_safe === 0 || log.output_audit_safe === 0;
            const isError = status >= 400 || log.error;
            let statusHtml;
            if (isBlocked) {
                statusHtml = `<span class="log-badge log-badge-blocked">${status}</span>`;
            } else if (isError) {
                statusHtml = `<span class="log-badge log-badge-error">${status}</span>`;
            } else {
                statusHtml = `<span class="log-badge log-badge-ok">${status}</span>`;
            }

            // 审查标签
            const inputBadge = _auditBadge(log.input_audit_safe, log.input_audit_score);
            const outputBadge = _auditBadge(log.output_audit_safe, log.output_audit_score);

            // 行背景色
            const rowBg = isBlocked ? 'background:rgba(231,76,60,0.05);' : isError ? 'background:rgba(243,156,18,0.05);' : '';

            return `<tr style="cursor:pointer;${rowBg}" onclick="showLogDetail(${idx})" title="点击查看详情">
                <td style="text-align:center;color:#999;font-size:0.8rem;">${idx + 1}</td>
                <td style="white-space:nowrap;font-size:0.85rem;">${time}</td>
                <td style="font-size:0.9rem;">${model}</td>
                <td style="text-align:center;">${statusHtml}</td>
                <td style="text-align:right;font-family:monospace;font-size:0.85rem;">${latency}</td>
                <td style="text-align:right;font-family:monospace;font-size:0.85rem;">${tokens}</td>
                <td style="text-align:center;">${inputBadge}</td>
                <td style="text-align:center;">${outputBadge}</td>
                <td style="text-align:center;">
                    <button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:0.75rem;" onclick="event.stopPropagation();showLogDetail(${idx})">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>`;
        }).join('');

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#e74c3c;">加载失败: ${e.message}</td></tr>`;
    }
}

function _auditBadge(safe, score) {
    if (safe === null || safe === undefined) return '<span style="color:#999;font-size:0.8rem;">-</span>';
    if (safe) return '<span style="color:#27ae60;font-size:0.85rem;"><i class="fas fa-check-circle"></i> 安全</span>';
    return `<span style="color:#e74c3c;font-size:0.85rem;"><i class="fas fa-times-circle"></i> ${score || 0}分</span>`;
}

// ─── 日志详情弹窗 ─────────────────────────────────

function showLogDetail(idx) {
    const log = _proxyLogsCache[idx];
    if (!log) return;

    // 基本信息
    document.getElementById('log-detail-id').textContent = `#${log.request_id || idx + 1}`;
    document.getElementById('ld-time').textContent = log.timestamp ? new Date(log.timestamp).toLocaleString('zh-CN') : '-';
    document.getElementById('ld-request-id').textContent = log.request_id || '-';
    document.getElementById('ld-url').textContent = log.url || '-';
    document.getElementById('ld-model').textContent = log.model || '-';

    const status = log.status_code || '-';
    const statusColor = status >= 200 && status < 300 ? '#27ae60' : status >= 400 ? '#e74c3c' : '#f39c12';
    document.getElementById('ld-status').innerHTML = `<span style="color:${statusColor};font-weight:600;">${status}</span>`;
    document.getElementById('ld-latency').textContent = log.latency_ms != null ? log.latency_ms + ' ms' : '-';

    const pt = log.prompt_tokens || 0, ct = log.completion_tokens || 0, tt = log.total_tokens || 0;
    document.getElementById('ld-tokens').textContent = tt > 0 ? `${tt} (输入${pt} + 输出${ct})` : '-';
    document.getElementById('ld-client-ip').textContent = log.client_ip || '-';

    // 审查结果
    document.getElementById('ld-input-audit').innerHTML = _auditDetailHtml(log.input_audit_safe, log.input_audit_score, log.input_audit_reason);
    document.getElementById('ld-output-audit').innerHTML = _auditDetailHtml(log.output_audit_safe, log.output_audit_score, log.output_audit_reason);

    // 请求/响应体
    const reqBody = _parseJsonField(log.request_body);
    const resBody = _parseJsonField(log.response_body);
    document.getElementById('ld-request-body').textContent = reqBody ? JSON.stringify(reqBody, null, 2) : '(无数据)';
    document.getElementById('ld-response-body').textContent = resBody ? JSON.stringify(resBody, null, 2) : '(无数据)';
    // 默认显示请求体
    toggleLogPanel('request');

    // 错误
    const errSection = document.getElementById('ld-error-section');
    if (log.error) {
        errSection.style.display = '';
        document.getElementById('ld-error').textContent = log.error;
    } else {
        errSection.style.display = 'none';
    }

    openModal('log-detail-modal');
}

function _auditDetailHtml(safe, score, reason) {
    if (safe === null || safe === undefined) return '<span style="color:#999;">未执行审查</span>';
    const color = safe ? '#27ae60' : '#e74c3c';
    const icon = safe ? 'check-circle' : 'times-circle';
    const label = safe ? '安全' : '风险';
    let html = `<div style="margin-bottom:0.25rem;"><i class="fas fa-${icon}" style="color:${color};"></i> <strong style="color:${color};">${label}</strong>`;
    if (score != null) html += ` <span style="color:#888;">(${score}分)</span>`;
    html += '</div>';
    if (reason) html += `<div style="font-size:0.85rem;color:#ccc;line-height:1.4;">${escapeHtml(reason)}</div>`;
    return html;
}

function _parseJsonField(val) {
    if (!val) return null;
    if (typeof val === 'object') return val;
    try { return JSON.parse(val); } catch { return val; }
}

function toggleLogPanel(panel) {
    const reqEl = document.getElementById('ld-request-body');
    const resEl = document.getElementById('ld-response-body');
    const btnReq = document.getElementById('ld-btn-request');
    const btnRes = document.getElementById('ld-btn-response');
    if (panel === 'request') {
        reqEl.style.display = '';
        resEl.style.display = 'none';
        btnReq.style.fontWeight = '600';
        btnRes.style.fontWeight = '';
    } else {
        reqEl.style.display = 'none';
        resEl.style.display = '';
        btnReq.style.fontWeight = '';
        btnRes.style.fontWeight = '600';
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
