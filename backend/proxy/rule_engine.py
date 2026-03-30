"""第一层规则引擎 — 基于正则/关键词的快速预筛

命中即拦截，未命中则交给第二层大模型 judge 做语义级深度审查。
规则参考来源：MCPScan tool-poisoning 检测模式 + OWASP LLM Top 10 + 常见中文攻击模式。

用法:
    from backend.proxy.rule_engine import RuleEngine
    engine = RuleEngine()
    result = engine.scan(text)
    if not result.safe:
        # 直接拦截
"""
import re
import base64
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  数据结构
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RuleHit:
    """单条规则命中记录"""
    rule_id: str
    category: str
    severity: str          # critical / high / medium / low
    pattern_name: str
    evidence: str          # 命中的文本片段（截断到 200 字符）
    description: str


@dataclass
class RuleScanResult:
    """规则引擎扫描结果"""
    safe: bool = True
    risk_score: int = 0
    hits: List[RuleHit] = field(default_factory=list)
    reason: str = ""

    def to_dict(self):
        return {
            "safe": self.safe,
            "risk_score": self.risk_score,
            "reason": self.reason,
            "hits": [
                {"rule_id": h.rule_id, "category": h.category,
                 "severity": h.severity, "pattern_name": h.pattern_name,
                 "evidence": h.evidence}
                for h in self.hits
            ],
        }


# ══════════════════════════════════════════════════════════════════════════════
#  规则定义
# ══════════════════════════════════════════════════════════════════════════════

# 严重度权重，用于计算 risk_score
_SEVERITY_WEIGHT = {"critical": 40, "high": 25, "medium": 15, "low": 5}


class _Rule:
    """一条正则规则"""
    __slots__ = ("rule_id", "category", "severity", "pattern_name",
                 "pattern", "description")

    def __init__(self, rule_id: str, category: str, severity: str,
                 pattern_name: str, pattern: re.Pattern, description: str):
        self.rule_id = rule_id
        self.category = category
        self.severity = severity
        self.pattern_name = pattern_name
        self.pattern = pattern
        self.description = description


