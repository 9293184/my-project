"""适配器工厂 - 根据模型类型创建对应的适配器"""
import json
import logging
from typing import Optional

from .base import ModelAdapter
from .custom_adapter import CustomAdapter
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class AdapterFactory:
    """适配器工厂类"""
    
    @staticmethod
    def create_adapter(
        model_type: str,
        api_url: str,
        api_key: str,
        model_name: str,
        custom_config: Optional[str] = None
    ) -> ModelAdapter:
        """
        根据模型类型创建对应的适配器
        
        Args:
            model_type: 模型类型 ('openai' 或 'custom')
            api_url: API 端点 URL
            api_key: API 密钥
            model_name: 模型名称/ID
            custom_config: 自定义配置（JSON 字符串）
        
        Returns:
            对应的适配器实例
        """
        # 解析自定义配置
        config = {}
        if custom_config:
            try:
                config = json.loads(custom_config)
            except json.JSONDecodeError:
                logger.warning(f"Invalid custom_config JSON: {custom_config}")
        
        # 根据类型创建适配器
        if model_type == "custom":
            logger.info(f"Creating CustomAdapter for {model_name}")
            return CustomAdapter(api_url, api_key, model_name, config)
        else:
            # 默认使用 OpenAI 适配器
            logger.info(f"Creating OpenAIAdapter for {model_name}")
            return OpenAIAdapter(api_url, api_key, model_name, config)
