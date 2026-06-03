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

- 状态：待实现
- 范围：
  - 搜索效果差时自动调整策略
  - 更细粒度的站点级并发执行器与实时 Redis 工作日志

- 当前进展：
  - 已补 `config/searcher.yaml`
  - 已实现查询词到命名搜索 Tool 的自动路由
  - 已实现配置化指数退避重试
  - 已实现站点策略优先裁剪入口

### 2.2 Organizer 高级清洗与版本 diff

- 状态：待实现
- 范围：
  - 更强的近似去重算法替换当前 Jaccard 近似
  - 更细粒度的 section 对 section 版本 diff

- 当前进展：
  - 已新增 `backend/services/organizer_processing.py`
  - 已实现 `readability / trafilatura / boilerpy3` 可选正文抽取与规则回退
  - 已实现来源可信度配置化评分
  - 已实现低质量内容 `discard_reason` 分流
  - 已实现去重入口
  - 已实现 `content_marked` HTML diff 入库

### 2.3 Retriever 对话闭环增强

- 状态：待实现
- 范围：
  - 会话结束后的更完整记忆沉淀

- 当前进展：
  - 已实现低置信度问题澄清返回
  - 已实现“不对/不是这个/重新回答”场景的重答 query 改写
  - 已实现无命中时结合语义记忆的补救提示

### 2.4 Token 全链路精确统计

- 状态：待实现
- 当前：`planner/searcher/organizer/retriever/context_manager/memory_manager` 已有基础统计，任务结束可落 `user_token_balance` 和按阶段拆分的 `token_consumption_log`。
- 还缺：
  - Tool 调用级 provider tokenizer 精确落账

## 3. 更新规则

1. 新增已确认问题时，直接补到“已确认待实现”。
2. 问题完成后，从“已确认待实现”移动到“已完成”，并写明日期、代码入口和影响范围。
3. 不保留“可能”“后续考虑”“待观察”这类空泛描述，只记录已经确认的问题和明确的执行状态。
