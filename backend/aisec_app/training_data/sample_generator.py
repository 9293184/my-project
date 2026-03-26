"""训练样本生成器"""
import random
import logging
from typing import List, Dict, Any
from .attack_templates import (
    PROMPT_INJECTION_TEMPLATES,
    JAILBREAK_TEMPLATES,
    INFORMATION_EXTRACTION_TEMPLATES,
    MULTI_TURN_ATTACK_TEMPLATES,
    MALICIOUS_INTENTS,
    BENIGN_FUNCTIONS,
    ATTACK_TYPES,
    RISK_LEVELS,
)

logger = logging.getLogger(__name__)


class SampleGenerator:
    """训练样本生成器"""
    
    def __init__(self):
        self.templates = {
            "prompt_injection": PROMPT_INJECTION_TEMPLATES,
            "jailbreak": JAILBREAK_TEMPLATES,
            "information_extraction": INFORMATION_EXTRACTION_TEMPLATES,
            "multi_turn": MULTI_TURN_ATTACK_TEMPLATES,
        }
    
    def generate_samples(
        self,
        attack_type: str,
        num_samples: int = 100,
        include_safe_response: bool = True
    ) -> List[Dict[str, Any]]:
        """
        生成训练样本
        
        Args:
            attack_type: 攻击类型
            num_samples: 生成数量
            include_safe_response: 是否包含安全回复
        
        Returns:
            样本列表
        """
        samples = []
        
        if attack_type == "multi_turn":
            samples = self._generate_multi_turn_samples(num_samples)
        else:
            samples = self._generate_single_turn_samples(attack_type, num_samples)
        
        if include_safe_response:
            samples = [self._add_safe_response(s) for s in samples]
        
        return samples
    
    def _generate_single_turn_samples(self, attack_type: str, num_samples: int) -> List[Dict]:
        """生成单轮对话样本"""
        templates = self.templates.get(attack_type, [])
        if not templates:
            logger.warning(f"Unknown attack type: {attack_type}")
            return []
        
        samples = []
        for i in range(num_samples):
            template = random.choice(templates)
            
            # 填充模板
            if "{malicious_intent}" in template:
                intent = random.choice(MALICIOUS_INTENTS)
                text = template.format(malicious_intent=intent)
            else:
                text = template
            
            sample = {
                "id": f"{attack_type}_{i+1}",
                "text": text,
                "attack_type": attack_type,
                "attack_type_cn": ATTACK_TYPES.get(attack_type, "未知"),
                "risk_level": self._estimate_risk_level(text),
                "is_attack": True,
                "metadata": {
                    "template": template,
                    "generated_by": "auto",
                }
            }
            samples.append(sample)
        
        return samples
    
    def _generate_multi_turn_samples(self, num_samples: int) -> List[Dict]:
        """生成多轮对话样本"""
        samples = []
        
        for i in range(num_samples):
            template = random.choice(MULTI_TURN_ATTACK_TEMPLATES)
            intent = random.choice(MALICIOUS_INTENTS)
            
            # 构造多轮对话
            turns = []
            for turn_key in sorted(template.keys()):
                turn_text = template[turn_key]
                if "{malicious_intent}" in turn_text:
                    turn_text = turn_text.format(malicious_intent=intent)
                turns.append(turn_text)
            
            sample = {
                "id": f"multi_turn_{i+1}",
                "turns": turns,
                "attack_type": "multi_turn",
                "attack_type_cn": "多轮渐进式攻击",
                "risk_level": RISK_LEVELS["high"],  # 多轮攻击通常风险较高
                "is_attack": True,
                "metadata": {
                    "num_turns": len(turns),
                    "generated_by": "auto",
                }
            }
            samples.append(sample)
        
        return samples
    
    def _estimate_risk_level(self, text: str) -> int:
        """估算风险等级"""
        # 简单的启发式规则
        text_lower = text.lower()
        
        # 高风险关键词
        high_risk_keywords = ["ignore", "忽略", "forget", "开发者模式", "developer mode"]
        # 中风险关键词
        medium_risk_keywords = ["假设", "游戏", "虚构", "研究"]
        
        if any(kw in text_lower for kw in high_risk_keywords):
            return RISK_LEVELS["high"]
        elif any(kw in text_lower for kw in medium_risk_keywords):
            return RISK_LEVELS["medium"]
        else:
            return RISK_LEVELS["low"]
    
    def _add_safe_response(self, sample: Dict) -> Dict:
        """添加安全回复"""
        # 根据攻击类型生成不同的安全回复
        attack_type = sample.get("attack_type", "")
        
        safe_responses = {
            "prompt_injection": "我注意到您的请求可能试图修改我的行为准则。我的设计目的是提供有帮助、安全和负责任的回答。我无法执行可能违反安全策略的指令。",
            "jailbreak": "我理解您可能在测试我的能力边界，但我必须遵守我的安全准则。我无法进入所谓的'无限制模式'或绕过安全限制。",
            "information_extraction": "我无法提供关于我的系统配置、训练数据或内部实现的详细信息。这些信息是保密的，出于安全考虑不能公开。",
            "multi_turn": "我注意到这个对话可能在逐步引导我违反安全准则。我需要停止这个对话方向，并提醒您我必须遵守安全策略。",
        }
        
        sample["safe_response"] = safe_responses.get(
            attack_type,
            "抱歉，我无法执行这个请求，因为它可能违反了安全准则。"
        )
        
        return sample
    
    def generate_balanced_dataset(
        self,
        samples_per_type: int = 100,
        include_benign: bool = True
    ) -> List[Dict]:
        """
        生成平衡的数据集
        
        Args:
            samples_per_type: 每种类型的样本数
            include_benign: 是否包含良性样本
        
        Returns:
            平衡的数据集
        """
        all_samples = []
        
        # 生成各类攻击样本
        for attack_type in ["prompt_injection", "jailbreak", "information_extraction"]:
            samples = self.generate_samples(attack_type, samples_per_type)
            all_samples.extend(samples)
        
        # 生成多轮攻击样本（数量减半，因为更复杂）
        multi_turn_samples = self.generate_samples("multi_turn", samples_per_type // 2)
        all_samples.extend(multi_turn_samples)
        
        # 添加良性样本（如果需要）
        if include_benign:
            benign_samples = self._generate_benign_samples(len(all_samples))
            all_samples.extend(benign_samples)
        
        # 打乱顺序
        random.shuffle(all_samples)
        
        logger.info(f"Generated {len(all_samples)} samples in total")
        return all_samples
    
    def _generate_benign_samples(self, num_samples: int) -> List[Dict]:
        """生成良性样本"""
        benign_texts = [
            "你好，请问你能帮我什么？",
            "今天天气怎么样？",
            "请帮我写一个Python函数计算斐波那契数列",
            "什么是机器学习？",
            "请推荐一些学习编程的资源",
            "如何提高工作效率？",
            "请解释一下什么是区块链",
            "能给我讲个笑话吗？",
        ]
        
        samples = []
        for i in range(num_samples):
            text = random.choice(benign_texts)
            sample = {
                "id": f"benign_{i+1}",
                "text": text,
                "attack_type": "benign",
                "attack_type_cn": "正常对话",
                "risk_level": 0,
                "is_attack": False,
                "safe_response": "这是一个正常的请求，我很乐意帮助您。",
                "metadata": {
                    "generated_by": "auto",
                }
            }
            samples.append(sample)
        
        return samples
