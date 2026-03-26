// ========== 安全策略管理 ==========

const SCENE_LABELS = {
    general: '通用场景',
    finance: '金融客服',
    medical: '医疗问答',
    education: '教育辅导',
    legal: '法律咨询',
    ecommerce: '电商客服',
    custom: '自定义场景',
};

let policiesCache = [];
let bindingsCache = [];

// ========== 加载策略列表 ==========
async function loadPolicies() {
    try {
        const result = await API.request('/policies');
        policiesCache = result.data || [];

        const sceneFilter = document.getElementById('policy-scene-filter')?.value || '';
        const filtered = sceneFilter
            ? policiesCache.filter(p => p.scene === sceneFilter)
            : policiesCache;

        // 更新统计
        document.getElementById('policy-total-count').textContent = policiesCache.length;
        const scenes = new Set(policiesCache.map(p => p.scene));
        document.getElementById('policy-scene-count').textContent = scenes.size;

        // 填充场景过滤器
        const filterSelect = document.getElementById('policy-scene-filter');
        if (filterSelect && filterSelect.options.length <= 1) {
            for (const [key, label] of Object.entries(SCENE_LABELS)) {
                const opt = document.createElement('option');
                opt.value = key;
                opt.textContent = label;
                filterSelect.appendChild(opt);
            }
        }

        // 渲染表格
        const tbody = document.getElementById('policies-table-body');
        if (!filtered.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#999;">暂无策略</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(p => {
            const bindCount = bindingsCache.filter(b => b.policy_id === p.id).length;
            return `<tr>
                <td>${p.id}</td>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td><span class="badge">${SCENE_LABELS[p.scene] || p.scene}</span></td>
                <td>${p.is_default ? '<span class="badge" style="background:#4caf50;color:#fff;">默认</span>' : '-'}</td>
                <td>${bindCount}</td>
                <td>${p.created_at || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-outline" onclick="editPolicy(${p.id})"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-outline" style="color:var(--danger-color);" onclick="deletePolicy(${p.id})"><i class="fas fa-trash"></i></button>
                </td>
            </tr>`;
        }).join('');

    } catch (e) {
        console.error('加载策略失败:', e);
        showToast('加载策略列表失败', 'error');
    }
}

// ========== 加载绑定列表 ==========
async function loadBindings() {
    try {
        const result = await API.request('/policies/bindings');
        bindingsCache = result.data || [];

        document.getElementById('policy-binding-count').textContent = bindingsCache.length;

        const tbody = document.getElementById('bindings-table-body');
        if (!bindingsCache.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无绑定</td></tr>';
            return;
        }

        tbody.innerHTML = bindingsCache.map(b => `<tr>
            <td>${b.id}</td>
            <td><code>${escapeHtml(b.model_key)}</code></td>
            <td>${escapeHtml(b.policy_name)}</td>
            <td><span class="badge">${SCENE_LABELS[b.scene] || b.scene}</span></td>
            <td>${b.priority}</td>
            <td>
                <button class="btn btn-sm btn-outline" style="color:var(--danger-color);" onclick="deleteBinding(${b.id})"><i class="fas fa-unlink"></i> 解绑</button>
            </td>
        </tr>`).join('');

    } catch (e) {
        console.error('加载绑定失败:', e);
    }
}

// ========== 初始化策略页面 ==========
async function initPoliciesPage() {
    await Promise.all([loadBindings(), loadPolicies()]);
}

// ========== 新建策略弹窗 ==========
function openCreatePolicyModal() {
    document.getElementById('policy-modal-title').textContent = '新建安全策略';
    document.getElementById('policy-edit-id').value = '';
    document.getElementById('policy-name').value = '';
    document.getElementById('policy-scene').value = 'general';
    document.getElementById('policy-description').value = '';
    document.getElementById('policy-prompt').value = '';
    document.getElementById('policy-is-default').checked = false;
    document.getElementById('policy-modal').style.display = 'flex';
}

function closePolicyModal() {
    document.getElementById('policy-modal').style.display = 'none';
}

// ========== 编辑策略 ==========
function editPolicy(id) {
    const p = policiesCache.find(x => x.id === id);
    if (!p) return;

    document.getElementById('policy-modal-title').textContent = '编辑安全策略';
    document.getElementById('policy-edit-id').value = p.id;
    document.getElementById('policy-name').value = p.name;
    document.getElementById('policy-scene').value = p.scene;
    document.getElementById('policy-description').value = p.description || '';
    document.getElementById('policy-prompt').value = p.prompt;
    document.getElementById('policy-is-default').checked = p.is_default;
    document.getElementById('policy-modal').style.display = 'flex';
}

