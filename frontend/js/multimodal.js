/**
 * 多模态安全防护前端逻辑
 * 图片内容安全检测 / 图文组合攻击检测
 */

const MM_API = API_BASE + '/multimodal';

// ==================== 图片预览 ====================

document.addEventListener('DOMContentLoaded', () => {
    const imageFile = document.getElementById('mm-image-file');
    if (imageFile) {
        imageFile.addEventListener('change', () => {
            _previewImage(imageFile, 'mm-image-preview', 'mm-image-preview-img');
        });
    }
    const combinedImage = document.getElementById('mm-combined-image');
    if (combinedImage) {
        combinedImage.addEventListener('change', () => {
            _previewImage(combinedImage, 'mm-combined-preview', 'mm-combined-preview-img');
        });
    }
});

function _previewImage(fileInput, containerId, imgId) {
    const file = fileInput.files[0];
    const container = document.getElementById(containerId);
    const img = document.getElementById(imgId);
    if (!file || !container || !img) {
        if (container) container.style.display = 'none';
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        img.src = e.target.result;
        container.style.display = '';
    };
    reader.readAsDataURL(file);
}

function _fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function _setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (loading) {
        btn.disabled = true;
        btn._origHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检测中...';
    } else {
        btn.disabled = false;
        if (btn._origHTML) btn.innerHTML = btn._origHTML;
    }
}

function _showMMResult(html, summary) {
    const card = document.getElementById('mm-result-card');
    const content = document.getElementById('mm-result-content');
    const summaryEl = document.getElementById('mm-result-summary');
    if (card) card.hidden = false;
    if (content) content.innerHTML = html;
    if (summaryEl) summaryEl.textContent = summary || '';
    card.scrollIntoView({ behavior: 'smooth' });
}

// ==================== 1. 图片内容安全检测 ====================

async function checkImageSafety() {
    const fileInput = document.getElementById('mm-image-file');
    if (!fileInput || !fileInput.files[0]) {
        showToast('请先选择图片', 'error');
        return;
    }

    _setLoading('btn-mm-image-check', true);
    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const resp = await fetch(MM_API + '/image-safety', {
            method: 'POST',
            body: formData,
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '检测失败');

        renderImageSafetyResult(result.data);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setLoading('btn-mm-image-check', false);
    }
}

