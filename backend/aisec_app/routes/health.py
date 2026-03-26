import logging

from flask import Blueprint, current_app, jsonify

from ..db import db_conn
from ..errors import DatabaseError

logger = logging.getLogger(__name__)

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health_check():
    settings = current_app.config["AISEC_SETTINGS"]
    try:
        with db_conn(settings) as conn:
            pass
        return jsonify({"success": True, "message": "API 服务正常", "database": "已连接"})
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise DatabaseError(f"数据库连接失败: {str(e)}")
