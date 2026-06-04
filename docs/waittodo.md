# 问题汇总与待办

本文档记录已经确认、需要持续跟踪的问题，以及最近已完成的关键收口项。代码行为有变化时，必须同步更新本文件，避免“代码已经改了，问题清单还停留在旧状态”。

## 1. 已完成

### 1.1 记忆管理子 Agent 已独立化

- 日期：`2026-06-03`
- 状态：已完成

执行情况：

1. 新增 `backend/agents/memory_manager.py`，作为独立的 `memory_manager` Agent 入口。
2. Planner 侧现在通过标准 `agent.task` handoff contract 把任务收尾动作交给 `memory_manager`。
3. Worker 不再直接调用 `run_task_memory_manager()` 作为裸 service，而是调度 `run_memory_manager_agent()`。
4. `memory_manager` 已纳入：
   - `agent_boundaries.yaml`
   - `agent_manifest.yaml`
   - `task_schema.json`
   - `result_schema.json`
   - `guardrails.AgentName`
5. 记忆持久化、工作区归档、token 结算仍复用 `backend/services/memory_manager.py`，但该文件现在是 `memory_manager` Agent 的内部持久化服务，而不是外部直接业务入口。
6. 已补单测：
   - `tests/agents/test_memory_manager_agent.py`
   - `tests/contracts/test_contract_smoke.py` 的 handoff smoke

### 1.2 核心 Agent 已具备原生可测试入口

- 日期：`2026-06-03`
- 状态：已完成

执行情况：

1. `planner` 已拆出原生入口：
   - `run_planner_agent()`
   - `run_quality_check_agent()`
2. `organizer` 已拆出原生入口：
   - `run_organizer_agent()`
3. `searcher` 已统一为独立可测试入口：
   - `run_searcher_agent()`
4. `retriever` 已统一为独立可测试入口：
   - `run_retriever_agent()`
5. 其中 `planner / organizer / retriever.answer` 的模型调用已切换到 PydanticAI `Agent.run()`。
6. `searcher` 作为 tool-orchestrated Agent，不强制插入无意义的 LLM hop，但主链路和单测入口已统一到独立 Agent 运行函数。
7. LangGraph 现在保留为 orchestration 层，节点内部直接调用各自的原生 Agent 入口，而不再把核心逻辑散落在图节点里。
8. 已补单测：
   - `tests/agents/test_native_agents.py`

### 1.3 用户偏好管理与 token 查询接口已补齐

- 日期：`2026-06-03`
- 状态：已完成

执行情况：

1. 用户偏好接口现已覆盖：
   - `GET /api/v1/users/me/preferences`
   - `PATCH /api/v1/users/me/preferences`
   - `PUT /api/v1/users/me/preferences/{key}`
   - `DELETE /api/v1/users/me/preferences/{key}`
   - `DELETE /api/v1/users/me/preferences`
2. 用户 token 账户接口现已覆盖：
   - `GET /api/v1/users/me/token-balance`
   - `GET /api/v1/users/me/token-consumption`
3. 路由 contract 已扩展覆盖：
   - `/api/v1/knowledge/query`
   - `/api/v1/users/me/preferences`
   - `/api/v1/users/me/preferences/{key}`
   - `/api/v1/reports/{report_id}/evaluate`
4. 已补 smoke test，防止 body 字段再次漂移。

### 1.4 Tool / MCP 运行时 registry 与 gateway 已落地

- 日期：`2026-06-03`
- 状态：已完成

执行情况：

1. `backend/services/tool_adapter.py` 已补运行时能力：
   - `discover_enabled_tools()`
   - `list_registered_mcp_servers()`
   - `call_named_search_tool()`
   - `call_named_crawler_tool()`
   - `call_mcp_tool()`
   - `register_mcp_handler()`
2. Tool 运行参数继续统一读取 `config/tool_mcp.yaml`。
3. Tool contract 继续统一读取 `backend/constraint/tool_contracts/*`。
4. MCP 现在必须经过注册校验和统一 gateway，不允许未注册 server 直接调用。
5. 已补单测：
   - `tests/services/test_tool_adapter.py`

## 2. 已确认待实现

### 2.1 Searcher 高级搜索策略

- 状态：已完成
- 日期：`2026-06-04`

执行情况：

