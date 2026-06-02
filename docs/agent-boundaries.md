# Agent 边界约束

本文档说明 Planner、Searcher、Organizer、Retriever 四个 Agent 的能力边界、数据边界、职责边界、权限边界、生命周期边界和审计规则。机器可读版本统一定义在 `backend/constraint/agent_contracts/agent_boundaries.yaml`。

## 1. 边界铁律

### 背景

Agent 具备不同职责和权限。如果边界不清，系统会出现跨 Agent 直接调用、越权访问数据、绕过 Tool contract、错误写入 DB 或在生命周期结束后继续执行的问题。

### 决策

所有 Agent 必须遵守以下规则：

1. 调用不在 `allowed_operations` 或 `allowed_tools` 中的能力，必须拒绝并告警。
2. 调用在 `denied_operations` 或 `denied_tools` 中的能力，必须拒绝并严重告警。
3. 访问不在 `data_boundary` 中的数据，必须拒绝。
4. 收到不属于自身职责的任务，必须拒绝并返回“这不是我的职责，请找 X”。
5. 单一会话里跨越职责边界，必须通过 orchestrator 转交，不能直接跨 Agent 调用。
6. Agent 不能执行超过自身 `permission.level` 的操作。
7. 临时提权必须经过用户确认。
8. Agent 不能超过自身生命周期；结束时按 `on_incomplete` 处理未完成任务。
9. Agent 边界校验必须在 Agent 接收任务、调用 Tool、写 Redis/DB、转交任务前执行。

### 实现要点

边界约束文件：

```text
backend/constraint/agent_contracts/agent_boundaries.yaml
```

全局策略：

| 项 | 策略 |
|---|---|
| 未声明操作 | `deny_and_warn` |
| 明确禁止操作 | `deny_and_critical_alert` |
| 职责违规 | `reject_with_owner_hint` |
| 临时提权 | `require_user_confirmation` |
| 跨用户数据 | `deny_and_critical_alert` |
| 跨 Agent 调用 | 必须通过 `orchestrator` |
| 生命周期结束 | 执行 `lifecycle.on_incomplete` |

边界校验入口：

- `validate_agent_operation(agent_name, operation, tool_name=None, required_permission=None)`：校验能力边界和权限边界。
- `validate_agent_responsibility(agent_name, responsibility)`：校验职责边界，并在越界时返回 owner hint。
- `validate_agent_data_access(agent_name, ...)`：校验 state、Redis key、DB table、配置路径和禁止数据。
- `validate_agent_lifecycle(agent_name, idle_seconds=0, active_seconds=0)`：校验空闲时间和执行时间。

边界契约字段：

- `capabilities.allowed_operations` / `capabilities.denied_operations`
- `capabilities.allowed_tools` / `capabilities.denied_tools`
- `data_boundary.allowed_state` / `allowed_redis_keys` / `allowed_db_tables` / `denied_data`
- `responsibilities.responsible_for` / `not_responsible` / `cross_boundary_handoff`
- `permission.level` / `required_permission` / `requires_confirmation_for`
- `lifecycle.lifespan` / `max_idle_seconds` / `max_active_seconds` / `on_incomplete`
- `audit.always_log` / `warn_on` / `critical_alert_on`

### 验收标准

- 新 Agent 必须先在 `agent_boundaries.yaml` 中声明边界。
- 新 Agent 能力必须同时声明允许项和禁止项。
- 所有职责转交必须经过 orchestrator。
- 所有未声明能力必须拒绝并写入 warning 审计。
- 所有明确禁止能力、越权访问和跨用户访问必须拒绝并写入 critical 审计。

## 2. Planner 边界

### 背景

Planner 是 P&E 推理中枢，负责理解用户意图、拆解任务、推进流程、评估结果和沉淀记忆。

### 决策

Planner 可以规划和评估，但不能执行搜索、爬虫、报告生成、RAG 回答或删除数据。

### 实现要点

允许能力：

- `understand_user_intent`
- `optimize_search_queries`
- `decompose_task`
- `prioritize_subtasks`
- `select_source_sites`
- `initialize_redis_workspace`
- `evaluate_search_result`
- `evaluate_organizer_result`
- `write_user_preference`
- `write_skill_memory`
- `archive_working_session`

禁止能力：

- `execute_search_api`
- `crawl_web_page`
- `generate_final_report`
- `write_knowledge_chunks`
- `answer_user_rag_query`
- `delete_database_rows`
- `access_other_user_data`

职责不匹配时：

- 搜索执行交给 Searcher。
- 报告生成交给 Organizer。
- RAG 问答交给 Retriever。

### 验收标准

- Planner 只通过 contract 交付 Searcher 子任务。
- Planner 写入记忆表前必须满足 `write_agent_memory` 权限。
- Planner 不直接调用搜索 API 或爬虫。

## 3. Searcher 边界

### 背景

Searcher 是执行型 Agent，负责搜索、爬取、限流、重试、搜索历史和结果初评。

### 决策

Searcher 可以调用搜索 API、爬虫、LLM、Redis 和 Postgres，但不能写报告、写知识切片、写用户偏好或回答 RAG 问题。

### 实现要点

允许能力：

- `reuse_recent_search_history`
- `build_execution_queue`
- `load_site_policy_from_config`
- `execute_search_api`
- `crawl_source_sites`
- `classify_search_error`
- `retry_search_subtask`
- `standardize_search_result`
- `deduplicate_by_url`
- `write_search_history`
- `evaluate_search_relevance`
- `suggest_search_strategy_update`

