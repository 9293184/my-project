import os
import logging

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Settings
from .errors import APIError
from .logging_config import setup_logging
from .routes.attachment import bp as attachment_bp
from .routes.chat import bp as chat_bp
from .routes.chat_logs import bp as chat_logs_bp
from .routes.config import bp as config_bp
from .routes.health import bp as health_bp
from .routes.keys import bp as keys_bp
from .routes.models import bp as models_bp
from .routes.stats import bp as stats_bp
from .routes.poison_detection import bp as poison_detection_bp

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from proxy.routes import bp as proxy_bp, init_audit_engine

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    settings = Settings.from_env()
    app.config["AISEC_SETTINGS"] = settings

    # 设置日志系统
    setup_logging(app)

    # 注册错误处理器
    @app.errorhandler(APIError)
    def handle_api_error(e: APIError):
        logger.error(f"API Error: {e.message}", exc_info=True)
        return jsonify({"success": False, "error": e.message}), e.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": "服务器内部错误"}), 500

    # 注册蓝图
    app.register_blueprint(models_bp)
    app.register_blueprint(keys_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(chat_logs_bp)
    app.register_blueprint(attachment_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(poison_detection_bp)
    app.register_blueprint(proxy_bp)

    # 初始化代理审查引擎（使用数据库中的judge配置或默认Ollama）
    try:
        from .services.config_service import get_judge_config
        from .db import db_cursor
        with db_cursor(settings) as (conn, cursor):
            judge_url, judge_model, judge_key = get_judge_config(cursor)
        init_audit_engine(
            judge_url=judge_url or 'http://localhost:11434/v1',
            judge_model=judge_model or 'huihui_ai/qwen3-abliterated:8b',
            judge_key=judge_key,
        )
    except Exception as e:
        logger.warning(f'代理审查引擎初始化失败(将使用默认配置): {e}')
        init_audit_engine()

    return app
