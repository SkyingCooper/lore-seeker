

记录范围：

- Agent 模型 provider / base_url / model
- embedding / reranker provider / base_url / model
- 搜索 API provider、base_url、API key
- Tool / MCP 外部接入项
- 爬虫运行时需要你明确指定的接入项



---

## 1. 配置文件分工

### 1.1 `backend/config.toml`

用途：

- 保存非敏感运行配置
- 选择默认 provider、模型名、base_url
- 选择搜索 API provider
- 选择爬虫基础运行方式

### 1.2 `.env`

用途：

- 保存敏感信息
- 保存数据库 / Redis 连接串
- 保存模型和搜索 API 的真实密钥

### 1.3 `config/tool_mcp.yaml`

用途：

- 保存 Tool / MCP 的结构化运行配置
- 保存搜索工具 provider 映射
- 保存爬虫工具声明
- 保存 MCP server 注册信息

---

## 2. 必须你自己填写的敏感项

这些项不能靠默认值运行真实能力，必须由你自己在 `.env` 中填写。

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `.env` | `SECRET_KEY` | JWT / Session 等签名密钥 | 必须自行确认正式值 |
| `.env` | `DATABASE_URL` | PostgreSQL 连接串 | 必须由你自己维护 |
| `.env` | `REDIS_URL` | Redis 连接串 | 必须由你自己维护 |
| `.env` | `DEEPSEEK_API_KEY` | DeepSeek 聊天模型 API Key | 需要真实值 |
| `.env` | `GEMINI_API_KEY` | Gemini 聊天模型 API Key | 需要真实值 |
| `.env` | `OPENAI_API_KEY` | OpenAI 聊天模型 API Key | 需要真实值 |
| `.env` | `DASHSCOPE_API_KEY` | 阿里云 DashScope，用于 embedding / rerank | 需要真实值 |
| `.env` | `JINA_API_KEY` | Jina embedding / rerank API Key | 需要真实值 |



| `.env` | `TAVILY_API_KEY` | Tavily 搜索 API Key | 需要真实值 |
| `.env` | `SERPAPI_KEY` | SerpAPI 搜索 Key | 需要真实值 |
| `.env` | `BING_SEARCH_API_KEY` | Bing Search API Key | 需要真实值 |

