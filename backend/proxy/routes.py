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
from .rule_engine import RuleEngine
from .logger import query_logs, get_log_stats
from .tasks import (create_task, get_task, list_tasks, update_task, delete_task,
                     default_audit_config, save_strategy_template,
                     list_strategy_templates, delete_strategy_template)

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
        judge_model=judge_model or "huihui_ai/qwen3-abliterated:8b",
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

def _do_proxy_forward(task_cfg, data):
    """核心转发逻辑 — 被透明路由和旧路由共用"""
    upstream_url = task_cfg["upstream_url"]

    # model: 优先 body > task配置
    if not data.get("model") and task_cfg.get("model"):
        data["model"] = task_cfg["model"]

    security_prompt = task_cfg.get("security_prompt", "")
    audit_config = task_cfg.get("audit_config")

    if not data.get("messages"):
        return jsonify({
            "error": {"message": "需要 messages 字段", "type": "invalid_request_error"}
        }), 400

    # 收集客户端原始请求头用于透传
    client_headers = dict(request.headers)

    # 透传转发
    result = forward_chat(
        upstream_url=upstream_url,
        body=data,
        client_headers=client_headers,
        api_key=task_cfg.get("api_key") or None,
        audit_engine=_audit_engine,
        security_prompt=security_prompt,
        context_summary=data.pop("_context_summary", ""),
        audit_config=audit_config,
        client_ip=request.remote_addr or "",
    )

    # 构建响应
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

    # 成功：返回上游原始响应（不注入额外字段，保持透明）
    response = result.response_data or {}
    return jsonify(response)


# ─── 透明代理路由（方案B）────────────────────────────
# 客户端只需把 API 地址改为: http://代理服务器:端口/proxy/<proxy_id>/v1
# 请求体和请求头完全不修改，代理从 URL 路径中提取 proxy_id
#
# 示例:
#   原来: POST https://api.openai.com/v1/chat/completions
#   改为: POST http://localhost:5001/proxy/PX-a1b2c3d4/v1/chat/completions

@bp.post("/proxy/<proxy_id>/v1/chat/completions")
def proxy_chat_transparent(proxy_id):
    """透明代理 — 从 URL 路径提取 proxy_id，请求体/头完全不动"""
    task_cfg = get_task(proxy_id)
    if not task_cfg:
        return jsonify({
            "error": {"message": f"代理项目不存在: {proxy_id}", "type": "invalid_request_error"}
        }), 404

    data = request.json or {}
    return _do_proxy_forward(task_cfg, data)


# ─── 旧路由（向下兼容）──────────────────────────────
# 旧的方式：body 里带 _proxy_id 字段

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

    if not task_cfg:
        # 无 proxy_id 时尝试从 body/_upstream_url 或 header 获取上游地址（兼容旧调用）
        upstream_url = (
            data.pop("_upstream_url", None)
            or request.headers.get("X-Upstream-Url")
            or request.headers.get("x-upstream-url")
        )
        if not upstream_url:
            return jsonify({
                "error": {"message": "需要指定 _proxy_id 或 _upstream_url", "type": "invalid_request_error"}
            }), 400
        # 构造临时 task_cfg
        task_cfg = {
            "upstream_url": upstream_url,
            "api_key": data.pop("_api_key", None) or "",
            "model": "",
            "security_prompt": data.pop("_security_prompt", ""),
            "audit_config": None,
        }

    # 剥离旧的扩展字段
    data.pop("_upstream_url", None)
    data.pop("_api_key", None)
    data.pop("_security_prompt", None)
    data.pop("_enable_input_audit", None)
    data.pop("_enable_output_audit", None)
    data.pop("_min_confidence", None)

    return _do_proxy_forward(task_cfg, data)


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
        custom_regex_rules=data.get("custom_regex_rules", []),
        audit_config=data.get("audit_config"),
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


# ─── GET /proxy/v1/audit/categories ───────────────────

@bp.get("/proxy/v1/audit/categories")
def get_audit_categories():
    """获取所有可用的内置规则分类"""
    return jsonify({
        "success": True,
        "categories": RuleEngine.ALL_CATEGORIES,
    })


@bp.get("/proxy/v1/audit/default-config")
def get_default_audit_config():
    """获取默认审查策略配置"""
    return jsonify({
        "success": True,
        "config": default_audit_config(),
    })


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


# ─── 策略模板 CRUD ──────────────────────────────────────

