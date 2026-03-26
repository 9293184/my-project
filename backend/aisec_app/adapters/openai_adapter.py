"""OpenAI 格式适配器 - 标准 LLM 接口"""
import logging
from typing import Dict, List, Optional

import requests

from .base import ModelAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(ModelAdapter):
    """OpenAI 兼容格式的模型适配器"""
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """调用标准 OpenAI 格式的 /chat/completions 接口"""
        try:
            response = requests.post(
                f"{self.api_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 2048),
                },
                timeout=kwargs.get("timeout", 60),
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OpenAI adapter error: {str(e)}", exc_info=True)
            return None
    
    def chat_with_attachment(self, text: str, file_data: bytes, file_name: str, **kwargs) -> Optional[str]:
        """
        OpenAI 格式不直接支持附件，需要先处理附件内容
        这里返回 None，由上层处理附件后再调用 chat()
        """
        logger.warning("OpenAI adapter does not support direct attachment upload")
        return None
