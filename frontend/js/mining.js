/**
 * 智能挖掘模块前端逻辑
 * 4个生成工具：提示注入 / 投毒数据 / 对抗数据 / 越狱模板
 */

const MINING_API = API_BASE + '/mining';

// ==================== 页面初始化 ====================

function initMiningPage() {
    populateMiningModelSelect();
}

async function populateMiningModelSelect() {
    const select = document.getElementById('mining-model-select');
    if (!select) return;

    let options = '<option value="">-- 使用默认模型 --</option>';

    // 数据库模型
    try {
        const result = await API.getModels();
        const models = result.data || [];
        if (models.length > 0) {
            options += '<option disabled>── API 模型 ──</option>';
            options += models.map(m =>
                `<option value="${m.id}">${escapeHtml(m.name)} (${escapeHtml(m.model_id)})</option>`
            ).join('');
        }
    } catch (e) {}

    // Ollama 本地模型
    try {
        const ollamaResult = await API.getOllamaModels();
        const ollamaModels = ollamaResult.data || [];
        if (ollamaModels.length > 0) {
            options += '<option disabled>── Ollama 本地模型 ──</option>';
            options += ollamaModels.map(m =>
                `<option value="ollama:${escapeHtml(m.name)}">[本地] ${escapeHtml(m.name)} (${escapeHtml(m.size)})</option>`
            ).join('');
        }
    } catch (e) {}

    select.innerHTML = options;
}

// ==================== 标签页切换 ====================

function switchMiningTab(tabName) {
    // 隐藏所有 tab 内容
    document.querySelectorAll('.mining-tab-content').forEach(el => {
        el.style.display = 'none';
    });
    // 显示目标 tab
    const target = document.getElementById('mining-tab-' + tabName);
    if (target) target.style.display = '';

    // 更新标签样式
    document.querySelectorAll('#mining-tabs button').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.style.borderBottomColor = '#3498db';
            btn.style.fontWeight = '600';
            btn.style.color = '';
        } else {
            btn.style.borderBottomColor = 'transparent';
            btn.style.fontWeight = '';
            btn.style.color = '#888';
        }
    });
}

// ==================== 公共工具 ====================

function _getSelectedModel() {
    const select = document.getElementById('mining-model-select');
    return select ? select.value : '';
}

function _parseTextareaJson(textareaId) {
    const el = document.getElementById(textareaId);
    if (!el || !el.value.trim()) return [];
    const lines = el.value.trim().split('\n');
    const results = [];
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
            results.push(JSON.parse(trimmed));
        } catch (e) {
            // 非 JSON 行忽略
        }
    }
    return results;
}

function _setButtonLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (loading) {
        btn.disabled = true;
        btn._origHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    } else {
        btn.disabled = false;
        if (btn._origHTML) btn.innerHTML = btn._origHTML;
    }
}

function _showResult(html, summary) {
    const card = document.getElementById('mining-result-card');
    const content = document.getElementById('mining-result-content');
    const summaryEl = document.getElementById('mining-result-summary');
    if (card) card.hidden = false;
    if (content) content.innerHTML = html;
    if (summaryEl) summaryEl.textContent = summary || '';
    card.scrollIntoView({ behavior: 'smooth' });
}

// ==================== 文件上传到 textarea ====================

function loadFileToTextarea(fileInput, textareaId) {
    const file = fileInput.files[0];
    if (!file) return;

    const nameSpan = fileInput.parentElement.querySelector('span');
    if (nameSpan) nameSpan.textContent = file.name;

    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const textarea = document.getElementById(textareaId);
        if (!textarea) return;

        // 尝试解析 JSON 数组格式，转为每行一条
        try {
            const arr = JSON.parse(content);
            if (Array.isArray(arr)) {
                textarea.value = arr.map(item => JSON.stringify(item)).join('\n');
                showToast(`已加载 ${arr.length} 条数据`, 'success');
                return;
            }
        } catch (e) {}

        // 直接填入原始内容
        textarea.value = content;
        const lineCount = content.trim().split('\n').filter(l => l.trim()).length;
        showToast(`已加载文件，共 ${lineCount} 行`, 'success');
    };
    reader.onerror = function() {
        showToast('文件读取失败', 'error');
    };
    reader.readAsText(file);
}

