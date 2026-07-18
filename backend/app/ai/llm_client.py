"""
LLM 统一配置
从核心配置读取参数
"""

from langchain_openai import ChatOpenAI
from app.config import settings, get_logger

logger = get_logger("LLMClient")


def get_llm(temperature: float = None, model: str = None) -> ChatOpenAI:
    """
    获取配置好的 LLM 实例

    Args:
        temperature: 温度参数，默认从配置读取
        model: 模型名称，默认从配置读取

    Returns:
        配置好的 ChatOpenAI 实例
    """
    if not settings.llm_api_key:
        raise RuntimeError("未设置 LLM API Key（请配置 LLM_API_KEY 或 DEEPSEEK_API_KEY）")

    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    model_name = model if model else settings.LLM_MODEL

    logger.debug(f"创建 LLM: model={model_name}, temp={temp}, base_url={settings.llm_base_url}")

    return ChatOpenAI(
        model=model_name,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temp,
    )