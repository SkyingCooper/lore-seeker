from langchain_openai import ChatOpenAI
from core.config import settings
from typing import Literal


LLMProvider = Literal["deepseek", "gemini", "openai"]


def get_llm(
    provider: LLMProvider | None = None,
    temperature: float = 0.3,
    streaming: bool = False,
):
    """返回对应厂商的 LangChain ChatModel 实例。"""
    p = provider or settings.DEFAULT_LLM_PROVIDER

    if p == "deepseek":
        return ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=temperature,
            streaming=streaming,
        )

    if p == "gemini":
        # Gemini 兼容 OpenAI 接口
        return ChatOpenAI(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            temperature=temperature,
            streaming=streaming,
        )

    # openai fallback
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=temperature,
        streaming=streaming,
    )
