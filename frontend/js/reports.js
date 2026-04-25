/**
 * 日志审计 — 系统日志查看与导出
 */

const AUDIT_API = 'http://127.0.0.1:5001';
let _auditLogsCache = [];

// ========== 加载统计概览 ==========
async function loadAuditStats() {
    try {
        const resp = await fetch(`${AUDIT_API}/proxy/v1/logs/stats`);
        const data = await resp.json();
        if (data.success) {
            document.getElementById('audit-stat-total').textContent = data.total_requests || 0;
            document.getElementById('audit-stat-blocked').textContent = (data.blocked_input || 0) + (data.blocked_output || 0);
            document.getElementById('audit-stat-tokens').textContent = _formatNumber(data.total_tokens || 0);
            document.getElementById('audit-stat-latency').textContent = (data.avg_latency_ms || 0) + 'ms';
        }
    } catch (e) {
        console.error('加载统计失败:', e);
    }
}

// ========== 加载日志列表 ==========
async function loadAuditLogs() {
    const status = document.getElementById('audit-filter-status').value;
    const startDate = document.getElementById('audit-filter-start').value;
    const endDate = document.getElementById('audit-filter-end').value;
    const limit = parseInt(document.getElementById('audit-filter-limit').value) || 100;

    const params = new URLSearchParams({ limit });
    if (startDate) params.append('start', startDate + 'T00:00:00');
    if (endDate) params.append('end', endDate + 'T23:59:59');

    const tbody = document.getElementById('audit-logs-table');
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:2rem;"><i class="fas fa-spinner fa-spin"></i> 加载中...</td></tr>';

    try {
        const resp = await fetch(`${AUDIT_API}/proxy/v1/logs?${params}`);
        const data = await resp.json();
        if (!data.success || !data.logs) throw new Error('查询失败');

        let logs = data.logs;

        // 前端筛选状态
        if (status === 'blocked') {
            logs = logs.filter(l => l.input_audit_safe === 0 || l.output_audit_safe === 0);
        } else if (status === 'error') {
            logs = logs.filter(l => l.status_code >= 400);
        } else if (status === 'success') {
            logs = logs.filter(l => l.status_code >= 200 && l.status_code < 400 && l.input_audit_safe !== 0);
        }

        _auditLogsCache = logs;
        _renderAuditTable(logs);
        loadAuditStats();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#e74c3c;padding:2rem;">加载失败: ${escapeHtml(e.message)}</td></tr>`;
    }
}

function _renderAuditTable(logs) {
    const tbody = document.getElementById('audit-logs-table');
    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#999;padding:2rem;">无匹配日志</td></tr>';
        document.getElementById('audit-logs-count').textContent = '';
        return;
    }

    tbody.innerHTML = logs.map((log, idx) => {
        const time = (log.timestamp || '').replace('T', ' ').substring(0, 19);
        const sc = log.status_code || 0;
        const statusBadge = sc >= 200 && sc < 400
            ? `<span class="log-badge log-badge-ok">${sc}</span>`
            : sc === 403
                ? `<span class="log-badge log-badge-blocked">${sc} 拦截</span>`
                : `<span class="log-badge log-badge-error">${sc}</span>`;

        const inputBadge = log.input_audit_safe === 1
            ? '<span style="color:#27ae60;">✅安全</span>'
            : log.input_audit_safe === 0
                ? '<span style="color:#e74c3c;">🚫风险</span>'
                : '<span style="color:#999;">-</span>';

        const outputBadge = log.output_audit_safe === 1
            ? '<span style="color:#27ae60;">✅安全</span>'
            : log.output_audit_safe === 0
                ? '<span style="color:#e74c3c;">🚫风险</span>'
                : '<span style="color:#999;">-</span>';

        return `<tr style="cursor:pointer;" onclick="showLogDetail(_auditLogsCache[${idx}])">
            <td>${log.id || idx + 1}</td>
            <td style="white-space:nowrap;">${time}</td>
            <td>${escapeHtml(log.model || '-')}</td>
            <td>${statusBadge}</td>
            <td>${inputBadge}</td>
            <td>${outputBadge}</td>
            <td>${log.total_tokens || 0}</td>
            <td>${log.latency_ms || 0}ms</td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="event.stopPropagation();showLogDetail(_auditLogsCache[${idx}])" title="详情">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        </tr>`;
    }).join('');

    document.getElementById('audit-logs-count').textContent = `共 ${logs.length} 条日志`;
}

// ========== 导出日志 ==========
function exportAuditLogs(format) {
    if (!_auditLogsCache || _auditLogsCache.length === 0) {
        showToast('暂无日志数据，请先查询', 'warning');
        return;
    }

    const now = new Date().toISOString().slice(0, 10);

    if (format === 'json') {
        const blob = new Blob([JSON.stringify(_auditLogsCache, null, 2)], { type: 'application/json' });
        _downloadBlob(blob, `audit-logs-${now}.json`);
        showToast(`已导出 ${_auditLogsCache.length} 条日志 (JSON)`, 'success');
    } else if (format === 'csv') {
        const headers = ['id', 'timestamp', 'request_id', 'model', 'url', 'status_code',
            'latency_ms', 'total_tokens', 'prompt_tokens', 'completion_tokens',
            'input_audit_safe', 'input_audit_score', 'input_audit_reason',
            'output_audit_safe', 'output_audit_score', 'output_audit_reason',
            'client_ip', 'error'];
        const rows = _auditLogsCache.map(log =>
            headers.map(h => {
                let v = log[h];
                if (v === null || v === undefined) v = '';
                v = String(v).replace(/"/g, '""');
                return `"${v}"`;
            }).join(',')
        );
        const csv = '\uFEFF' + headers.join(',') + '\n' + rows.join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        _downloadBlob(blob, `audit-logs-${now}.csv`);
        showToast(`已导出 ${_auditLogsCache.length} 条日志 (CSV)`, 'success');
    }
}

function _downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ========== 工具函数 ==========
function _formatNumber(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}

// ========== 页面初始化 ==========
function initAuditPage() {
    loadAuditStats();
}
