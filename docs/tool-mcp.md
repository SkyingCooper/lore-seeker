# Tool 与 MCP 配置设计

## 1. 模块职责

Tool / MCP 层负责把外部能力以受约束、可配置、可审计的方式暴露给 Agent。当前重点覆盖搜索检索 API、网页爬虫、动态页面爬虫和反爬处理。

对应文件：

- `config/tool_mcp.yaml`
- `backend/constraint/tool_contracts/tool_registry.yaml`
- `backend/constraint/tool_contracts/schemas/tool_input_schema.json`
- `backend/constraint/tool_contracts/schemas/tool_output_schema.json`
- `backend/services/tool_adapter.py`

## 2. 设计原则

### 背景

搜索 API、爬虫和 MCP Server 都会访问外部系统。如果配置散落在代码里，容易出现 provider 切换困难、限流失控、敏感字段进入日志、MCP 直接绕过 contract 等问题。

### 决策

所有 Tool / MCP 运行参数统一放在 `config/tool_mcp.yaml`。Agent 调用任何 Tool 或 MCP 前，必须先通过 Tool contract、Agent boundary 和 Context Manager。

### 实现要点

- Tool 注册信息声明在 `tool_registry.yaml`。
- 运行参数声明在 `config/tool_mcp.yaml`。
- API key 只允许使用环境变量占位符，例如 `${SERPER_API_KEY}`。
- Searcher 是搜索和爬虫类 Tool 的唯一 owner Agent。
- MCP Server 通过 `tool_adapter.call_mcp_tool()` 统一进入网关；未注册 server 不允许调用。
- 运行时支持 `discover_enabled_tools()` 和 `list_registered_mcp_servers()`，用于动态发现和审计。

### 验收标准

- 新增搜索 provider 不需要改 Agent 代码。
- 新增 MCP Server 前必须先注册配置和 contract。
- Tool/MCP 输出进入 Agent 前必须脱敏、校验和记录。
- 单测环境可通过 `register_mcp_handler()` 注册本地 handler，不依赖真实外部 server。

## 3. 搜索检索 API

### 背景

不同来源适合不同检索工具：通用搜索适合开放互联网，学术搜索适合论文/专利，GitHub 适合代码，StackOverflow 适合技术问答，新闻搜索适合实时信息。

### 决策

搜索检索 API 按能力拆分为五类可配置工具。

### 实现要点

| 工具 | 职责 | Owner Agent | 配置位置 |
|---|---|---|---|
| `web_search` | 搜索互联网内容 | Searcher | `tool_mcp.search.web_search` |
| `academic_search` | 搜索论文、专利和学术资料 | Searcher | `tool_mcp.search.academic_search` |
| `github_search` | 搜索代码、仓库、Issue 和讨论 | Searcher | `tool_mcp.search.github_search` |
| `stackoverflow_search` | 搜索技术问答 | Searcher | `tool_mcp.search.stackoverflow_search` |
| `news_search` | 搜索实时新闻 | Searcher | `tool_mcp.search.news_search` |

通用配置：

- `enabled`
- `default_engine`
- `engines`
- `base_url`
- `timeout_seconds`
- `max_results`
- `rate_limit`
- `backoff`
- `cost`
- `quota`

运行时入口：

- `call_search_api_tool()`：兼容历史 `search_api` 包装。
- `call_named_search_tool()`：按 `web_search / academic_search / github_search / stackoverflow_search / news_search` 名称走统一 contract。

成本与额度统计：

- 每次 Tool 调用完成后，`tool_adapter` 按配置估算一条 `cost_usage`：
  - `estimated_cost_usd = base_request_cost_usd + per_result_cost_usd * result_count`
  - crawler 额外支持 `per_page_cost_usd`
- 每次调用默认记 1 次请求；如果后续 provider 能返回更精确账单，可替换为真实值。
- 额度统一记录：
  - `quota_consumed`
  - `quota_unit`
