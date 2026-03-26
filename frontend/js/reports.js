/**
 * 报告管理
 */

let reportCurrentPage = 1;
const reportPageSize = 20;

// 当前查看详情的任务ID（用于导出）
let _currentEvalTaskId = null;

// ========== 加载报告列表 ==========
async function loadReports() {
    const taskId = document.getElementById('report-filter-task')?.value || '';
    const params = new URLSearchParams({
        page: reportCurrentPage,
        page_size: reportPageSize,
    });
    if (taskId) params.append('task_id', taskId);

    try {
        const result = await API.request(`/evaluation/reports?${params}`);
        renderReportsTable(result.data, result.total);
    } catch (error) {
        showToast('加载报告列表失败: ' + error.message, 'error');
    }
}

// ========== 渲染报告表格 ==========
function renderReportsTable(reports, total) {
    const tbody = document.getElementById('reports-table-body');
    if (!reports || reports.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #999;">暂无报告</td></tr>';
        document.getElementById('reports-pagination').innerHTML = '';
        return;
    }

    tbody.innerHTML = reports.map(r => {
        const fmtBadge = r.report_format === 'html'
            ? '<span class="badge" style="background:#3498db;color:#fff;">HTML</span>'
            : '<span class="badge" style="background:#27ae60;color:#fff;">JSON</span>';
        const sizeStr = formatFileSize(r.file_size || 0);
        return `
            <tr>
                <td>${r.id}</td>
                <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                    title="${escapeHtml(r.report_name || '')}">${escapeHtml(r.report_name || '')}</td>
                <td>${escapeHtml(r.task_name || '-')}</td>
                <td>${fmtBadge}</td>
                <td>${sizeStr}</td>
                <td>${r.created_at || '-'}</td>
                <td>
                    <div style="display: flex; gap: 0.25rem;">
                        <button class="btn btn-sm btn-outline" onclick="previewReport(${r.id})" title="预览">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="downloadReport(${r.id})" title="下载">
                            <i class="fas fa-download"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteReport(${r.id})" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
    }).join('');

    // 分页
    const totalPages = Math.ceil(total / reportPageSize);
    const pagination = document.getElementById('reports-pagination');
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    let html = '';
    if (reportCurrentPage > 1) {
        html += `<button class="btn btn-sm btn-outline" onclick="reportGoPage(${reportCurrentPage - 1})">上一页</button>`;
    }
    html += `<span style="padding: 0 0.5rem; line-height: 2;">第 ${reportCurrentPage}/${totalPages} 页（共 ${total} 条）</span>`;
    if (reportCurrentPage < totalPages) {
        html += `<button class="btn btn-sm btn-outline" onclick="reportGoPage(${reportCurrentPage + 1})">下一页</button>`;
    }
    pagination.innerHTML = html;
}

function reportGoPage(page) {
    reportCurrentPage = page;
    loadReports();
}

// ========== 填充任务筛选下拉 ==========
async function populateReportTaskFilter() {
    try {
        const result = await API.request('/evaluation/tasks?page_size=100');
        const select = document.getElementById('report-filter-task');
        if (!select) return;
        const current = select.value;
        select.innerHTML = '<option value="">全部任务</option>';
        (result.data || []).forEach(t => {
            select.innerHTML += `<option value="${t.id}">${escapeHtml(t.task_name)}</option>`;
        });
        select.value = current;
    } catch (e) {
        // 静默失败
    }
}

// ========== 导出报告（从评估详情弹窗调用） ==========
async function exportEvalReport(format) {
    if (!_currentEvalTaskId) {
        showToast('无法确定任务ID', 'error');
        return;
    }
    try {
        const result = await API.request(`/evaluation/tasks/${_currentEvalTaskId}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format }),
        });
        showToast(`报告已生成：${result.data.report_name}`, 'success');
    } catch (error) {
        showToast('导出失败: ' + error.message, 'error');
    }
}

// ========== 预览报告 ==========
async function previewReport(reportId) {
    try {
        const result = await API.request(`/evaluation/reports/${reportId}`);
        const report = result.data;

        if (report.report_format === 'html') {
            const win = window.open('', '_blank');
            win.document.write(report.content);
            win.document.close();
        } else {
            // JSON 预览：在新窗口中格式化显示
            let parsed;
            try {
                parsed = JSON.parse(report.content);
            } catch (e) {
                parsed = report.content;
            }
            const win = window.open('', '_blank');
            win.document.write(`<!DOCTYPE html><html><head><title>${escapeHtml(report.report_name)}</title>
                <style>body{font-family:monospace;padding:1rem;white-space:pre-wrap;word-break:break-all;}</style>
                </head><body>${escapeHtml(JSON.stringify(parsed, null, 2))}</body></html>`);
            win.document.close();
        }
    } catch (error) {
        showToast('预览失败: ' + error.message, 'error');
    }
}

// ========== 下载报告 ==========
function downloadReport(reportId) {
    window.open(`${API_BASE}/evaluation/reports/${reportId}/download`, '_blank');
}

// ========== 删除报告 ==========
async function deleteReport(reportId) {
    if (!confirm('确定删除该报告？')) return;
    try {
        await API.request(`/evaluation/reports/${reportId}`, { method: 'DELETE' });
        showToast('报告已删除', 'success');
        loadReports();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

// ========== 工具函数 ==========
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
