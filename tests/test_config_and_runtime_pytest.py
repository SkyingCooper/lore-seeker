"""Pytest coverage for deterministic config and runtime wiring."""

from __future__ import annotations

import os
from unittest.mock import patch

from agents import pydantic_runtime
from core import llm_router
from core.config import Settings, TomlSource


def test_settings_load_env_overrides_and_secret_keys() -> None:
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://env-user:env-pass@localhost:5432/env_db",
            "REDIS_URL": "redis://localhost:6379/9",
            "SECRET_KEY": "env-secret",
            "DASHSCOPE_API_KEY": "dashscope-from-env",
        },
        clear=False,
    ):
        settings = Settings()

    assert settings.DATABASE_URL == "postgresql+asyncpg://env-user:env-pass@localhost:5432/env_db"
    assert settings.REDIS_URL == "redis://localhost:6379/9"
    assert settings.SECRET_KEY == "env-secret"
    assert settings.DASHSCOPE_API_KEY == "dashscope-from-env"


def test_toml_source_exposes_retriever_and_memory_manager_runtime_slots() -> None:
    values = TomlSource(Settings)()

    assert values["RETRIEVER_PROVIDER"]
    assert values["RETRIEVER_MODEL"]
    assert values["MEMORY_MANAGER_PROVIDER"]
    assert values["MEMORY_MANAGER_MODEL"]
    assert values["QWEN3_BASE_URL"].startswith("http")


def test_get_llm_uses_dashscope_runtime_when_provider_is_qwen3_alias() -> None:
    with patch.object(llm_router, "ChatOpenAI", autospec=True) as chat_model:
        llm_router.get_llm(provider="dashscope", model_name="qwen-test", temperature=0.1, streaming=True)

    _, kwargs = chat_model.call_args
    assert kwargs["model"] == "qwen-test"
    assert kwargs["api_key"] == llm_router.settings.DASHSCOPE_API_KEY
    assert kwargs["base_url"] == llm_router.settings.QWEN3_BASE_URL
    assert kwargs["temperature"] == 0.1
    assert kwargs["streaming"] is True


def test_build_agent_model_reads_retriever_specific_model_slot() -> None:
    with patch.object(pydantic_runtime, "build_provider_model", return_value="mock-model") as build_provider:
        result = pydantic_runtime.build_agent_model("retriever")

    assert result == "mock-model"
    build_provider.assert_called_once_with(
        pydantic_runtime.settings.RETRIEVER_PROVIDER,
        pydantic_runtime.settings.RETRIEVER_MODEL,
    )


def test_build_agent_model_reads_memory_manager_specific_model_slot() -> None:
    with patch.object(pydantic_runtime, "build_provider_model", return_value="memory-model") as build_provider:
        result = pydantic_runtime.build_agent_model("memory_manager")

    assert result == "memory-model"
    build_provider.assert_called_once_with(
        pydantic_runtime.settings.MEMORY_MANAGER_PROVIDER,
        pydantic_runtime.settings.MEMORY_MANAGER_MODEL,
    )