| `.env` | `GITHUB_TOKEN` | GitHub Search / API Token | 需要真实值 |
| `.env` | `SERPER_API_KEY` | Serper.dev，用于 `web_search` / `academic_search.google_scholar` | 需要真实值 |
| `.env` | `BAIDU_SEARCH_API_KEY` | 百度搜索 API Key | 需要真实值 |
| `.env` | `BAIDU_SEARCH_SECRET` | 百度搜索 API Secret | 需要真实值 |
| `.env` | `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API Key | 需要真实值 |
| `.env` | `STACKEXCHANGE_API_KEY` | StackExchange / StackOverflow API Key | 需要真实值 |
| `.env` | `NEWSAPI_KEY` | NewsAPI Key | 需要真实值 |
| `.env` | `GNEWS_API_KEY` | GNews API Key | 需要真实值 |

说明：

1. 不是所有 Key 都必须同时填写。
2. 你只需要填写“当前实际启用的 provider”对应的 Key。
3. 但如果 `config/tool_mcp.yaml` 中某个 Tool 已启用，而其 provider 的 Key 为空，运行时会在调用时失败。
4. 上述这些 Key 现在已经在项目根目录的 `.env` 和 `.env.example` 中预留了配置键；你后面只需要填值，不需要自己再补字段名。

---

## 3. Agent 模型配置

这些项在 `backend/config.toml` 里已经有默认值，但是否继续使用默认值，需要你自己决定。

### 3.1 Planner Agent

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `agent.planner.provider` | Planner 使用哪个聊天模型 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `agent.planner.model` | Planner 使用的模型名 | 已有默认值，需你确认是否继续使用 |

### 3.2 Searcher Agent

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `agent.searcher.provider` | Searcher 搜索评估或小模型判断使用的 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `agent.searcher.model` | Searcher 使用的模型名 | 已有默认值，需你确认是否继续使用 |

### 3.3 Organizer Agent

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `agent.organizer.provider` | Organizer 报告整理使用的 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `agent.organizer.model` | Organizer 使用的模型名 | 已有默认值，需你确认是否继续使用 |

### 3.4 Retriever Agent

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `agent.retriever.provider` | Retriever / 问答 Agent 使用的聊天模型 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `agent.retriever.model` | Retriever / 问答 Agent 使用的模型名 | 已有默认值，需你确认是否继续使用 |

### 3.5 Memory Manager Agent

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `agent.memory_manager.provider` | 记忆管理子 Agent 在做偏好/语义/情景记忆抽取时使用的 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `agent.memory_manager.model` | 记忆管理子 Agent 使用的模型名 | 已有默认值，需你确认是否继续使用 |

### 3.6 全局默认聊天模型

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `llm.default_provider` | 未显式指定 Agent 时的默认聊天模型 provider | 已有默认值，需你确认是否继续使用 |
| `backend/config.toml` | `llm.deepseek.base_url` | DeepSeek OpenAI 兼容接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.deepseek.model` | DeepSeek 默认模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.gemini.base_url` | Gemini 接口基地址 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.gemini.model` | Gemini 默认模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.openai.base_url` | OpenAI 接口基地址 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.openai.model` | OpenAI 默认模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.dashscope.base_url` | Qwen3 OpenAI 兼容接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `llm.dashscope.model` | Qwen3 默认模型名 | 已有默认值，按需改 |

---

## 4. Embedding 与 Reranker 配置

### 4.1 Embedding

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `embedding.provider` | embedding provider 选择 | 已有默认值，需你确认 |
| `backend/config.toml` | `embedding.dashscope.model` | DashScope embedding 模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `embedding.dashscope.base_url` | DashScope embedding 接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `embedding.openai.model` | OpenAI embedding 模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `embedding.jina.model` | Jina embedding 模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `embedding.jina.base_url` | Jina embedding 接口地址 | 已有默认值，按需改 |

### 4.2 Reranker

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `reranker.provider` | rerank provider 选择 | 已有默认值，需你确认 |
| `backend/config.toml` | `reranker.dashscope.model` | DashScope rerank 模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `reranker.dashscope.base_url` | DashScope rerank 接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `reranker.jina.model` | Jina rerank 模型名 | 已有默认值，按需改 |
| `backend/config.toml` | `reranker.jina.base_url` | Jina rerank 接口地址 | 已有默认值，按需改 |

---

## 5. 搜索 API 主配置

这是旧搜索主通道配置，代码仍在使用。

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `search.api_provider` | 主搜索 API provider 选择 | 已有默认值，需你确认 |
| `backend/config.toml` | `search.tavily.base_url` | Tavily 接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `search.serpapi.base_url` | SerpAPI 接口地址 | 已有默认值，按需改 |
| `backend/config.toml` | `search.bing.base_url` | Bing Search 接口地址 | 已有默认值，按需改 |

说明：

1. `search.api_provider` 决定 `backend/services/search_service.py` 的主搜索实现。
2. Searcher 的命名搜索 Tool 又额外通过 `config/tool_mcp.yaml` 做了一层路由声明。
3. 这两套配置当前是并存的，后续如果你要再收敛，可以统一到 `config/tool_mcp.yaml`。

---

## 6. Tool / 搜索工具配置

以下配置位于 `config/tool_mcp.yaml`。

### 6.1 `web_search`

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.default_engine` | 默认网页搜索引擎 | 已有默认值，需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.google.api_key` | Google 搜索的 Serper Key，占位 `${SERPER_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.google.base_url` | Google 搜索接口地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.baidu.api_key` | 百度搜索 API Key，占位 `${BAIDU_SEARCH_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.baidu.api_secret` | 百度搜索 API Secret，占位 `${BAIDU_SEARCH_SECRET}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.baidu.base_url` | 百度搜索接口地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.bing.api_key` | Bing Search Key，占位 `${BING_SEARCH_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.bing.base_url` | Bing Search 接口地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.engines.duckduckgo.base_url` | DuckDuckGo 接口地址 | 已有默认值，按需改 |

### 6.2 `academic_search`

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.default_engine` | 默认学术搜索引擎 | 已有默认值，需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.engines.google_scholar.api_key` | Google Scholar 的 Serper Key，占位 `${SERPER_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.engines.google_scholar.base_url` | Google Scholar 接口地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.engines.semantic_scholar.api_key` | Semantic Scholar API Key，占位 `${SEMANTIC_SCHOLAR_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.engines.semantic_scholar.base_url` | Semantic Scholar 接口地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.engines.arxiv.base_url` | arXiv API 地址 | 已有默认值，按需改 |

### 6.3 `github_search`

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.search.github_search.api_key` | GitHub Token，占位 `${GITHUB_TOKEN}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.github_search.base_url` | GitHub API 地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.github_search.api_type` | GitHub 搜索接入方式 | 已有默认值，按需改 |

### 6.4 `stackoverflow_search`

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.search.stackoverflow_search.api_key` | StackExchange API Key，占位 `${STACKEXCHANGE_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.stackoverflow_search.base_url` | StackExchange API 地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.stackoverflow_search.site` | 固定搜索站点，默认 `stackoverflow` | 已有默认值，按需改 |

### 6.5 `news_search`

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.default_engine` | 默认新闻搜索引擎 | 已有默认值，需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.engines.newsapi.api_key` | NewsAPI Key，占位 `${NEWSAPI_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.engines.newsapi.base_url` | NewsAPI 地址 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.engines.gnews.api_key` | GNews Key，占位 `${GNEWS_API_KEY}` | 需要真实环境变量 |
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.engines.gnews.base_url` | GNews 地址 | 已有默认值，按需改 |

---

## 7. 爬虫与工具运行项

### 7.1 基础爬虫

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `backend/config.toml` | `crawler.enabled` | 是否启用基础爬虫能力 | 已有默认值，需你确认 |
| `backend/config.toml` | `crawler.headless` | 浏览器是否无头运行 | 已有默认值，需你确认 |
| `backend/config.toml` | `crawler.user_agent` | 基础爬虫 User-Agent | 已有默认值，按需改 |

### 7.2 Tool crawler 声明

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.crawler.http_crawler.enabled` | 是否启用静态网页爬虫 Tool | 已有默认值，需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.http_crawler.user_agent` | 静态网页爬虫 User-Agent | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.dynamic_crawler.enabled` | 是否启用动态页面爬虫 | 当前为关闭，若要启用需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.dynamic_crawler.engine` | 动态爬虫引擎类型 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.dynamic_crawler.browser` | 动态爬虫浏览器类型 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.dynamic_crawler.user_data_dir` | Playwright 用户数据目录 | 已有默认值，按需改 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.anti_ban.proxy_pool.enabled` | 是否启用代理池 | 当前为关闭，若要启用需你确认 |
| `config/tool_mcp.yaml` | `tool_mcp.crawler.anti_ban.proxy_pool.sources` | 代理池来源列表 | 当前为空，如启用必须填写 |

说明：

1. `dynamic_crawler` 虽然配置结构已存在，但默认未启用。
2. 代理池也是同样逻辑：结构已存在，但当前没有真实代理源。

---

## 8. MCP 需要你填写的项

当前 `config/tool_mcp.yaml` 里：

```yaml
tool_mcp:
  mcp:
    servers: []
```

这表示 **MCP 结构已接上，但没有任何真实 server 注册**。

如果你要启用 MCP，至少需要自己填写这些字段：

| 文件 | 参数名 | 含义 | 当前状态 |
|---|---|---|---|
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].name` | MCP server 名称 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].enabled` | 是否启用该 MCP server | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].transport` | 传输方式，例如 `stdio` / `http` | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].timeout_seconds` | MCP 超时 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].allowed_tools` | 允许暴露给 Agent 的工具名列表 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].command` | `stdio` 模式下启动命令 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].args` | `stdio` 模式下命令参数 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].endpoint` | `http` 模式下服务地址 | 当前未配置 |
| `config/tool_mcp.yaml` | `tool_mcp.mcp.servers[].env` | MCP server 所需环境变量 | 当前未配置 |

说明：

1. 你不填 `servers`，MCP 运行时就不会接任何真实外部 server。
2. 代码里已经强制 `deny_unregistered_servers: true`，所以没注册就不能调用。
3. 如果后续确定了具体 MCP server，再按统一命名补对应 `.env` 项即可，例如：

```env
MCP_GITHUB_API_KEY=
MCP_BROWSER_TOKEN=
MCP_INTERNAL_SEARCH_SECRET=
```

---

## 9. 可以保持默认，但建议你显式确认的项

这些项不是“必须现在填真实值”，但它们决定了系统最终使用哪条外部能力链路，建议你明确确认一次：

| 文件 | 参数名 | 含义 |
|---|---|---|
| `backend/config.toml` | `llm.default_provider` | 默认聊天模型 provider |
| `backend/config.toml` | `embedding.provider` | 默认 embedding provider |
| `backend/config.toml` | `reranker.provider` | 默认 reranker provider |
| `backend/config.toml` | `search.api_provider` | 主搜索 API provider |
| `config/tool_mcp.yaml` | `tool_mcp.search.web_search.default_engine` | 默认网页搜索引擎 |
| `config/tool_mcp.yaml` | `tool_mcp.search.academic_search.default_engine` | 默认学术搜索引擎 |
| `config/tool_mcp.yaml` | `tool_mcp.search.news_search.default_engine` | 默认新闻搜索引擎 |

---

## 10. 最小可运行填写清单

如果你只想先把系统跑起来，最少需要你确认或填写这些：

### 10.1 必填

- `.env`
  - `SECRET_KEY`
  - `DATABASE_URL`
  - `REDIS_URL`
  - 至少一种聊天模型 Key：
    - `DEEPSEEK_API_KEY` 或 `GEMINI_API_KEY` 或 `OPENAI_API_KEY`
  - 至少一种 embedding / rerank Key：
    - `DASHSCOPE_API_KEY` 或 `JINA_API_KEY` 或 `OPENAI_API_KEY`

### 10.2 如果要启用搜索 API

- `.env`
  - `TAVILY_API_KEY` 或 `SERPAPI_KEY` 或 `BING_SEARCH_API_KEY`
- `backend/config.toml`
  - `search.api_provider`

### 10.3 如果要启用命名搜索 Tool

- `.env`
  - `SERPER_API_KEY`
  - `GITHUB_TOKEN`
  - `STACKEXCHANGE_API_KEY`
  - `NEWSAPI_KEY`
  - `GNEWS_API_KEY`
  - `SEMANTIC_SCHOLAR_API_KEY`
- `config/tool_mcp.yaml`
  - 对应 Tool 的 `enabled`
  - 对应 Tool 的 `default_engine`

### 10.4 如果要启用动态 crawler

- `config/tool_mcp.yaml`
  - `tool_mcp.crawler.dynamic_crawler.enabled = true`
- 本机运行环境
  - 必须具备 Playwright / 浏览器运行条件

### 10.5 如果要启用 MCP

- `config/tool_mcp.yaml`
  - 填完整的 `tool_mcp.mcp.servers[]`

---

## 11. 结论

当前项目的配置状态可以概括为：

1. **结构已经补齐**：模型、搜索、Tool、crawler、MCP 都有配置入口。
2. **默认值已经补齐**：provider、base_url、model 名称大多已有默认值。
3. **真实敏感值没有替你填写**：API Key、Token、MCP server 真实接入信息仍然需要你自己填。
4. **MCP 目前只是框架接通，未注册真实 server**。
5. **项目根目录的 `.env` 与 `.env.example` 已预留当前需要的敏感配置键，填好后即可直接启动当前实现的能力。**
