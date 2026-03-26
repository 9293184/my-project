import logging

from flask import Blueprint, current_app, jsonify, request

from ..db import db_cursor
from ..errors import DatabaseError

logger = logging.getLogger(__name__)

bp = Blueprint("config", __name__)


@bp.get("/api/config")
def get_config():
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute("SELECT config_key, config_value FROM system_config")
            rows = cursor.fetchall()
        config = {row["config_key"]: row["config_value"] for row in rows}
        return jsonify({"success": True, "data": config})
    except Exception as e:
        logger.error(f"Failed to get config: {str(e)}", exc_info=True)
        raise DatabaseError("获取系统配置失败")


@bp.post("/api/config")
def save_config():
    try:
        data = request.json or {}
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            for key, value in data.items():
                cursor.execute(
                    """
                    INSERT INTO system_config (config_key, config_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE config_value = %s
                    """,
                    (key, str(value), str(value)),
                )
            conn.commit()
        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        logger.error(f"Failed to save config: {str(e)}", exc_info=True)
        raise DatabaseError("保存系统配置失败")
