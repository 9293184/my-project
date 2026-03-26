// HuggingFace 模型下载和训练集上传功能

// 打开下载模型弹窗
function openDownloadModelModal() {
    document.getElementById('download-model-modal').classList.add('active');
    document.getElementById('download-progress').style.display = 'none';
    document.getElementById('hf-model-name').value = '';
    document.getElementById('hf-token').value = '';
}

// 打开上传训练集弹窗
function openUploadDatasetModal() {
    document.getElementById('upload-dataset-modal').classList.add('active');
    document.getElementById('upload-progress').style.display = 'none';
    document.getElementById('dataset-file').value = '';
    document.getElementById('dataset-name').value = '';
}

// 下载 HuggingFace 模型
async function downloadHFModel() {
    const modelName = document.getElementById('hf-model-name').value.trim();
    const token = document.getElementById('hf-token').value.trim();
    
    if (!modelName) {
        showToast('请输入模型名称', 'error');
        return;
    }
    
    const progressDiv = document.getElementById('download-progress');
    const progressFill = document.getElementById('download-progress-fill');
    const progressText = document.getElementById('download-progress-text');
    const statusDiv = document.getElementById('download-status');
    const downloadBtn = document.getElementById('download-model-btn');
    
    try {
        progressDiv.style.display = 'block';
        downloadBtn.disabled = true;
        statusDiv.textContent = '正在连接 HuggingFace...';
        
        const response = await fetch(`${API_BASE_URL}/api/train/download-model`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                model_name: modelName,
                token: token || null
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 开始轮询下载进度
            const taskId = data.task_id;
            pollDownloadProgress(taskId, progressFill, progressText, statusDiv, downloadBtn);
        } else {
            throw new Error(data.error || '下载失败');
        }
    } catch (error) {
        console.error('下载模型失败:', error);
        showToast(error.message || '下载模型失败', 'error');
        downloadBtn.disabled = false;
        statusDiv.textContent = '下载失败: ' + error.message;
    }
}

// 轮询下载进度
async function pollDownloadProgress(taskId, progressFill, progressText, statusDiv, downloadBtn) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/train/download-status/${taskId}`);
            const data = await response.json();
            
            if (data.status === 'downloading') {
                const progress = data.progress || 0;
                progressFill.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;
                statusDiv.textContent = data.message || '正在下载...';
            } else if (data.status === 'completed') {
                clearInterval(interval);
                progressFill.style.width = '100%';
                progressText.textContent = '100%';
                statusDiv.textContent = '下载完成！';
                showToast('模型下载成功', 'success');
                downloadBtn.disabled = false;
                
                // 刷新模型列表
                if (typeof loadAvailableModels === 'function') {
                    setTimeout(() => {
                        loadAvailableModels();
                        closeTrainingModal('download-model-modal');
                    }, 2000);
                }
            } else if (data.status === 'failed') {
                clearInterval(interval);
                statusDiv.textContent = '下载失败: ' + (data.error || '未知错误');
                showToast('模型下载失败', 'error');
                downloadBtn.disabled = false;
            }
        } catch (error) {
            console.error('获取下载进度失败:', error);
            clearInterval(interval);
            downloadBtn.disabled = false;
        }
    }, 2000);
}

// 上传训练集
async function uploadDataset() {
    const fileInput = document.getElementById('dataset-file');
    const datasetName = document.getElementById('dataset-name').value.trim();
    
    if (!fileInput.files || fileInput.files.length === 0) {
        showToast('请选择文件', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    const progressDiv = document.getElementById('upload-progress');
    const progressFill = document.getElementById('upload-progress-fill');
    const progressText = document.getElementById('upload-progress-text');
    const statusDiv = document.getElementById('upload-status');
    const uploadBtn = document.getElementById('upload-dataset-btn');
    
    try {
        progressDiv.style.display = 'block';
        uploadBtn.disabled = true;
        statusDiv.textContent = '正在上传...';
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('dataset_name', datasetName || file.name);
        
        const xhr = new XMLHttpRequest();
        
        // 监听上传进度
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const progress = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;
                statusDiv.textContent = `正在上传... ${(e.loaded / 1024 / 1024).toFixed(2)} MB / ${(e.total / 1024 / 1024).toFixed(2)} MB`;
            }
        });
        
        // 监听完成
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                statusDiv.textContent = '上传完成！';
                showToast('训练集上传成功', 'success');
                
                // 刷新数据集列表
                if (typeof loadAvailableDatasets === 'function') {
                    setTimeout(() => {
                        loadAvailableDatasets();
                        closeTrainingModal('upload-dataset-modal');
                    }, 2000);
                }
            } else {
                const data = JSON.parse(xhr.responseText);
                throw new Error(data.error || '上传失败');
            }
            uploadBtn.disabled = false;
        });
        
        // 监听错误
        xhr.addEventListener('error', () => {
            statusDiv.textContent = '上传失败';
            showToast('训练集上传失败', 'error');
            uploadBtn.disabled = false;
        });
        
        xhr.open('POST', `${API_BASE_URL}/api/train/upload-dataset`);
        xhr.send(formData);
        
    } catch (error) {
        console.error('上传训练集失败:', error);
        showToast(error.message || '上传训练集失败', 'error');
        uploadBtn.disabled = false;
        statusDiv.textContent = '上传失败: ' + error.message;
    }
}
