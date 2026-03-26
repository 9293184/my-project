/**
 * 安全评估任务管理
 */

let evalCurrentPage = 1;
const evalPageSize = 20;

const EVAL_TYPE_LABELS = {
    comprehensive: '综合评估',
    prompt_injection: '提示注入',
    jailbreak: '越狱攻击',
    adversarial: '对抗评估',
    poison_detection: '投毒检测',
};

const EVAL_STATUS_LABELS = {
    pending: '待执行',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
};

const EVAL_STATUS_COLORS = {
    pending: '#95a5a6',
    running: '#3498db',
    completed: '#27ae60',
    failed: '#e74c3c',
    cancelled: '#f39c12',
};

// ========== 加载任务列表 ==========
async function loadEvalTasks(page) {
    if (page) evalCurrentPage = page;

    const taskType = document.getElementById('eval-filter-type').value;
    const status = document.getElementById('eval-filter-status').value;

    const params = new URLSearchParams({
        page: evalCurrentPage,
        page_size: evalPageSize,
    });
    if (taskType) params.append('task_type', taskType);
    if (status) params.append('status', status);

    try {
        const result = await API.request(`/evaluation/tasks?${params}`);
        const { tasks, total } = result.data;

        document.getElementById('eval-task-count').textContent = `${total} 个任务`;

        const tbody = document.getElementById('eval-tasks-table');
        if (!tasks || tasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                        <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 1rem; display: block; opacity: 0.5;"></i>
                        暂无评估任务，点击上方按钮创建
                    </td>
                </tr>`;
            document.getElementById('eval-pagination').style.display = 'none';
            return;
        }

        tbody.innerHTML = tasks.map(t => `
            <tr>
                <td>${t.id}</td>
                <td><strong>${escapeHtml(t.task_name)}</strong></td>
                <td><span class="badge" style="background: #8e44ad; color: #fff;">${EVAL_TYPE_LABELS[t.task_type] || t.task_type}</span></td>
                <td>${t.model_name || '-'}</td>
                <td><span class="badge" style="background: ${EVAL_STATUS_COLORS[t.status] || '#999'}; color: #fff;">${EVAL_STATUS_LABELS[t.status] || t.status}</span></td>
                <td>${t.total_samples || 0}</td>
                <td>${t.risk_score != null ? renderRiskBadge(t.risk_score) : '-'}</td>
                <td>${t.created_at || '-'}</td>
                <td>
                    <div style="display: flex; gap: 0.25rem; flex-wrap: wrap;">
                        <button class="btn btn-sm btn-outline btn-icon" onclick="viewEvalTask(${t.id})" title="查看详情">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${t.status === 'pending' ? `
                            <button class="btn btn-sm btn-primary btn-icon" onclick="runEvalTask(${t.id})" title="执行">
                                <i class="fas fa-play"></i>
                            </button>` : ''}
                        ${t.status === 'running' ? `
                            <button class="btn btn-sm btn-danger btn-icon" onclick="stopEvalTask(${t.id})" title="停止">
                                <i class="fas fa-stop"></i>
                            </button>` : ''}
                        ${t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled' ? `
                            <button class="btn btn-sm btn-outline btn-icon" onclick="rerunEvalTask(${t.id})" title="重新评估">
                                <i class="fas fa-redo"></i>
                            </button>` : ''}
                        <button class="btn btn-sm btn-outline btn-icon" onclick="viewTaskLogs(${t.id})" title="运行日志">
                            <i class="fas fa-file-alt"></i>
                        </button>
                        <button class="btn btn-sm btn-outline btn-icon" onclick="copyEvalTask(${t.id})" title="复制">
                            <i class="fas fa-copy"></i>
                        </button>
                        ${t.status !== 'running' ? `
                            <button class="btn btn-sm btn-danger btn-icon" onclick="deleteEvalTask(${t.id})" title="删除">
                                <i class="fas fa-trash"></i>
                            </button>` : ''}
                    </div>
                </td>
            </tr>
        `).join('');

        // 分页
        const totalPages = Math.ceil(total / evalPageSize);
        if (totalPages > 1) {
            document.getElementById('eval-pagination').style.display = 'flex';
            document.getElementById('eval-page-info').textContent = `第 ${evalCurrentPage} / ${totalPages} 页`;
        } else {
            document.getElementById('eval-pagination').style.display = 'none';
        }

    } catch (error) {
        showToast('加载评估任务失败: ' + error.message, 'error');
    }
}

function evalGoToPage(page) {
    if (page < 1) return;
    loadEvalTasks(page);
}

// ========== 风险评分徽章 ==========
function renderRiskBadge(score) {
    let color = '#27ae60';
    if (score >= 60) color = '#e74c3c';
    else if (score >= 30) color = '#f39c12';
    return `<span class="badge" style="background: ${color}; color: #fff;">${score}</span>`;
}

// ========== 填充模型下拉 ==========
async function populateEvalModelSelect() {
    const select = document.getElementById('eval-model-select');
    if (!select) return;

    try {
        const result = await API.getModels();
        const models = result.data || [];
        const dbOptions = models.map(m => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join('');

        let ollamaOptions = '';
        let hfOptions = '';
        try {
            const [ollamaResult, localResult] = await Promise.allSettled([
                API.getOllamaModels(),
                API.getLocalModels(),
            ]);
            const ollamaModels = ollamaResult.status === 'fulfilled' ? (ollamaResult.value.data || []) : [];
            const localModels = localResult.status === 'fulfilled' ? (localResult.value.data || []) : [];

            if (ollamaModels.length > 0) {
                ollamaOptions = '<option disabled>── Ollama 模型 ──</option>' +
                    ollamaModels.map(m => `<option value="ollama:${escapeHtml(m.name)}">[Ollama] ${escapeHtml(m.name)} (${escapeHtml(m.size)})</option>`).join('');
            }
            if (localModels.length > 0) {
                hfOptions = '<option disabled>── HuggingFace 本地模型 ──</option>' +
                    localModels.map(m => `<option value="hf:${escapeHtml(m.name)}">[HF本地] ${escapeHtml(m.name)} (${escapeHtml(m.parameters || m.size)})</option>`).join('');
            }
        } catch (e) {}

        select.innerHTML = '<option value="">-- 不指定 --</option>' + dbOptions + ollamaOptions + hfOptions;
    } catch (e) {
        console.error('加载模型列表失败', e);
    }
}

// ========== 创建任务 ==========
function openCreateEvalModal() {
    document.getElementById('eval-task-name').value = '';
    document.getElementById('eval-task-type').value = 'comprehensive';
    document.getElementById('eval-samples-per-type').value = '20';
    document.getElementById('eval-auto-run').value = 'yes';
    const customQ = document.getElementById('eval-custom-questions');
    if (customQ) customQ.value = '';
    const dimContainer = document.getElementById('eval-custom-dimensions');
    if (dimContainer) dimContainer.querySelectorAll('.custom-dim-row').forEach(r => r.remove());
    populateEvalModelSelect();
    openModal('create-eval-modal');
}

function addCustomDimension() {
    const container = document.getElementById('eval-custom-dimensions');
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:0.5rem;margin-bottom:0.5rem;align-items:center;';
    row.className = 'custom-dim-row';
    row.innerHTML = `
        <input type="text" class="form-control dim-name" placeholder="如: bias_detection" style="flex:1;">
        <input type="text" class="form-control dim-label" placeholder="如: 偏见检测" style="flex:1;">
        <button class="btn btn-sm btn-danger btn-icon" onclick="this.parentElement.remove()" style="width:2rem;height:2rem;padding:0;"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(row);
}

function _parseCustomQuestions() {
    const el = document.getElementById('eval-custom-questions');
    if (!el || !el.value.trim()) return null;
    const lines = el.value.trim().split('\n');
    const results = [];
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
            results.push(JSON.parse(trimmed));
        } catch (e) {
            results.push(trimmed);
        }
    }
    return results.length > 0 ? results : null;
}

function _parseCustomDimensions() {
    const rows = document.querySelectorAll('#eval-custom-dimensions .custom-dim-row');
    const dims = [];
    rows.forEach(row => {
        const name = row.querySelector('.dim-name')?.value.trim();
        const label = row.querySelector('.dim-label')?.value.trim();
        if (name && label) dims.push({ name, label });
    });
    return dims.length > 0 ? dims : null;
}

async function createEvalTask() {
    const taskName = document.getElementById('eval-task-name').value.trim();
    const taskType = document.getElementById('eval-task-type').value;
    const modelId = document.getElementById('eval-model-select').value;
    const samplesPerType = parseInt(document.getElementById('eval-samples-per-type').value) || 20;
    const autoRun = document.getElementById('eval-auto-run').value === 'yes';

    if (!taskName) {
        showToast('请输入任务名称', 'error');
        return;
    }

    const customQuestions = _parseCustomQuestions();
    const customDimensions = _parseCustomDimensions();

    const config = { samples_per_type: samplesPerType };
    if (customQuestions) config.custom_questions = customQuestions;
    if (customDimensions) config.custom_dimensions = customDimensions;

    try {
        const result = await API.request('/evaluation/tasks', {
            method: 'POST',
            body: JSON.stringify({
                task_name: taskName,
                task_type: taskType,
                model_id: modelId || null,
                config: config,
            }),
        });

        showToast('任务创建成功', 'success');
        closeModal('create-eval-modal');

        const newId = result.data.id;

        // 自动执行
        if (autoRun) {
            await runEvalTask(newId);
        }

        loadEvalTasks();
    } catch (error) {
        showToast('创建失败: ' + error.message, 'error');
    }
}

// ========== 执行 / 停止 / 重新评估 / 复制 / 删除 ==========
async function runEvalTask(taskId) {
    try {
        await API.request(`/evaluation/tasks/${taskId}/run`, { method: 'POST' });
        showToast('任务已启动', 'success');
        loadEvalTasks();
        // 自动刷新
        setTimeout(() => loadEvalTasks(), 3000);
        setTimeout(() => loadEvalTasks(), 8000);
        setTimeout(() => loadEvalTasks(), 15000);
        setTimeout(() => loadEvalTasks(), 30000);
    } catch (error) {
        showToast('启动失败: ' + error.message, 'error');
    }
}

async function stopEvalTask(taskId) {
    try {
        await API.request(`/evaluation/tasks/${taskId}/stop`, { method: 'POST' });
        showToast('已发送停止信号', 'success');
        setTimeout(() => loadEvalTasks(), 2000);
    } catch (error) {
        showToast('停止失败: ' + error.message, 'error');
    }
}

async function rerunEvalTask(taskId) {
    if (!confirm('确定要重新评估此任务吗？原有结果将被清除。')) return;
    try {
        await API.request(`/evaluation/tasks/${taskId}/rerun`, { method: 'POST' });
        showToast('任务已重新启动', 'success');
        loadEvalTasks();
        setTimeout(() => loadEvalTasks(), 3000);
        setTimeout(() => loadEvalTasks(), 10000);
        setTimeout(() => loadEvalTasks(), 30000);
    } catch (error) {
        showToast('重新评估失败: ' + error.message, 'error');
    }
}

async function copyEvalTask(taskId) {
    try {
        await API.request(`/evaluation/tasks/${taskId}/copy`, { method: 'POST' });
        showToast('任务已复制', 'success');
        loadEvalTasks();
    } catch (error) {
        showToast('复制失败: ' + error.message, 'error');
    }
}

async function deleteEvalTask(taskId) {
    if (!confirm('确定要删除此评估任务吗？')) return;
    try {
        await API.request(`/evaluation/tasks/${taskId}`, { method: 'DELETE' });
        showToast('任务已删除', 'success');
        loadEvalTasks();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

// ========== 查看详情 ==========
async function viewEvalTask(taskId) {
    try {
        const result = await API.request(`/evaluation/tasks/${taskId}`);
        const task = result.data;

        // 记录当前任务ID，供导出使用
        _currentEvalTaskId = task.id;

        document.getElementById('eval-detail-name').textContent = task.task_name;
        document.getElementById('eval-detail-type').textContent = EVAL_TYPE_LABELS[task.task_type] || task.task_type;
        document.getElementById('eval-detail-model').textContent = task.model_name || '未指定';
        document.getElementById('eval-detail-status').textContent = EVAL_STATUS_LABELS[task.status] || task.status;
        document.getElementById('eval-detail-status').style.background = EVAL_STATUS_COLORS[task.status] || '#999';
        document.getElementById('eval-detail-status').style.color = '#fff';
        document.getElementById('eval-detail-risk').innerHTML = task.risk_score != null ? renderRiskBadge(task.risk_score) : '-';
        document.getElementById('eval-detail-summary').textContent = task.summary || '-';
        document.getElementById('eval-detail-created').textContent = task.created_at || '-';
        document.getElementById('eval-detail-completed').textContent = task.completed_at || '-';

        // 导出按钮：仅已完成的任务可导出
        const isCompleted = task.status === 'completed';
        document.getElementById('eval-export-json-btn').hidden = !isCompleted;
        document.getElementById('eval-export-html-btn').hidden = !isCompleted;

        const metricsSection = document.getElementById('eval-detail-metrics-section');
        const dimensionsSection = document.getElementById('eval-detail-dimensions-section');
        const resultSection = document.getElementById('eval-detail-result-section');
        const resultTable = document.getElementById('eval-detail-result-table');

        metricsSection.hidden = true;
        dimensionsSection.hidden = true;
        resultSection.hidden = true;

        if (task.result && task.result.summary_metrics) {
            // ===== 汇总指标 =====
            const m = task.result.summary_metrics;
            metricsSection.hidden = false;
            document.getElementById('eval-detail-metrics').innerHTML = `
                <div class="stat-card">
                    <div class="stat-icon green"><i class="fas fa-shield-alt"></i></div>
                    <div class="stat-info">
                        <h3>防御成功率</h3>
                        <p class="stat-number">${m.defense_rate}%</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon orange"><i class="fas fa-eye-slash"></i></div>
                    <div class="stat-info">
                        <h3>漏杀率</h3>
                        <p class="stat-number">${m.miss_rate}%</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon purple"><i class="fas fa-ban"></i></div>
                    <div class="stat-info">
                        <h3>误杀率</h3>
                        <p class="stat-number">${m.false_reject_rate}%</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon ${m.risk_score < 30 ? 'green' : m.risk_score < 60 ? 'orange' : 'blue'}">
                        <i class="fas fa-exclamation-circle"></i>
                    </div>
                    <div class="stat-info">
                        <h3>综合风险</h3>
                        <p class="stat-number">${m.risk_score}</p>
                    </div>
                </div>
            `;
        }

        if (task.result && task.result.dimensions) {
            // ===== 多维度评分 =====
            dimensionsSection.hidden = false;
            const dims = task.result.dimensions;
            let dimHtml = '<div style="display: flex; flex-direction: column; gap: 0.75rem;">';

            for (const [key, dim] of Object.entries(dims)) {
                const barColor = dim.score >= 80 ? '#27ae60' :
                                 dim.score >= 60 ? '#f39c12' : '#e74c3c';
                dimHtml += `
                    <div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                            <span style="font-weight: 600;">${escapeHtml(dim.label)}</span>
                            <span>${dim.correct}/${dim.total}
                                <strong style="color: ${barColor}; margin-left: 0.5rem;">${dim.score}%</strong>
                            </span>
                        </div>
                        <div style="background: #e9ecef; border-radius: 4px; height: 20px; overflow: hidden;">
                            <div style="background: ${barColor}; height: 100%; width: ${dim.score}%; border-radius: 4px; transition: width 0.5s;"></div>
                        </div>
                    </div>`;
            }
            dimHtml += '</div>';
            document.getElementById('eval-detail-dimensions').innerHTML = dimHtml;
        }

        if (task.result && task.result.details && task.result.details.length > 0) {
            // ===== 详细结果表格 =====
            resultSection.hidden = false;
            resultTable.innerHTML = task.result.details.map((d, i) => {
                let verdict = '';
                if (d.is_attack && d.detected) {
                    verdict = '<span style="color:#27ae60;">✓ 正确拦截</span>';
                } else if (d.is_attack && !d.detected) {
                    verdict = '<span style="color:#e74c3c;">✗ 漏杀</span>';
                } else if (!d.is_attack && !d.detected) {
                    verdict = '<span style="color:#27ae60;">✓ 正确放行</span>';
                } else {
                    verdict = '<span style="color:#f39c12;">⚠ 误杀</span>';
                }
                return `
                    <tr>
                        <td>${d.index != null ? d.index + 1 : i + 1}</td>
                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                            title="${escapeHtml(d.text || '')}">${escapeHtml(d.text || '')}</td>
                        <td>${EVAL_TYPE_LABELS[d.attack_type] || d.attack_type || '-'}</td>
                        <td>${d.is_attack ? '<span style="color:#e74c3c;">攻击</span>' : '正常'}</td>
                        <td>${d.detected ? '<span style="color:#e74c3c;">拦截</span>' : '<span style="color:#27ae60;">放行</span>'}</td>
                        <td>${verdict}</td>
                    </tr>`;
            }).join('');
        } else if (task.result && task.result.suspicious_samples) {
            // 投毒检测结果
            resultSection.hidden = false;
            resultTable.innerHTML = task.result.suspicious_samples.map((s, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(s.text || '')}</td>
                    <td>${s.original_label || '-'}</td>
                    <td>-</td>
                    <td><span style="color:#e74c3c;">${s.risk_level || '-'}</span></td>
                    <td>${(s.issues || []).join('; ')}</td>
                </tr>
            `).join('');
        }

        openModal('eval-detail-modal');
    } catch (error) {
        showToast('获取详情失败: ' + error.message, 'error');
    }
}

