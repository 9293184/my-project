"""
训练 API 接口
提供模型训练、监控和管理功能
"""

from flask import Blueprint, request, jsonify
import os
import json
import subprocess
import threading
import requests as http_requests
from datetime import datetime

train_bp = Blueprint('train', __name__)

# 训练任务状态
training_tasks = {}

class TrainingTask:
    def __init__(self, task_id, config):
        self.task_id = task_id
        self.config = config
        self.status = "pending"
        self.progress = 0
        self.start_time = None
        self.end_time = None
        self.logs = []
        self.error = None
        
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "config": self.config,
            "status": self.status,
            "progress": self.progress,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "logs": self.logs[-50:],  # 最近50条日志
            "error": self.error
        }

@train_bp.route('/api/train/start', methods=['POST'])
def start_training():
    """启动训练任务"""
    try:
        data = request.json
        
        # 验证参数
        required_fields = ['model_name', 'dataset_path', 'output_dir']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # 创建任务ID
        task_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建训练配置
        config = {
            "model_name": data['model_name'],
            "dataset_path": data['dataset_path'],
            "output_dir": data['output_dir'],
            "epochs": data.get('epochs', 3),
            "batch_size": data.get('batch_size', 1),
            "learning_rate": data.get('learning_rate', 2e-4),
            "lora_rank": data.get('lora_rank', 8),
            "max_seq_length": data.get('max_seq_length', 512),
            "use_gpu": data.get('use_gpu', True)
        }
        
        # 创建任务
        task = TrainingTask(task_id, config)
        training_tasks[task_id] = task
        
        # 启动训练线程
        thread = threading.Thread(target=run_training, args=(task,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "task_id": task_id,
            "status": "started",
            "message": "Training task started successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@train_bp.route('/api/train/status/<task_id>', methods=['GET'])
def get_training_status(task_id):
    """获取训练状态"""
    if task_id not in training_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = training_tasks[task_id]
    return jsonify(task.to_dict()), 200

@train_bp.route('/api/train/list', methods=['GET'])
def list_training_tasks():
    """列出所有训练任务"""
    tasks = [task.to_dict() for task in training_tasks.values()]
    return jsonify({"tasks": tasks}), 200

@train_bp.route('/api/train/stop/<task_id>', methods=['POST'])
def stop_training(task_id):
    """停止训练任务"""
    if task_id not in training_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = training_tasks[task_id]
    if task.status == "running":
        task.status = "stopped"
        task.logs.append("Training stopped by user")
        return jsonify({"message": "Training stopped"}), 200
    else:
        return jsonify({"error": "Task is not running"}), 400

def run_training(task):
    """执行训练任务"""
    try:
        task.status = "running"
        task.start_time = datetime.now().isoformat()
        task.logs.append(f"Training started at {task.start_time}")
        
        # 准备训练脚本
        script_path = os.path.join(os.path.dirname(__file__), 'train_defender_lora.py')
        
        # 构建命令
        cmd = [
            'python', script_path,
            '--model_name', task.config['model_name'],
            '--dataset_path', task.config['dataset_path'],
            '--output_dir', task.config['output_dir'],
            '--epochs', str(task.config['epochs']),
            '--batch_size', str(task.config['batch_size']),
            '--learning_rate', str(task.config['learning_rate']),
            '--lora_rank', str(task.config['lora_rank']),
            '--max_seq_length', str(task.config['max_seq_length'])
        ]
        
        if not task.config['use_gpu']:
            cmd.append('--no_gpu')
        
        task.logs.append(f"Command: {' '.join(cmd)}")
        
        # 执行训练
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # 读取输出
        for line in process.stdout:
            line = line.strip()
            if line:
                task.logs.append(line)
                
                # 解析进度
                if "epoch" in line.lower() or "step" in line.lower():
                    # 简单的进度估算
                    if task.progress < 90:
                        task.progress += 1
        
        # 等待完成
        process.wait()
        
        if process.returncode == 0:
            task.status = "completed"
            task.progress = 100
            task.logs.append("Training completed successfully")
        else:
            task.status = "failed"
            task.error = f"Training failed with exit code {process.returncode}"
            task.logs.append(task.error)
        
        task.end_time = datetime.now().isoformat()
        
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        task.logs.append(f"Error: {str(e)}")
        task.end_time = datetime.now().isoformat()

@train_bp.route('/api/train/models', methods=['GET'])
def list_available_models():
    """列出可用的模型（从 Ollama 本地获取）"""
    models = []
    try:
        resp = http_requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            for m in resp.json().get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                if size_bytes > 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024**3):.1f}GB"
                elif size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024**2):.0f}MB"
                else:
                    size_str = f"{size_bytes / 1024:.0f}KB"

                family = m.get("details", {}).get("family", "")
                param_size = m.get("details", {}).get("parameter_size", "")
                models.append({
                    "name": name,
                    "size": param_size or size_str,
                    "type": family or "local",
                    "description": f"Ollama 本地模型 ({size_str})",
                })
    except Exception:
        pass

    return jsonify({"models": models}), 200

@train_bp.route('/api/train/datasets', methods=['GET'])
def list_available_datasets():
    """列出可用的数据集"""
    datasets_dir = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'public')
    datasets = []
    
    if os.path.exists(datasets_dir):
        for file in os.listdir(datasets_dir):
            if file.endswith('.jsonl'):
                file_path = os.path.join(datasets_dir, file)
                size = os.path.getsize(file_path)
                
                # 统计样本数
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        sample_count = sum(1 for _ in f)
                except:
                    sample_count = 0
                
                datasets.append({
                    "name": file,
                    "path": file_path,
                    "size": size,
                    "sample_count": sample_count
                })
    
    return jsonify({"datasets": datasets}), 200
