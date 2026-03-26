import logging
from pathlib import Path

import requests as http_requests
from flask import Blueprint, current_app, jsonify

from ..db import db_cursor
from ..errors import DatabaseError

logger = logging.getLogger(__name__)

bp = Blueprint("stats", __name__)


def _count_local_models():
    """统计本地模型数量（Ollama + HuggingFace）"""
    ollama_count = 0
    hf_count = 0

    # Ollama
    try:
        resp = http_requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            ollama_count = len(resp.json().get("models", []))
    except Exception:
        pass

    # HuggingFace 缓存
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    if hf_cache.exists():
        for entry in hf_cache.iterdir():
            if entry.is_dir() and entry.name.startswith("models--"):
                snapshots = entry / "snapshots"
                if snapshots.exists() and any(snapshots.iterdir()):
                    hf_count += 1

    return ollama_count, hf_count


@bp.get("/api/stats")
def get_stats():
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT COUNT(*) as count FROM models")
            api_model_count = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM models WHERE security_prompt IS NOT NULL AND security_prompt != ''"
            )
            security_count = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM models WHERE api_key IS NOT NULL AND api_key != ''"
            )
            apikey_count = cursor.fetchone()["count"]

            cursor.execute(
                """
                SELECT COUNT(*) as count FROM chat_logs
                WHERE DATE(created_at) = CURDATE()
                """
            )
            chat_count = cursor.fetchone()["count"]

        ollama_count, hf_count = _count_local_models()
        local_model_count = ollama_count + hf_count

        return jsonify(
            {
                "success": True,
                "data": {
                    "model_count": api_model_count + local_model_count,
                    "api_model_count": api_model_count,
                    "local_model_count": local_model_count,
                    "ollama_count": ollama_count,
                    "hf_count": hf_count,
                    "security_count": security_count,
                    "apikey_count": apikey_count,
                    "chat_count": chat_count,
                },
            }
        )
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}", exc_info=True)
        raise DatabaseError("获取统计数据失败")
