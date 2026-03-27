"""透明审查代理 — HTTP 路由

核心端点：
  POST /proxy/v1/chat/completions   — 透传转发（含审查+全量日志）
  GET  /proxy/v1/logs               — 查询代理日志
  GET  /proxy/v1/logs/stats         — 日志统计
"""
import logging
from flask import Blueprint, jsonify, request

from .gateway import forward_chat
from .audit import AuditEngine
from .logger import query_logs, get_log_stats
from .tasks import create_task, get_task, list_tasks, update_task, delete_task

logger = logging.getLogger(__name__)

bp = Blueprint("proxy", __name__)

# 审查引擎实例（启动时根据配置初始化）
_audit_engine: AuditEngine = None


def init_audit_engine(judge_url: str = None, judge_model: str = None,
                      judge_key: str = None):
    """初始化审查引擎（由应用启动时调用）"""
    global _audit_engine
    _audit_engine = AuditEngine(
        judge_url=judge_url or "http://localhost:11434/v1",
        judge_model=judge_model or "qwen2.5:latest",
        judge_key=judge_key,
    )
    logger.info(
        f"[proxy] 审查引擎初始化: judge={_audit_engine.judge_url}/{_audit_engine.judge_model}"
    )


# ─── POST /proxy/v1/chat/completions ──────────────────
# 透明代理：原样转发到上游 URL，只做审查+记录
#
# 请求格式（OpenAI 兼容 + 代理扩展字段）：
# {
#   "model": "qwen-plus",       // 可省略，会从代理项目配置填充
#   "messages": [...],
#   "_proxy_id": "PX-a1b2c3d4", // 代理项目号（必填，转发前剥离）
#   // 下面字段可省略，省略时使用代理项目的默认配置
#   "_upstream_url": "...",
#   "_api_key": "...",
#   "_enable_input_audit": true,
#   "_enable_output_audit": true,
#   "_min_confidence": 60,
# }

@bp.post("/proxy/v1/chat/completions")
def proxy_chat():
    data = request.json or {}

    # 提取并剥离 _proxy_id
    proxy_id = data.pop("_proxy_id", None)
    task_cfg = None
    if proxy_id:
        task_cfg = get_task(proxy_id)
        if not task_cfg:
            return jsonify({
                "error": {"message": f"代理项目不存在: {proxy_id}", "type": "invalid_request_error"}
            }), 404

    # 提取上游地址：优先 body > task配置 > header
    upstream_url = (
        data.pop("_upstream_url", None)
        or (task_cfg["upstream_url"] if task_cfg else None)
        or request.headers.get("X-Upstream-Url")
        or request.headers.get("x-upstream-url")
    )
    if not upstream_url:
        return jsonify({
            "error": {"message": "需要指定上游地址（_proxy_id 或 _upstream_url）", "type": "invalid_request_error"}
        }), 400

    # 提取API Key：优先 body > task配置 > header
    api_key = data.pop("_api_key", None)
    if not api_key and task_cfg:
        api_key = task_cfg.get("api_key") or None
    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()

    # model: 优先 body > task配置
    if not data.get("model") and task_cfg and task_cfg.get("model"):
        data["model"] = task_cfg["model"]

    # 提取代理扩展参数（body优先，否则用task配置）
    security_prompt = data.pop("_security_prompt", task_cfg.get("security_prompt", "") if task_cfg else "")
    context_summary = data.pop("_context_summary", "")
    enable_input = data.pop("_enable_input_audit", task_cfg["enable_input_audit"] if task_cfg else True)
    enable_output = data.pop("_enable_output_audit", task_cfg["enable_output_audit"] if task_cfg else True)
    min_confidence = data.pop("_min_confidence", task_cfg.get("min_confidence", 60) if task_cfg else 60)

    if not data.get("model") or not data.get("messages"):
        return jsonify({
            "error": {"message": "需要 model 和 messages 字段", "type": "invalid_request_error"}
        }), 400

    # 透传转发
    result = forward_chat(
        upstream_url=upstream_url,
        body=data,
        api_key=api_key,
        audit_engine=_audit_engine,
        security_prompt=security_prompt,
        context_summary=context_summary,
        enable_input_audit=enable_input,
        enable_output_audit=enable_output,
        client_ip=request.remote_addr or "",
        min_confidence_threshold=min_confidence,
    )

    # 构建响应——不包含 proxy_id，直接转发
    if result.blocked:
        return jsonify({
            "blocked": True,
            "block_type": result.block_type,
            "audit": (result.input_audit.to_dict() if result.block_type == "input" and result.input_audit
                      else result.output_audit.to_dict() if result.output_audit else {}),
            "latency_ms": result.latency_ms,
        })

    if not result.success:
        status = result.status_code if result.status_code >= 400 else 502
        return jsonify({
            "error": {"message": result.error, "type": "proxy_error"},
            "latency_ms": result.latency_ms,
        }), status

    # 成功：返回上游原始响应 + 代理元信息（不含 proxy_id）
    response = result.response_data or {}
    response["_proxy"] = {
        "upstream_url": upstream_url,
        "model": data.get("model"),
        "latency_ms": result.latency_ms,
        "tokens": result.usage,
        "input_audit": result.input_audit.to_dict() if result.input_audit else None,
        "output_audit": result.output_audit.to_dict() if result.output_audit else None,
    }
    return jsonify(response)