@bp.get("/proxy/v1/templates")
def api_list_templates():
    """列出所有策略模板"""
    return jsonify({"success": True, "templates": list_strategy_templates()})


@bp.post("/proxy/v1/templates")
def api_save_template():
    """保存策略模板（新建或更新）"""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "模板名称不能为空"}), 400
    tpl = save_strategy_template(
        name=name,
        direction=data.get("direction", "input"),
        security_prompt=data.get("security_prompt", ""),
        audit_config=data.get("audit_config", {}),
        description=data.get("description", ""),
        tpl_id=data.get("tpl_id"),
    )
    return jsonify({"success": True, "template": tpl}), 201


@bp.delete("/proxy/v1/templates/<tpl_id>")
def api_delete_template(tpl_id):
    """删除策略模板"""
    if delete_strategy_template(tpl_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "模板不存在"}), 404


# ─── AI 辅助生成 ────────────────────────────────────────

@bp.post("/proxy/v1/ai/generate-prompt")
def ai_generate_prompt():
    """AI 辅助生成安全提示词"""
    if _audit_engine is None:
        return jsonify({"success": False, "error": "审查引擎未初始化"}), 500

    data = request.json or {}
    business_desc = data.get("business_desc", "").strip()
    direction = data.get("direction", "input")

    if not business_desc:
        return jsonify({"success": False, "error": "请描述业务场景"}), 400

    dir_label = {"input": "用户输入", "output": "模型输出", "both": "用户输入和模型输出"}
    system_msg = (
        "你是一个 LLM 安全策略专家。根据用户描述的业务场景，生成一段简洁专业的安全审查提示词。\n"
        "该提示词将被注入到审查大模型的 system prompt 中，用于指导审查大模型判断"
        f"{dir_label.get(direction, '用户输入')}是否存在安全风险。\n\n"
        "要求：\n"
        "- 直接输出提示词内容，不要加标题或解释\n"
        "- 提示词应该明确列出该业务场景下需要拦截的风险类别\n"
        "- 语言简洁，每条规则一行\n"
        "- 中文输出"
    )

    try:
        import requests as http_req
        resp = http_req.post(
            f"{_audit_engine.judge_url}/chat/completions",
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {_audit_engine.judge_key}"}
                        if _audit_engine.judge_key else {})},
            json={
                "model": _audit_engine.judge_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"业务场景：{business_desc}"},
                ],
                "temperature": 0.7,
                "max_tokens": 800,
            },
            timeout=30,
        )
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return jsonify({"success": True, "prompt": content})
    except Exception as e:
        logger.error(f"[ai-generate-prompt] 生成失败: {e}")
        return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500


@bp.post("/proxy/v1/ai/generate-regex")
def ai_generate_regex():
    """AI 辅助按规则描述生成正则表达式"""
    if _audit_engine is None:
        return jsonify({"success": False, "error": "审查引擎未初始化"}), 500

    data = request.json or {}
    rule_desc = data.get("rule_desc", "").strip()

    if not rule_desc:
        return jsonify({"success": False, "error": "请描述要检测的规则"}), 400

    system_msg = (
        "你是一个正则表达式专家。根据用户描述的检测需求，生成正则表达式规则。\n\n"
        "输出格式要求（严格遵守）：\n"
        "- 每行一条规则，格式为：规则名称 | 正则表达式\n"
        "- 正则表达式使用 Python re 语法\n"
        "- 只输出规则行，不要加解释、标题、代码块或其他任何文字\n"
        "- 正则要尽量精确，避免误匹配\n\n"
        "示例输出：\n"
        "禁止讨论竞品 | (?:竞品A|竞品B|竞品C)\n"
        "内部代号保护 | (?:Project\\s*X|代号\\w+)"
    )

    try:
        import requests as http_req
        resp = http_req.post(
            f"{_audit_engine.judge_url}/chat/completions",
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {_audit_engine.judge_key}"}
                        if _audit_engine.judge_key else {})},
            json={
                "model": _audit_engine.judge_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"检测需求：{rule_desc}"},
                ],
                "temperature": 0.3,
                "max_tokens": 600,
            },
            timeout=30,
        )
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return jsonify({"success": True, "rules": content})
    except Exception as e:
        logger.error(f"[ai-generate-regex] 生成失败: {e}")
        return jsonify({"success": False, "error": f"生成失败: {str(e)}"}), 500
