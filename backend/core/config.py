from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

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
            # agent llm
            "PLANNER_PROVIDER": d["agent"]["planner"]["provider"],
            "PLANNER_MODEL": d["agent"]["planner"]["model"],
            "SEARCHER_PROVIDER": d["agent"]["searcher"]["provider"],
            "SEARCHER_MODEL": d["agent"]["searcher"]["model"],
            "ORGANIZER_PROVIDER": d["agent"]["organizer"]["provider"],
            "ORGANIZER_MODEL": d["agent"]["organizer"]["model"],
            # llm vendors
            "DEFAULT_LLM_PROVIDER": d["llm"]["default_provider"],
            "DEEPSEEK_BASE_URL": d["llm"]["deepseek"]["base_url"],
            "DEEPSEEK_MODEL": d["llm"]["deepseek"]["model"],
            "GEMINI_BASE_URL": d["llm"]["gemini"]["base_url"],
            "GEMINI_MODEL": d["llm"]["gemini"]["model"],
            "OPENAI_BASE_URL": d["llm"]["openai"]["base_url"],
            "OPENAI_MODEL": d["llm"]["openai"]["model"],
            # embedding
            "EMBEDDING_PROVIDER": d["embedding"]["provider"],
            "DASHSCOPE_EMBEDDING_MODEL": d["embedding"]["dashscope"]["model"],
            "DASHSCOPE_EMBEDDING_BASE_URL": d["embedding"]["dashscope"]["base_url"],
            "OPENAI_EMBEDDING_MODEL": d["embedding"]["openai"]["model"],
            "JINA_EMBEDDING_MODEL": d["embedding"]["jina"]["model"],
            "JINA_EMBEDDING_BASE_URL": d["embedding"]["jina"]["base_url"],
            # reranker
            "RERANKER_PROVIDER": d["reranker"]["provider"],
            "DASHSCOPE_RERANKER_MODEL": d["reranker"]["dashscope"]["model"],
            "DASHSCOPE_RERANKER_BASE_URL": d["reranker"]["dashscope"]["base_url"],
            "JINA_RERANKER_MODEL": d["reranker"]["jina"]["model"],
            "JINA_RERANKER_BASE_URL": d["reranker"]["jina"]["base_url"],
            # search
            "SEARCH_API_PROVIDER": d["search"]["api_provider"],
            "TAVILY_BASE_URL": d["search"]["tavily"]["base_url"],
            "SERPAPI_BASE_URL": d["search"]["serpapi"]["base_url"],
            "BING_BASE_URL": d["search"]["bing"]["base_url"],
            # crawler
            "CRAWLER_ENABLED": d["crawler"]["enabled"],
            "PLAYWRIGHT_HEADLESS": d["crawler"]["headless"],
            "CRAWLER_USER_AGENT": d["crawler"]["user_agent"],
            "CRAWLER_REQUEST_DELAY_MS": d["crawler"]["request_delay_ms"],
            "CRAWLER_SITE_POLICIES": d["crawler"].get("site_policies", {}),
            # site tokens
            "GITHUB_TOKEN_ENABLED": d["site_tokens"]["github_enabled"],
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), extra="ignore")

    # ---- 从 TOML 读取（非敏感） ----
    DATABASE_URL: str = ""
    REDIS_URL: str = ""

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080
    CORS_ORIGINS: list[str] = []
    COOKIE_SECURE: bool = False

    # Agent LLM
    PLANNER_PROVIDER: Literal["deepseek", "gemini", "openai"] = "deepseek"
    PLANNER_MODEL: str = "deepseek-chat"
    SEARCHER_PROVIDER: Literal["deepseek", "gemini", "openai"] = "deepseek"
    SEARCHER_MODEL: str = "deepseek-chat"
    ORGANIZER_PROVIDER: Literal["deepseek", "gemini", "openai"] = "deepseek"
    ORGANIZER_MODEL: str = "deepseek-chat"

    # LLM vendors
    DEFAULT_LLM_PROVIDER: Literal["deepseek", "gemini", "openai"] = "deepseek"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Embedding
    EMBEDDING_PROVIDER: Literal["dashscope", "openai", "jina"] = "dashscope"
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    DASHSCOPE_EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    JINA_EMBEDDING_MODEL: str = "jina-embeddings-v3"
    JINA_EMBEDDING_BASE_URL: str = "https://api.jina.ai/v1"

    # Reranker
    RERANKER_PROVIDER: Literal["dashscope", "jina"] = "dashscope"
    DASHSCOPE_RERANKER_MODEL: str = "gte-rerank"
    DASHSCOPE_RERANKER_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    JINA_RERANKER_MODEL: str = "jina-reranker-v2-base-multilingual"
    JINA_RERANKER_BASE_URL: str = "https://api.jina.ai/v1"

    # Search API
    SEARCH_API_PROVIDER: Literal["tavily", "serpapi", "bing"] = "tavily"
    TAVILY_BASE_URL: str = "https://api.tavily.com/search"
    SERPAPI_BASE_URL: str = "https://serpapi.com/search"
    BING_BASE_URL: str = "https://api.bing.microsoft.com/v7.0/search"

    # Crawler
    CRAWLER_ENABLED: bool = True
    PLAYWRIGHT_HEADLESS: bool = True
    CRAWLER_USER_AGENT: str = "LoreSeeker/1.0"
    CRAWLER_REQUEST_DELAY_MS: int = 1000
    CRAWLER_SITE_POLICIES: dict[str, Any] = {}

    # Site tokens
    GITHUB_TOKEN_ENABLED: bool = False

    # ---- 从 .env 读取（secrets） ----
    SECRET_KEY: str = "change-me"
    DEEPSEEK_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""
    JINA_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    SERPAPI_KEY: str = ""
    BING_SEARCH_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return env_settings, dotenv_settings, TomlSource(settings_cls), init_settings


settings = Settings()
