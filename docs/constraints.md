# 约束接口设计

本文档定义 Lore Seeker 的约束性接口铁律、目录结构、校验边界和落地方式。涉及 Agent 交互、Tool 交互、Redis/DB 交互时，必须先经过 `backend/constraint` 中定义的 contract，而不是直接传递自由结构或直接读写外部资源。

## 1. 项目铁律

### 背景

多 Agent 系统中，Agent 输出、Tool 输入输出、Redis 临时状态和数据库读写都会跨模块流动。如果没有统一约束，字段漂移会导致任务失败、状态不可追踪、数据越权或调试困难。

### 决策

以下规则作为本系统开发铁律：

1. Agent 之间交互必须使用 `backend/constraint/agent_contracts` 下定义的约束。
2. Agent 调用 Tool 前后必须使用 `backend/constraint/tool_contracts` 下定义的约束。
3. 与 Redis/DB 交互必须使用 `backend/constraint/storage_contracts` 下定义的 key、value、表和查询约束。
4. 新增 Agent、Tool、Redis key、DB 查询前，必须先补 contract，再写业务代码。
5. 不允许绕过 contract 直接传自由 JSON、直接调用 Tool、直接写 Redis 或直接拼接 DB 查询。
6. 任何进入 prompt 的上下文必须先经过 Context Manager，按 `context-manager.md` 的优先级、裁剪、摘要和压缩规则处理。

### 实现要点

约束目录：

```text
backend/constraint
├── agent_contracts
│   ├── schemas
│   │   ├── task_schema.json
│   │   ├── result_schema.json
│   │   └── error_schema.json
│   ├── agent_manifest.yaml
│   └── agent_boundaries.yaml
├── tool_contracts
│   ├── schemas
│   │   ├── tool_input_schema.json
│   │   └── tool_output_schema.json
│   └── tool_registry.yaml
├── storage_contracts
│   ├── redis
│   │   ├── key_patterns.yaml
│   │   └── data_schema.json
│   └── db
│       ├── table_schemas.sql
│       └── query_contracts.yaml
└── validation
    ├── validator.py
    └── middleware.py
```

统一校验入口：

- `validate_agent_task()`
- `validate_agent_result()`
- `validate_agent_error()`
- `validate_agent_operation()`
- `validate_agent_responsibility()`
- `validate_agent_data_access()`
- `validate_agent_lifecycle()`
- `validate_tool_input()`
- `validate_tool_output()`
- `validate_redis_value()`

### 验收标准

- 新 Agent handoff 不直接传裸 dict，必须符合 `agent.task`、`agent.result` 或 `agent.error`。
- 新 Tool 不直接暴露自由参数，必须注册到 `tool_registry.yaml`。
- 新 Redis key 必须出现在 `key_patterns.yaml`，value 必须有 schema。
- 新 DB 查询必须出现在 `query_contracts.yaml`，并声明用户隔离规则。

## 2. Agent 交互约束

### 背景

Planner、Searcher、Organizer、Retriever 的输入输出不同，但都需要可追踪、可校验、可扩展。

### 决策

Agent 之间只使用三类 contract：

| Contract | 文件 | 使用场景 |
|---|---|---|
| `agent.task` | `agent_contracts/schemas/task_schema.json` | 任务、计划、子任务交付 |
| `agent.result` | `agent_contracts/schemas/result_schema.json` | 搜索结果、报告结果、RAG 结果 |
| `agent.error` | `agent_contracts/schemas/error_schema.json` | 失败、重试、降级、终止 |

Agent 能接收和发出的 contract 在 `agent_manifest.yaml` 中声明。
Agent 的能力、数据、职责、权限、生命周期和审计边界在 `agent_boundaries.yaml` 中声明。
Agent 接收任务、调用 Tool、访问存储或跨职责转交前，必须先通过 `validate_agent_operation()`、`validate_agent_responsibility()`、`validate_agent_data_access()` 或 `validate_agent_lifecycle()` 做边界校验。
Agent 运行期必须通过 `backend/agents/guardrails.py` 中的 Pydantic AI 护栏 hook 执行前置/后置校验，具体说明见 `agent-guardrails.md`。

