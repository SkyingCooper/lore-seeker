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
| Planner | `agent-planner.md` | 任务规划和质量检查 |
| Searcher | `agent-searcher.md` | 搜索 API、爬虫、结果去重 |
| Organizer | `agent-organizer.md` | Markdown 报告、TOC、切片入库 |
| Retriever | `agent-retriever.md` | 向量召回、重排序、RAG 回答 |
| Agent 边界 | `agent-boundaries.md` | 四个 Agent 的能力、数据、职责、权限、生命周期约束 |
| Agent 护栏 | `agent-guardrails.md` | Pydantic AI hook、运行前后校验、Tool/LLM 拦截和审计 |
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

### 约束接口铁律

- Agent 之间交互必须先定义并使用 `backend/constraint/agent_contracts`。
- Tool 调用前后必须先定义并使用 `backend/constraint/tool_contracts`。
- Redis/DB 交互必须先定义并使用 `backend/constraint/storage_contracts`。
- 不允许绕过 contract 直接传自由 JSON、直接调用 Tool、直接写 Redis 或直接拼接 DB 查询。

## 5. 当前已确认待实现

1. Agent 记忆表已经建模，但 working / episodic / semantic / skill 的完整写入服务仍待实现。
2. `/api/v1/search/start` 与 `/api/v1/tasks` 的职责边界后续单独收敛。
3. Agent、Tool、Redis/DB contract 已建目录和基础 schema，运行链路自动校验待接入。

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
