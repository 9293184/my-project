"""训练数据投毒检测模块

在训练数据写入数据集之前，对每条样本进行质量审查，
检测标签一致性、异常样本和潜在的后门模式，防止投毒攻击。
"""
import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter

import requests

logger = logging.getLogger(__name__)


class PoisonDetector:
    """训练数据投毒检测器"""

    # 高风险关键词 —— 出现这些词的样本如果标签为"安全"则高度可疑
    HIGH_RISK_KEYWORDS = [
        "忽略", "ignore", "忘记", "forget", "覆盖", "override",
        "系统提示", "system prompt", "开发者模式", "developer mode",
        "DAN", "越狱", "jailbreak", "无限制", "no restriction",
        "泄露", "密钥", "api_key", "密码", "password",
        "base64", "rot13", "编码绕过",
    ]

    # 后门触发模式 —— 可能被用作后门触发词的异常模式
    BACKDOOR_PATTERNS = [
        r"\[TRIGGER\]",
        r"\[SAFE\]",
        r"\[BYPASS\]",
        r"<\|.*?\|>",
        r"###\s*OVERRIDE",
    ]

    def __init__(self, llm_url: str = None, llm_model: str = None, llm_api_key: str = None):
        """
        初始化投毒检测器

        Args:
            llm_url: LLM API 地址（用于深度标签一致性校验）
            llm_model: LLM 模型名称
            llm_api_key: LLM API 密钥
        """
        self.llm_url = llm_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key

    def detect_batch(self, samples: List[Dict], deep_check: bool = False) -> Dict[str, Any]:
        """
        批量检测训练数据是否存在投毒

        Args:
            samples: 训练样本列表
            deep_check: 是否启用 LLM 深度校验（较慢但更准确）

        Returns:
            检测报告，包含可疑样本列表和统计信息
        """
        results = {
            "total_samples": len(samples),
            "clean_samples": 0,
            "suspicious_samples": [],
            "statistics": {
                "label_inconsistency": 0,
                "backdoor_pattern": 0,
                "duplicate_anomaly": 0,
                "distribution_anomaly": 0,
            },
        }

        # 1. 规则检测（快速）
        for i, sample in enumerate(samples):
            issues = []

            # 1.1 标签一致性检查
            label_issue = self._check_label_consistency(sample)
            if label_issue:
                issues.append(label_issue)
                results["statistics"]["label_inconsistency"] += 1

            # 1.2 后门模式检测
            backdoor_issue = self._check_backdoor_patterns(sample)
            if backdoor_issue:
                issues.append(backdoor_issue)
                results["statistics"]["backdoor_pattern"] += 1

            if issues:
                results["suspicious_samples"].append({
                    "index": i,
                    "sample_id": sample.get("id", f"unknown_{i}"),
                    "text": self._truncate(sample.get("text", ""), 200),
                    "original_label": "attack" if sample.get("is_attack") else "safe",
                    "issues": issues,
                    "risk_level": "high" if len(issues) > 1 else "medium",
                })

        # 2. 分布异常检测（全局）
        distribution_issues = self._check_distribution_anomaly(samples)
        results["statistics"]["distribution_anomaly"] = len(distribution_issues)

        # 3. 重复/近似样本检测
        duplicate_issues = self._check_duplicates(samples)
        results["statistics"]["duplicate_anomaly"] = len(duplicate_issues)

        # 4. LLM 深度校验（可选）
        if deep_check and self.llm_url and self.llm_model:
            # 只对规则检测出的可疑样本做深度校验，节省资源
            suspicious_indices = {s["index"] for s in results["suspicious_samples"]}
            for item in results["suspicious_samples"]:
                idx = item["index"]
                llm_result = self._llm_label_verify(samples[idx])
                if llm_result:
                    item["llm_verification"] = llm_result
                    if llm_result.get("label_mismatch"):
                        item["risk_level"] = "critical"

        results["clean_samples"] = results["total_samples"] - len(results["suspicious_samples"])

        logger.info(
            f"投毒检测完成: {results['total_samples']} 条样本, "
            f"{len(results['suspicious_samples'])} 条可疑"
        )

        return results

    def detect_single(self, sample: Dict, deep_check: bool = False) -> Tuple[bool, List[str]]:
        """
        检测单条样本是否可疑

        Args:
            sample: 训练样本
            deep_check: 是否启用 LLM 深度校验

        Returns:
            (is_clean, issues) - 是否干净, 问题列表
        """
        issues = []

        label_issue = self._check_label_consistency(sample)
        if label_issue:
            issues.append(label_issue)

        backdoor_issue = self._check_backdoor_patterns(sample)
        if backdoor_issue:
            issues.append(backdoor_issue)

        if deep_check and self.llm_url and self.llm_model and issues:
            llm_result = self._llm_label_verify(sample)
            if llm_result and llm_result.get("label_mismatch"):
                issues.append(f"LLM校验: 标签不一致 - {llm_result.get('reason', '')}")

        return len(issues) == 0, issues

    def filter_clean_samples(self, samples: List[Dict], deep_check: bool = False) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤训练数据，返回干净样本和被拦截的样本

        Args:
            samples: 训练样本列表
            deep_check: 是否启用 LLM 深度校验

        Returns:
            (clean_samples, rejected_samples)
        """
        report = self.detect_batch(samples, deep_check=deep_check)

        suspicious_indices = {s["index"] for s in report["suspicious_samples"]}

        clean = []
        rejected = []
        for i, sample in enumerate(samples):
            if i in suspicious_indices:
                rejected.append(sample)
            else:
                clean.append(sample)

        logger.info(f"过滤结果: {len(clean)} 条通过, {len(rejected)} 条被拦截")
        return clean, rejected

    # ==================== 规则检测方法 ====================

    def _check_label_consistency(self, sample: Dict) -> Optional[str]:
        """
        检查标签一致性：
        - 包含高风险关键词但标签为"安全" → 可疑
        - 内容完全正常但标签为"攻击" → 可疑
        """
        text = sample.get("text", "")
        if isinstance(sample.get("turns"), list):
            text = " ".join(sample["turns"])

        text_lower = text.lower()
        is_attack = sample.get("is_attack", False)

        if not is_attack:
            # 标签为"安全"，但包含高风险关键词
            matched_keywords = [kw for kw in self.HIGH_RISK_KEYWORDS if kw.lower() in text_lower]
            if len(matched_keywords) >= 2:
                return f"标签为安全但包含高风险关键词: {', '.join(matched_keywords[:5])}"

        return None

    def _check_backdoor_patterns(self, sample: Dict) -> Optional[str]:
        """检测可能的后门触发模式"""
        text = sample.get("text", "")
        if isinstance(sample.get("turns"), list):
            text = " ".join(sample["turns"])

        for pattern in self.BACKDOOR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"检测到可疑后门模式: '{match.group()}'"

        return None

    def _check_distribution_anomaly(self, samples: List[Dict]) -> List[str]:
        """
        检测数据分布异常：
        - 某类攻击样本占比异常高或异常低
        - 标签比例严重失衡
        """
        issues = []

        if not samples:
            return issues

        # 标签分布
        attack_count = sum(1 for s in samples if s.get("is_attack", False))
        safe_count = len(samples) - attack_count

        if len(samples) > 10:
            attack_ratio = attack_count / len(samples)
            if attack_ratio > 0.95:
                issues.append(f"攻击样本占比异常高: {attack_ratio:.1%}")
            elif attack_ratio < 0.05 and attack_count > 0:
                issues.append(f"攻击样本占比异常低: {attack_ratio:.1%}")

        # 攻击类型分布
        type_counter = Counter(s.get("attack_type", "unknown") for s in samples if s.get("is_attack"))
        if len(type_counter) > 1:
            total_attacks = sum(type_counter.values())
            for attack_type, count in type_counter.items():
                ratio = count / total_attacks
                if ratio > 0.8:
                    issues.append(f"攻击类型 '{attack_type}' 占比异常高: {ratio:.1%}")

        return issues

    def _check_duplicates(self, samples: List[Dict]) -> List[str]:
        """检测重复或高度相似的样本"""
        issues = []
        texts = []

        for sample in samples:
            text = sample.get("text", "")
            if isinstance(sample.get("turns"), list):
                text = " ".join(sample["turns"])
            texts.append(text.strip())

        # 完全重复检测
        text_counter = Counter(texts)
        for text, count in text_counter.items():
            if count > 5 and text:
                issues.append(f"样本重复 {count} 次: '{text[:80]}...'")

        return issues

    # ==================== LLM 深度校验 ====================

    def _llm_label_verify(self, sample: Dict) -> Optional[Dict]:
        """
        使用 LLM 重新判断样本标签是否合理

        Returns:
            {"label_mismatch": bool, "llm_label": str, "reason": str} 或 None
        """
        text = sample.get("text", "")
        if isinstance(sample.get("turns"), list):
            text = " ".join(sample["turns"])

        original_label = "攻击" if sample.get("is_attack") else "安全"

        prompt = f"""你是一个AI安全数据质量审查专家。请判断以下训练样本的标签是否正确。

【样本内容】
{text[:500]}

【当前标签】{original_label}

请判断这个标签是否合理，按以下JSON格式回复（只返回JSON）：
{{"correct": true/false, "should_be": "攻击/安全", "reason": "判断理由"}}"""

        try:
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"

            response = requests.post(
                f"{self.llm_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 256,
                },
                timeout=15,
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return {
                        "label_mismatch": not data.get("correct", True),
                        "llm_label": data.get("should_be", ""),
                        "reason": data.get("reason", ""),
                    }
        except Exception as e:
            logger.warning(f"LLM 标签校验失败: {e}")

        return None

    # ==================== 工具方法 ====================

    @staticmethod
    def _truncate(text: str, max_len: int = 200) -> str:
        """截断文本"""
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
