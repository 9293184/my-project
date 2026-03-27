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

import requests

from .audit import AuditEngine, AuditResult
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

def forward_chat(
    upstream_url: str,
    body: Dict[str, Any],
    api_key: str = None,
    audit_engine: Optional[AuditEngine] = None,
    security_prompt: str = "",
    context_summary: str = "",
    enable_input_audit: bool = True,
    enable_output_audit: bool = True,
    client_ip: str = "",
    min_confidence_threshold: int = 60,
    max_retries: int = MAX_RETRY_ATTEMPTS,
    timeout: int = FETCH_TIMEOUT_S,
) -> ForwardResult:
    """
    透明代理转发 — 原样转发到用户指定的上游 URL

    Args:
        upstream_url: 上游 API 地址（如 https://dashscope.aliyuncs.com/compatible-mode/v1）
        body: 请求体，原样转发（OpenAI 兼容格式）
        api_key: 上游 API Key（可选，Ollama 本地不需要）
        audit_engine: 审查引擎实例（None = 跳过审查）
        security_prompt: 安全策略文本
        context_summary: 历史对话摘要
        enable_input_audit: 是否启用输入审查
        enable_output_audit: 是否启用输出审查
        client_ip: 客户端IP
        min_confidence_threshold: 风险拦截阈值（0-100）
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

    # ─── 2. 输入审查 ───
    if audit_engine and enable_input_audit and user_content:
        logger.info(f"[proxy:{request_id}] 输入审查中...")
        input_audit = audit_engine.audit_input(user_content, security_prompt, context_summary)
        result.input_audit = input_audit

        if not input_audit.safe and input_audit.risk_score >= min_confidence_threshold:
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

    # ─── 3. 原样转发到上游 ───
    headers = {"Content-Type": "application/json"}
    if api_key:
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

    # ─── 5. 输出审查 ───
    if audit_engine and enable_output_audit and result.response_text:
        logger.info(f"[proxy:{request_id}] 输出审查中...")
        output_audit = audit_engine.audit_output(result.response_text, security_prompt, context_summary)
        result.output_audit = output_audit

        if not output_audit.safe and output_audit.risk_score >= min_confidence_threshold:
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
