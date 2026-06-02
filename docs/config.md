# 配置系统设计

## 1. 模块职责

配置系统负责加载应用配置、模型路由、搜索服务、数据库、Redis 和 secrets。

对应代码：

- `backend/core/config.py`
- `backend/config.toml`
- `.env.example`

## 2. 配置分层

### 背景

模型名、URL、开关等配置需要进 git；API key、密码和私有连接串不能进 git。

### 决策

配置分三层：

| 来源 | 内容 | 是否进 git |
|---|---|---|
| `backend/config.toml` | 非敏感配置 | 是 |
| `.env` | secrets 和本地私有值 | 否 |
| 环境变量 | 部署覆盖 | 不固定 |

优先级：

```text
环境变量 > .env > backend/config.toml > 字段默认值
```

### 实现要点

- `Settings` 使用 `pydantic-settings`。
- `.env` 路径基于 `__file__` 定位到项目根目录，避免启动目录影响。
- `TomlSource` 读取 TOML 并展平成 Pydantic 字段。
- `tomllib` 使用 Python 标准库。

### 验收标准

- 从项目根目录或 `backend/` 目录启动都能读取同一份 `.env`。
- `.env.example` 不含真实密钥。
- Docker 环境变量能覆盖 TOML。

## 3. TOML 配置

### 背景

非敏感配置需要结构化，避免散落在代码里。

### 决策

`backend/config.toml` 使用分组配置。

### 实现要点

| 分组 | 职责 |
|---|---|
| `[app]` | JWT、CORS、Cookie |
| `[database]` | 数据库 URL |
| `[redis]` | Redis URL |
| `[agent.planner]` | Planner 模型 |
| `[agent.searcher]` | Searcher 模型 |
| `[agent.organizer]` | Organizer 模型 |
| `[llm]` | LLM provider 和模型 |
| `[embedding]` | embedding provider 和模型 |
| `[reranker]` | reranker provider 和模型 |
| `[search]` | 搜索 API provider |
| `[crawler]` | Playwright 爬虫配置 |
| `[crawler.site_policies]` | 站点限流策略 |
| `[site_tokens]` | 站点 token 开关 |

### 验收标准

- 修改 provider 和 model 不需要改业务代码。
- 非敏感默认值能被版本管理。

## 4. Secrets

### 背景

API key、数据库密码、Redis 密码必须避免提交到仓库。

### 决策

secrets 只进入 `.env` 或部署环境变量。

### 实现要点

`.env.example` 只保留变量名和空值模板，包括：

- `SECRET_KEY`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `REDIS_PASSWORD`
- `DEEPSEEK_API_KEY`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `DASHSCOPE_API_KEY`
- `JINA_API_KEY`
- `TAVILY_API_KEY`
- `SERPAPI_KEY`
- `BING_SEARCH_API_KEY`
- `GITHUB_TOKEN`

### 验收标准

- 测试文件不硬编码真实连接串。
- 文档和示例不出现真实 IP、密码或 token。

## 5. 路由配置

### 背景

系统需要支持多个 LLM、embedding、reranker 和搜索提供商。

### 决策

路由层通过配置选择 provider。

### 实现要点

- LLM：`deepseek / gemini / openai`
- Embedding：`dashscope / openai / jina`
- Reranker：`dashscope / jina`
- Search API：`tavily / serpapi / bing`
- Crawler：`enabled/headless/user_agent/request_delay_ms`

### 验收标准

- 默认 provider 配置完整时服务可启动。
- 切换 provider 后对应 API key 缺失会在调用时暴露明确错误。

## 6. 站点限流策略

### 背景

Searcher 对不同来源站点执行搜索或爬取时，需要控制并发、请求间隔、超时和重试，避免同一站点请求过快导致限流或封禁。

### 决策

站点限流策略暂时放在 `backend/config.toml` 的 `crawler.site_policies` 中，不进入数据库。

### 实现要点

配置示例：

```toml
[crawler.site_policies.default]
concurrency_limit = 2
request_delay_ms = 1000
timeout_seconds = 60
max_retries = 3
backoff = "exponential"

[crawler.site_policies.github]
concurrency_limit = 2
request_delay_ms = 1500
timeout_seconds = 60
max_retries = 3
backoff = "exponential"
```

后端通过 `settings.CRAWLER_SITE_POLICIES` 读取该配置。

### 验收标准

- Searcher 不从数据库读取站点限流策略。
- 未匹配具体站点时使用 `default` 策略。
- 站点策略调整只需要改配置文件，不需要迁移数据库。
