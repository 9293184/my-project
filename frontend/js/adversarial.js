// 对抗训练功能

let advTrainingInterval = null;

// 打开对抗训练弹窗
function openAdversarialTrainingModal() {
    document.getElementById('adversarial-training-modal').classList.add('active');
    document.getElementById('adv-progress').style.display = 'none';
    
    // 加载可用模型到下拉框
    loadModelsForAdversarial();
}

// 加载可用模型
async function loadModelsForAdversarial() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/train/models`);
        const data = await response.json();
        
        const select = document.getElementById('adv-model-select');
        
        if (data.models && data.models.length > 0) {
            select.innerHTML = '<option value="">-- 请选择 --</option>' +
                data.models.map(model => `<option value="${model.name}">${model.name} (${model.size})</option>`).join('');
        } else {
            select.innerHTML = '<option value="">-- 暂无可用模型 --</option>';
        }
    } catch (error) {
        console.error('加载模型失败:', error);
    }
}

// 开始对抗训练
async function startAdversarialTraining() {
    const scenario = document.getElementById('adv-scenario').value.trim();
    const modelName = document.getElementById('adv-model-select').value;
    const rounds = parseInt(document.getElementById('adv-rounds').value);
    const attackLevel = document.getElementById('adv-attack-level').value;
    const trainingMode = document.getElementById('adv-training-mode').value;
    const outputDir = document.getElementById('adv-output-dir').value;
    
    if (!scenario) {
        showToast('请描述业务场景', 'error');
        return;
    }
    
    if (!modelName) {
        showToast('请选择基础模型', 'error');
        return;
    }
    
    const progressDiv = document.getElementById('adv-progress');
    const progressFill = document.getElementById('adv-progress-fill');
    const progressText = document.getElementById('adv-progress-text');
    const statusDiv = document.getElementById('adv-status');
    const logsDiv = document.getElementById('adv-logs');
    const advBtn = document.getElementById('adv-training-btn');
    
    try {
        progressDiv.style.display = 'block';
        advBtn.disabled = true;
        logsDiv.innerHTML = '';
        statusDiv.textContent = '正在启动对抗训练...';
        
        const response = await fetch(`${API_BASE_URL}/api/train/adversarial-start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                scenario: scenario,
                model_name: modelName,
                rounds: rounds,
                attack_level: attackLevel,
                training_mode: trainingMode,
                output_dir: outputDir
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const taskId = data.task_id;
            statusDiv.textContent = '对抗训练已启动，正在生成攻击样本...';
            addAdvLog('✓ 对抗训练任务已创建');
            addAdvLog(`场景: ${scenario}`);
            addAdvLog(`模型: ${modelName}`);
            addAdvLog(`对抗轮数: ${rounds}`);
            addAdvLog('---');
            
            // 开始轮询进度
            pollAdversarialProgress(taskId, progressFill, progressText, statusDiv, logsDiv, advBtn);
        } else {
            throw new Error(data.error || '启动对抗训练失败');
        }
    } catch (error) {
        console.error('启动对抗训练失败:', error);
        showToast(error.message || '启动对抗训练失败', 'error');
        advBtn.disabled = false;
        statusDiv.textContent = '启动失败: ' + error.message;
    }
}

// 轮询对抗训练进度
async function pollAdversarialProgress(taskId, progressFill, progressText, statusDiv, logsDiv, advBtn) {
    advTrainingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/train/adversarial-status/${taskId}`);
            const data = await response.json();
            
            if (data.status === 'running') {
                const progress = data.progress || 0;
                progressFill.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;
                statusDiv.textContent = data.message || '对抗训练进行中...';
                
                // 添加新日志
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(log => {
                        if (!logsDiv.textContent.includes(log)) {
                            addAdvLog(log);
                        }
                    });
                }
            } else if (data.status === 'completed') {
                clearInterval(advTrainingInterval);
                progressFill.style.width = '100%';
                progressText.textContent = '100%';
                statusDiv.textContent = '对抗训练完成！';
                addAdvLog('---');
                addAdvLog('✓ 对抗训练成功完成');
                addAdvLog(`训练轮数: ${data.rounds_completed || 0}`);
                addAdvLog(`防御成功率: ${data.defense_rate || 0}%`);
                showToast('对抗训练完成', 'success');
                advBtn.disabled = false;
                
                // 刷新模型列表
                if (typeof loadAvailableModels === 'function') {
                    setTimeout(() => {
                        loadAvailableModels();
                    }, 2000);
                }
            } else if (data.status === 'failed') {
                clearInterval(advTrainingInterval);
                statusDiv.textContent = '对抗训练失败: ' + (data.error || '未知错误');
                addAdvLog('✗ 对抗训练失败: ' + (data.error || '未知错误'));
                showToast('对抗训练失败', 'error');
                advBtn.disabled = false;
            }
        } catch (error) {
            console.error('获取对抗训练进度失败:', error);
            clearInterval(advTrainingInterval);
            advBtn.disabled = false;
        }
    }, 3000);
}

// 添加对抗训练日志
function addAdvLog(message) {
    const logsDiv = document.getElementById('adv-logs');
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    logLine.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logsDiv.appendChild(logLine);
    logsDiv.scrollTop = logsDiv.scrollHeight;
}
