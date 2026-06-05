"""PydanticAI 运行时辅助。

把现有的 provider 配置转换为 PydanticAI 可直接运行的模型对象，并提供统一的
token usage 提取函数，避免各 Agent 重复处理 provider/base_url/api_key。
"""

from __future__ import annotations

from typing import Literal

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel

from core.config import settings


LLMProvider = Literal["deepseek", "gemini", "openai", "qwen3", "dashscope"]
AgentModelName = Literal["planner", "searcher", "organizer", "retriever", "memory_manager"]


def build_agent_model(agent_name: AgentModelName) -> OpenAIModel:
    """按 Agent 读取配置，返回 PydanticAI OpenAI-compatible model。"""

    if agent_name == "planner":
        provider = settings.PLANNER_PROVIDER
        model_name = settings.PLANNER_MODEL
    elif agent_name == "searcher":
        provider = settings.SEARCHER_PROVIDER
        model_name = settings.SEARCHER_MODEL
    elif agent_name == "organizer":
        provider = settings.ORGANIZER_PROVIDER
        model_name = settings.ORGANIZER_MODEL
    elif agent_name == "retriever":
        provider = settings.RETRIEVER_PROVIDER
        model_name = settings.RETRIEVER_MODEL
    elif agent_name == "memory_manager":
        provider = settings.MEMORY_MANAGER_PROVIDER
        model_name = settings.MEMORY_MANAGER_MODEL
    else:
        provider = settings.DEFAULT_LLM_PROVIDER
        model_name = _default_model_for_provider(provider)

    return build_provider_model(provider, model_name)


def build_provider_model(provider: LLMProvider, model_name: str) -> OpenAIModel:
    """把 DeepSeek/Gemini/OpenAI 配置转换为 PydanticAI 模型对象。"""

    if provider == "deepseek":
        runtime_provider = OpenAIProvider(
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
        )
    elif provider == "gemini":
        runtime_provider = OpenAIProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.GEMINI_API_KEY,
        )
    elif provider in {"qwen3", "dashscope"}:
        runtime_provider = OpenAIProvider(
            base_url=settings.QWEN3_BASE_URL,
            api_key=settings.DASHSCOPE_API_KEY,
        )
    else:
        runtime_provider = OpenAIProvider(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
        )
    return OpenAIModel(model_name, provider=runtime_provider)


def usage_from_pydantic_result(result) -> dict[str, int]:
    """从 PydanticAI AgentRunResult 提取 token usage。"""

    usage = getattr(result, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total": 0}
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total": input_tokens + output_tokens,
    }


def _default_model_for_provider(provider: LLMProvider) -> str:
    if provider == "deepseek":
        return settings.DEEPSEEK_MODEL
    if provider == "gemini":
        return settings.GEMINI_MODEL
    if provider in {"qwen3", "dashscope"}:
        return settings.QWEN3_MODEL
    return settings.OPENAI_MODEL
