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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
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
                security_prompt: str = "") -> Dict[str, Any]:
    """创建代理项目，返回完整记录"""
    _ensure_table()
    proxy_id = _gen_proxy_id()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        INSERT INTO proxy_tasks
            (proxy_id, name, upstream_url, api_key, model,
             enable_input_audit, enable_output_audit, min_confidence,
             security_prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (proxy_id, name, upstream_url, api_key, model,
          int(enable_input_audit), int(enable_output_audit), min_confidence,
          security_prompt, now, now))
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
        result.append(d)
    return result


def update_task(proxy_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """更新代理项目字段"""
    _ensure_table()
    allowed = {"name", "upstream_url", "api_key", "model",
               "enable_input_audit", "enable_output_audit",
               "min_confidence", "security_prompt"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return get_task(proxy_id)

    # 布尔转整数
    for bk in ("enable_input_audit", "enable_output_audit"):
        if bk in fields:
            fields[bk] = int(fields[bk])

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