1. Searcher 已实现 `query × site` job 拆分、全局并发和每站点并发控制。
2. 站点限流、请求间隔和指数退避重试已配置化落地。
3. Redis `subtasks`、`working_log`、`results_raw` 会实时推进子任务状态。
4. 结果不足或相关性偏低时，会先触发 `web_search` 补搜。
5. 补搜后仍存在明显偏科时，会按查询语义触发策略修复：
   - 代码 / 仓库类问题优先补 `github_search`
   - 论文 / 专利类问题优先补 `academic_search`
   - 实时新闻类问题优先补 `news_search`
6. Searcher 的外部 Tool 调用成本与额度消耗会同步汇总到 `state.cost_usage` 和 `reports.cost_usage`。

### 2.2 Organizer 高级清洗与版本 diff

- 状态：已完成
- 日期：`2026-06-04`

执行情况：

1. 已新增 `backend/services/organizer_processing.py`。
2. 已实现 `readability / trafilatura / boilerpy3` 可选正文抽取与规则回退。
3. 已实现来源可信度配置化评分和 `discard_reason` 分流。
4. 已实现 `Jaccard 预筛 + SimHash/Hamming` 去重入口。
5. 已实现 `section_anchor -> section_title -> chunk_index` 的版本对齐。
6. `content_marked` 现在优先按段落级 diff，对替换段落再做行内词级 diff，避免轻微改动整段高亮。

### 2.3 Retriever 对话闭环增强

- 状态：已完成
- 日期：`2026-06-04`

执行情况：

1. 已实现低置信度问题澄清返回。
2. 已实现“不对/不是这个/重新回答”场景的重答 query 改写。
3. 已实现无命中时结合语义记忆的补救提示。
4. 首轮对话会预加载：
   - `session:{user_id}:{session_id}:context`
   - `user:{user_id}:semantic`
   - `user:{user_id}:preferences`
5. 每轮对话后会把 `user_message` 和 `agent_response` 双事件写入 Redis 会话上下文，并沉淀到 `zr_episodic_logs`。
6. 用户偏好变更后会刷新 Redis 偏好缓存；新的语义事实写入后会刷新 Redis 语义缓存。
7. 回答 prompt 现在会同时注入用户偏好、长期语义记忆和近期情景记忆。

### 2.4 Tool 成本与额度统计

- 状态：已完成
- 日期：`2026-06-03`

执行情况：

1. 新增 `backend/agents/cost_usage.py`，把外部 Tool 成本与额度消耗从 token 结构里独立出来。
2. `backend/services/tool_adapter.py` 现在会在 `tool.output.metadata.cost_usage` 中返回统一成本元数据。
3. `config/tool_mcp.yaml` 已为搜索 API 和 crawler 补默认成本/额度配置。
4. Searcher 会把每次 Tool 调用的 `cost_usage` 聚合到任务态 `state.cost_usage`。
5. `backend/services/knowledge_service.py` 会把最终聚合结果写入 `reports.cost_usage`。
6. `backend/services/memory_manager.py` 会把同阶段 `cost_usage` 写入 `token_consumption_log.metadata`，便于对账时同时查看 token 与外部调用成本。
7. 报告接口已经返回 `cost_usage`，前端可以直接展示任务外部资源消耗账本。

## 3. 更新规则

1. 新增已确认问题时，直接补到“已确认待实现”。
2. 问题完成后，从“已确认待实现”移动到“已完成”，并写明日期、代码入口和影响范围。
3. 不保留“可能”“后续考虑”“待观察”这类空泛描述，只记录已经确认的问题和明确的执行状态。

## 4. 当前结论

- 日期：`2026-06-04`
- 状态：已确认

结论说明：

1. 当前设计范围内的后端核心功能已经实现完成。
2. 这些核心功能包括：
   - 多 Agent 主链路：`planner / searcher / organizer / retriever / memory_manager`
   - PydanticAI 原生可测试入口
   - Agent / Tool / Redis / DB contract
   - 用户偏好管理 API
   - token 余额与消耗流水
   - 搜索 API / crawler / MCP 统一网关
   - Searcher 并发、限流、重试、补搜与修复性补搜
   - Organizer 正文抽取、可信度评分、去重、低质量分流、版本 diff
   - Retriever 双路检索、RRF、rerank、对话记忆闭环
   - 记忆管理子 Agent
   - `reports.token_usage` 与 `reports.cost_usage`
3. 当前剩余内容属于增强项，不属于本阶段“基础功能未实现”问题。
4. 因此，后续如再新增内容，应默认归入“增强优化”而不是“核心功能缺失”，除非设计范围再次扩大。
