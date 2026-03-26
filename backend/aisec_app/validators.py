"""输入验证模型"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CreateModelRequest(BaseModel):
    """创建模型请求验证"""
    name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    model_id: str = Field(..., min_length=1, max_length=100, description="模型ID")
    model_type: str = Field(default="openai", description="模型类型: openai=标准OpenAI格式, custom=自定义POST接口")
    url: str = Field(default="", max_length=500, description="API URL")
    api_key: str = Field(default="", max_length=500, description="API密钥")
    security_prompt: str = Field(default="", max_length=5000, description="安全提示词")
    custom_config: str = Field(default="", description="自定义接口配置(JSON)")

    @field_validator('name', 'model_id')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('不能为空或只包含空格')
        return v.strip()
    
    @field_validator('model_type')
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        if v not in ['openai', 'custom']:
            raise ValueError('模型类型必须是 openai 或 custom')
        return v


class UpdateModelRequest(BaseModel):
    """更新模型请求验证"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_id: Optional[str] = Field(None, min_length=1, max_length=100)
    model_type: Optional[str] = Field(None)
    url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)
    security_prompt: Optional[str] = Field(None, max_length=5000)
    custom_config: Optional[str] = Field(None)

    @field_validator('name', 'model_id')
    @classmethod
    def not_empty_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('不能为空或只包含空格')
        return v.strip() if v else v
    
    @field_validator('model_type')
    @classmethod
    def validate_model_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ['openai', 'custom']:
            raise ValueError('模型类型必须是 openai 或 custom')
        return v


class SaveKeyRequest(BaseModel):
    """保存API密钥请求验证"""
    key_name: str = Field(..., min_length=1, max_length=100, description="密钥名称")
    key_value: str = Field(..., min_length=1, max_length=1000, description="密钥值")
    description: str = Field(default="", max_length=500, description="描述")

    @field_validator('key_name', 'key_value')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('不能为空或只包含空格')
        return v.strip()


class ChatRequest(BaseModel):
    """对话请求验证"""
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")
    model_name: Optional[str] = Field(None, max_length=100, description="模型名称")
    model_id: Optional[str] = Field(None, description="模型ID（数字或 ollama:xxx / hf:xxx）")
    user_id: str = Field(default="anonymous", max_length=100, description="用户ID")
    enable_check: bool = Field(default=True, description="是否启用安全检查")
    scene: str = Field(default="general", max_length=100, description="业务场景")

    @field_validator('message')
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('消息不能为空')
        return v.strip()

    @field_validator('model_id', mode='before')
    @classmethod
    def coerce_model_id(cls, v):
        if v is None:
            return v
        return str(v)

    def model_post_init(self, __context):
        """验证至少提供model_name或model_id之一"""
        if not self.model_name and not self.model_id:
            raise ValueError('必须提供model_name或model_id之一')
