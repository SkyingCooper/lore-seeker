# Lore Seeker 设计总览

本文档只保留系统级架构、模块边界和跨模块约定。具体实现细节以各模块文档为准。

## 1. 系统目标

Lore Seeker 是一个多 Agent 知识库系统。用户创建搜索任务后，系统自动完成主题规划、内容搜索、资料整理、报告生成、知识入库和后续问答。

核心链路：

```text
任务创建 -> Agent 搜索整理 -> 报告生成 -> Markdown 切片 -> 向量入库 -> 知识问答
```

## 2. 技术架构

### 后端

- Python 3.12
- FastAPI
- SQLAlchemy async
- PostgreSQL + pgvector
- Redis
- Celery
- LangGraph
- LlamaIndex
- PydanticAI

### 前端

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- Naive UI
- Pinia
- Vue Router
- Axios
- md-editor-v3
- @lucide/vue

### 基础设施

- Docker Compose
- `db`：PostgreSQL + pgvector
- `redis`：Celery、Session、Token 状态
- `backend`：FastAPI
- `worker`：Celery Agent worker
- `frontend`：Vite dev server

## 3. 模块边界

| 模块 | 文档 | 职责 |
|---|---|---|
| 系统架构 | `overview.md` | 总体目标、模块关系、主数据流 |
| API | `api.md` | 认证、接口规范、任务 API、错误码 |
| 存储 | `storage.md` | 表结构、向量库、Redis、Agent 记忆 |
| Redis 缓存 | `redis.md` | Redis key、缓存内容、TTL、过期策略 |
| 上下文管理 | `context-manager.md` | Prompt 上下文注入、裁剪、摘要、压缩、token 窗口管理 |
| Celery 调度 | `celery.md` | 异步任务、Beat 定时任务、周期任务触发 |
| Planner | `agent-planner.md` | 任务规划和质量检查 |
| Searcher | `agent-searcher.md` | 搜索 API、爬虫、结果去重 |
| Organizer | `agent-organizer.md` | Markdown 报告、TOC、切片入库 |
| Retriever | `agent-retriever.md` | 向量召回、重排序、RAG 回答 |
| Memory Manager | `agent-memory-manager.md` | 用户偏好、Skill 经验、工作日志归档和记忆淘汰 |
| Agent 边界 | `agent-boundaries.md` | 核心 Agent 与 `memory_manager` 子 Agent 的能力、数据、职责、权限、生命周期约束 |
| Agent 护栏 | `agent-guardrails.md` | Pydantic AI hook、运行前后校验、Tool/LLM 拦截和审计 |
| Tool / MCP | `tool-mcp.md` | 搜索 API、爬虫、反爬、MCP Server 和工具配置 |
| 前端 | `frontend.md` | 工作台布局、路由、状态、组件约定 |
| 配置 | `config.md` | TOML、`.env`、环境变量优先级 |
| Prompt 配置 | `prompts.md` | Markdown 提示词目录、prompt-id、加载和渲染规则 |
| 基础设施 | `infra.md` | Docker Compose 和本地验证 |
| 约束接口 | `constraints.md` | Agent、Tool、Redis、DB 交互 contract |

## 4. 全局约定

### 配置

配置优先级固定为：

```text
环境变量 > .env > backend/config.toml > 字段默认值
```

非敏感配置进入 `backend/config.toml`，secrets 进入 `.env`。

### Prompt

- LLM 提示词统一存放在 `prompts/*.md`。
- 每个可加载提示词必须使用 `prompt-id` 注释块。
- Agent 代码只通过 `backend/core/prompt_loader.py` 读取或渲染提示词。

### 搜索任务

- 混合搜索模式统一命名为 `mixed`。
- 搜索来源字段统一命名为 `source_sites`。
- 新任务管理使用 `/api/v1/tasks`。
- 旧快速搜索入口 `/api/v1/search/start` 暂时保留，职责边界后续单独调整。

### 数据隔离

- 所有用户数据必须通过 `current_user.id` 隔离。
- 知识检索必须通过 `knowledge_chunks -> reports -> search_tasks -> user_id` 过滤。
- 游客只允许只读访问，写操作必须使用 `require_member`。

### 数据库初始化

- PostgreSQL 初始化文件统一为 `backend/db/schema.sql`。

### 可配置项

- 凡是运行策略、阈值、模型名、调度频率、重试、超时、排序权重、RRF 常量、rerank 阈值等可配置内容，必须抽到配置文件。
- 不允许把可配置策略写死在 Agent、Tool 或 API 代码里。
- 当前独立配置包括 `config/context_manager.yaml`、`config/celery.yaml`、`config/retriever.yaml`、`config/source_credibility.yaml`、`config/tool_mcp.yaml`。

### 约束接口铁律

- Agent 之间交互必须先定义并使用 `backend/constraint/agent_contracts`。
- Tool 调用前后必须先定义并使用 `backend/constraint/tool_contracts`。
- Redis/DB 交互必须先定义并使用 `backend/constraint/storage_contracts`。
- 不允许绕过 contract 直接传自由 JSON、直接调用 Tool、直接写 Redis 或直接拼接 DB 查询。

## 5. 当前状态

1. Agent 记忆表已经建模；任务收尾现在通过独立 `memory_manager` 子 Agent 执行 Redis 工作区归档、显式偏好写入、Skill 使用反馈、高分任务 Skill 写入，以及 LLM 隐式偏好、语义记忆和情景日志抽取。记忆抽取失败会降级为工作日志，不阻断已完成报告。
2. Token 使用量已按任务环节写入 `reports.token_usage`；任务结束后由记忆管理子 Agent 更新 `user_token_balance` 并写入 `token_consumption_log` 扣减流水。
3. 搜索 API、crawler 和 MCP 的外部消耗已从 token 结构中拆出，统一聚合到 `reports.cost_usage`；阶段级成本也会写入 `token_consumption_log.metadata` 便于对账。
4. `planner / organizer / retriever.answer` 已切换到 PydanticAI `Agent.run()`；`searcher` 已统一为独立可测试入口，LangGraph 当前只保留 orchestration 责任。
5. Retriever 首轮问答会预加载会话上下文、语义记忆和用户偏好；每轮问答后会把用户消息与 Agent 回复双事件沉淀到 Redis 和 `zr_episodic_logs`。
6. `/api/v1/search/start` 与 `/api/v1/tasks` 的职责边界已收敛为“快速 facade + 任务主入口”的模式。
7. Agent、Tool、Redis/DB contract 已建目录和基础 schema；Agent 节点边界、Searcher Tool 调用、任务 Redis 工作区、关键 DB 写入 / 查询已接入校验。HTTP 路由级 `ContractValidationMiddleware` 已覆盖 `/api/v1/tasks`、`/api/v1/search/start`、`/api/v1/knowledge/query`、`/api/v1/users/me/preferences*`、`/api/v1/reports/{id}/evaluate` 的核心字段漂移校验。
8. Tool / MCP 运行时已具备动态发现与统一网关：`discover_enabled_tools()`、`list_registered_mcp_servers()`、`call_named_search_tool()`、`call_named_crawler_tool()`、`call_mcp_tool()` 均已落地；Searcher 还具备结果不足补搜和按问题类型修复性补搜。

## 6. 验收基线

每次跨模块修改至少执行：

```bash
python3 -m compileall -q backend
cd frontend && npm run build
```

涉及数据库、Redis 或远程连接时执行：

```bash
.venv/bin/python tests/infra/test_connections.py
```