// ==================== 1. 提示注入问题生成 ====================

async function generatePromptInjection() {
    const body = {
        model_id: _getSelectedModel(),
        modality: document.getElementById('injection-modality')?.value || 'text',
        attack_method: document.getElementById('injection-method')?.value || '',
        count: parseInt(document.getElementById('injection-count')?.value || '10'),
        keywords: document.getElementById('injection-keywords')?.value || '',
    };

    _setButtonLoading('btn-gen-injection', true);
    try {
        const resp = await fetch(MINING_API + '/prompt-injection/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '生成失败');

        const samples = result.data.samples || [];
        let html = `<div class="table-responsive"><table class="data-table">
            <thead><tr><th>#</th><th>攻击问题</th><th>攻击手段</th><th>难度</th><th>说明</th></tr></thead><tbody>`;
        samples.forEach((s, i) => {
            const diffColor = s.difficulty === 'hard' ? '#e74c3c' : s.difficulty === 'easy' ? '#27ae60' : '#f39c12';
            html += `<tr>
                <td>${i + 1}</td>
                <td style="max-width:400px;word-break:break-all;">${escapeHtml(s.text || '')}</td>
                <td>${escapeHtml(s.attack_method || '')}</td>
                <td><span style="color:${diffColor};font-weight:600;">${escapeHtml(s.difficulty || 'medium')}</span></td>
                <td style="color:#888;font-size:0.85rem;">${escapeHtml(s.description || '')}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';

        _showResult(html, result.message);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setButtonLoading('btn-gen-injection', false);
    }
}

// ==================== 2. 投毒数据生成 ====================

async function generatePoisonData() {
    const originalSamples = _parseTextareaJson('poison-upload-data');
    const body = {
        model_id: _getSelectedModel(),
        algorithm: document.getElementById('poison-gen-algorithm')?.value || 'label_flip',
        count: parseInt(document.getElementById('poison-gen-count')?.value || '10'),
        original_samples: originalSamples,
    };

    _setButtonLoading('btn-gen-poison', true);
    try {
        const resp = await fetch(MINING_API + '/poison/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '生成失败');

        const data = result.data;
        const samples = data.samples || [];

        // 统计卡片
        let html = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1rem;">
            <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
                <div style="font-size:1.5rem;font-weight:700;">${data.total}</div>
                <div style="color:#888;font-size:0.85rem;">总样本数</div>
            </div>
            <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
                <div style="font-size:1.5rem;font-weight:700;color:#e74c3c;">${data.poisoned_count}</div>
                <div style="color:#888;font-size:0.85rem;">投毒样本</div>
            </div>
            <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
                <div style="font-size:1.5rem;font-weight:700;color:#27ae60;">${data.clean_count}</div>
                <div style="color:#888;font-size:0.85rem;">干净样本</div>
            </div>
        </div>`;

        html += `<div class="table-responsive"><table class="data-table">
            <thead><tr><th>#</th><th>样本文本</th><th>标签</th><th>是否投毒</th><th>投毒类型</th><th>隐藏模式</th></tr></thead><tbody>`;
        samples.forEach((s, i) => {
            const poisonBadge = s.is_poisoned
                ? '<span style="color:#e74c3c;font-weight:600;">☠ 是</span>'
                : '<span style="color:#27ae60;">否</span>';
            html += `<tr style="${s.is_poisoned ? 'background:#fff5f5;' : ''}">
                <td>${i + 1}</td>
                <td style="max-width:300px;word-break:break-all;">${escapeHtml(s.text || '')}</td>
                <td>${escapeHtml(s.label || '')}</td>
                <td>${poisonBadge}</td>
                <td style="font-size:0.85rem;">${escapeHtml(s.poison_type || '-')}</td>
                <td style="font-size:0.85rem;color:#888;">${escapeHtml(s.hidden_pattern || '-')}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';

        _showResult(html, result.message);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setButtonLoading('btn-gen-poison', false);
    }
}

// ==================== 3. 对抗数据生成 ====================

async function generateAdversarialData() {
    const originalSamples = _parseTextareaJson('adversarial-upload-data');
    const body = {
        model_id: _getSelectedModel(),
        algorithm: document.getElementById('adversarial-algorithm')?.value || 'synonym_replace',
        perturbation_rate: parseFloat(document.getElementById('adversarial-rate')?.value || '0.3'),
        count: parseInt(document.getElementById('adversarial-count')?.value || '10'),
        original_samples: originalSamples,
    };

    _setButtonLoading('btn-gen-adversarial', true);
    try {
        const resp = await fetch(MINING_API + '/adversarial/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '生成失败');

        const samples = result.data.samples || [];
        let html = `<div class="table-responsive"><table class="data-table">
            <thead><tr><th>#</th><th>原始文本</th><th>→</th><th>对抗文本</th><th>扰动方式</th><th>相似度</th></tr></thead><tbody>`;
        samples.forEach((s, i) => {
            const sim = s.similarity ? (s.similarity * 100).toFixed(0) + '%' : '-';
            html += `<tr>
                <td>${i + 1}</td>
                <td style="max-width:250px;word-break:break-all;">${escapeHtml(s.original_text || '')}</td>
                <td style="color:#3498db;font-size:1.2rem;">→</td>
                <td style="max-width:250px;word-break:break-all;color:#e74c3c;">${escapeHtml(s.adversarial_text || '')}</td>
                <td style="font-size:0.85rem;">${escapeHtml(s.perturbation_type || '')}</td>
                <td>${sim}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';

        _showResult(html, result.message);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setButtonLoading('btn-gen-adversarial', false);
    }
}

// ==================== 4. 越狱模板生成 ====================

async function generateJailbreakTemplate() {
    const body = {
        model_id: _getSelectedModel(),
        algorithm: document.getElementById('jailbreak-algorithm')?.value || 'iterative_refine',
        rounds: parseInt(document.getElementById('jailbreak-rounds')?.value || '3'),
        initial_template: document.getElementById('jailbreak-initial')?.value || '',
    };

    _setButtonLoading('btn-gen-jailbreak', true);
    try {
        const resp = await fetch(MINING_API + '/jailbreak-template/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '生成失败');

        const templates = result.data.templates || [];
        let html = '';

        templates.forEach((t, i) => {
            const isLast = i === templates.length - 1;
            const borderColor = isLast ? '#27ae60' : '#e0e0e0';
            const badge = isLast ? '<span style="background:#27ae60;color:#fff;padding:0.15rem 0.5rem;border-radius:4px;font-size:0.75rem;margin-left:0.5rem;">最优</span>' : '';
            html += `<div style="border:2px solid ${borderColor};border-radius:8px;padding:1rem;margin-bottom:1rem;">
                <div style="font-weight:600;margin-bottom:0.5rem;">
                    第 ${t.round} 轮${badge}
                    <span style="color:#888;font-weight:400;font-size:0.85rem;margin-left:0.5rem;">${escapeHtml(t.improvement || '')}</span>
                </div>
                <pre style="background:#f8f9fa;padding:0.75rem;border-radius:4px;white-space:pre-wrap;word-break:break-all;font-size:0.85rem;max-height:200px;overflow-y:auto;">${escapeHtml(t.template || '')}</pre>
            </div>`;
        });

        _showResult(html, result.message);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setButtonLoading('btn-gen-jailbreak', false);
    }
}