def _build_rules() -> List[_Rule]:
    """构建全部规则列表"""
    rules: List[_Rule] = []
    _i = [0]  # 闭包计数器

    def add(category: str, severity: str, name: str,
            pattern: str, desc: str, flags: int = re.IGNORECASE):
        _i[0] += 1
        rules.append(_Rule(
            rule_id=f"RL-{_i[0]:03d}",
            category=category,
            severity=severity,
            pattern_name=name,
            pattern=re.compile(pattern, flags),
            description=desc,
        ))

    # ─── 1. 提示注入 — 指令覆盖（英文） ─────────────────────────────────
    add("prompt_injection", "critical",
        "指令覆盖: ignore previous",
        r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?|directives?)",
        "试图让模型忽略先前的系统指令")

    add("prompt_injection", "critical",
        "指令覆盖: disregard",
        r"disregard\s+(?:all\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions?|rules?|guidelines?)",
        "试图让模型无视先前指令")

    add("prompt_injection", "critical",
        "指令覆盖: override",
        r"override\s+(?:your\s+)?(?:instructions?|directives?|rules?|constraints?|guidelines?|safety)",
        "试图覆盖模型的安全约束")

    add("prompt_injection", "critical",
        "指令覆盖: new instruction",
        r"new\s+(?:primary\s+)?(?:instruction|directive|rule|task|objective)\s*:",
        "试图注入新的主指令")

    add("prompt_injection", "high",
        "指令覆盖: do not follow",
        r"do\s+not\s+(?:follow|obey|adhere\s+to|comply\s+with)\s+(?:your|any|the)\s+(?:previous|prior|original|system|safety)",
        "试图让模型不遵守安全策略")

    add("prompt_injection", "high",
        "指令覆盖: from now on",
        r"(?:from\s+now\s+on|henceforth|going\s+forward)[,:]?\s+(?:you|act|behave|respond|your)",
        "试图重新定义模型后续行为")

    # ─── 2. 提示注入 — 指令覆盖（中文） ─────────────────────────────────
    add("prompt_injection", "critical",
        "指令覆盖: 忽略之前指令",
        r"(?:忽略|无视|忘记|抛弃|丢掉|放弃)(?:你的|所有|全部|之前的?|上面的?|先前的?)?(?:指令|规则|提示词?|系统提示|安全策略|限制|约束|设定)",
        "中文形式的指令覆盖攻击")

    add("prompt_injection", "critical",
        "指令覆盖: 新指令",
        r"(?:现在|从现在开始|接下来)(?:你的)?(?:新|唯一的?)?(?:指令|任务|目标|规则|身份)\s*(?:是|为|：|:)",
        "中文形式的新指令注入")

    add("prompt_injection", "high",
        "指令覆盖: 不要遵守",
        r"(?:不要|不用|不必|无需|别)(?:再)?(?:遵守|遵循|执行|听从|服从)(?:你的|之前的?|原来的?|系统的?)?(?:指令|规则|限制|约束|策略|设定)",
        "中文形式的指令违抗攻击")

    # ─── 3. 角色扮演/越狱（英文） ───────────────────────────────────────
    add("jailbreak", "high",
        "角色扮演: you are now",
        r"you\s+are\s+now\s+(?:a|an|the|my)\s+\w",
        "试图通过角色重新定义绕过安全限制")

    add("jailbreak", "high",
        "角色扮演: pretend to be",
        r"pretend\s+(?:you\s+are|to\s+be|you'?re)\s+(?:a|an|the|my)\s+\w",
        "试图通过假扮角色绕过安全限制")

    add("jailbreak", "high",
        "角色扮演: act as",
        r"(?:act|behave|respond|function)\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a|an|the|my)\s+\w",
        "试图通过角色指派绕过安全限制")

    add("jailbreak", "critical",
        "已知越狱模式: DAN/Developer Mode",
        r"(?:DAN\s+mode|developer\s+mode\s+enabled|DUDE\s+mode|AIM\s+mode|maximum\s+mode|evil\s+mode)",
        "已知的越狱攻击模板名称")

    add("jailbreak", "critical",
        "越狱关键词",
        r"\bjailbreak(?:ed|ing)?\b",
        "直接包含 jailbreak 关键词")

    # ─── 4. 角色扮演/越狱（中文） ───────────────────────────────────────
    add("jailbreak", "high",
        "角色扮演: 你现在是",
        r"(?:你现在是|你的身份是|你要扮演|请你扮演|假装你是|假设你是|你是一个?(?:没有|不受|不被)(?:限制|约束|监管)的)",
        "中文形式的角色劫持攻击")

    add("jailbreak", "high",
        "越狱: 进入模式",
        r"(?:进入|切换到?|开启|启动|激活)\s*(?:开发者|无限制|自由|越狱|DAN|邪恶|暗黑|真实)\s*模式",
        "中文形式的越狱模式切换")

    add("jailbreak", "medium",
        "越狱: 虚构场景",
        r"(?:在一个虚构的?|在一个假想的?|在小说中|在故事里|在游戏中)(?:世界|场景|情境|设定)(?:中|里|下)?[，,]?\s*(?:你|AI|助手)",
        "通过虚构场景绕过安全限制")

    # ─── 5. 系统提示词提取 ──────────────────────────────────────────────
    add("info_extraction", "high",
        "系统提示词提取: 英文",
        r"(?:(?:show|reveal|display|output|print|repeat|tell\s+me|what\s+(?:is|are))\s+(?:your\s+)?(?:system\s+prompt|initial\s+(?:prompt|instruction)|hidden\s+(?:prompt|instruction)|pre-?prompt|(?:original|full)\s+(?:prompt|instruction)))",
        "试图提取系统提示词")

    add("info_extraction", "high",
        "系统提示词提取: 中文",
        r"(?:告诉我|输出|显示|展示|复述|重复|泄露|透露)(?:你的)?(?:系统提示词?|初始指令|隐藏指令|预设提示|系统设定|系统角色|完整提示词?|原始指令)",
        "中文形式的系统提示词提取")

    add("info_extraction", "high",
        "系统提示词提取: verbatim",
        r"(?:repeat|recite|echo)\s+(?:your\s+)?(?:instructions?|prompt|rules?)\s+(?:verbatim|word\s+for\s+word|exactly|in\s+full)",
        "要求逐字复述系统指令")

    # ─── 6. 模型特殊标记利用 ────────────────────────────────────────────
    add("token_smuggling", "critical",
        "模型标记注入: Llama/ChatML",
        r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>",
        "注入模型训练时使用的特殊标记，试图伪造系统/用户/助手角色边界")

    add("token_smuggling", "high",
        "模型标记注入: XML系统标签",
        r"<(?:SYSTEM|system)[\s>]|</(?:SYSTEM|system)>|<(?:human|assistant|user|bot)[\s>]",
        "注入 XML 格式的系统/角色标签")

    # ─── 7. 隐藏 Unicode 字符 ──────────────────────────────────────────
    add("obfuscation", "high",
        "隐藏Unicode字符",
        r"[\u200B-\u200F\u202A-\u202E\u2060-\u2064\u206A-\u206F\u2800\uFEFF\u180E]",
        "包含零宽字符、RTL覆盖符等人眼不可见的 Unicode 字符，可能用于隐藏恶意指令",
        flags=re.UNICODE)

    # ─── 8. 编码绕过 ────────────────────────────────────────────────────
    add("obfuscation", "medium",
        "Base64编码载荷",
        r"(?:base64|decode|atob|b64decode)\s*[\(（]\s*['\"]?[A-Za-z0-9+/]{20,}={0,2}",
        "包含 Base64 解码调用，可能藏匿恶意载荷")

    add("obfuscation", "medium",
        "十六进制/Unicode转义序列",
        r"(?:\\x[0-9a-fA-F]{2}){4,}|(?:\\u[0-9a-fA-F]{4}){3,}",
        "包含连续的十六进制或 Unicode 转义序列，可能用于混淆攻击内容")

    # ─── 9. Markdown/HTML 外泄 ─────────────────────────────────────────
    add("exfiltration", "high",
        "Markdown图片外泄",
        r"!\[.*?\]\(https?://(?!localhost|127\.\d+\.\d+\.\d+)[^\)]+\)",
        "Markdown 图片语法指向外部 URL，可能用于数据外泄")

    add("exfiltration", "medium",
        "HTML标签注入",
        r"<(?:script|iframe|img|object|embed|form|link|meta)\s[^>]*(?:src|href|action)\s*=\s*['\"]?https?://",
        "HTML 标签引用外部资源，可能用于数据外泄或 XSS")

    # ─── 10. 敏感操作指令 ───────────────────────────────────────────────
    add("dangerous_command", "high",
        "危险系统命令",
        r"(?:^|\s)(?:rm\s+-rf|sudo\s+|chmod\s+777|mkfs\.|dd\s+if=|:\(\)\s*\{|fork\s+bomb|wget\s+.*\|\s*(?:bash|sh)|curl\s+.*\|\s*(?:bash|sh))",
        "包含危险的系统命令模式")

    add("dangerous_command", "medium",
        "代码执行意图",
        r"(?:exec|eval|subprocess|os\.system|os\.popen|__import__|compile)\s*\(",
        "包含 Python 代码执行函数调用")

    # ─── 11. 敏感信息模式 ───────────────────────────────────────────────
    add("credential_leak", "high",
        "API密钥泄露: OpenAI/Anthropic",
        r"sk-(?:proj-)?[A-Za-z0-9\-_T]{32,}|sk-ant-(?:api\d{2}-)?[A-Za-z0-9\-_]{32,}",
        "检测到可能的 OpenAI 或 Anthropic API 密钥")

    add("credential_leak", "high",
        "API密钥泄露: AWS",
        r"AKIA[A-Z0-9]{16}",
        "检测到可能的 AWS Access Key ID")

    add("credential_leak", "medium",
        "私钥材料",
        r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----",
        "检测到私钥材料")

    # ─── 12. 违规内容关键词（中文） ──────────────────────────────────────
    add("prohibited_content", "high",
        "违规内容: 违法犯罪",
        r"(?:如何|怎么|教我|帮我|方法|步骤|教程).{0,10}(?:制造|制作|合成|配制|获取)\s*(?:炸弹|炸药|毒药|毒品|枪支|武器|管制刀具)",
        "请求违法犯罪相关的具体操作方法")

    add("prohibited_content", "high",
        "违规内容: 自伤自杀",
        r"(?:如何|怎么|方法|最好的方式).{0,10}(?:自杀|自残|自伤|结束生命|了结自己)",
        "涉及自伤自杀的方法请求")

    add("prohibited_content", "medium",
        "违规内容: 网络攻击",
        r"(?:如何|怎么|教我|帮我|方法).{0,10}(?:入侵|黑进|攻破|渗透|破解|绕过防火墙|DDoS|SQL注入|XSS攻击|提权)",
        "请求网络攻击/入侵的具体方法")

    return rules


