import logging
from pydantic import ValidationError as PydanticValidationError

from flask import Blueprint, current_app, jsonify, request

from ..db import db_cursor
from ..errors import DatabaseError, ValidationError
from ..utils import normalize_datetimes
from ..validators import SaveKeyRequest

logger = logging.getLogger(__name__)

bp = Blueprint("keys", __name__)


@bp.get("/api/keys")
def get_keys():
    try:
        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute(
                "SELECT id, key_name, description, created_at FROM api_keys"
            )
            keys = cursor.fetchall()
        return jsonify({"success": True, "data": normalize_datetimes(keys)})
    except Exception as e:
        logger.error(f"Failed to get API keys: {str(e)}", exc_info=True)
        raise DatabaseError("获取API密钥列表失败")


@bp.post("/api/keys")
def save_key():
    try:
        data = request.json or {}
        try:
            validated = SaveKeyRequest(**data)
        except PydanticValidationError as e:
            raise ValidationError(str(e.errors()[0]['msg']))

        settings = current_app.config["AISEC_SETTINGS"]
        with db_cursor(settings) as (conn, cursor):
            cursor.execute(
                """
                REPLACE INTO api_keys (key_name, key_value, description)
                VALUES (%s, %s, %s)
                """,
                (validated.key_name, validated.key_value, validated.description),
            )
            conn.commit()

        return jsonify({"success": True, "message": "API 密钥已保存"})
    except Exception as e:
        logger.error(f"Failed to save API keys: {str(e)}", exc_info=True)
        raise DatabaseError("保存API密钥失败")
