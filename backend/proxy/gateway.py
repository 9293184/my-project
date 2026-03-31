"""透明审查代理网关

纯透传设计 — 代理不关心上游是谁，只负责：
1. 接收客户端请求
2. 输入审查（可选）
3. 原样转发到用户指定的上游 URL
4. 输出审查（可选）
5. 全量日志记录（打开黑盒）
6. 返回给客户端

流程：
  客户端 POST → 代理(审查+记录) → upstream_url/chat/completions
  客户端 ← 代理(审查+记录) ← upstream 响应
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional

import re as _re

import requests

from .audit import AuditEngine, AuditResult
from .rule_engine import RuleEngine
from .logger import ProxyLogEntry, save_log

logger = logging.getLogger(__name__)

# ─── 配置 ─────────────────────────────────────────────

MAX_RETRY_ATTEMPTS = 3
FETCH_TIMEOUT_S = 60
RETRY_BACKOFF_BASE = 1.0  # 1s, 2s, 4s ...


def _retry_delay(attempt: int) -> float:
    return min(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)), 8.0)


def _should_retry(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _extract_usage(data: Dict[str, Any]) -> Dict[str, int]:
    """从 OpenAI 兼容响应中提取 token 用量"""
    usage = data.get("usage", {})
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": usage.get("total_tokens", prompt + completion),
    }


def _extract_response_text(data: Dict[str, Any]) -> str:
    """从 OpenAI 兼容响应中提取回复文本"""
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return ""


# ─── 代理转发结果 ──────────────────────────────────────

class ForwardResult:
    def __init__(self):
        self.success: bool = False
        self.status_code: int = 0
        self.response_data: Optional[Dict] = None
        self.response_text: str = ""
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.latency_ms: int = 0
        self.error: str = ""
        self.retry_attempts: int = 0
        self.input_audit: Optional[AuditResult] = None
        self.output_audit: Optional[AuditResult] = None
        self.blocked: bool = False
        self.block_type: str = ""  # "input" or "output"


# ─── 核心透传转发 ─────────────────────────────────────

def _match_custom_regex(text: str, rules: list) -> list:
    """对文本执行自定义正则规则匹配

    Args:
        text: 待匹配文本
        rules: 自定义规则列表，每项为 {"pattern": "正则表达式", "label": "规则名称"}

    Returns:
        命中列表，每项为 {"pattern": "...", "label": "...", "matched": "..."}
    """
    hits = []
    for rule in rules:
        pattern = rule.get("pattern", "")
        label = rule.get("label", "未命名规则")
        if not pattern:
            continue
        try:
            m = _re.search(pattern, text, _re.IGNORECASE)
            if m:
                matched = m.group()
                if len(matched) > 200:
                    matched = matched[:200] + "…"
                hits.append({"pattern": pattern, "label": label, "matched": matched})
        except _re.error as e:
            logger.warning(f"[proxy] 自定义正则编译失败「{label}」: {e}")
    return hits


def _run_audit_pipeline(
    text: str,
    direction: str,
    side_cfg: dict,
    audit_engine: Optional[AuditEngine],
    security_prompt: str,
    context_summary: str,
    request_id: str,
) -> Optional[AuditResult]:
    """执行单侧（输入/输出）的多层审查流水线

    流程：
      1. 内置规则引擎（如启用）
      2. 自定义正则（如启用）
      3. 大模型 judge（如启用）

    各层的 action 决定行为：
      - "block": 命中后直接产生不安全结果
      - "enhance": 命中后将信息传给大模型做增强确认

    Returns:
        AuditResult 或 None（全部跳过时）
    """
    if not side_cfg.get("enabled", True):
        return None

    block_threshold = side_cfg.get("block_threshold", 60)
    builtin_cfg = side_cfg.get("builtin_rules", {})
    custom_cfg = side_cfg.get("custom_regex", {})
    llm_cfg = side_cfg.get("llm_judge", {})

    all_regex_hints = []  # 收集所有 "enhance" 模式的命中信息
    blocked_result = None  # 被 "block" 模式直接拦截的结果

    # ── 第一层：内置规则引擎（规则不可更改，始终使用全部分类） ──
    if builtin_cfg.get("enabled", False):
        engine = RuleEngine()
        rule_result = engine.scan(text)

        if rule_result.hits:
            action = builtin_cfg.get("action", "block")
            logger.info(
                f"[proxy:{request_id}] {direction}内置规则命中 {len(rule_result.hits)} 条 "
                f"(action={action}): {rule_result.reason[:80]}"
            )
            if action == "block" and not rule_result.safe:
                blocked_result = AuditResult(
                    safe=False,
                    risk_score=rule_result.risk_score,
                    reason=f"[内置规则] {rule_result.reason}",
                    summary=f"内置规则引擎拦截：{rule_result.hits[0].pattern_name}",
                )
            elif action == "enhance":
                for h in rule_result.hits:
                    all_regex_hints.append({
                        "label": f"[内置]{h.pattern_name}",
                        "pattern": "",
                        "matched": h.evidence,
                    })

    # 如果已被 block，直接返回
    if blocked_result:
        return blocked_result

    # ── 第二层：自定义正则 ──
    if custom_cfg.get("enabled", False):
        rules = custom_cfg.get("rules", [])
        if rules:
            regex_hits = _match_custom_regex(text, rules)
            if regex_hits:
                action = custom_cfg.get("action", "enhance")
                logger.info(
                    f"[proxy:{request_id}] {direction}自定义正则命中 {len(regex_hits)} 条 "
                    f"(action={action})"
                )
                if action == "block":
                    labels = ", ".join(h["label"] for h in regex_hits)
                    blocked_result = AuditResult(
                        safe=False,
                        risk_score=80,
                        reason=f"[自定义正则] 命中: {labels}",
                        summary=f"自定义正则直接拦截：{labels[:60]}",
                    )
                elif action == "enhance":
                    all_regex_hints.extend(regex_hits)

    if blocked_result:
        return blocked_result

    # ── 第三层：大模型 judge ──
    if llm_cfg.get("enabled", False) and audit_engine:
        if all_regex_hints:
            logger.info(
                f"[proxy:{request_id}] {direction}规则命中 {len(all_regex_hints)} 条，"
                f"交由大模型增强确认..."
            )
            if direction == "输入":
                audit_result = audit_engine.audit_input_with_regex_hint(
                    text, all_regex_hints, security_prompt, context_summary
                )
            else:
                audit_result = audit_engine.audit_output(text, security_prompt, context_summary)
        else:
            logger.info(f"[proxy:{request_id}] {direction}大模型审查中...")
            if direction == "输入":
                audit_result = audit_engine.audit_input(text, security_prompt, context_summary)
            else:
                audit_result = audit_engine.audit_output(text, security_prompt, context_summary)
        return audit_result

    # 大模型未启用但有 enhance 命中 → 作为风险返回
    if all_regex_hints:
        labels = ", ".join(h["label"] for h in all_regex_hints)
        return AuditResult(
            safe=False,
            risk_score=50,
            reason=f"[规则命中] {labels}（大模型未启用，无法二次确认）",
            summary=f"规则命中但大模型未启用: {labels[:60]}",
        )

    # 所有策略层均跳过
    return AuditResult(safe=True, risk_score=0, reason="审查通过")


def forward_chat(
    upstream_url: str,
    body: Dict[str, Any],
    client_headers: Dict[str, str] = None,
    api_key: str = None,
    audit_engine: Optional[AuditEngine] = None,
    security_prompt: str = "",
    context_summary: str = "",
    audit_config: dict = None,
    client_ip: str = "",
    max_retries: int = MAX_RETRY_ATTEMPTS,
    timeout: int = FETCH_TIMEOUT_S,
) -> ForwardResult:
    """
    透明代理转发 — 原样转发到用户指定的上游 URL

    Args:
        upstream_url: 上游 API 地址
        body: 请求体（OpenAI 兼容格式）
        client_headers: 客户端原始请求头（透传给上游）
        api_key: 上游 API Key（仅在 client_headers 无 Authorization 时使用）
        audit_engine: 大模型审查引擎实例
        security_prompt: 安全策略文本
        context_summary: 历史对话摘要
        audit_config: 审查策略配置（单方向，含 direction 字段）
        client_ip: 客户端IP
        max_retries: 最大重试次数
        timeout: 单次请求超时（秒）
    """
    result = ForwardResult()
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    model = body.get("model", "unknown")
    url = f"{upstream_url.rstrip('/')}/chat/completions"

    # ─── 1. 提取用户消息用于审查 ───
    user_content = ""
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            if isinstance(user_content, list):
                user_content = " ".join(
                    b.get("text", "") for b in user_content if b.get("type") == "text"
                )
            break

    # ─── 2. 输入审查（direction=input 或 both 时执行） ───
    cfg = audit_config or {}
    audit_direction = cfg.get("direction", "input")
    if audit_direction in ("input", "both") and user_content and cfg.get("enabled", True):
        input_audit = _run_audit_pipeline(
            text=user_content,
            direction="输入",
            side_cfg=cfg,
            audit_engine=audit_engine,
            security_prompt=security_prompt,
            context_summary=context_summary,
            request_id=request_id,
        )
        result.input_audit = input_audit

        block_threshold = cfg.get("block_threshold", 60)
        if input_audit and not input_audit.safe and input_audit.risk_score >= block_threshold:
            result.blocked = True
            result.block_type = "input"
            result.status_code = 200
            result.latency_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"[proxy:{request_id}] 输入被拦截 (score={input_audit.risk_score}): "
                f"{input_audit.reason[:100]}"
            )
            _save_forward_log(request_id, url, model, body, None, result, client_ip)
            return result

    # ─── 3. 原样转发到上游（透传客户端请求头） ───
    headers = {}
    if client_headers:
        # 透传客户端原始请求头，排除 hop-by-hop 头和 Host
        _skip = {"host", "content-length", "transfer-encoding", "connection", "keep-alive"}
        for k, v in client_headers.items():
            if k.lower() not in _skip:
                headers[k] = v
    # 确保 Content-Type 存在
    if "Content-Type" not in headers and "content-type" not in headers:
        headers["Content-Type"] = "application/json"
    # 仅当客户端未带 Authorization 且代理项目配了 api_key 时才补充（向下兼容）
    has_auth = any(k.lower() == "authorization" for k in headers)
    if not has_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_error = ""
    upstream_resp = None

    for attempt in range(1, max_retries + 1):
        result.retry_attempts = attempt
        try:
            upstream_resp = requests.post(
                url, headers=headers, json=body, timeout=timeout,
            )
        except requests.exceptions.Timeout:
            last_error = f"请求超时 ({timeout}s)"
            logger.warning(f"[proxy:{request_id}] 超时 (attempt {attempt})")
            if attempt < max_retries:
                time.sleep(_retry_delay(attempt))
                continue
            break
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.warning(f"[proxy:{request_id}] 网络错误 (attempt {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(_retry_delay(attempt))
                continue
            break

        if upstream_resp.status_code < 400:
            break

        last_error = f"HTTP {upstream_resp.status_code}"
        if _should_retry(upstream_resp.status_code) and attempt < max_retries:
            delay = _retry_delay(attempt)
            logger.info(f"[proxy:{request_id}] 重试 ({upstream_resp.status_code}), 等待 {delay}s")
            time.sleep(delay)
            continue
        break

    # ─── 4. 处理上游响应 ───
    if upstream_resp is None:
        result.error = f"上游请求失败: {last_error}"
        result.status_code = 502
        result.latency_ms = int((time.time() - start_time) * 1000)
        _save_forward_log(request_id, url, model, body, None, result, client_ip)
        return result

    result.status_code = upstream_resp.status_code

    if upstream_resp.status_code >= 400:
        try:
            result.response_data = upstream_resp.json()
        except Exception:
            result.response_data = {"raw": upstream_resp.text[:2000]}
        result.error = last_error
        result.latency_ms = int((time.time() - start_time) * 1000)
        _save_forward_log(request_id, url, model, body, result.response_data, result, client_ip)
        return result

    try:
        response_data = upstream_resp.json()
        result.response_data = response_data
        result.usage = _extract_usage(response_data)
        result.response_text = _extract_response_text(response_data)
        result.success = True
    except Exception as e:
        result.error = f"响应解析失败: {e}"
        result.latency_ms = int((time.time() - start_time) * 1000)
        _save_forward_log(request_id, url, model, body, None, result, client_ip)
        return result

    # ─── 5. 输出审查（direction=output 或 both 时执行） ───
    if audit_direction in ("output", "both") and result.response_text and cfg.get("enabled", True):
        output_audit = _run_audit_pipeline(
            text=result.response_text,
            direction="输出",
            side_cfg=cfg,
            audit_engine=audit_engine,
            security_prompt=security_prompt,
            context_summary=context_summary,
            request_id=request_id,
        )
        result.output_audit = output_audit

        block_threshold = cfg.get("block_threshold", 60)
        if output_audit and not output_audit.safe and output_audit.risk_score >= block_threshold:
            result.blocked = True
            result.block_type = "output"
            logger.warning(
                f"[proxy:{request_id}] 输出被拦截 (score={output_audit.risk_score}): "
                f"{output_audit.reason[:100]}"
            )

    result.latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"[proxy:{request_id}] {model} → {upstream_url} | "
        f"{result.latency_ms}ms | tokens={result.usage.get('total_tokens', 0)} | "
        f"blocked={result.blocked}"
    )

    # ─── 6. 全量记录 ───
    _save_forward_log(request_id, url, model, body, result.response_data, result, client_ip)

    return result


def _save_forward_log(
    request_id: str,
    url: str,
    model: str,
    request_body: Dict,
    response_body: Optional[Dict],
    result: ForwardResult,
    client_ip: str,
):
    """保存完整转发日志"""
    try:
        entry = ProxyLogEntry()
        entry.request_id = request_id
        entry.provider = url  # 用上游URL代替供应商ID
        entry.model = model
        entry.url = url
        entry.request_body = request_body
        entry.response_body = response_body
        entry.status_code = result.status_code
        entry.latency_ms = result.latency_ms
        entry.prompt_tokens = result.usage.get("prompt_tokens", 0)
        entry.completion_tokens = result.usage.get("completion_tokens", 0)
        entry.total_tokens = result.usage.get("total_tokens", 0)
        entry.error = result.error
        entry.client_ip = client_ip

        if result.input_audit:
            entry.input_audit = result.input_audit.to_dict()
        if result.output_audit:
            entry.output_audit = result.output_audit.to_dict()

        entry.extra = {
            "blocked": result.blocked,
            "block_type": result.block_type,
            "retry_attempts": result.retry_attempts,
        }

        save_log(entry)
    except Exception as e:
        logger.warning(f"[proxy:{request_id}] 日志保存失败: {e}")