禁止能力：

- `write_final_report`
- `write_knowledge_chunks`
- `write_user_preference`
- `write_skill_memory`
- `answer_user_rag_query`
- `delete_database_rows`
- `access_other_user_data`

数据边界：

- 可访问 `search_tasks`、`search_histories`。
- 可写 `task:{task_id}:subtasks`、`task:{task_id}:results_raw`、`task:{task_id}:working_log`。
- 站点限流策略只能从 `config/tool_mcp.yaml` 的 `tool_mcp.crawler.site_policies` 读取。

### 验收标准

- Searcher 全局并发不超过边界声明。
- Searcher 不从数据库读取站点限流策略。
- Searcher 写搜索历史时可用 `parent_id` 区分整体记录和子任务记录。

## 4. Organizer 边界

### 背景

Organizer 负责把搜索结果整理为 Markdown 报告，并完成 TOC、摘要、切片和知识入库。

### 决策

Organizer 可以写报告和知识切片，但不能执行搜索、爬虫、任务拆解、用户偏好写入或 RAG 回答。

### 实现要点

允许能力：

- `filter_low_quality_search_results`
- `generate_markdown_report`
- `generate_toc`
- `apply_quality_feedback`
- `chunk_markdown`
- `generate_embeddings`
- `write_report`
- `write_knowledge_chunks`
- `write_refined_results`

禁止能力：

- `decompose_task`
- `execute_search_api`
- `crawl_web_page`
- `evaluate_user_satisfaction`
- `write_user_preference`
- `write_skill_memory`
- `answer_user_rag_query`
- `delete_database_rows`

### 验收标准

- Organizer 只消费 Searcher 的标准化结果。
- Organizer 写入 `reports` 和 `knowledge_chunks` 前必须符合 storage contract。
- Organizer 不直接修改用户偏好和技能记忆。

## 5. Retriever 边界

### 背景

Retriever 负责对当前用户知识库做向量召回、重排序和基于上下文的回答。

### 决策

Retriever 只能读取当前用户的知识切片和报告上下文，并且只能访问自己的会话级 Redis key。它不能写任务、写报告、搜索、爬虫或直接写长期记忆表。

### 实现要点

允许能力：

- `embed_user_query`
- `retrieve_user_knowledge_chunks`
- `rerank_retrieved_chunks`
- `generate_context_grounded_answer`
- `return_sources`
- `load_retriever_session_context`
- `cache_retriever_session_context`
- `load_retriever_semantic_memory`
- `cache_retriever_semantic_memory`
- `append_retriever_worklog`

禁止能力：

- `decompose_task`
- `execute_search_api`
- `crawl_web_page`
- `write_report`
- `write_knowledge_chunks`
- `write_user_preference`
- `write_skill_memory`
- `delete_database_rows`
- `access_other_user_data`

强制查询路径：

```text
knowledge_chunks.report_id -> reports.id
reports.task_id -> search_tasks.id
search_tasks.user_id = current_user.id
search_tasks.deleted_at IS NULL
```

允许 Redis key：

- `session:{user_id}:{session_id}:context`
- `user:{user_id}:semantic`
- `session:{user_id}:{session_id}:retriever_worklog`

### 验收标准

- Retriever 不能检索未经过用户隔离的 `knowledge_chunks`。
- Retriever 不能直接写任何长期业务数据。
- Retriever 只能访问自身会话级 Redis key。
- Retriever 生命周期为请求级，超时后直接取消。

## 6. 权限等级

### 背景

Agent 能力需要统一权限层级，避免低权限 Agent 执行写入或敏感操作。

### 决策

权限等级定义在 `agent_boundaries.yaml` 的 `permission_levels`。

### 实现要点

| 权限 | 说明 |
|---|---|
| `read_context` | 读取当前任务上下文 |
| `read_user_knowledge` | 读取当前用户知识数据 |
| `write_task_state` | 写任务状态和中间结果 |
| `write_agent_memory` | 写 Agent 记忆 |
| `write_report` | 写报告和知识切片 |
| `admin_or_destructive` | 删除、跨用户、schema、系统命令等敏感操作 |

### 验收标准

- Agent 不得执行超过自身 `permission.level` 的操作。
- 触发 `requires_confirmation_for` 时必须先得到用户确认。

## 7. 生命周期与审计

### 背景

不同 Agent 的生命周期不同。Retriever 应是请求级，Searcher 是子任务批次级，Planner 和 Organizer 是任务级。

### 决策

生命周期由 `lifecycle` 声明，审计由 `audit.always_log` 声明。

### 实现要点

| Agent | 生命周期 | 过期处理 |
|---|---|---|
| Planner | `task_scoped` | `save_state_for_resume` |
| Searcher | `subtask_batch_scoped` | `save_state_for_resume` |
| Organizer | `task_scoped` | `save_state_for_resume` |
| Retriever | `request_scoped` | `cancel` |

审计必须记录：

- Tool 调用。
- LLM 调用。
- 文件或 DB 写入。
- 权限违规。
- 职责违规。
- 记忆写入。
- 检索来源返回。

### 验收标准

- Agent 生命周期过期后不能继续执行。
- 未完成任务必须按 `on_incomplete` 处理。
- 边界违规必须可审计。
