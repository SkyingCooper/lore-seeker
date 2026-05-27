# 配置系统

## 设计原则

配置按敏感程度分层，职责分离：

| 文件 | 内容 | 是否进 git |
|---|---|---|
| `backend/config.toml` | 非敏感配置（模型名、URL、开关等） | 是 |
| `.env` | Secrets（API Key、数据库密码等） | 否 |
| 环境变量 | Docker 部署时覆盖任意配置 | — |

## 优先级规则

```
环境变量 > .env > config.toml > 字段默认值
```

这意味着：
- 本地开发：修改 `config.toml` 和 `.env` 即可
- Docker 部署：通过 `docker-compose.yml` 的 `environment` 或外部注入的环境变量覆盖，无需修改文件

## config.toml 结构

```toml
[app]           # JWT、CORS 等应用级配置
[database]      # 数据库连接 URL
[redis]         # Redis 连接 URL
[llm]           # LLM 路由：default_provider + 各厂商子表
[embedding]     # 向量模型：provider + 各厂商子表
[reranker]      # 重排序模型：provider + 各厂商子表
[search]        # 搜索 API：api_provider
[crawler]       # 爬虫开关和无头模式
```

## .env 结构

只保留 secrets：
```
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB  # Docker Compose 数据库初始化
SECRET_KEY                                        # JWT 签名密钥
DEEPSEEK_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY
DASHSCOPE_API_KEY
TAVILY_API_KEY / SERPAPI_KEY / BING_SEARCH_API_KEY
```

## 实现机制

`core/config.py` 中定义了 `TomlSource`，继承 `PydanticBaseSettingsSource`，在 `settings_customise_sources` 中注册为第三优先级 source。

`TomlSource.__call__()` 负责将 TOML 的嵌套结构展平为 pydantic-settings 期望的扁平字典（全大写 key）。

`tomllib` 是 Python 3.11+ 标准库，无需额外依赖。

## 相关文件

- `backend/config.toml` — 非敏感配置
- `.env.example` — secrets 模板
- `backend/core/config.py` — Settings 类 + TomlSource

---

## 2025-05-27 — 初始设计

**背景**：需要将可进 git 的配置和不可进 git 的 secrets 分离。

**决策**：使用 TOML 而非第二个 `.env` 文件，因为 TOML 支持嵌套结构，配置可读性更好，且有注释支持。

**放弃的方案**：
- 全部放 `.env`：secrets 和普通配置混在一起，`.env` 不能进 git，导致模型名等配置也无法版本管理
- 使用 `dynaconf`：引入额外依赖，pydantic-settings 自定义 source 已足够

**影响范围**：`core/config.py`、`config.toml`、`.env.example`
