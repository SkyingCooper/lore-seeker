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
| `config/context_manager.yaml` | 上下文窗口管理策略 | 是 |
| `config/celery.yaml` | Celery Beat、任务超时、重试、记忆淘汰策略 | 是 |
| `config/retriever.yaml` | 检索召回、RRF、rerank、embedding 维度策略 | 是 |
| `config/source_credibility.yaml` | 来源可信度、去重阈值、低质量内容标记策略 | 是 |
| `config/tool_mcp.yaml` | Tool/MCP、搜索 API、爬虫、反爬、限流策略 | 是 |
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
- 上下文窗口策略独立于模型/provider 配置，修改策略不需要改 Agent 代码。
- Celery、Retriever、Tool/MCP 等运行策略独立成配置文件，修改阈值不需要改业务代码。

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
| `[search]` | 搜索 API provider，后续逐步迁移到 `config/tool_mcp.yaml` |
| `[crawler]` | Playwright 爬虫配置，后续逐步迁移到 `config/tool_mcp.yaml` |
| `[site_tokens]` | 站点 token 开关 |

### 验收标准

- 修改 provider 和 model 不需要改业务代码。
- 非敏感默认值能被版本管理。

`[app]` 中的验证码配置：

| 字段 | 默认值 | 说明 |
|---|---:|---|
| `captcha_ttl_seconds` | `300` | 滑块验证码 Redis TTL，验证成功立即删除 |

## 4. 上下文管理配置

### 背景

上下文窗口管理是跨 Agent、Tool、Redis 和 DB 的策略配置，不属于单一后端服务配置。它需要独立维护，避免和模型 provider、数据库连接等运行配置混在一起。

### 决策

上下文窗口策略放在项目根目录 `config/context_manager.yaml`。

### 实现要点

核心配置：

- `default_max_tokens`：默认模型 token 上限。
- `trim_threshold`：触发裁剪的比例。
- `scenarios.agent_communication`：Agent 之间交互。
- `scenarios.tool_call`：Tool / MCP 调用。
- `scenarios.storage_interaction`：Redis / DB 交互。
- `summarizer`：摘要策略。
- `compressor`：极端情况下的压缩策略。

详细规则见 `context-manager.md`。

### 验收标准

- 上下文管理参数可以独立修改。
- 新增上下文场景时必须同步 `context-manager.md`。

## 5. Celery 配置

### 背景

Celery 承载后台任务、周期任务和记忆淘汰，调度频率、超时、重试和清理阈值都属于运行策略。

### 决策

Celery 调度策略统一放在 `config/celery.yaml`。

### 实现要点

核心配置：

- `beat.memory_eviction`：每天夜里 `02:00` 触发记忆淘汰。
- `beat.periodic_search_dispatcher`：重复搜索任务扫描间隔。
- `task_defaults`：全局超时、重试和 result 过期时间。
- `task_routes`：不同后台任务的队列和超时策略。
- `memory_policy`：语义记忆、情景记忆和 Skill 状态管理阈值。
- `periodic_report_version`：当前日期内报告版本 sequence 的 Redis key 策略。

详细规则见 `celery.md`。

### 验收标准

- 新增 Celery Beat 任务前必须先补 `config/celery.yaml` 和 `celery.md`。
- 定时任务参数不允许写死在 worker 代码中。

## 6. Retriever 配置

### 背景

检索 Agent 的 embedding 维度、BM25 引擎、RRF 常量和 rerank 模型都属于可调整策略。

### 决策

Retriever 策略统一放在 `config/retriever.yaml`。

### 实现要点

核心配置：

- `config/retriever.yaml` 只保存检索策略，不重复保存聊天模型 provider / model。
- Retriever 问答模型来源于 `backend/config.toml` 的 `agent.retriever.provider / model`。
- embedding / reranker provider 与模型来源于 `backend/config.toml` 的 `embedding.*` / `reranker.*`。
- embedding 维度为 `1024`。
- 关键词检索使用 PostgreSQL `tsvector`。
- 向量索引类型固定为 HNSW。
- RRF 常量 `rrf_k` 进入配置文件，默认 `60`。

详细规则见 `agent-retriever.md`。

### 验收标准

- 检索召回和 rerank 参数修改不需要改代码。
- DB 向量维度、Tool contract 和 Retriever 配置必须一致。

## 7. 来源可信度配置

### 背景

Organizer 需要按来源可信度排序、去重和标记低质量内容。这些权重会随着业务经验调整，不能写死在代码里。

### 决策

来源可信度策略统一放在 `config/source_credibility.yaml`。

### 实现要点

核心配置：

- `duplicate_similarity_threshold`：正文重复判定阈值。
- `low_quality_storage`：低质量内容保留位置，固定为 `search_histories.raw_results`。
- `base_scores`：官方文档、GitHub、StackOverflow、博客等来源基础分。
- `bonuses`：近期更新、认证作者、代码示例、多来源引用等加分规则。
- `discard_reasons`：低质量内容原因枚举。

### 验收标准

- Organizer 不硬编码来源权重。
- 低质量内容只在 `raw_results` 中标记，不额外建表。

## 8. Tool/MCP 配置

### 背景

搜索 API、爬虫、反爬策略和 MCP Server 都属于外部能力配置，不能散落在 Agent 或服务代码中。

### 决策

Tool/MCP 运行参数统一放在 `config/tool_mcp.yaml`。

### 实现要点

核心配置：

- `global`：默认超时、重试、并发和敏感字段。
- `search.web_search`：通用网页搜索。
- `search.academic_search`：论文、专利和学术资料搜索。
- `search.github_search`：GitHub 代码/仓库/Issue/讨论搜索。
- `search.stackoverflow_search`：StackOverflow 技术问答搜索。
- `search.news_search`：实时新闻搜索。
- `crawler.http_crawler`：静态网页爬虫。
- `crawler.dynamic_crawler`：动态页面爬虫。
- `crawler.anti_ban`：代理池、指纹伪装和限流检测。
- `crawler.site_policies`：按站点配置并发、延迟、超时、重试和退避。
- `mcp`：MCP Server 注册和调用规则。
- `tools_registry`：配置层工具清单。

详细规则见 `tool-mcp.md`。

### 验收标准

- 新增 Tool/MCP 前必须先补 `config/tool_mcp.yaml`、Tool contract 和 `tool-mcp.md`。
- API key 只允许使用环境变量占位符或 `.env`。
- 站点限流策略不进入数据库。

## 9. Secrets

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

## 10. 路由配置

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

## 11. 站点限流策略

### 背景

Searcher 对不同来源站点执行搜索或爬取时，需要控制并发、请求间隔、超时和重试，避免同一站点请求过快导致限流或封禁。

### 决策

站点限流策略暂时放在 `config/tool_mcp.yaml` 的 `tool_mcp.crawler.site_policies` 中，不进入数据库。

### 实现要点

配置示例见 `config/tool_mcp.yaml` 的 `tool_mcp.crawler.site_policies`。

### 验收标准

- Searcher 不从数据库读取站点限流策略。
- 未匹配具体站点时使用 `default` 策略。
- 站点策略调整只需要改配置文件，不需要迁移数据库。