# ══════════════════════════════════════════════════════════════════════════════
#  规则引擎
# ══════════════════════════════════════════════════════════════════════════════

class RuleEngine:
    """第一层规则引擎

    快速正则预筛，命中直接拦截；未命中交给第二层大模型 judge。
    阈值可按 proxy task 独立配置。

    Args:
        block_threshold: 风险分阈值，达到即拦截（默认 40，即一条 critical 命中）
    """

    # 所有规则分类（供前端展示用）
    ALL_CATEGORIES = {
        "prompt_injection": "提示注入/指令覆盖",
        "jailbreak": "越狱/角色扮演",
        "info_extraction": "系统提示词提取",
        "token_smuggling": "模型标记注入",
        "obfuscation": "编码混淆/隐藏字符",
        "exfiltration": "数据外泄",
        "dangerous_command": "危险命令",
        "credential_leak": "凭证泄露",
        "prohibited_content": "违规内容",
    }

    def __init__(self, block_threshold: int = 40):
        self.rules = _build_rules()
        self.block_threshold = block_threshold
        logger.info(f"[rule_engine] 已加载 {len(self.rules)} 条规则，拦截阈值={block_threshold}")

    def scan(self, text: str) -> RuleScanResult:
        """扫描文本，返回规则命中结果"""
        if not text or not text.strip():
            return RuleScanResult(safe=True, risk_score=0, reason="空内容")

        hits: List[RuleHit] = []
        score = 0

        for rule in self.rules:
            match = rule.pattern.search(text)
            if match:
                evidence = match.group()
                if len(evidence) > 200:
                    evidence = evidence[:200] + "…"

                hits.append(RuleHit(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    pattern_name=rule.pattern_name,
                    evidence=evidence,
                    description=rule.description,
                ))
                score += _SEVERITY_WEIGHT.get(rule.severity, 10)

        safe = score < self.block_threshold
        reason = ""
        if hits:
            top = hits[0]
            reason = f"[{top.rule_id}] {top.pattern_name}: {top.description}"
            if len(hits) > 1:
                reason += f"（共命中 {len(hits)} 条规则）"

        # 上限 100
        score = min(score, 100)

        return RuleScanResult(
            safe=safe,
            risk_score=score,
            hits=hits,
            reason=reason,
        )

    def scan_input(self, content: str) -> RuleScanResult:
        """扫描用户输入（别名）"""
        return self.scan(content)

    def scan_output(self, content: str) -> RuleScanResult:
        """扫描模型输出 — 侧重凭证泄露和外泄检测"""
        return self.scan(content)
