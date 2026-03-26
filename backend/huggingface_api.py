"""
HuggingFace 模型下载和训练集上传 API
"""
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import threading
import time
from datetime import datetime

hf_bp = Blueprint('huggingface', __name__)

# 下载任务状态
download_tasks = {}

class DownloadTask:
    def __init__(self, task_id, model_name):
        self.task_id = task_id
        self.model_name = model_name
        self.status = "pending"  # pending, downloading, completed, failed
        self.progress = 0
        self.message = ""
        self.error = None
        
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "model_name": self.model_name,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error
        }

@hf_bp.route('/api/train/download-model', methods=['POST'])
def download_model():
    """从 HuggingFace 下载模型"""
    try:
        data = request.json
        model_name = data.get('model_name')
        token = data.get('token')
        
        if not model_name:
            return jsonify({"error": "Missing model_name"}), 400
        
        # 创建任务ID
        task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建下载任务
        task = DownloadTask(task_id, model_name)
        download_tasks[task_id] = task
        
        # 启动下载线程
        thread = threading.Thread(target=run_download, args=(task, model_name, token))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "task_id": task_id,
            "status": "started",
            "message": "Download task started"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@hf_bp.route('/api/train/download-status/<task_id>', methods=['GET'])
def get_download_status(task_id):
    """获取下载状态"""
    if task_id not in download_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = download_tasks[task_id]
    return jsonify(task.to_dict()), 200

def run_download(task, model_name, token):
    """执行下载任务"""
    try:
        task.status = "downloading"
        task.message = f"正在下载模型 {model_name}..."
        
        # 使用 huggingface_hub 下载模型
        from huggingface_hub import snapshot_download
        
        save_dir = os.path.join(os.path.dirname(__file__), '..', 'models', 'huggingface', model_name.replace('/', '_'))
        os.makedirs(save_dir, exist_ok=True)
        
        # 下载模型
        snapshot_download(
            repo_id=model_name,
            local_dir=save_dir,
            token=token,
            resume_download=True
        )
        
        task.status = "completed"
        task.progress = 100
        task.message = f"模型 {model_name} 下载完成"
        
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        task.message = f"下载失败: {str(e)}"

@hf_bp.route('/api/train/upload-dataset', methods=['POST'])
def upload_dataset():
    """上传训练集"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        dataset_name = request.form.get('dataset_name', file.filename)
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # 安全的文件名
        filename = secure_filename(dataset_name)
        
        # 保存路径
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'public')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        
        # 保存文件
        file.save(file_path)
        
        # 统计样本数
        sample_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sample_count = sum(1 for _ in f)
        except:
            pass
        
        return jsonify({
            "success": True,
            "message": "Dataset uploaded successfully",
            "filename": filename,
            "path": file_path,
            "sample_count": sample_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