- 这些值会进入 `tool.output.metadata.cost_usage`，再由 Searcher 聚合进 `reports.cost_usage`。

### 验收标准

- Searcher 根据任务类型选择搜索工具。
- API key 不进入仓库，只通过 `.env` 或部署环境变量注入。
- 每个搜索工具都有超时、限流和重试策略。

## 4. 爬虫

### 背景

网页抓取分为静态页面、动态 JS 页面和反爬处理。不同网站限流策略不同，不能全局使用同一并发和延迟。

### 决策

爬虫配置拆为源能力声明、HTTP 爬虫、动态页面爬虫、反爬处理、正文解析、决策规则和站点策略。

### 实现要点

| 工具 | 职责 | Owner Agent | 配置位置 |
|---|---|---|---|
| `http_crawler` | 抓取静态网页内容 | Searcher | `tool_mcp.crawler.http_crawler` |
| `dynamic_crawler` | 渲染 JS 页面 | Searcher | `tool_mcp.crawler.dynamic_crawler` |
| `anti_ban` | 代理池、指纹伪装、限流检测 | Searcher | `tool_mcp.crawler.anti_ban` |

抓取优先级：

1. 站点如果声明 `api_tool`，Searcher 直接生成 API job，不再先走 crawler。
2. 站点如果声明 `rss_url`，crawler 优先抓 RSS。
3. 都没有时先走 HTTP 静态抓取。
4. 静态结果命中规则阈值后自动降级到 Playwright。

爬虫关键配置：

- `source_capabilities`：按域名声明 `api_tool / rss_url`。
- User-Agent 和 headers。
- `follow_redirects`。
- `verify_ssl`。
- Playwright / Selenium 引擎选择。
- `wait_until`。
- 代理池和请求间隔。
- 内容解析器：默认 `trafilatura`，失败回退 `readability` 和 `BeautifulSoup`。
- `decision`：静态/动态判定的阈值、特征权重、SPA 标记、错误关键词。
- `site_policies`：按域名配置并发、延迟、超时、重试和退避。
- `cost / quota`：统一记录静态 crawler、动态 crawler 和反爬成本估算。

静态/动态判定算法：

1. 先用 HTTP 抓原始 HTML。
2. 用 `trafilatura -> readability -> BeautifulSoup` 顺序抽正文。
3. 对以下特征加权打分：
   - 正文为空
   - 正文过短
   - HTML 体积过小
   - 命中 SPA 标记
   - `noscript` / `enable javascript`
   - script-heavy shell
   - link density 过高
   - 反爬关键词
   - 历史静态失败率过高
   - 历史动态成功率过高
4. `score >= dynamic_threshold` 时自动降级到 Playwright。
5. 最终判定结果写入：
   - Redis `task:{task_id}:crawl_decisions`
   - 单条结果 `crawl_decision`
   - PostgreSQL `site_crawl_profiles`

运行时入口：

- `call_crawler_tool()`：兼容历史 crawler 包装。
- `call_named_crawler_tool()`：按 `http_crawler / dynamic_crawler / anti_ban` 名称走统一 contract。

### 验收标准

- 动态页面爬虫默认关闭，按任务需要启用。
- 同一站点并发和请求间隔从配置读取。
- 被限流时按 `Retry-After` 和退避策略处理。
- Redis miss 时先查数据库 `site_crawl_profiles`，命中后回填 Redis。

## 5. MCP

### 背景

MCP Server 可以扩展外部工具能力，但也会放大权限和数据边界风险。MCP 不能绕过 Tool contract 直接给 Agent 传自由数据。

### 决策

MCP 作为 Tool 层的一部分管理，统一配置在 `tool_mcp.mcp`。默认允许 MCP 能力，但拒绝未注册 server。Agent 不直接调用 MCP Server，必须通过 `mcp_gateway` 统一 Tool 入口调用。

