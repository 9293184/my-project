"""代理项目管理 — 每个代理项目有唯一 proxy_id 及完整配置

每个代理项目包含：
- proxy_id: 唯一标识（自动生成短ID）
- name: 项目名称
- upstream_url: 上游 API 地址
- api_key: 上游 API Key
- model: 默认模型名称
- enable_input_audit: 是否审查输入
- enable_output_audit: 是否审查输出
- min_confidence: 拦截阈值
- security_prompt: 安全提示词
- created_at: 创建时间

调用方只需传 _proxy_id，代理自动匹配配置并转发，响应中剥离 proxy_id。
"""
import json
import os
import sqlite3
import threading
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def default_audit_config() -> dict:
    """默认审查策略配置（单方向）"""
    return {
        "direction": "input",
        "enabled": True,
        "builtin_rules": {
            "enabled": True,
            "action": "block",
        },
        "custom_regex": {
            "enabled": False,
            "action": "enhance",
            "rules": [],
        },
        "llm_judge": {"enabled": True},
        "block_threshold": 60,
    }


_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "proxy_logs.db")
_lock = threading.Lock()
_table_ready = False


def _ensure_table():
    """确保 proxy_tasks 表存在"""
    global _table_ready
    if _table_ready:
        return
    with _lock:
        if _table_ready:
            return
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proxy_tasks (
                proxy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                upstream_url TEXT NOT NULL,
                api_key TEXT DEFAULT '',
                model TEXT DEFAULT '',
                enable_input_audit INTEGER DEFAULT 1,
                enable_output_audit INTEGER DEFAULT 1,
                min_confidence INTEGER DEFAULT 60,
                security_prompt TEXT DEFAULT '',
                custom_regex_rules TEXT DEFAULT '[]',
                audit_config TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # 兼容旧表：如果缺少新增列则添加
        for col, default in [("custom_regex_rules", "'[]'"), ("audit_config", "''")]:
            try:
                conn.execute(f"SELECT {col} FROM proxy_tasks LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE proxy_tasks ADD COLUMN {col} TEXT DEFAULT {default}")
                logger.info(f"[proxy-tasks] 已迁移: 添加 {col} 列")

        conn.commit()
        conn.close()
        _table_ready = True
        logger.info("[proxy-tasks] proxy_tasks 表就绪")


def _gen_proxy_id() -> str:
    """生成 8 位短ID，如 PX-a1b2c3d4"""
    return "PX-" + uuid.uuid4().hex[:8]


def create_task(name: str, upstream_url: str, api_key: str = "",
                model: str = "", enable_input_audit: bool = True,
                enable_output_audit: bool = True, min_confidence: int = 60,
                security_prompt: str = "",
                custom_regex_rules: list = None,
                audit_config: dict = None) -> Dict[str, Any]:
    """创建代理项目，返回完整记录"""
    _ensure_table()
    proxy_id = _gen_proxy_id()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(_DB_PATH)
    regex_json = json.dumps(custom_regex_rules or [], ensure_ascii=False)
    # 如果提供了 audit_config 则使用，否则从旧字段生成兼容配置
    if audit_config:
        cfg = audit_config
    else:
        cfg = default_audit_config()
        cfg["direction"] = "input" if enable_input_audit else "output"
        cfg["block_threshold"] = min_confidence
        if custom_regex_rules:
            cfg["custom_regex"]["enabled"] = True
            cfg["custom_regex"]["rules"] = custom_regex_rules
    audit_config_json = json.dumps(cfg, ensure_ascii=False)
    conn.execute("""
        INSERT INTO proxy_tasks
            (proxy_id, name, upstream_url, api_key, model,
             enable_input_audit, enable_output_audit, min_confidence,
             security_prompt, custom_regex_rules, audit_config,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (proxy_id, name, upstream_url, api_key, model,
          int(enable_input_audit), int(enable_output_audit), min_confidence,
          security_prompt, regex_json, audit_config_json, now, now))
    conn.commit()
    conn.close()
    return get_task(proxy_id)


def get_task(proxy_id: str) -> Optional[Dict[str, Any]]:
    """根据 proxy_id 获取单个代理项目"""
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM proxy_tasks WHERE proxy_id = ?", (proxy_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["enable_input_audit"] = bool(d["enable_input_audit"])
    d["enable_output_audit"] = bool(d["enable_output_audit"])
    try:
        d["custom_regex_rules"] = json.loads(d.get("custom_regex_rules") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["custom_regex_rules"] = []
    # audit_config: 反序列化，旧数据兼容
    try:
        raw_cfg = d.get("audit_config") or ""
        d["audit_config"] = json.loads(raw_cfg) if raw_cfg else None
    except (json.JSONDecodeError, TypeError):
        d["audit_config"] = None
    if not d["audit_config"]:
        d["audit_config"] = default_audit_config()
        d["audit_config"]["direction"] = "input" if d["enable_input_audit"] else "output"
        d["audit_config"]["block_threshold"] = d.get("min_confidence", 60)
        if d["custom_regex_rules"]:
            d["audit_config"]["custom_regex"]["enabled"] = True
            d["audit_config"]["custom_regex"]["rules"] = d["custom_regex_rules"]
    # 兼容旧版双侧格式 -> 新版单侧格式
    if "input" in d["audit_config"] and "direction" not in d["audit_config"]:
        old = d["audit_config"]
        side = old.get("input", {}) if old.get("input", {}).get("enabled", True) else old.get("output", {})
        direction = "input" if old.get("input", {}).get("enabled", True) else "output"
        d["audit_config"] = {"direction": direction, **side}
    return d


def list_tasks() -> List[Dict[str, Any]]:
    """列出所有代理项目"""
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM proxy_tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["enable_input_audit"] = bool(d["enable_input_audit"])
        d["enable_output_audit"] = bool(d["enable_output_audit"])
        try:
            d["custom_regex_rules"] = json.loads(d.get("custom_regex_rules") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["custom_regex_rules"] = []
        try:
            raw_cfg = d.get("audit_config") or ""
            d["audit_config"] = json.loads(raw_cfg) if raw_cfg else None
        except (json.JSONDecodeError, TypeError):
            d["audit_config"] = None
        if not d["audit_config"]:
            d["audit_config"] = default_audit_config()
        result.append(d)
    return result


def update_task(proxy_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """更新代理项目字段"""
    _ensure_table()
    allowed = {"name", "upstream_url", "api_key", "model",
               "enable_input_audit", "enable_output_audit",
               "min_confidence", "security_prompt", "custom_regex_rules",
               "audit_config"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return get_task(proxy_id)

    # 布尔转整数
    for bk in ("enable_input_audit", "enable_output_audit"):
        if bk in fields:
            fields[bk] = int(fields[bk])

    # 列表/字典转 JSON 字符串
    if "custom_regex_rules" in fields:
        if isinstance(fields["custom_regex_rules"], list):
            fields["custom_regex_rules"] = json.dumps(fields["custom_regex_rules"], ensure_ascii=False)
    if "audit_config" in fields:
        if isinstance(fields["audit_config"], dict):
            fields["audit_config"] = json.dumps(fields["audit_config"], ensure_ascii=False)

    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [proxy_id]

    conn = sqlite3.connect(_DB_PATH)
    conn.execute(f"UPDATE proxy_tasks SET {set_clause} WHERE proxy_id = ?", values)
    conn.commit()
    conn.close()
    return get_task(proxy_id)


def delete_task(proxy_id: str) -> bool:
    """删除代理项目"""
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.execute("DELETE FROM proxy_tasks WHERE proxy_id = ?", (proxy_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# ─── 策略模板 CRUD ──────────────────────────────────────

_tpl_table_ready = False
_tpl_lock = threading.Lock()


def _ensure_tpl_table():
    """确保 audit_strategy_templates 表存在"""
    global _tpl_table_ready
    if _tpl_table_ready:
        return
    with _tpl_lock:
        if _tpl_table_ready:
            return
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_strategy_templates (
                tpl_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                direction TEXT DEFAULT 'input',
                security_prompt TEXT DEFAULT '',
                audit_config TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        _tpl_table_ready = True
        logger.info("[proxy-tasks] audit_strategy_templates 表就绪")


def _gen_tpl_id() -> str:
    return "TPL-" + uuid.uuid4().hex[:8]


def save_strategy_template(name: str, direction: str, security_prompt: str,
                           audit_config: dict, description: str = "",
                           tpl_id: str = None) -> Dict[str, Any]:
    """保存策略模板（新建或更新）"""
    _ensure_tpl_table()
    now = datetime.now().isoformat()
    config_json = json.dumps(audit_config, ensure_ascii=False)

    conn = sqlite3.connect(_DB_PATH)
    if tpl_id:
        # 更新已有模板
        conn.execute("""
            UPDATE audit_strategy_templates
            SET name=?, description=?, direction=?, security_prompt=?,
                audit_config=?, updated_at=?
            WHERE tpl_id=?
        """, (name, description, direction, security_prompt, config_json, now, tpl_id))
    else:
        tpl_id = _gen_tpl_id()
        conn.execute("""
            INSERT INTO audit_strategy_templates
                (tpl_id, name, description, direction, security_prompt,
                 audit_config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tpl_id, name, description, direction, security_prompt,
              config_json, now, now))
    conn.commit()
    conn.close()
    return get_strategy_template(tpl_id)


def get_strategy_template(tpl_id: str) -> Optional[Dict[str, Any]]:
    """获取单个策略模板"""
    _ensure_tpl_table()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM audit_strategy_templates WHERE tpl_id=?",
                       (tpl_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["audit_config"] = json.loads(d.get("audit_config") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["audit_config"] = {}
    return d


def list_strategy_templates() -> List[Dict[str, Any]]:
    """列出所有策略模板"""
    _ensure_tpl_table()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM audit_strategy_templates ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["audit_config"] = json.loads(d.get("audit_config") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["audit_config"] = {}
        result.append(d)
    return result


def delete_strategy_template(tpl_id: str) -> bool:
    """删除策略模板"""
    _ensure_tpl_table()
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.execute("DELETE FROM audit_strategy_templates WHERE tpl_id=?",
                          (tpl_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
