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
from .routes.training_data import bp as training_data_bp
from .routes.adversarial import bp as adversarial_bp
from .routes.poison_detection import bp as poison_detection_bp
from .routes.evaluation import bp as evaluation_bp
from .routes.security_policies import bp as security_policies_bp
from .routes.smart_mining import bp as smart_mining_bp
from .routes.multimodal_security import bp as multimodal_security_bp

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
    app.register_blueprint(training_data_bp)
    app.register_blueprint(adversarial_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(poison_detection_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(security_policies_bp)
    app.register_blueprint(smart_mining_bp)
    app.register_blueprint(multimodal_security_bp)

    return app
