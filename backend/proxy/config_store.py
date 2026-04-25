"""代理审查引擎配置持久化 — SQLite

首次部署时表为空，用户通过前端设置后写入。
启动时读取，如无记录则返回 None，由上层决定是否用默认值。
"""
import os
import sqlite3
import threading
import logging

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "proxy_logs.db")
_lock = threading.Lock()
_table_ready = False


def _ensure_table():
    global _table_ready
    if _table_ready:
        return
    with _lock:
        if _table_ready:
            return
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proxy_config (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        conn.close()
        _table_ready = True


def load_judge_config() -> dict:
    """读取已保存的 judge 配置，返回 dict，缺失的 key 值为 None"""
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    rows = conn.execute(
        "SELECT key, value FROM proxy_config WHERE key IN (?, ?, ?, ?)",
        ("judge_url", "judge_model", "judge_key", "http_proxy"),
    ).fetchall()
    conn.close()
    cfg = {r[0]: r[1] for r in rows}
    return {
        "judge_url": cfg.get("judge_url"),
        "judge_model": cfg.get("judge_model"),
        "judge_key": cfg.get("judge_key"),
        "http_proxy": cfg.get("http_proxy"),
    }


def save_judge_config(*, judge_url: str = None, judge_model: str = None,
                      judge_key: str = None, http_proxy: str = None):
    """保存 judge 配置（仅写入非 None 的字段）"""
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    pairs = []
    if judge_url is not None:
        pairs.append(("judge_url", judge_url))
    if judge_model is not None:
        pairs.append(("judge_model", judge_model))
    if judge_key is not None:
        pairs.append(("judge_key", judge_key))
    if http_proxy is not None:
        pairs.append(("http_proxy", http_proxy))
    for k, v in pairs:
        conn.execute(
            "INSERT INTO proxy_config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (k, v),
        )
    conn.commit()
    conn.close()
    logger.info(f"[proxy-config] 已保存配置: {[k for k, _ in pairs]}")
