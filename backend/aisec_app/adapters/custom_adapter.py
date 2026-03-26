"""自定义接口适配器 - 客户的 POST 接口"""
import json
import logging
from typing import Dict, List, Optional

import requests

from .base import ModelAdapter

logger = logging.getLogger(__name__)


class CustomAdapter(ModelAdapter):
    """自定义 POST 接口适配器 - 用于对接客户的非标准接口"""
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        """
        调用客户的自定义接口（纯文本）
        
        默认行为：
        - 提取最后一条用户消息作为文本
        - POST 到客户接口
        - 从响应中提取结果
        
        可通过 custom_config 自定义请求和响应格式
        """
        try:
            # 提取用户消息
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            # 构造请求数据（可通过 config 自定义）
            request_format = self.config.get("request_format", "default")
            
            if request_format == "json":
                # JSON 格式：{"text": "...", "model": "..."}
                data = {
                    self.config.get("text_field", "text"): user_message,
                    self.config.get("model_field", "model"): self.model_name,
                }
                headers = {
                    "Content-Type": "application/json",
                    **self.config.get("headers", {})
                }
                response = requests.post(
                    self.api_url,
                    json=data,
                    headers=headers,
                    timeout=kwargs.get("timeout", 60),
                )
            else:
                # 默认：form-data 格式
                data = {
                    "text": user_message,
                    "model": self.model_name,
                }
                response = requests.post(
                    self.api_url,
                    data=data,
                    timeout=kwargs.get("timeout", 60),
                )
            
            if response.status_code == 200:
                # 解析响应（可通过 config 自定义）
                response_format = self.config.get("response_format", "text")
                
                if response_format == "json":
                    # JSON 响应：{"result": "...", "status": "ok"}
                    result = response.json()
                    result_field = self.config.get("result_field", "result")
                    return result.get(result_field, "")
                else:
                    # 默认：直接返回文本
                    return response.text
            else:
                logger.error(f"Custom API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Custom adapter error: {str(e)}", exc_info=True)
            return None
    
    def chat_with_attachment(self, text: str, file_data: bytes, file_name: str, **kwargs) -> Optional[str]:
        """
        调用客户的自定义接口（带附件）
        
        使用 multipart/form-data 格式上传文件
        """
        try:
            # 构造 multipart 请求
            files = {
                self.config.get("file_field", "file"): (file_name, file_data)
            }
            data = {
                self.config.get("text_field", "text"): text,
                self.config.get("model_field", "model"): self.model_name,
            }
            
            # 添加自定义 headers
            headers = self.config.get("headers", {})
            
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=kwargs.get("timeout", 120),
            )
            
            if response.status_code == 200:
                # 解析响应
                response_format = self.config.get("response_format", "text")
                
                if response_format == "json":
                    result = response.json()
                    result_field = self.config.get("result_field", "result")
                    return result.get(result_field, "")
                else:
                    return response.text
            else:
                logger.error(f"Custom API (attachment) error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Custom adapter (attachment) error: {str(e)}", exc_info=True)
            return None
