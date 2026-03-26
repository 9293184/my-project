"""统一错误处理机制"""
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API业务错误基类"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(APIError):
    """输入验证错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class NotFoundError(APIError):
    """资源不存在错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class DatabaseError(APIError):
    """数据库操作错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class ExternalAPIError(APIError):
    """外部API调用错误"""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code)