// ========== 风险评估报告 ==========

async function openRiskAssessmentModal() {
    // 获取已完成的任务列表
    try {
        const result = await API.request('/evaluation/tasks?status=completed&page_size=100');
        const tasks = (result.data?.tasks || []);

        if (tasks.length === 0) {
            showToast('暂无已完成的评估任务，请先执行评估', 'error');
            return;
        }

        let checkboxes = tasks.map(t =>
            `<label style="display:flex;align-items:center;gap:0.5rem;padding:0.35rem 0;cursor:pointer;">
                <input type="checkbox" class="risk-task-check" value="${t.id}" checked>
                <span>#${t.id} ${escapeHtml(t.task_name)}</span>
                <span style="color:#888;font-size:0.8rem;">(${EVAL_TYPE_LABELS[t.task_type] || t.task_type})</span>
            </label>`
        ).join('');

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `
            <div class="modal" style="max-width:600px;">
                <div class="modal-header">
                    <h2><i class="fas fa-file-medical-alt"></i> 生成风险评估报告</h2>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>选择评估任务（可多选）</label>
                        <div style="max-height:200px;overflow-y:auto;border:1px solid #e0e0e0;border-radius:4px;padding:0.5rem;">
                            ${checkboxes}
                        </div>
                    </div>
                    <div class="form-group">
                        <label>输出格式</label>
                        <select id="risk-format" class="form-control" style="max-width:200px;">
                            <option value="json">JSON 数据</option>
                            <option value="html" selected>HTML 报告</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">取消</button>
                    <button class="btn btn-primary" onclick="generateRiskAssessment(this)">
                        <i class="fas fa-file-export"></i> 生成报告
                    </button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
    } catch (e) {
        showToast('加载任务列表失败: ' + e.message, 'error');
    }
}

async function generateRiskAssessment(btn) {
    const overlay = btn.closest('.modal-overlay');
    const checks = overlay.querySelectorAll('.risk-task-check:checked');
    const taskIds = Array.from(checks).map(c => parseInt(c.value));

    if (taskIds.length === 0) {
        showToast('请至少选择一个任务', 'error');
        return;
    }

    const fmt = overlay.querySelector('#risk-format')?.value || 'html';

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';

    try {
        const result = await API.request('/evaluation/risk-assessment/generate', {
            method: 'POST',
            body: JSON.stringify({ task_ids: taskIds, format: fmt }),
        });

        overlay.remove();

        if (fmt === 'html' && result.data?.content) {
            // 在新窗口打开 HTML 报告
            const win = window.open('', '_blank');
            win.document.write(result.data.content);
            win.document.close();
            showToast('风险评估报告已在新窗口打开', 'success');
        } else {
            // JSON 格式，弹窗展示
            const jsonStr = JSON.stringify(result.data, null, 2);
            const viewOverlay = document.createElement('div');
            viewOverlay.className = 'modal-overlay active';
            viewOverlay.onclick = (e) => { if (e.target === viewOverlay) viewOverlay.remove(); };
            viewOverlay.innerHTML = `
                <div class="modal" style="max-width:800px;">
                    <div class="modal-header">
                        <h2><i class="fas fa-file-medical-alt"></i> 风险评估报告</h2>
                        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <pre style="max-height:500px;overflow:auto;background:#f8f9fa;padding:1rem;border-radius:4px;font-size:0.8rem;">${escapeHtml(jsonStr)}</pre>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">关闭</button>
                    </div>
                </div>`;
            document.body.appendChild(viewOverlay);
        }
    } catch (e) {
        showToast('生成报告失败: ' + e.message, 'error');
    }
}

// ========== 查看任务运行日志 ==========
async function viewTaskLogs(taskId) {
    try {
        const result = await API.request(`/evaluation/tasks/${taskId}/logs`);
        const logs = result.data || [];

        const levelColors = { info: '#3498db', warn: '#f39c12', error: '#e74c3c' };
        const levelIcons = { info: 'info-circle', warn: 'exclamation-triangle', error: 'times-circle' };

        let html;
        if (logs.length === 0) {
            html = '<div style="text-align:center;padding:2rem;color:#888;"><i class="fas fa-inbox" style="font-size:2rem;display:block;margin-bottom:0.5rem;opacity:0.5;"></i>暂无运行日志（任务尚未执行或日志表未创建）</div>';
        } else {
            html = '<div style="max-height:400px;overflow-y:auto;font-family:monospace;font-size:0.85rem;">';
            logs.forEach(log => {
                const color = levelColors[log.level] || '#888';
                const icon = levelIcons[log.level] || 'info-circle';
                const time = log.created_at ? log.created_at.split(' ')[1] || log.created_at : '';
                html += `<div style="padding:0.35rem 0.5rem;border-bottom:1px solid #f0f0f0;display:flex;gap:0.5rem;align-items:flex-start;">
                    <span style="color:${color};min-width:1rem;"><i class="fas fa-${icon}"></i></span>
                    <span style="color:#888;min-width:60px;flex-shrink:0;">${escapeHtml(time)}</span>
                    <span>${escapeHtml(log.message)}</span>
                </div>`;
            });
            html += '</div>';
        }

        // 使用通用弹窗
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `
            <div class="modal" style="max-width:700px;">
                <div class="modal-header">
                    <h2><i class="fas fa-file-alt"></i> 任务 #${taskId} 运行日志</h2>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
                </div>
                <div class="modal-body" style="padding:0;">
                    ${html}
                </div>
                <div class="modal-footer">
                    <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">关闭</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
    } catch (error) {
        showToast('获取日志失败: ' + error.message, 'error');
    }
}
