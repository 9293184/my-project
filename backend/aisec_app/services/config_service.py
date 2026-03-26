"""配置查询服务 - 避免重复的DB查询"""
from typing import Dict, Optional, Tuple


def get_judge_config(cursor) -> Tuple[str, str, str]:
    """
    获取审查模型配置
    
    Returns:
        (judge_api_url, judge_model_name, judge_api_key)
    """
    cursor.execute(
        "SELECT config_value FROM system_config WHERE config_key = %s",
        ("judge_api_url",),
    )
    judge_url_row = cursor.fetchone()
    
    cursor.execute(
        "SELECT config_value FROM system_config WHERE config_key = %s",
        ("judge_model_name",),
    )
    judge_model_row = cursor.fetchone()
    
    cursor.execute(
        "SELECT key_value FROM api_keys WHERE key_name = %s",
        ("JUDGE_API_KEY",),
    )
    judge_key_row = cursor.fetchone()
    
    judge_api_url = judge_url_row.get("config_value") if judge_url_row else None
    judge_model_name = judge_model_row.get("config_value") if judge_model_row else None
    judge_api_key = judge_key_row.get("key_value") if judge_key_row else None
    
    return judge_api_url, judge_model_name, judge_api_key


def get_vision_config(cursor) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    获取视觉模型配置
    
    Returns:
        (vision_api_url, vision_model_name, vision_api_key)
    """
    cursor.execute(
        "SELECT config_value FROM system_config WHERE config_key = %s",
        ("vision_api_url",),
    )
    vision_url_row = cursor.fetchone()
    
    cursor.execute(
        "SELECT config_value FROM system_config WHERE config_key = %s",
        ("vision_model_name",),
    )
    vision_model_row = cursor.fetchone()
    
    cursor.execute(
        "SELECT key_value FROM api_keys WHERE key_name = %s",
        ("VISION_API_KEY",),
    )
    vision_key_row = cursor.fetchone()
    
    vision_api_url = vision_url_row.get("config_value") if vision_url_row else None
    vision_model_name = vision_model_row.get("config_value") if vision_model_row else None
    vision_api_key = vision_key_row.get("key_value") if vision_key_row else None
    
    return vision_api_url, vision_model_name, vision_api_key
