# Tool 与 MCP 配置设计

## 1. 模块职责

Tool / MCP 层负责把外部能力以受约束、可配置、可审计的方式暴露给 Agent。当前重点覆盖搜索检索 API、网页爬虫、动态页面爬虫和反爬处理。

对应文件：

- `config/tool_mcp.yaml`
- `backend/constraint/tool_contracts/tool_registry.yaml`
- `backend/constraint/tool_contracts/schemas/tool_input_schema.json`
- `backend/constraint/tool_contracts/schemas/tool_output_schema.json`

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
- MCP Server 默认不注册具体服务，后续新增时必须先补配置和 contract。

### 验收标准

- 新增搜索 provider 不需要改 Agent 代码。
- 新增 MCP Server 前必须先注册配置和 contract。
- Tool/MCP 输出进入 Agent 前必须脱敏、校验和记录。

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

### 验收标准

- Searcher 根据任务类型选择搜索工具。
- API key 不进入仓库，只通过 `.env` 或部署环境变量注入。
- 每个搜索工具都有超时、限流和重试策略。

## 4. 爬虫

### 背景

网页抓取分为静态页面、动态 JS 页面和反爬处理。不同网站限流策略不同，不能全局使用同一并发和延迟。

### 决策

爬虫配置拆为 HTTP 爬虫、动态页面爬虫、反爬处理、正文解析和站点策略。

### 实现要点

| 工具 | 职责 | Owner Agent | 配置位置 |
|---|---|---|---|
| `http_crawler` | 抓取静态网页内容 | Searcher | `tool_mcp.crawler.http_crawler` |
| `dynamic_crawler` | 渲染 JS 页面 | Searcher | `tool_mcp.crawler.dynamic_crawler` |
| `anti_ban` | 代理池、指纹伪装、限流检测 | Searcher | `tool_mcp.crawler.anti_ban` |

爬虫关键配置：

- User-Agent 和 headers。
- `follow_redirects`。
- `verify_ssl`。
- Playwright / Selenium 引擎选择。
- `wait_until`。
- 代理池和请求间隔。
- 内容解析器：`readability / trafilatura / newspaper3k`。
- `site_policies`：按域名配置并发、延迟、超时、重试和退避。

### 验收标准

- 动态页面爬虫默认关闭，按任务需要启用。
- 同一站点并发和请求间隔从配置读取。
- 被限流时按 `Retry-After` 和退避策略处理。

## 5. MCP

### 背景

MCP Server 可以扩展外部工具能力，但也会放大权限和数据边界风险。MCP 不能绕过 Tool contract 直接给 Agent 传自由数据。

### 决策

MCP 作为 Tool 层的一部分管理，统一配置在 `tool_mcp.mcp`。默认允许 MCP 能力，但拒绝未注册 server。Agent 不直接调用 MCP Server，必须通过 `mcp_gateway` 统一 Tool 入口调用。

### 实现要点

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

当前 Searcher 的 `search_api` 和 `crawler` 已通过 `backend/services/tool_adapter.py` 包装，执行 tool.input / tool.output 校验和 Tool 注册表 caller 校验。新增 Tool 必须沿用该 adapter 模式。

建议后续补齐以下能力：

1. Tool 级熔断器：连续失败超过阈值后短时间停用该 provider。
2. Provider 健康检查：定时检查 API key、额度和可用性。
3. 成本统计：按 Tool/provider 记录调用次数、耗时和 token / API 成本。
4. 搜索质量反馈：把低相关 provider 降权，进入 `config/source_credibility.yaml` 或独立质量配置。
5. MCP 权限分级：只读 MCP、写入型 MCP、敏感 MCP 分级授权。