// ========== 保存策略 ==========
async function savePolicy() {
    const editId = document.getElementById('policy-edit-id').value;
    const data = {
        name: document.getElementById('policy-name').value.trim(),
        scene: document.getElementById('policy-scene').value,
        description: document.getElementById('policy-description').value.trim(),
        prompt: document.getElementById('policy-prompt').value.trim(),
        is_default: document.getElementById('policy-is-default').checked,
    };

    if (!data.name) { showToast('请输入策略名称', 'warning'); return; }
    if (!data.prompt) { showToast('请输入安全提示词', 'warning'); return; }

    try {
        if (editId) {
            await API.request(`/policies/${editId}`, { method: 'PUT', body: JSON.stringify(data) });
            showToast('策略更新成功', 'success');
        } else {
            await API.request('/policies', { method: 'POST', body: JSON.stringify(data) });
            showToast('策略创建成功', 'success');
        }
        closePolicyModal();
        await initPoliciesPage();
    } catch (e) {
        showToast(e.message || '保存失败', 'error');
    }
}

// ========== 删除策略 ==========
async function deletePolicy(id) {
    if (!confirm('确定删除该策略？关联的绑定也会被删除。')) return;
    try {
        await API.request(`/policies/${id}`, { method: 'DELETE' });
        showToast('策略已删除', 'success');
        await initPoliciesPage();
    } catch (e) {
        showToast(e.message || '删除失败', 'error');
    }
}

// ========== 绑定弹窗 ==========
async function openBindPolicyModal() {
    // 填充模型下拉
    const modelSelect = document.getElementById('bind-model-select');
    let options = '<option value="">-- 请选择模型 --</option>';

    // 数据库模型
    if (modelsCache.length) {
        options += modelsCache.map(m =>
            `<option value="${m.id}">${escapeHtml(m.name)} (${escapeHtml(m.model_id)})</option>`
        ).join('');
    }

    // Ollama 模型
    try {
        const ollamaResult = await API.getOllamaModels();
        const ollamaModels = ollamaResult.data || [];
        if (ollamaModels.length) {
            options += '<option disabled>── Ollama 模型 ──</option>';
            options += ollamaModels.map(m =>
                `<option value="ollama:${escapeHtml(m.name)}">[Ollama] ${escapeHtml(m.name)}</option>`
            ).join('');
        }
    } catch (e) {}

    // HuggingFace 模型
    try {
        const hfResult = await API.getLocalModels();
        const hfModels = hfResult.data || [];
        if (hfModels.length) {
            options += '<option disabled>── HuggingFace 本地 ──</option>';
            options += hfModels.map(m =>
                `<option value="hf:${escapeHtml(m.name)}">[HF] ${escapeHtml(m.name)}</option>`
            ).join('');
        }
    } catch (e) {}

    modelSelect.innerHTML = options;

    // 填充策略下拉
    const policySelect = document.getElementById('bind-policy-select');
    policySelect.innerHTML = '<option value="">-- 请选择策略 --</option>' +
        policiesCache.map(p =>
            `<option value="${p.id}">${escapeHtml(p.name)} (${SCENE_LABELS[p.scene] || p.scene})</option>`
        ).join('');

    document.getElementById('bind-priority').value = '0';
    document.getElementById('bind-policy-modal').style.display = 'flex';
}

function closeBindPolicyModal() {
    document.getElementById('bind-policy-modal').style.display = 'none';
}

// ========== 保存绑定 ==========
async function saveBinding() {
    const modelKey = document.getElementById('bind-model-select').value;
    const policyId = document.getElementById('bind-policy-select').value;
    const priority = parseInt(document.getElementById('bind-priority').value) || 0;

    if (!modelKey) { showToast('请选择模型', 'warning'); return; }
    if (!policyId) { showToast('请选择策略', 'warning'); return; }

    try {
        await API.request('/policies/bindings', {
            method: 'POST',
            body: JSON.stringify({ model_key: modelKey, policy_id: parseInt(policyId), priority }),
        });
        showToast('绑定成功', 'success');
        closeBindPolicyModal();
        await initPoliciesPage();
    } catch (e) {
        showToast(e.message || '绑定失败', 'error');
    }
}

// ========== 删除绑定 ==========
async function deleteBinding(id) {
    if (!confirm('确定解除该绑定？')) return;
    try {
        await API.request(`/policies/bindings/${id}`, { method: 'DELETE' });
        showToast('已解绑', 'success');
        await initPoliciesPage();
    } catch (e) {
        showToast(e.message || '解绑失败', 'error');
    }
}
