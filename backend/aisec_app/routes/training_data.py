"""训练数据生成 API"""
import logging
from flask import Blueprint, current_app, jsonify, request

from ..training_data.sample_generator import SampleGenerator
from ..training_data.dataset_exporter import DatasetExporter
from ..training_data.poison_detector import PoisonDetector
from ..errors import ValidationError

logger = logging.getLogger(__name__)

bp = Blueprint("training_data", __name__)


@bp.post("/api/training-data/generate")
def generate_training_data():
    """生成训练数据"""
    try:
        data = request.json or {}
        
        # 参数验证
        attack_types = data.get("attack_types", ["prompt_injection", "jailbreak", "information_extraction"])
        samples_per_type = data.get("samples_per_type", 100)
        include_benign = data.get("include_benign", True)
        export_format = data.get("export_format", "jsonl")  # jsonl, csv, json
        format_type = data.get("format_type", "openai")  # openai, huggingface, custom
        
        # 生成样本
        generator = SampleGenerator()
        
        if "all" in attack_types:
            # 生成平衡数据集
            samples = generator.generate_balanced_dataset(
                samples_per_type=samples_per_type,
                include_benign=include_benign
            )
        else:
            # 生成指定类型
            samples = []
            for attack_type in attack_types:
                type_samples = generator.generate_samples(
                    attack_type=attack_type,
                    num_samples=samples_per_type,
                    include_safe_response=True
                )
                samples.extend(type_samples)
            
            # 添加良性样本
            if include_benign:
                benign_samples = generator._generate_benign_samples(len(samples))
                samples.extend(benign_samples)
        
        # 投毒检测（自动过滤可疑样本）
        enable_poison_check = data.get("enable_poison_check", True)
        poison_report = None
        if enable_poison_check:
            detector = PoisonDetector()
            poison_report = detector.detect_batch(samples)
            if poison_report["suspicious_samples"]:
                suspicious_indices = {s["index"] for s in poison_report["suspicious_samples"]}
                samples = [s for i, s in enumerate(samples) if i not in suspicious_indices]
                logger.info(f"投毒检测: 过滤了 {len(suspicious_indices)} 条可疑样本")

        # 导出数据
        exporter = DatasetExporter(output_dir="d:/langchain2.0/datasets")
        
        if export_format == "jsonl":
            file_path = exporter.export_to_jsonl(samples, format_type=format_type)
        elif export_format == "csv":
            file_path = exporter.export_to_csv(samples)
        elif export_format == "json":
            file_path = exporter.export_to_json(samples)
        else:
            raise ValidationError(f"不支持的导出格式: {export_format}")
        
        # 生成统计信息
        stats_path = exporter.export_statistics(samples)
        
        result_data = {
            "total_samples": len(samples),
            "file_path": file_path,
            "stats_path": stats_path,
            "preview": samples[:5],
        }
        if poison_report:
            result_data["poison_check"] = {
                "enabled": True,
                "suspicious_count": len(poison_report["suspicious_samples"]),
                "suspicious_samples": poison_report["suspicious_samples"][:10],
                "statistics": poison_report["statistics"],
            }

        return jsonify({
            "success": True,
            "data": result_data,
            "message": f"成功生成 {len(samples)} 条训练样本"
        })
    
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to generate training data: {str(e)}", exc_info=True)
        raise ValidationError(f"生成训练数据失败: {str(e)}")


@bp.get("/api/training-data/templates")
def get_attack_templates():
    """获取攻击模板列表"""
    try:
        from ..training_data.attack_templates import (
            ATTACK_TYPES,
            RISK_LEVELS,
            PROMPT_INJECTION_TEMPLATES,
            JAILBREAK_TEMPLATES,
        )
        
        return jsonify({
            "success": True,
            "data": {
                "attack_types": ATTACK_TYPES,
                "risk_levels": RISK_LEVELS,
                "template_counts": {
                    "prompt_injection": len(PROMPT_INJECTION_TEMPLATES),
                    "jailbreak": len(JAILBREAK_TEMPLATES),
                },
                "supported_formats": ["jsonl", "csv", "json"],
                "format_types": ["openai", "huggingface", "custom"]
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to get templates: {str(e)}", exc_info=True)
        raise ValidationError("获取模板失败")


@bp.post("/api/training-data/preview")
def preview_samples():
    """预览生成的样本（不导出文件）"""
    try:
        data = request.json or {}
        attack_type = data.get("attack_type", "prompt_injection")
        num_samples = min(data.get("num_samples", 10), 50)  # 最多预览50条
        
        generator = SampleGenerator()
        samples = generator.generate_samples(
            attack_type=attack_type,
            num_samples=num_samples,
            include_safe_response=True
        )
        
        return jsonify({
            "success": True,
            "data": {
                "samples": samples,
                "count": len(samples)
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to preview samples: {str(e)}", exc_info=True)
        raise ValidationError("预览样本失败")
