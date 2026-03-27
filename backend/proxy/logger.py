"""全量日志记录器 — 打开黑盒

记录每一次代理转发的完整信息：
- 请求时间、来源、目标供应商
- 完整请求体（messages, model, params）
- 完整响应体（choices, usage）
- 审查结果（输入审查 + 输出审查）
- 延迟、Token用量、错误信息

日志存储到本地 JSON Lines 文件 + SQLite，方便后续分析。
"""
import json
import os
import sqlite3
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "proxy_logs.db")
_JSONL_PATH = os.path.join(os.path.dirname(__file__), "..", "proxy_logs.jsonl")
_lock = threading.Lock()
_db_initialized = False


def _ensure_db():
    """确保 SQLite 日志表存在"""
    global _db_initialized
    if _db_initialized:
        return
    with _lock:
        if _db_initialized:
            return
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proxy_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                request_id TEXT,
                provider TEXT,
                model TEXT,
                direction TEXT,
                method TEXT,
                url TEXT,
                request_body TEXT,
                response_body TEXT,
                status_code INTEGER,
                latency_ms INTEGER,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                input_audit_safe INTEGER,
                input_audit_score INTEGER,
                input_audit_reason TEXT,
                output_audit_safe INTEGER,
                output_audit_score INTEGER,
                output_audit_reason TEXT,
                error TEXT,
                stream INTEGER DEFAULT 0,
                client_ip TEXT,
                extra TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proxy_logs_ts ON proxy_logs(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proxy_logs_provider ON proxy_logs(provider)
        """)
        conn.commit()
        conn.close()
        _db_initialized = True
        logger.info(f"[proxy-log] SQLite 日志库就绪: {os.path.abspath(_DB_PATH)}")


class ProxyLogEntry:
    """一次代理转发的完整日志"""

    def __init__(self):
        self.timestamp: str = datetime.now().isoformat()
        self.request_id: str = ""
        self.provider: str = ""
        self.model: str = ""
        self.method: str = "POST"
        self.url: str = ""
        self.request_body: Optional[Dict] = None
        self.response_body: Optional[Dict] = None
        self.status_code: int = 0
        self.latency_ms: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.input_audit: Optional[Dict] = None   # {"safe": bool, "risk_score": int, "reason": str}
        self.output_audit: Optional[Dict] = None
        self.error: str = ""
        self.stream: bool = False
        self.client_ip: str = ""
        self.extra: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "method": self.method,
            "url": self.url,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "input_audit": self.input_audit,
            "output_audit": self.output_audit,
            "error": self.error,
            "stream": self.stream,
            "client_ip": self.client_ip,
            "extra": self.extra,
        }


def _truncate_body(body: Optional[Dict], max_len: int = 50000) -> Optional[str]:
    """序列化并截断，防止超大日志"""
    if body is None:
        return None
    try:
        text = json.dumps(body, ensure_ascii=False)
        if len(text) > max_len:
            return text[:max_len] + "...[truncated]"
        return text
    except (TypeError, ValueError):
        return str(body)[:max_len]


def save_log(entry: ProxyLogEntry):
    """保存日志到 SQLite + JSONL"""
    _ensure_db()

    record = entry.to_dict()

    # 1. 写 JSONL（追加）
    try:
        with _lock:
            with open(_JSONL_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[proxy-log] JSONL 写入失败: {e}")

    # 2. 写 SQLite
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            INSERT INTO proxy_logs (
                timestamp, request_id, provider, model, direction, method, url,
                request_body, response_body, status_code, latency_ms,
                prompt_tokens, completion_tokens, total_tokens,
                input_audit_safe, input_audit_score, input_audit_reason,
                output_audit_safe, output_audit_score, output_audit_reason,
                error, stream, client_ip, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.timestamp,
            entry.request_id,
            entry.provider,
            entry.model,
            "forward",
            entry.method,
            entry.url,
            _truncate_body(entry.request_body),
            _truncate_body(entry.response_body),
            entry.status_code,
            entry.latency_ms,
            entry.prompt_tokens,
            entry.completion_tokens,
            entry.total_tokens,
            int(entry.input_audit["safe"]) if entry.input_audit else None,
            entry.input_audit.get("risk_score") if entry.input_audit else None,
            entry.input_audit.get("reason") if entry.input_audit else None,
            int(entry.output_audit["safe"]) if entry.output_audit else None,
            entry.output_audit.get("risk_score") if entry.output_audit else None,
            entry.output_audit.get("reason") if entry.output_audit else None,
            entry.error,
            int(entry.stream),
            entry.client_ip,
            json.dumps(entry.extra, ensure_ascii=False) if entry.extra else None,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[proxy-log] SQLite 写入失败: {e}")


def query_logs(limit: int = 50, provider: str = None,
               start: str = None, end: str = None) -> list:
    """查询日志记录"""
    _ensure_db()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row

    sql = "SELECT * FROM proxy_logs WHERE 1=1"
    params = []
    if provider:
        sql += " AND provider = ?"
        params.append(provider)
    if start:
        sql += " AND timestamp >= ?"
        params.append(start)
    if end:
        sql += " AND timestamp <= ?"
        params.append(end)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_log_stats() -> Dict[str, Any]:
    """获取日志统计"""
    _ensure_db()
    conn = sqlite3.connect(_DB_PATH)

    total = conn.execute("SELECT COUNT(*) FROM proxy_logs").fetchone()[0]
    blocked_input = conn.execute(
        "SELECT COUNT(*) FROM proxy_logs WHERE input_audit_safe = 0"
    ).fetchone()[0]
    blocked_output = conn.execute(
        "SELECT COUNT(*) FROM proxy_logs WHERE output_audit_safe = 0"
    ).fetchone()[0]
    total_tokens = conn.execute(
        "SELECT COALESCE(SUM(total_tokens), 0) FROM proxy_logs"
    ).fetchone()[0]
    avg_latency = conn.execute(
        "SELECT COALESCE(AVG(latency_ms), 0) FROM proxy_logs WHERE status_code = 200"
    ).fetchone()[0]

    by_provider = {}
    for row in conn.execute(
        "SELECT provider, COUNT(*) as cnt FROM proxy_logs GROUP BY provider"
    ).fetchall():
        by_provider[row[0]] = row[1]

    conn.close()
    return {
        "total_requests": total,
        "blocked_input": blocked_input,
        "blocked_output": blocked_output,
        "total_tokens": total_tokens,
        "avg_latency_ms": round(avg_latency),
        "by_provider": by_provider,
    }
