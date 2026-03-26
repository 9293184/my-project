"""统一 LLM 调用服务

支持三种模型来源：
1. API 模型（数据库配置的远程 API）
2. Ollama 本地模型（通过 OpenAI 兼容接口）
3. HuggingFace 本地模型（通过 transformers 加载）

所有调用统一走 OpenAI 兼容的 chat/completions 格式。
"""
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_API_BASE = "http://localhost:11434/v1"


def resolve_model_params(model_value: str, db_cursor=None):
    """
    根据前端传来的模型标识，解析出实际的调用参数。

    Args:
        model_value: 前端传来的值，格式为:
            - 数字 ID (如 "3") → 数据库模型
            - "ollama:<model_name>" → Ollama 本地模型
            - "hf:<repo_id>" → HuggingFace 本地模型
        db_cursor: 数据库游标（查询数据库模型时需要）

    Returns:
        dict: {
            "source": "api" | "ollama" | "hf",
            "api_url": str,
            "api_key": str | None,
            "model_name": str,
            "security_prompt": str,
            "model_id": int | None,  # 数据库 ID（仅 API 模型）
            "model_record": dict | None,  # 完整数据库记录
        }
    """
    if not model_value:
        return None

    model_value = str(model_value).strip()

    # Ollama 本地模型
    if model_value.startswith("ollama:"):
        ollama_name = model_value[7:]
        return {
            "source": "ollama",
            "api_url": OLLAMA_API_BASE,
            "api_key": None,
            "model_name": ollama_name,
            "security_prompt": "",
            "model_id": None,
            "model_record": None,
        }

    # HuggingFace 本地模型（也通过 Ollama 或本地服务调用）
    if model_value.startswith("hf:"):
        hf_name = model_value[3:]
        return {
            "source": "hf",
            "api_url": OLLAMA_API_BASE,
            "api_key": None,
            "model_name": hf_name,
            "security_prompt": "",
            "model_id": None,
            "model_record": None,
        }

    # 数据库模型（数字 ID）
    if db_cursor and model_value.isdigit():
        db_cursor.execute("SELECT * FROM models WHERE id = %s", (int(model_value),))
        model = db_cursor.fetchone()
        if model:
            return {
                "source": "api",
                "api_url": model.get("url") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": model.get("api_key"),
                "model_name": model.get("model_id"),
                "security_prompt": model.get("security_prompt", ""),
                "model_id": model.get("id"),
                "model_record": model,
            }

    # 按模型名查数据库
    if db_cursor:
        db_cursor.execute("SELECT * FROM models WHERE name = %s", (model_value,))
        model = db_cursor.fetchone()
        if model:
            return {
                "source": "api",
                "api_url": model.get("url") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": model.get("api_key"),
                "model_name": model.get("model_id"),
                "security_prompt": model.get("security_prompt", ""),
                "model_id": model.get("id"),
                "model_record": model,
            }

    return None


def call_chat(api_url: str, model_name: str, messages: list,
              api_key: str = None, temperature: float = 0.7,
              max_tokens: int = 2048, timeout: int = 60):
    """
    统一的 LLM chat/completions 调用。

    Ollama 和远程 API 都走 OpenAI 兼容接口，区别仅在于 URL 和是否需要 api_key。

    Returns:
        str: 模型回复文本，失败返回 None
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )

        if response.status_code == 200:
            return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            logger.warning(f"LLM 调用失败 [{response.status_code}]: {response.text[:200]}")
            return None
    except requests.exceptions.Timeout:
        logger.warning(f"LLM 调用超时: {api_url} / {model_name}")
        raise
    except requests.exceptions.RequestException as e:
        logger.warning(f"LLM 网络错误: {e}")
        raise
    except Exception as e:
        logger.error(f"LLM 调用异常: {e}", exc_info=True)
        return None
