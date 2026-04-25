"""对话历史管理

按 (proxy_id, user_id) 存储压缩后的对话摘要，供后续审查使用。
每条记录为单次交互的语义摘要（≤50字），保留最近 N 轮（默认10轮）。

开关配置放在 audit_config.context_history：
  {
    "enabled": true,
    "window": 10       # 检测窗口，最多参考最近N轮
  }
"""
import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import List, Tuple

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
            CREATE TABLE IF NOT EXISTS context_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_id    TEXT    NOT NULL,
                user_id     TEXT    NOT NULL,
                summary     TEXT    NOT NULL,
                risk_score  INTEGER DEFAULT 0,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ctx_hist "
            "ON context_history(proxy_id, user_id, created_at)"
        )
        conn.commit()
        conn.close()
        _table_ready = True
        logger.info("[history] context_history 表就绪")


def save_summary(proxy_id: str, user_id: str,
                 summary: str, risk_score: int = 0) -> None:
    """异步可调用：保存一条压缩摘要"""
    _ensure_table()
    with _lock:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute(
            "INSERT INTO context_history "
            "(proxy_id, user_id, summary, risk_score, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (proxy_id, user_id, summary, risk_score,
             datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    logger.debug(f"[history] saved: proxy={proxy_id} user={user_id} "
                 f"score={risk_score} summary={summary[:40]}")


def get_recent(proxy_id: str, user_id: str,
               limit: int = 10) -> List[Tuple[str, int]]:
    """获取最近 limit 轮对话摘要，按时间从旧到新返回

    Returns:
        [(summary, risk_score), ...]  oldest first
    """
    _ensure_table()
    conn = sqlite3.connect(_DB_PATH)
    rows = conn.execute(
        "SELECT summary, risk_score FROM context_history "
        "WHERE proxy_id=? AND user_id=? "
        "ORDER BY created_at DESC LIMIT ?",
        (proxy_id, user_id, limit)
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in reversed(rows)]


def build_context_str(records: List[Tuple[str, int]]) -> str:
    """将历史记录格式化为 context_summary 字符串"""
    if not records:
        return ""
    lines = []
    for i, (summary, score) in enumerate(records, 1):
        flag = "⚠️" if score >= 50 else "✅"
        lines.append(f"  [{i}] {flag}(风险{score}分) {summary}")
    return "【该用户近期对话记录（旧→新）】\n" + "\n".join(lines)


def clear_user_history(proxy_id: str, user_id: str) -> int:
    """清除指定用户的全部历史（解封/重置时使用）"""
    _ensure_table()
    with _lock:
        conn = sqlite3.connect(_DB_PATH)
        n = conn.execute(
            "DELETE FROM context_history WHERE proxy_id=? AND user_id=?",
            (proxy_id, user_id)
        ).rowcount
        conn.commit()
        conn.close()
    return n