### 实现要点

`agent.task` 的核心字段：

- `schema_version`
- `contract_type`
- `task`
- `planning`
- `subtasks`
- `routing`
- `extensions`

`agent.result` 的核心字段：

- `task_id`
- `producer_agent`
- `status`
- `search`
- `organizer`
- `retriever`
- `next_action`
- `metrics`

`agent.error` 的核心字段：

- `trace`
- `error.code`
- `error.category`
- `error.retryable`
- `fallback_action`

扩展规则：

- 稳定业务字段必须写入 schema。
- 临时扩展字段只能放在 `metadata` 或 `extensions`。
- `additionalProperties` 默认关闭，避免主结构漂移。

### 验收标准

- Planner 交给 Searcher 的任务必须包含 `subtasks` 或可回退的 `search_queries`。
- Searcher 返回 Planner/Organizer 的结果必须包含标准化 `results` 和 `histories`。
- Organizer 返回 Planner 的结果必须包含 `content_md`、`toc`、质量评分上下文。
- 所有失败必须走 `agent.error`。
- Agent 调用不在 `allowed_operations` 或 `allowed_tools` 中的能力时必须拒绝并告警。
- Agent 调用 `denied_operations` 或 `denied_tools` 中的能力时必须拒绝并严重告警。
- Agent 收到不属于自身职责的任务时，必须返回 owner hint，并通过 orchestrator 转交。
- Agent 不能直接调用另一个 Agent；跨职责转交只允许通过 orchestrator。
- Agent 生命周期结束时，未完成任务必须按 `lifecycle.on_incomplete` 处理。

## 3. Tool 交互约束

### 背景

搜索 API、爬虫、embedding、reranker、LLM、Redis、Postgres 都是 Tool。Tool 如果自由暴露参数，会造成重试、超时、敏感字段和返回结构不可控。

### 决策

Tool 统一使用 input/output envelope：

| Contract | 文件 | 说明 |
|---|---|---|
| `tool.input` | `tool_contracts/schemas/tool_input_schema.json` | Agent 调用 Tool 的输入 |
| `tool.output` | `tool_contracts/schemas/tool_output_schema.json` | Tool 返回 Agent 的输出 |
| Tool 注册 | `tool_contracts/tool_registry.yaml` | Tool 所有权、调用方、超时、重试、敏感字段 |

### 实现要点

已注册 Tool：

- `search_api`
- `crawler`
- `web_search`
- `academic_search`
- `github_search`
- `stackoverflow_search`
- `news_search`
- `http_crawler`
- `dynamic_crawler`
- `anti_ban`
- `mcp_gateway`
- `embedding`
- `reranker`
- `llm`
- `redis`
- `postgres`

通用字段：

- `trace`
- `tool_name`
- `caller`
- `input.kind`
- `timeout_seconds`
- `retry`
- `metadata`

敏感字段规则：

- API key、token、cookie、password、authorization 不允许进入日志。
- Tool 输出错误时必须返回可分类错误，不允许只返回字符串异常。

### 验收标准

- Searcher 调搜索 API 和爬虫前必须构造 `tool.input`。
- Tool 结果必须返回 `tool.output`，包含 `status`、`data`、`error`、`metrics`。
- 新 Tool 必须先注册 `tool_registry.yaml`。

## 4. Storage 交互约束

### 背景

Redis 是临时状态，PostgreSQL 是长期事实来源。二者职责不同，必须通过 contract 固定 key、value、表名、查询边界和用户隔离。

### 决策

Storage contract 分为 Redis 和 DB：

| 类型 | 文件 | 说明 |
|---|---|---|
| Redis key | `storage_contracts/redis/key_patterns.yaml` | key 模式、TTL、owner |
| Redis value | `storage_contracts/redis/data_schema.json` | value JSON Schema |
| DB 表约束 | `storage_contracts/db/table_schemas.sql` | 表名、关系、向量维度、逻辑删除 |
| DB 查询约束 | `storage_contracts/db/query_contracts.yaml` | 查询场景、表、必需过滤、输出 |