### 实现要点

MCP 分两类：

1. 搜索型 MCP
   - 例如 Google Search MCP、Bing Search MCP、新闻搜索 MCP。
   - 本质仍是通用搜索能力，只是 provider 通过 MCP server 暴露。
   - 默认优先级低于本地已接入的搜索 API Tool。

2. 站点型 MCP
   - 例如 GitHub MCP、Hugging Face MCP、内部知识库 MCP。
   - 面向特定站点或特定系统，通常有更结构化的数据和更稳定的语义边界。
   - 对命中的目标站点，可以高于通用搜索 API，直接作为该站点的首选入口。

默认优先级：

1. 站点专属 API Tool 或站点型 MCP
2. 通用搜索 API Tool
3. 搜索型 MCP
4. RSS
5. `http_crawler`
6. `dynamic_crawler`

当前约束：

- MCP 已实现统一网关，但默认主链路仍以本地 API Tool / crawler 为主。
- 站点型 MCP 是否前置，必须通过域名级配置显式声明，不允许隐式覆盖默认顺序。

MCP 强规则：

- `require_tool_contract: true`
- `require_context_manager: true`
- `deny_unregistered_servers: true`
- `sanitize_outputs: true`

MCP Server 注册项后续至少包含：

- server name。
- transport。
- command 或 endpoint。
- allowed tools。
- timeout。
- sensitive fields。
- owner Agent。

当前运行时能力：

- `list_registered_mcp_servers()`：读取配置中的 server 注册信息。
- `call_mcp_tool()`：校验 caller、server、tool 和 contract 后统一调用。
- `register_mcp_handler()`：为本地测试或嵌入式 MCP 场景注册 handler。

### 验收标准

- 未注册 MCP Server 不能被调用。
- MCP 调用必须使用 `mcp_gateway` 的 `tool.input` envelope。
- MCP 输出进入 Agent 前必须脱敏和 contract 校验。
- MCP 调用摘要必须写入 `task:{task_id}:working_log`。

## 6. 工具注册表

### 背景

`tool_registry.yaml` 负责声明系统可调用的 Tool 边界，`config/tool_mcp.yaml` 负责声明运行配置。二者职责不同，不能混用。

### 决策

Tool 分两层：

1. Contract 层：`tool_registry.yaml` 声明 Tool 名称、owner、allowed_callers、input_kind、output_data_shape。
2. Config 层：`config/tool_mcp.yaml` 声明 provider、URL、限流、超时、重试、反爬和 MCP Server。

### 实现要点

已配置工具：

- `web_search`
- `academic_search`
- `github_search`
- `stackoverflow_search`
- `news_search`
- `http_crawler`
- `dynamic_crawler`
- `anti_ban`
- `mcp_gateway`

保留的基础能力：

- `embedding`
- `reranker`
- `llm`
- `redis`
- `postgres`

### 验收标准

- 新增 Tool 时必须同时更新 Tool contract、`config/tool_mcp.yaml` 和本文档。
- 工具配置变更不需要改 Agent 代码。

## 7. 建议补充

当前 Searcher 的 `search_api`、命名搜索 Tool、crawler 和 MCP gateway 都通过 `backend/services/tool_adapter.py` 包装，执行 tool.input / tool.output 校验和 Tool 注册表 caller 校验。新增 Tool 必须沿用该 adapter 模式。

建议后续补齐以下能力：

1. Tool 级熔断器：连续失败超过阈值后短时间停用该 provider。
2. Provider 健康检查：定时检查 API key、额度和可用性。
3. 成本统计：当前已按 Tool/provider 记录调用次数、耗时和估算 API/crawler 成本；后续可接真实账单回填。
4. 搜索质量反馈：把低相关 provider 降权，进入 `config/source_credibility.yaml` 或独立质量配置。
5. MCP 权限分级：只读 MCP、写入型 MCP、敏感 MCP 分级授权。
