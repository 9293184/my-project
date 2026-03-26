// 训练管理相关功能
// API_BASE_URL 已在 app.js 中定义
let currentTaskId = null;
let trainingRefreshInterval = null;

// 加载可用模型
async function loadAvailableModels() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/models`);
        const data = await response.json();
        
        const container = document.getElementById('available-models-list');
        const select = document.getElementById('train-model-select');
        
        if (data.models && data.models.length > 0) {
            container.innerHTML = data.models.map(model => `
                <div class="resource-item">
                    <h4>${model.name}</h4>
                    <div class="meta">
                        <span><i class="fas fa-cube"></i> ${model.size}</span>
                        <span><i class="fas fa-tag"></i> ${model.type}</span>
                    </div>
                </div>
            `).join('');
            
            select.innerHTML = '<option value="">-- 请选择 --</option>' +
                data.models.map(model => `<option value="${model.name}">${model.name} (${model.size})</option>`).join('');
        } else {
            container.innerHTML = '<p class="text-center">暂无可用模型</p>';
        }
    } catch (error) {
        console.error('加载模型失败:', error);
        showToast('加载模型失败', 'error');
    }
}

// 加载可用数据集
async function loadAvailableDatasets() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/datasets`);
        const data = await response.json();
        
        const container = document.getElementById('available-datasets-list');
        const select = document.getElementById('train-dataset-select');
        
        if (data.datasets && data.datasets.length > 0) {
            // 过滤掉无效的数据集（sample_count为0或负数）
            const validDatasets = data.datasets.filter(dataset => dataset.sample_count > 0);
            
            if (validDatasets.length > 0) {
                container.innerHTML = validDatasets.map(dataset => `
                    <div class="resource-item">
                        <h4>${dataset.name}</h4>
                        <div class="meta">
                            <span><i class="fas fa-database"></i> ${(dataset.size / 1024 / 1024).toFixed(2)} MB</span>
                            <span><i class="fas fa-list"></i> ${dataset.sample_count} 条样本</span>
                        </div>
                    </div>
                `).join('');
                
                select.innerHTML = '<option value="">-- 请选择 --</option>' +
                    validDatasets.map(dataset => `<option value="${dataset.path}">${dataset.name} (${dataset.sample_count}条)</option>`).join('');
            } else {
                container.innerHTML = '<p class="text-center">暂无可用数据集</p>';
                select.innerHTML = '<option value="">-- 暂无可用数据集 --</option>';
            }
        } else {
            container.innerHTML = '<p class="text-center">暂无可用数据集</p>';
            select.innerHTML = '<option value="">-- 暂无可用数据集 --</option>';
        }
    } catch (error) {
        console.error('加载数据集失败:', error);
        showToast('加载数据集失败', 'error');
    }
}

// 加载训练任务列表
async function loadTrainingTasks() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/list`);
        const data = await response.json();
        
        const tbody = document.getElementById('training-tasks-table');
        
        if (data.tasks && data.tasks.length > 0) {
            tbody.innerHTML = data.tasks.map(task => `
                <tr>
                    <td>${task.task_id}</td>
                    <td>${task.config.model_name}</td>
                    <td>${task.config.dataset_path.split('/').pop()}</td>
                    <td><span class="badge ${task.status}">${getStatusText(task.status)}</span></td>
                    <td>${task.progress}%</td>
                    <td>${task.start_time ? new Date(task.start_time).toLocaleString() : '-'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline" onclick="viewTrainingDetail('${task.task_id}')">
                            <i class="fas fa-eye"></i> 查看
                        </button>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">暂无训练任务</td></tr>';
        }
    } catch (error) {
        console.error('加载训练任务失败:', error);
        showToast('加载训练任务失败', 'error');
    }
}

function getStatusText(status) {
    const statusMap = {
        'pending': '等待中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败',
        'stopped': '已停止'
    };
    return statusMap[status] || status;
}

// 打开启动训练弹窗
function openStartTrainingModal() {
    document.getElementById('start-training-modal').classList.add('active');
    loadAvailableModels();
    loadAvailableDatasets();
}

// 启动训练
async function startTraining() {
    const modelName = document.getElementById('train-model-select').value;
    const datasetPath = document.getElementById('train-dataset-select').value;
    const outputDir = document.getElementById('train-output-dir').value;
    const epochs = parseInt(document.getElementById('train-epochs').value);
    const batchSize = parseInt(document.getElementById('train-batch-size').value);
    const learningRate = parseFloat(document.getElementById('train-learning-rate').value);
    
    if (!modelName || !datasetPath || !outputDir) {
        showToast('请填写所有必填项', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                model_name: modelName,
                dataset_path: datasetPath,
                output_dir: outputDir,
                epochs: epochs,
                batch_size: batchSize,
                learning_rate: learningRate,
                lora_rank: 8,
                max_seq_length: 512,
                use_gpu: true
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('训练任务已启动', 'success');
            closeTrainingModal('start-training-modal');
            loadTrainingTasks();
        } else {
            showToast(data.error || '启动训练失败', 'error');
        }
    } catch (error) {
        console.error('启动训练失败:', error);
        showToast('启动训练失败', 'error');
    }
}

// 查看训练详情
async function viewTrainingDetail(taskId) {
    currentTaskId = taskId;
    document.getElementById('training-detail-modal').classList.add('active');
    
    refreshTrainingDetail(taskId);
    trainingRefreshInterval = setInterval(() => refreshTrainingDetail(taskId), 3000);
}

async function refreshTrainingDetail(taskId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/status/${taskId}`);
        const task = await response.json();
        
        document.getElementById('detail-task-id').textContent = task.task_id;
        document.getElementById('detail-status').textContent = getStatusText(task.status);
        document.getElementById('detail-status').className = `badge ${task.status}`;
        document.getElementById('detail-progress').textContent = `${task.progress}%`;
        
        const logsContainer = document.getElementById('training-logs');
        if (task.logs && task.logs.length > 0) {
            logsContainer.innerHTML = task.logs.map(log => `<div>${log}</div>`).join('');
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
        
        if (task.status === 'completed' || task.status === 'failed' || task.status === 'stopped') {
            if (trainingRefreshInterval) {
                clearInterval(trainingRefreshInterval);
                trainingRefreshInterval = null;
            }
        }
    } catch (error) {
        console.error('刷新训练详情失败:', error);
    }
}

// 停止训练
async function stopCurrentTraining() {
    if (!currentTaskId || !confirm('确定要停止此训练任务吗？')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/stop/${currentTaskId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('训练已停止', 'success');
            refreshTrainingDetail(currentTaskId);
        } else {
            showToast(data.error || '停止训练失败', 'error');
        }
    } catch (error) {
        console.error('停止训练失败:', error);
        showToast('停止训练失败', 'error');
    }
}

// 刷新训练任务列表
function refreshTrainingTasks() {
    loadTrainingTasks();
    showToast('已刷新', 'success');
}

// 关闭弹窗
function closeTrainingModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    if (modalId === 'training-detail-modal' && trainingRefreshInterval) {
        clearInterval(trainingRefreshInterval);
        trainingRefreshInterval = null;
    }
}

// 初始化训练页面
function initTrainingPage() {
    if (document.getElementById('page-training')) {
        loadAvailableModels();
        loadAvailableDatasets();
        loadTrainingTasks();
    }
}