### 实现要点

Redis key 约束：

- `session:{session_id}`
- `refresh_token:{user_id}`
- `bl_access:{jti}`
- `captcha:{token}`
- `task:{task_id}:context`
- `task:{task_id}:subtasks`
- `task:{task_id}:results_raw`
- `task:{task_id}:results_refined`
- `task:{task_id}:working_log`
- `session:{user_id}:{session_id}:context`
- `user:{user_id}:semantic`
- `session:{user_id}:{session_id}:retriever_worklog`
- `llm:cache:{model}:{prompt_hash}`

Redis 设计细节：

- 集中记录在 `docs/redis.md`。
- Redis key 模式和 TTL 以 `backend/constraint/storage_contracts/redis/key_patterns.yaml` 为准。
- Redis value 结构以 `backend/constraint/storage_contracts/redis/data_schema.json` 为准。

Agent 记忆表名：

- `zr_working_sessions`
- `zr_episodic_logs`
- `zr_semantic_memories`
- `zr_user_preferences`
- `zr_skill_memories`

DB 查询强规则：

- 用户数据查询必须携带 `user_id` 或通过 ownership join 证明隔离。
- 任务、报告、知识查询必须过滤 `search_tasks.deleted_at IS NULL`。
- 写操作必须由注册用户触发。
- 向量维度固定为 `1024`。
- 凡涉及向量检索的索引必须使用 HNSW。

### 验收标准

- 新 Redis key 不在 `key_patterns.yaml` 中则不能使用。
- 新 DB 查询不在 `query_contracts.yaml` 中则不能进入业务代码。
- 知识检索必须通过 `knowledge_chunks -> reports -> search_tasks -> user_id` 隔离。
- Redis 工作日志最终归档到 `zr_working_sessions`。
- prompt 上下文超限时不得绕过 Context Manager 直接调用模型。

## 5. 当前实现与扩展规则

当前实现：

- `backend/agents/contracts.py` 已把 LangGraph state 转换为 agent.task / agent.result envelope，并在 Worker、Planner、Searcher、Organizer 节点边界校验。
- `backend/services/tool_adapter.py` 已包裹 Searcher 的 `search_api` 和 `crawler` 调用，执行 tool.input / tool.output 校验和 Tool 注册表 caller 校验。
- `backend/constraint/validation/validator.py` 已提供 `validate_db_contract()`，并接入报告入库、Retriever 知识检索、记忆管理和护栏审计归档。

- `backend/core/task_redis.py` 已在 `task:{task_id}:context`、`subtasks`、`results_raw`、`results_refined`、`working_log` 写入前调用 `validate_redis_value()`。
- `task:{task_id}:working_log` 已支持 `GuardrailDecision` 摘要，普通通过记录映射为 `info`，warning / critical 由归档服务写入 `log_guardrail`。

扩展规则：

1. `ContractValidationMiddleware` 已接入 FastAPI，并覆盖 `/api/v1/tasks` 与 `/api/v1/search/start` 的请求字段漂移校验；后续新增业务路由必须同步声明路由级 contract。
2. 为更多 Tool 和 DB 查询逐步接入同一 adapter，不允许新增直连路径。

## 6. 已确认决策

1. Tool 的实际 LLM router 文件名固定为 `backend/core/llm_router.py`。
2. 站点限流策略暂时放在 `config/tool_mcp.yaml` 的 `tool_mcp.crawler.site_policies` 中，不进入数据库。
3. `search_histories` 不拆分子任务级表，通过 `parent_id` 区分整体搜索记录和子任务搜索记录。
4. `search_histories` 作为来源事实表，记录本次实际执行的 `source_sites`、`search_mode` 和原始结果。
5. `knowledge_chunks` 不重复保存来源 URL / 标题，通过 `source_search_ids` 保存原始 `search_histories.id` 集合。
