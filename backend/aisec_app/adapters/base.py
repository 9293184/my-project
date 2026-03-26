"""模型适配器基类"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class ModelAdapter(ABC):
    """模型适配器基类"""
    
    def __init__(self, api_url: str, api_key: str, model_name: str, config: Optional[Dict] = None):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.config = config or {}
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        发送对话请求
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            **kwargs: 其他参数（temperature, max_tokens等）
        
        Returns:
            模型返回的文本内容，失败返回 None
        """
        pass
    
    @abstractmethod
    def chat_with_attachment(self, text: str, file_data: bytes, file_name: str, **kwargs) -> Optional[str]:
        """
        发送带附件的对话请求
        
        Args:
            text: 文本内容
            file_data: 文件二进制数据
            file_name: 文件名
            **kwargs: 其他参数
        
        Returns:
            模型返回的文本内容，失败返回 None
        """
        pass
