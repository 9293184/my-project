"""日志配置与请求追踪"""
import logging
import uuid
from flask import Flask, g, request
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_logging(app: Flask):
    """配置应用日志系统"""
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 为 aisec_app 设置日志级别
    app_logger = logging.getLogger('aisec_app')
    app_logger.setLevel(logging.INFO)
    
    @app.before_request
    def log_request_start():
        """请求开始时记录日志并生成request_id"""
        g.request_id = str(uuid.uuid4())[:8]
        g.request_start_time = datetime.now()
        
        logger.info(
            f"[{g.request_id}] {request.method} {request.path} "
            f"from {request.remote_addr}"
        )
    
    @app.after_request
    def log_request_end(response):
        """请求结束时记录响应时间"""
        if hasattr(g, 'request_start_time'):
            duration = (datetime.now() - g.request_start_time).total_seconds() * 1000
            logger.info(
                f"[{g.request_id}] {request.method} {request.path} "
                f"-> {response.status_code} ({duration:.2f}ms)"
            )
        return response
    
    @app.errorhandler(Exception)
    def log_unhandled_exception(e):
        """记录未捕获的异常"""
        request_id = getattr(g, 'request_id', 'unknown')
        logger.error(
            f"[{request_id}] Unhandled exception: {str(e)}",
            exc_info=True
        )
        # 不返回响应，让其他错误处理器处理
        raise