function renderImageSafetyResult(data) {
    const safeColor = data.safe ? '#27ae60' : '#e74c3c';
    const safeText = data.safe ? '安全' : '存在风险';
    const scoreColor = data.risk_score < 30 ? '#27ae60' : data.risk_score < 60 ? '#f39c12' : '#e74c3c';

    let riskTypesHtml = '';
    if (data.risk_types && data.risk_types.length > 0) {
        riskTypesHtml = data.risk_types.map(t =>
            `<span style="display:inline-block;background:#fff5f5;color:#e74c3c;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.85rem;margin:0.15rem;">${escapeHtml(t)}</span>`
        ).join('');
    } else {
        riskTypesHtml = '<span style="color:#27ae60;">未检测到风险类型</span>';
    }

    let html = `
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.5rem;">
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:${safeColor};">${safeText}</div>
            <div style="color:#888;font-size:0.85rem;">安全判定</div>
        </div>
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:${scoreColor};">${data.risk_score}</div>
            <div style="color:#888;font-size:0.85rem;">风险评分</div>
        </div>
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;">${(data.risk_types || []).length}</div>
            <div style="color:#888;font-size:0.85rem;">风险类型数</div>
        </div>
    </div>

    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-tags" style="color:#3498db;"></i> 风险类型</h3>
        <div>${riskTypesHtml}</div>
    </div>

    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-eye" style="color:#3498db;"></i> 图片描述</h3>
        <div style="background:#f8f9fa;padding:0.75rem;border-radius:8px;font-size:0.9rem;">${escapeHtml(data.description || '-')}</div>
    </div>`;

    if (data.text_extracted) {
        html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-font" style="color:#f39c12;"></i> 提取的文字</h3>
        <div style="background:#fff8e1;padding:0.75rem;border-radius:8px;font-size:0.9rem;">${escapeHtml(data.text_extracted)}</div>
    </div>`;
    }

    html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-comment-alt" style="color:#e74c3c;"></i> 分析详情</h3>
        <div style="background:${data.safe ? '#f0fff4' : '#fff5f5'};padding:0.75rem;border-radius:8px;font-size:0.9rem;border-left:4px solid ${safeColor};">
            ${escapeHtml(data.reason || '无')}
        </div>
    </div>

    <div style="color:#888;font-size:0.8rem;">
        视觉模型: ${escapeHtml(data.vision_model || '-')} · 审查模型: ${escapeHtml(data.judge_model || '-')}
    </div>`;

    _showMMResult(html, data.safe ? '图片安全' : `检测到 ${(data.risk_types || []).length} 类风险`);
}

// ==================== 2. 图文组合攻击检测 ====================

async function detectCombinedAttack() {
    const text = document.getElementById('mm-combined-text')?.value?.trim() || '';
    const fileInput = document.getElementById('mm-combined-image');
    const hasImage = fileInput && fileInput.files[0];

    if (!text && !hasImage) {
        showToast('请至少输入文字或上传图片', 'error');
        return;
    }

    _setLoading('btn-mm-combined', true);
    try {
        const formData = new FormData();
        if (text) formData.append('text', text);
        if (hasImage) formData.append('file', fileInput.files[0]);

        const resp = await fetch(MM_API + '/combined-attack', {
            method: 'POST',
            body: formData,
        });
        const result = await resp.json();
        if (!result.success) throw new Error(result.error || '检测失败');

        renderCombinedResult(result.data);
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        _setLoading('btn-mm-combined', false);
    }
}

function renderCombinedResult(data) {
    const ca = data.combined_analysis || {};
    const ta = data.text_only_analysis || {};
    const img = data.image_info || {};

    const safeColor = ca.safe ? '#27ae60' : '#e74c3c';
    const safeText = ca.safe ? '安全' : '检测到攻击';
    const scoreColor = ca.risk_score < 30 ? '#27ae60' : ca.risk_score < 60 ? '#f39c12' : '#e74c3c';

    // 攻击类型标签
    const attackBadges = (ca.attack_types || []).map(t =>
        `<span style="display:inline-block;background:#fff5f5;color:#e74c3c;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.85rem;margin:0.15rem;">${escapeHtml(t)}</span>`
    ).join('') || '<span style="color:#27ae60;">无</span>';

    // 攻击来源指示
    const sources = [];
    if (ca.text_attack) sources.push('<span style="color:#e74c3c;font-weight:600;">文字攻击</span>');
    if (ca.image_attack) sources.push('<span style="color:#e74c3c;font-weight:600;">图片攻击</span>');
    if (ca.combined_attack) sources.push('<span style="color:#e74c3c;font-weight:600;">组合攻击</span>');
    const sourcesHtml = sources.length > 0 ? sources.join(' · ') : '<span style="color:#27ae60;">未检测到攻击来源</span>';

    let html = `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem;">
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;color:${safeColor};">${safeText}</div>
            <div style="color:#888;font-size:0.85rem;">组合判定</div>
        </div>
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:${scoreColor};">${ca.risk_score || 0}</div>
            <div style="color:#888;font-size:0.85rem;">组合风险分</div>
        </div>
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:${ta.safe ? '#27ae60' : '#e74c3c'};">${ta.risk_score || 0}</div>
            <div style="color:#888;font-size:0.85rem;">纯文字风险分</div>
        </div>
        <div style="background:#f8f9fa;border-radius:8px;padding:1rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;">${ca.attack_detected ? '<span style="color:#e74c3c;">是</span>' : '<span style="color:#27ae60;">否</span>'}</div>
            <div style="color:#888;font-size:0.85rem;">攻击检出</div>
        </div>
    </div>

    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-bullseye" style="color:#e74c3c;"></i> 攻击来源</h3>
        <div>${sourcesHtml}</div>
    </div>

    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-tags" style="color:#3498db;"></i> 攻击类型</h3>
        <div>${attackBadges}</div>
    </div>

    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-comment-alt" style="color:#e74c3c;"></i> 组合分析</h3>
        <div style="background:${ca.safe ? '#f0fff4' : '#fff5f5'};padding:0.75rem;border-radius:8px;font-size:0.9rem;border-left:4px solid ${safeColor};">
            ${escapeHtml(ca.reason || '无')}
        </div>
    </div>`;

    if (ca.recommendation) {
        html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-lightbulb" style="color:#f39c12;"></i> 安全建议</h3>
        <div style="background:#fff8e1;padding:0.75rem;border-radius:8px;font-size:0.9rem;border-left:4px solid #f39c12;">
            ${escapeHtml(ca.recommendation)}
        </div>
    </div>`;
    }

    if (img.description) {
        html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-eye" style="color:#3498db;"></i> 图片描述</h3>
        <div style="background:#f8f9fa;padding:0.75rem;border-radius:8px;font-size:0.9rem;">${escapeHtml(img.description)}</div>
    </div>`;
    }

    if (img.extracted_text) {
        html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-font" style="color:#f39c12;"></i> 图片中提取的文字</h3>
        <div style="background:#fff8e1;padding:0.75rem;border-radius:8px;font-size:0.9rem;">${escapeHtml(img.extracted_text)}</div>
    </div>`;
    }

    if (ta.reason) {
        html += `
    <div style="margin-bottom:1rem;">
        <h3 style="font-size:1rem;margin-bottom:0.5rem;"><i class="fas fa-file-alt" style="color:#888;"></i> 纯文字分析</h3>
        <div style="background:#f8f9fa;padding:0.75rem;border-radius:8px;font-size:0.9rem;">${escapeHtml(ta.reason)}</div>
    </div>`;
    }

    html += `
    <div style="color:#888;font-size:0.8rem;">
        视觉模型: ${escapeHtml(data.models_used?.vision || '-')} · 审查模型: ${escapeHtml(data.models_used?.judge || '-')}
    </div>`;

    const summary = ca.attack_detected
        ? `检测到攻击 (风险分: ${ca.risk_score})`
        : '未检测到攻击';
    _showMMResult(html, summary);
}
