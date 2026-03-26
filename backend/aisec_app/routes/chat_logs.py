import logging

from flask import Blueprint, current_app, jsonify, request

from ..db import db_cursor
from ..errors import DatabaseError, ValidationError
from ..utils import normalize_datetimes

logger = logging.getLogger(__name__)

bp = Blueprint("chat_logs", __name__)


@bp.get("/api/chat/logs")
def get_chat_logs():
    """获取对话记录（支持筛选和分页）"""
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 30, type=int)
        model_id = request.args.get("model_id", type=int)
        user_id = request.args.get("user_id", "")
        status = request.args.get("status", "")  # success / blocked

        page_size = min(page_size, 100)
        offset = (page - 1) * page_size

        where_clause = "WHERE 1=1"
        params: list = []

        if model_id:
            where_clause += " AND c.model_id = %s"
            params.append(model_id)

        if user_id:
            where_clause += " AND c.user_id LIKE %s"
            params.append(f"%{user_id}%")

        if status == "success":
            where_clause += " AND c.input_blocked = 0 AND c.output_blocked = 0"
        elif status == "blocked":
            where_clause += " AND (c.input_blocked = 1 OR c.output_blocked = 1)"

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            count_sql = f"SELECT COUNT(*) as total FROM chat_logs c {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]

            sql = f"""
                SELECT c.*, m.name as model_name
                FROM chat_logs c
                LEFT JOIN models m ON c.model_id = m.id
                {where_clause}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, params + [page_size, offset])
            logs = cursor.fetchall()

        total_pages = (total + page_size - 1) // page_size

        return jsonify(
            {
                "success": True,
                "data": normalize_datetimes(logs),
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                },
            }
        )
    except Exception as e:
        logger.error(f"Failed to get chat logs: {str(e)}", exc_info=True)
        raise DatabaseError("获取对话日志失败")


@bp.get("/api/chat/users")
def get_chat_users():
    """获取所有用户ID列表"""
    try:
        model_id = request.args.get("model_id", type=int)

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            if model_id:
                cursor.execute(
                    """
                    SELECT DISTINCT user_id FROM chat_logs
                    WHERE user_id IS NOT NULL AND user_id != '' AND model_id = %s
                    ORDER BY user_id
                    """,
                    (model_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT DISTINCT user_id FROM chat_logs
                    WHERE user_id IS NOT NULL AND user_id != ''
                    ORDER BY user_id
                    """
                )

            users = [row["user_id"] for row in cursor.fetchall()]

        return jsonify({"success": True, "data": users})
    except Exception as e:
        logger.error(f"Failed to get users: {str(e)}", exc_info=True)
        raise DatabaseError("获取用户列表失败")


@bp.post("/api/chat/logs")
def save_chat_log():
    """保存对话记录"""
    try:
        data = request.json or {}

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO chat_logs
                (model_id, user_id, user_input, ai_response, input_blocked, output_blocked, block_reason, confidence, context_summary, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data.get("model_id"),
                    data.get("user_id"),
                    data.get("user_input"),
                    data.get("ai_response"),
                    data.get("input_blocked", False),
                    data.get("output_blocked", False),
                    data.get("block_reason"),
                    data.get("confidence"),
                    data.get("context_summary"),
                    data.get("response_time_ms"),
                ),
            )
            conn.commit()

        return jsonify({"success": True, "message": "对话记录已保存"})
    except Exception as e:
        logger.error(f"Failed to save chat log: {str(e)}", exc_info=True)
        raise DatabaseError("保存对话记录失败")
