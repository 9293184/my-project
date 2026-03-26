"""对抗训练 API"""
import logging
from flask import Blueprint, jsonify, request
from threading import Thread

from ..adversarial.engine import AdversarialEngine
from ..errors import ValidationError

logger = logging.getLogger(__name__)

bp = Blueprint("adversarial", __name__)

# 全局对抗引擎实例
adversarial_engine = None


@bp.post("/api/adversarial/start-training")
def start_training():
    """开始对抗训练"""
    global adversarial_engine
    
    try:
        data = request.json or {}
        
        num_rounds = data.get("num_rounds", 10)
        attack_types = data.get("attack_types", ["prompt_injection", "jailbreak", "information_extraction"])
        
        # 创建引擎
        if adversarial_engine is None:
            adversarial_engine = AdversarialEngine()
        
        # 在后台线程运行训练
        def run_training_thread():
            global adversarial_engine
            try:
                adversarial_engine.run_training(
                    num_rounds=num_rounds,
                    attack_types=attack_types
                )
            except Exception as e:
                logger.error(f"Training error: {str(e)}", exc_info=True)
        
        thread = Thread(target=run_training_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": f"对抗训练已启动，共 {num_rounds} 轮"
        })
    
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}", exc_info=True)
        raise ValidationError(f"启动训练失败: {str(e)}")


@bp.get("/api/adversarial/status")
def get_status():
    """获取训练状态"""
    global adversarial_engine
    
    if adversarial_engine is None:
        return jsonify({
            "success": True,
            "data": {
                "is_training": False,
                "current_round": 0,
                "total_rounds": 0
            }
        })
    
    history = adversarial_engine.get_training_history()
    
    # 计算统计数据
    if history:
        recent_10 = history[-10:]
        attack_success_rate = sum(1 for r in recent_10 if r.get("attack_successful", False)) / len(recent_10)
        defense_accuracy = sum(1 for r in recent_10 if r.get("defense_successful", False)) / len(recent_10)
    else:
        attack_success_rate = 0
        defense_accuracy = 0
    
    return jsonify({
        "success": True,
        "data": {
            "is_training": adversarial_engine.is_training,
            "current_round": adversarial_engine.current_round,
            "total_rounds": len(history),
            "attack_success_rate": attack_success_rate,
            "defense_accuracy": defense_accuracy,
            "latest_round": history[-1] if history else None
        }
    })


@bp.post("/api/adversarial/stop")
def stop_training():
    """停止训练"""
    global adversarial_engine
    
    if adversarial_engine:
        adversarial_engine.stop_training()
    
    return jsonify({
        "success": True,
        "message": "训练已停止"
    })


@bp.get("/api/adversarial/history")
def get_history():
    """获取训练历史"""
    global adversarial_engine
    
    if adversarial_engine is None:
        return jsonify({
            "success": True,
            "data": {
                "history": [],
                "statistics": {}
            }
        })
    
    history = adversarial_engine.get_training_history()
    stats = adversarial_engine._calculate_statistics(history)
    
    return jsonify({
        "success": True,
        "data": {
            "history": history,
            "statistics": stats
        }
    })


@bp.post("/api/adversarial/reset")
def reset_training():
    """重置训练"""
    global adversarial_engine
    
    if adversarial_engine:
        adversarial_engine.reset()
    
    return jsonify({
        "success": True,
        "message": "训练已重置"
    })


@bp.post("/api/adversarial/test-round")
def test_round():
    """测试单轮对抗"""
    global adversarial_engine
    
    try:
        data = request.json or {}
        attack_type = data.get("attack_type", "prompt_injection")
        
        if adversarial_engine is None:
            adversarial_engine = AdversarialEngine()
        
        result = adversarial_engine.run_adversarial_round(attack_type)
        
        return jsonify({
            "success": True,
            "data": result
        })
    
    except Exception as e:
        logger.error(f"Failed to run test round: {str(e)}", exc_info=True)
        raise ValidationError(f"测试失败: {str(e)}")
