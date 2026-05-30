from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TOML_PATH = Path(__file__).parent.parent / "config.toml"
_ENV_PATH = _PROJECT_ROOT / ".env"


class TomlSource(PydanticBaseSettingsSource):
    """从 config.toml 读取配置，展平嵌套结构供 pydantic-settings 使用。"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        with open(_TOML_PATH, "rb") as f:
            self._data: dict[str, Any] = tomllib.load(f)

    def get_field_value(self, field, field_name):
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        d = self._data
        return {
            # app
            "JWT_ALGORITHM": d["app"]["jwt_algorithm"],
            "JWT_EXPIRE_MINUTES": d["app"]["jwt_expire_minutes"],
            "CORS_ORIGINS": d["app"]["cors_origins"],
            "COOKIE_SECURE": d["app"]["cookie_secure"],
            # database
            "DATABASE_URL": d["database"]["url"],
            # redis
            "REDIS_URL": d["redis"]["url"],
            # llm
            "DEFAULT_LLM_PROVIDER": d["llm"]["default_provider"],
            "DEEPSEEK_BASE_URL": d["llm"]["deepseek"]["base_url"],
            "DEEPSEEK_MODEL": d["llm"]["deepseek"]["model"],
            "GEMINI_MODEL": d["llm"]["gemini"]["model"],
            "OPENAI_BASE_URL": d["llm"]["openai"]["base_url"],
            "OPENAI_MODEL": d["llm"]["openai"]["model"],
            # embedding
            "EMBEDDING_PROVIDER": d["embedding"]["provider"],
            "DASHSCOPE_EMBEDDING_MODEL": d["embedding"]["dashscope"]["model"],
            # reranker
            "RERANKER_PROVIDER": d["reranker"]["provider"],
            "DASHSCOPE_RERANKER_MODEL": d["reranker"]["dashscope"]["model"],
            # search
            "SEARCH_API_PROVIDER": d["search"]["api_provider"],
            # crawler
            "CRAWLER_ENABLED": d["crawler"]["enabled"],
            "PLAYWRIGHT_HEADLESS": d["crawler"]["headless"],
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), extra="ignore")

    # ---- 从 TOML 读取（非敏感） ----
    DATABASE_URL: str = "postgresql+asyncpg://loreseeker:loreseeker@db:5432/loreseeker"
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    COOKIE_SECURE: bool = False

    DEFAULT_LLM_PROVIDER: Literal["deepseek", "gemini", "openai"] = "deepseek"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    EMBEDDING_PROVIDER: Literal["dashscope", "openai", "jina"] = "dashscope"
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    RERANKER_PROVIDER: Literal["dashscope", "jina"] = "dashscope"
    DASHSCOPE_RERANKER_MODEL: str = "gte-rerank"

    SEARCH_API_PROVIDER: Literal["tavily", "serpapi", "bing"] = "tavily"
    CRAWLER_ENABLED: bool = True
    PLAYWRIGHT_HEADLESS: bool = True

    # ---- 从 .env 读取（secrets） ----
    SECRET_KEY: str = "change-me"
    DEEPSEEK_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    SERPAPI_KEY: str = ""
    BING_SEARCH_API_KEY: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # 优先级：环境变量 > .env > config.toml > 字段默认值
        return env_settings, dotenv_settings, TomlSource(settings_cls), init_settings


settings = Settings()