# ─── GET /proxy/v1/config ─────────────────────────────

@bp.get("/proxy/v1/config")
def get_proxy_config():
    """获取当前代理审查引擎配置"""
    if _audit_engine is None:
        return jsonify({"success": False, "error": "审查引擎未初始化"}), 500
    return jsonify({
        "success": True,
        "config": {
            "judge_url": _audit_engine.judge_url,
            "judge_model": _audit_engine.judge_model,
            "judge_key_set": bool(_audit_engine.judge_key),
        }
    })


# ─── POST /proxy/v1/config ────────────────────────────

@bp.post("/proxy/v1/config")
def update_proxy_config():
    """动态更新代理审查引擎配置"""
    data = request.json or {}
    judge_url = data.get("judge_url")
    judge_model = data.get("judge_model")
    judge_key = data.get("judge_key")

    if not judge_url and not judge_model:
        return jsonify({"success": False, "error": "至少提供 judge_url 或 judge_model"}), 400

    init_audit_engine(
        judge_url=judge_url or (_audit_engine.judge_url if _audit_engine else None),
        judge_model=judge_model or (_audit_engine.judge_model if _audit_engine else None),
        judge_key=judge_key if judge_key is not None else (_audit_engine.judge_key if _audit_engine else None),
    )
    return jsonify({"success": True, "message": "审查引擎配置已更新"})


# ─── POST /proxy/v1/test ─────────────────────────────

@bp.post("/proxy/v1/test")
def test_audit():
    """测试审查引擎是否正常工作"""
    if _audit_engine is None:
        return jsonify({"success": False, "error": "审查引擎未初始化"}), 500

    data = request.json or {}
    test_text = data.get("text", "你好，请问今天天气怎么样？")
    direction = data.get("direction", "input")  # input or output

    if direction == "input":
        result = _audit_engine.audit_input(test_text)
    else:
        result = _audit_engine.audit_output(test_text)

    return jsonify({
        "success": True,
        "direction": direction,
        "test_text": test_text,
        "result": result.to_dict(),
    })


# ─── CRUD /proxy/v1/tasks ─────────────────────────

@bp.get("/proxy/v1/tasks")
def api_list_tasks():
    """列出所有代理项目"""
    tasks = list_tasks()
    return jsonify({"success": True, "tasks": tasks})


@bp.get("/proxy/v1/tasks/<proxy_id>")
def api_get_task(proxy_id):
    """获取单个代理项目"""
    task = get_task(proxy_id)
    if not task:
        return jsonify({"success": False, "error": "代理项目不存在"}), 404
    return jsonify({"success": True, "task": task})


@bp.post("/proxy/v1/tasks")
def api_create_task():
    """创建代理项目"""
    data = request.json or {}
    name = data.get("name", "").strip()
    upstream_url = data.get("upstream_url", "").strip()
    if not name or not upstream_url:
        return jsonify({"success": False, "error": "名称和上游地址不能为空"}), 400
    task = create_task(
        name=name,
        upstream_url=upstream_url,
        api_key=data.get("api_key", ""),
        model=data.get("model", ""),
        enable_input_audit=data.get("enable_input_audit", True),
        enable_output_audit=data.get("enable_output_audit", True),
        min_confidence=data.get("min_confidence", 60),
        security_prompt=data.get("security_prompt", ""),
    )
    return jsonify({"success": True, "task": task}), 201


@bp.put("/proxy/v1/tasks/<proxy_id>")
def api_update_task(proxy_id):
    """更新代理项目"""
    data = request.json or {}
    task = update_task(proxy_id, **data)
    if not task:
        return jsonify({"success": False, "error": "代理项目不存在"}), 404
    return jsonify({"success": True, "task": task})


@bp.delete("/proxy/v1/tasks/<proxy_id>")
def api_delete_task(proxy_id):
    """删除代理项目"""
    if delete_task(proxy_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "代理项目不存在"}), 404


# ─── GET /proxy/v1/logs ──────────────────────────────

@bp.get("/proxy/v1/logs")
def get_logs():
    limit = min(int(request.args.get("limit", 50)), 200)
    start = request.args.get("start")
    end = request.args.get("end")

    logs = query_logs(limit=limit, start=start, end=end)
    return jsonify({"success": True, "count": len(logs), "logs": logs})


# ─── GET /proxy/v1/logs/stats ─────────────────────────

@bp.get("/proxy/v1/logs/stats")
def logs_stats():
    stats = get_log_stats()
    return jsonify({"success": True, **stats})
