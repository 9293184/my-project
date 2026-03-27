"""训练数据投毒检测 API"""
import logging
from flask import Blueprint, current_app, jsonify, request

from ..security_utils import PoisonDetector
from ..errors import ValidationError

logger = logging.getLogger(__name__)

bp = Blueprint("poison_detection", __name__)


def _get_detector() -> PoisonDetector:
    """获取投毒检测器实例"""
    return PoisonDetector(
        llm_url="http://localhost:11434/v1",
        llm_model="qwen2.5:latest",
    )


@bp.post("/api/poison-detection/scan")
def scan_training_data():
    """
    扫描训练数据集，检测是否存在投毒样本

    请求体:
    {
        "samples": [...],          // 训练样本列表
        "deep_check": false        // 是否启用 LLM 深度校验
    }
    """
    try:
        data = request.json or {}
        samples = data.get("samples")
        deep_check = data.get("deep_check", False)

        if not samples or not isinstance(samples, list):
            raise ValidationError("请提供训练样本列表 (samples)")

        detector = _get_detector()
        report = detector.detect_batch(samples, deep_check=deep_check)

        return jsonify({
            "success": True,
            "data": report,
            "message": f"扫描完成: {report['total_samples']} 条样本, "
                       f"{len(report['suspicious_samples'])} 条可疑"
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"投毒检测失败: {str(e)}", exc_info=True)
        raise ValidationError(f"投毒检测失败: {str(e)}")


@bp.post("/api/poison-detection/filter")
def filter_training_data():
    """
    过滤训练数据，返回干净样本和被拦截的样本

    请求体:
    {
        "samples": [...],          // 训练样本列表
        "deep_check": false        // 是否启用 LLM 深度校验
    }
    """
    try:
        data = request.json or {}
        samples = data.get("samples")
        deep_check = data.get("deep_check", False)

        if not samples or not isinstance(samples, list):
            raise ValidationError("请提供训练样本列表 (samples)")

        detector = _get_detector()
        clean, rejected = detector.filter_clean_samples(samples, deep_check=deep_check)

        return jsonify({
            "success": True,
            "data": {
                "clean_samples": clean,
                "rejected_samples": rejected,
                "clean_count": len(clean),
                "rejected_count": len(rejected),
            },
            "message": f"过滤完成: {len(clean)} 条通过, {len(rejected)} 条被拦截"
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"投毒过滤失败: {str(e)}", exc_info=True)
        raise ValidationError(f"投毒过滤失败: {str(e)}")


@bp.post("/api/poison-detection/verify-single")
def verify_single_sample():
    """
    检测单条训练样本是否可疑

    请求体:
    {
        "sample": {...},           // 单条训练样本
        "deep_check": false        // 是否启用 LLM 深度校验
    }
    """
    try:
        data = request.json or {}
        sample = data.get("sample")
        deep_check = data.get("deep_check", False)

        if not sample or not isinstance(sample, dict):
            raise ValidationError("请提供训练样本 (sample)")

        detector = _get_detector()
        is_clean, issues = detector.detect_single(sample, deep_check=deep_check)

        return jsonify({
            "success": True,
            "data": {
                "is_clean": is_clean,
                "issues": issues,
            },
            "message": "样本安全" if is_clean else f"发现 {len(issues)} 个问题"
        })

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"单条检测失败: {str(e)}", exc_info=True)
        raise ValidationError(f"单条检测失败: {str(e)}")
