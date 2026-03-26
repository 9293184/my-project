"""训练数据集导出器"""
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatasetExporter:
    """数据集导出器 - 支持多种格式"""
    
    def __init__(self, output_dir: str = "datasets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_to_jsonl(
        self,
        samples: List[Dict],
        filename: str = None,
        format_type: str = "openai"
    ) -> str:
        """
        导出为 JSONL 格式（适用于 OpenAI fine-tuning）
        
        Args:
            samples: 样本列表
            filename: 输出文件名
            format_type: 格式类型 ('openai', 'huggingface', 'custom')
        
        Returns:
            输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.jsonl"
        
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                if format_type == "openai":
                    formatted = self._format_openai(sample)
                elif format_type == "huggingface":
                    formatted = self._format_huggingface(sample)
                else:
                    formatted = sample
                
                f.write(json.dumps(formatted, ensure_ascii=False) + '\n')
        
        logger.info(f"Exported {len(samples)} samples to {output_path}")
        return str(output_path)
    
    def _format_openai(self, sample: Dict) -> Dict:
        """格式化为 OpenAI fine-tuning 格式"""
        # OpenAI 格式：{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
        
        if "turns" in sample:
            # 多轮对话
            messages = []
            for i, turn in enumerate(sample["turns"]):
                messages.append({"role": "user", "content": turn})
                if i < len(sample["turns"]) - 1:
                    messages.append({"role": "assistant", "content": "请继续"})
            messages.append({"role": "assistant", "content": sample.get("safe_response", "")})
        else:
            # 单轮对话
            messages = [
                {"role": "user", "content": sample["text"]},
                {"role": "assistant", "content": sample.get("safe_response", "")}
            ]
        
        return {"messages": messages}
    
    def _format_huggingface(self, sample: Dict) -> Dict:
        """格式化为 HuggingFace 格式"""
        # HuggingFace 格式：{"text": "...", "label": ...}
        
        if "turns" in sample:
            text = "\n".join(sample["turns"])
        else:
            text = sample["text"]
        
        return {
            "text": text,
            "label": 1 if sample.get("is_attack", False) else 0,
            "attack_type": sample.get("attack_type", ""),
            "risk_level": sample.get("risk_level", 0),
            "response": sample.get("safe_response", "")
        }
    
    def export_to_csv(self, samples: List[Dict], filename: str = None) -> str:
        """导出为 CSV 格式"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.csv"
        
        output_path = self.output_dir / filename
        
        # 展平多轮对话
        flat_samples = []
        for sample in samples:
            if "turns" in sample:
                text = " | ".join(sample["turns"])
            else:
                text = sample.get("text", "")
            
            flat_samples.append({
                "id": sample.get("id", ""),
                "text": text,
                "attack_type": sample.get("attack_type", ""),
                "attack_type_cn": sample.get("attack_type_cn", ""),
                "risk_level": sample.get("risk_level", 0),
                "is_attack": sample.get("is_attack", False),
                "safe_response": sample.get("safe_response", "")
            })
        
        # 写入 CSV
        if flat_samples:
            fieldnames = flat_samples[0].keys()
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flat_samples)
        
        logger.info(f"Exported {len(samples)} samples to {output_path}")
        return str(output_path)
    
    def export_to_json(self, samples: List[Dict], filename: str = None) -> str:
        """导出为 JSON 格式"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported {len(samples)} samples to {output_path}")
        return str(output_path)
    
    def export_statistics(self, samples: List[Dict], filename: str = None) -> str:
        """导出数据集统计信息"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dataset_stats_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # 统计信息
        stats = {
            "total_samples": len(samples),
            "attack_samples": sum(1 for s in samples if s.get("is_attack", False)),
            "benign_samples": sum(1 for s in samples if not s.get("is_attack", False)),
            "attack_type_distribution": {},
            "risk_level_distribution": {},
            "multi_turn_samples": sum(1 for s in samples if "turns" in s),
        }
        
        # 攻击类型分布
        for sample in samples:
            attack_type = sample.get("attack_type", "unknown")
            stats["attack_type_distribution"][attack_type] = \
                stats["attack_type_distribution"].get(attack_type, 0) + 1
        
        # 风险等级分布
        for sample in samples:
            risk_level = sample.get("risk_level", 0)
            stats["risk_level_distribution"][str(risk_level)] = \
                stats["risk_level_distribution"].get(str(risk_level), 0) + 1
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported statistics to {output_path}")
        return str(output_path)
