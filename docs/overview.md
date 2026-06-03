# 系统架构设计

本文档负责系统主链路、模块边界和异步执行模型。具体接口、存储、Agent、前端和部署细节见对应模块文档。

## 1. 系统主链路

### 背景

Lore Seeker 面向持续研究场景。用户不是只做一次搜索，而是围绕主题创建任务，让系统自动搜索、整理、沉淀报告，并在后续问答中复用知识。

### 决策

系统采用“API 创建任务、Worker 执行 Agent、报告与知识统一入库、前端读取结果”的流水线。

### 实现要点

```text
用户创建任务
  -> FastAPI 校验用户和请求参数
  -> PostgreSQL 写入 SearchTask
  -> Celery 投递 run_search_pipeline
  -> LangGraph 执行 Planner / Searcher / Organizer / Retriever
  -> Report 写入 Markdown 报告和 TOC
  -> KnowledgeChunk 写入向量切片
  -> 前端查询任务、报告和知识问答
```

核心模块：

| 模块 | 职责 | 详细文档 |
|---|---|---|
| Frontend | 工作台、任务、报告、设置、账户入口 | `frontend.md` |
| FastAPI | 认证、权限、REST API、任务投递 | `api.md` |
| Celery Worker | 异步执行 Agent 流程 | `infra.md` |
| LangGraph Agent | 规划、搜索、整理、质量检查、问答 | `agent-*.md` |
| PostgreSQL + pgvector | 结构化数据、报告、向量切片 | `storage.md` |
| Redis | Session、Token、Celery broker/backend | `storage.md` |

### 验收标准

- HTTP 请求不直接阻塞长耗时搜索和 LLM 任务。
- 成功任务必须产生可查询的 `Report` 和 `KnowledgeChunk`。
- 前端只能通过 API 访问任务、报告和知识数据。

## 2. 模块边界

### 背景

Agent、API、存储和前端都参与任务链路。如果边界混乱，权限校验、报告写入和知识入库会分散到多个位置。

### 决策

API 层处理认证、权限和请求入口；Worker 处理长耗时任务；Service 层承接可复用业务逻辑；Agent 只负责智能流程；前端只通过 REST API 与后端交互。

### 实现要点

```text
frontend
  -> api/v1/*
    -> db/models
    -> services/*
    -> worker.tasks.run_search_pipeline
      -> agents.graph
        -> planner
        -> searcher -> services.search_service
        -> organizer
        -> quality_check
      -> services.knowledge_service
        -> reports
        -> knowledge_chunks
```

边界规则：

| 边界 | 当前规则 |
|---|---|
| 前端 / 后端 | 前端不访问数据库，不拼接内部 Redis key |
| API / Worker | API 只投递任务，不执行搜索和 LLM 主流程 |
| API / 权限 | 所有用户资源必须从 `current_user.id` 过滤 |
| Agent / HTTP | Agent 不处理 Cookie、Token 和 HTTP 异常 |
| 报告 / 知识 | 报告写入和切片入库集中在 service 层 |

### 验收标准

- 新增搜索源时，不需要改动前端页面结构。
- 新增前端页面时，不绕过后端权限校验。
- 报告写入和知识切片逻辑不散落在多个 Agent 文件。

## 3. 异步任务模型

### 背景

搜索 API、网页抓取、LLM 生成和向量入库都有明显耗时，也需要失败恢复和状态展示。

### 决策

任务先落库，再由 Celery Worker 执行。Redis 作为 Celery broker/backend，并承接任务运行过程中的短期状态。

### 实现要点

任务创建：

- `POST /api/v1/tasks` 创建结构化任务。
- `POST /api/v1/search/start` 保留快速搜索入口。
- 任务初始状态为 `pending`。

任务执行：

- `/tasks/{id}/start` 投递 `run_search_pipeline`。
- Worker 读取 `SearchTask` 和关联 `Topic`。
- Agent 执行搜索、整理和报告生成。
- 任务成功后状态变为 `completed`。
- 任务失败后状态变为 `failed`，错误写入任务上下文或日志。

状态约定：

| 状态 | 说明 |
|---|---|
| `pending` | 已创建，未执行 |
| `fetching` | 正在搜索采集 |
| `organizing` | 正在整理报告 |
| `completed` | 任务完成 |
| `failed` | 任务失败 |

### 验收标准

- 任务列表能展示状态、标题、搜索模式和频率。
- 运行中的任务不能被重复启动。
- 失败任务能通过详情页重新触发。

## 4. 跨模块数据约定

### 背景

搜索任务字段会穿过前端表单、API schema、数据库、Worker config 和 Agent state。字段不一致会直接导致任务缺参或行为偏差。

### 决策

跨模块字段采用单一命名，前端、后端、Agent 和文档保持一致。

### 实现要点

| 概念 | 字段 | 合法值 / 类型 |
|---|---|---|
| 搜索模式 | `search_mode` | `api / crawl / mixed` |
| 搜索来源 | `source_sites` | URL 或站点名数组 |
| 任务频率 | `frequency` | `once / daily / weekly / biweekly / monthly` |
| 任务标题展示 | `topic_title` | 后端任务列表返回 |
| 用户隔离 | `user_id` | 来自 `current_user.id` |

### 验收标准

- 前端提交字段与后端 Pydantic schema 一致。
- Worker 传入 Agent 的 `topic_config` 使用同名字段。
- 任务列表返回 `topic_title`，前端不依赖 `#id` 作为主要标题。

## 5. 当前状态

1. Agent 记忆表已有模型，任务收尾已通过独立 `memory_manager` 子 Agent 接入 Redis 工作区归档、显式用户偏好写入、Skill 使用反馈、高分任务 Skill 写入、LLM 隐式偏好抽取、语义记忆和情景日志写入流程。
2. `/api/v1/search/start` 与 `/api/v1/tasks` 的职责边界已确认后续单独收敛。
